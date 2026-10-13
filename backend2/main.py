import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend2.ambiguity import (
    check_outcomes_diverge,
    verify_ambiguities,
)
from backend2.fixtures import get_fixture_analysis
from backend2.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    CandidateAmbiguity,
    CandidateInterpretation,
    HealthResponse,
)
from backend2.simulator import (
    UnsupportedActionError,
    UnsupportedConditionError,
    get_default_dataset,
    simulate_all_branches,
)

try:
    from ai.ai_engine import generate_interpretations as default_ai_engine
except ImportError:
    default_ai_engine = None

logger = logging.getLogger("semantic_chaos_monkey.backend2")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Semantic Chaos Monkey - Backend Sandbox & Simulator",
    description="Deterministic sandbox for executing AI-interpreted actions and verifying semantic divergence.",
    version="0.1.0",
)

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ai_engine_provider: Optional[Callable[[str, str], Dict[str, Any]]] = default_ai_engine


def set_ai_engine_provider(provider: Optional[Callable[[str, str], Dict[str, Any]]]) -> None:
    """Injects or resets the AI engine interpretation provider."""
    global _ai_engine_provider
    _ai_engine_provider = provider


def get_ai_engine_provider() -> Optional[Callable[[str, str], Dict[str, Any]]]:
    """Retrieves current AI engine provider."""
    return _ai_engine_provider


def resolve_interpretations(
    instruction: str,
    scenario: str,
) -> Dict[str, Any]:
    """
    Retrieves interpretations from the plugged-in AI engine or deterministic fixtures.
    """
    raw_payload: Optional[Dict[str, Any]] = None

    if _ai_engine_provider is not None:
        try:
            raw_payload = _ai_engine_provider(instruction, scenario)
        except Exception as exc:
            logger.warning("Plugged-in AI engine failed (%s); falling back to deterministic fixtures", exc)
            raw_payload = None

    if raw_payload is None:
        raw_payload = get_fixture_analysis(instruction, scenario)

    if raw_payload is None:
        return {
            "status": "unsupported",
            "reason": f"No valid interpretation could be derived for instruction '{instruction}'.",
            "interpretations": [],
            "candidate_ambiguities": [],
            "suggested_rewrite": "",
        }

    return raw_payload


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """Readiness probe confirming the backend service is operational."""
    return HealthResponse(
        status="ok",
        service="semantic-chaos-monkey",
        version="0.1.0",
    )


@app.post("/api/analyze", response_model=AnalysisResult, tags=["Analysis"])
def analyze_instruction(request: AnalyzeRequest) -> AnalysisResult:
    """
    Executes safe deterministic sandbox analysis of a natural language instruction:
    1. Obtains candidate interpretations from AI engine or deterministic fixtures.
    2. Strictly validates and rejects any unsupported actions or conditions.
    3. Runs each interpretation against an isolated copy of the dataset.
    4. Computes true affected record IDs independently from the model.
    5. Evaluates semantic divergence and verifies candidate ambiguities against actual outcomes.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    instruction = request.instruction.strip()
    scenario = request.scenario.strip()

    if scenario != "user_cleanup":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario '{scenario}' is not supported. Supported scenarios: ['user_cleanup'].",
        )

    ai_data = resolve_interpretations(instruction, scenario)

    if ai_data.get("status") in ("unsupported", "error"):
        return AnalysisResult(
            run_id=run_id,
            instruction=instruction,
            scenario=scenario,
            status=ai_data.get("status"),
            reason=ai_data.get("reason", "Instruction is outside the supported simulation scope."),
            outcomes_diverge=False,
            suggested_rewrite=ai_data.get("suggested_rewrite", ""),
            interpretations=[],
            ambiguities=[],
        )

    raw_interps = ai_data.get("interpretations", [])
    raw_ambiguities = ai_data.get("candidate_ambiguities", [])
    suggested_rewrite = ai_data.get("suggested_rewrite", "")

    parsed_interps: List[CandidateInterpretation] = []
    for item in raw_interps:
        if isinstance(item, CandidateInterpretation):
            parsed_interps.append(item)
        elif isinstance(item, dict):
            try:
                parsed_interps.append(CandidateInterpretation.model_validate(item))
            except ValidationError as val_err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Malformed interpretation data received: {val_err}",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid interpretation object type: {type(item)}",
            )

    if len(parsed_interps) != 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Simulation requires exactly 3 candidate interpretations ('A', 'B', 'C'), received {len(parsed_interps)}.",
        )

    parsed_ambiguities: List[CandidateAmbiguity] = []
    for item in raw_ambiguities:
        if isinstance(item, CandidateAmbiguity):
            parsed_ambiguities.append(item)
        elif isinstance(item, dict):
            try:
                parsed_ambiguities.append(CandidateAmbiguity.model_validate(item))
            except ValidationError as val_err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Malformed ambiguity data received: {val_err}",
                )

    initial_dataset = get_default_dataset()
    try:
        branch_results = simulate_all_branches(parsed_interps, dataset=initial_dataset)
    except UnsupportedActionError as act_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution rejected: {act_err}",
        )
    except UnsupportedConditionError as cond_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution rejected: {cond_err}",
        )

    outcomes_diverge = check_outcomes_diverge(branch_results)
    verified_ambiguities = verify_ambiguities(
        parsed_ambiguities,
        branch_results,
        initial_dataset,
    )

    return AnalysisResult(
        run_id=run_id,
        instruction=instruction,
        scenario=scenario,
        status="ok",
        outcomes_diverge=outcomes_diverge,
        suggested_rewrite=suggested_rewrite,
        interpretations=branch_results,
        ambiguities=verified_ambiguities,
    )
