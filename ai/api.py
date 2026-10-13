"""Local HTTP API for the Semantic Chaos Monkey analysis and simulator."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai.ai_engine import analyze_and_branch
from ai.outcomes import SimulationOutcomes
from ai.tools.reference_simulator import compare_outcomes, run_all

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Semantic Chaos Monkey API",
    description="Analyze ambiguous instructions and simulate their interpretations on synthetic data.",
    version="0.1.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "SCM_CORS_ORIGINS",
        "http://localhost:8443,http://127.0.0.1:8443",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    instruction: str = Field(min_length=10, max_length=12_000)
    scenario: str = Field(default="auto", max_length=80)


def _analyze_and_simulate(instruction: str, scenario: str) -> dict[str, Any]:
    analysis = analyze_and_branch(instruction, scenario=scenario)
    status = analysis.get("status", "incomplete")

    if status != "ok":
        return {
            "status": status,
            "reason": analysis.get("reason") or analysis.get("fallback_reason") or "The instruction could not be analyzed.",
            "source": analysis.get("source"),
            "fallback_reason": analysis.get("fallback_reason"),
            "model_info": analysis.get("model_info"),
            "warnings": analysis.get("warnings", []),
        }

    world = analysis.get("world")
    branches = analysis.get("branches") or []
    if not isinstance(world, dict) or not world.get("records") or not branches:
        return {
            "status": "incomplete",
            "reason": "The analyzer returned no synthetic world or no validated interpretation plans.",
            "source": analysis.get("source"),
            "model_info": analysis.get("model_info"),
        }

    try:
        raw_outcomes = run_all(world, branches)
        validated = SimulationOutcomes.coerce(raw_outcomes, branches=branches)
        evidence = validated.get_evidence_summary()
        comparison = compare_outcomes(raw_outcomes)
        plans_by_id = {plan["id"]: plan for plan in branches}
        outcome_patterns = {
            json.dumps(
                {
                    "operation": plans_by_id[outcome["branch_id"]].get(
                        "operation", "unknown"
                    ),
                    "records_after": outcome["records_after"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for outcome in raw_outcomes
        }
        comparison["diverges"] = len(outcome_patterns) > 1
        comparison["distinct_sets"] = len(outcome_patterns)
    except Exception as exc:
        logger.error("Synthetic simulation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=422,
            detail="The generated interpretation plans could not be simulated safely.",
        ) from exc

    outcomes_by_id = {item["branch_id"]: item for item in raw_outcomes}
    response_branches = []
    for plan in branches:
        outcome = outcomes_by_id[plan["id"]]
        response_branches.append(
            {
                "id": plan["id"],
                "title": plan.get("title") or plan["id"],
                "assumption": plan.get("assumption", ""),
                "explanation": plan.get("explanation", ""),
                "operation": plan.get("operation", "unknown"),
                "where": plan.get("where", {}),
                "update_set": plan.get("update_set"),
                "chosen_meanings": plan.get("chosen_meanings", {}),
                "affected_ids": outcome["affected_ids"],
                "affected_count": outcome["affected_count"],
            }
        )

    return {
        "status": "ok",
        "instruction": instruction,
        "source": analysis.get("source"),
        "fallback_reason": analysis.get("fallback_reason"),
        "model_info": analysis.get("model_info"),
        "timings_ms": analysis.get("timings_ms", {}),
        "domain": analysis.get("domain"),
        "world": {
            "entity": world.get("entity", analysis.get("entity_schema", {}).get("name", "record")),
            "today": world.get("today"),
            "record_count": len(world["records"]),
        },
        "branches": response_branches,
        "comparison": {
            **comparison,
            "evidence": evidence,
        },
        "ambiguous_terms": analysis.get("ambiguous_terms", []),
        "suggested_rewrite": analysis.get("suggested_rewrite", ""),
        "warnings": analysis.get("warnings", []),
    }


@app.get("/api/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "semantic-chaos-monkey"}


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    instruction = request.instruction.strip()
    if len(instruction) < 10:
        raise HTTPException(status_code=422, detail="Enter at least 10 non-whitespace characters.")
    return await run_in_threadpool(_analyze_and_simulate, instruction, request.scenario)
