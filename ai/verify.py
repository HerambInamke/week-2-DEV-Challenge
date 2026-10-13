"""
Rewrite Verification Loop for Semantic Chaos Monkey.
Verifies whether an operational instruction rewrite genuinely resolves or reduces
semantic divergence by executing competing interpretations in the simulator.

Never trusts the model's own claim that a rewrite is clear.
Verdicts are computed strictly from deterministic simulator outcomes.
"""

from typing import Dict, Any, Optional, Callable, List, Union
from copy import deepcopy

from ai.outcomes import SimulationOutcomes, BranchOutcome
from ai.tools.reference_simulator import run_all as ref_run_all, compare_outcomes as ref_compare_outcomes


def verify_rewrite(
    original_instruction: str,
    rewrite: str,
    before_outcomes: Optional[Any] = None,
    simulate: Optional[Callable[[Any, Any], Any]] = None,
    engine: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Executes the rewrite verification loop:
    1. Analyzes the rewritten instruction via analyze_and_branch.
    2. Runs the simulator on the rewritten instruction's world and branches.
    3. Evaluates distinct outcome sets before vs after and computes a verdict:
       - 'resolved': all branches agree (distinct_sets == 1) or no ambiguity found (branch_count == 1).
       - 'reduced': fewer distinct outcome sets than before.
       - 'not_improved': same or more distinct outcome sets than before.
       - 'unverifiable': live path unavailable, analysis failed, or unsupported.
    4. Labels the simulator used.
    """
    # 0. Simulator attribution
    if simulate is not None:
        simulator_label = getattr(simulate, "__name__", "custom_injected_simulator")
        run_sim = simulate
    else:
        simulator_label = "reference_simulator"
        run_sim = ref_run_all

    # Validate rewrite string
    if not rewrite or not rewrite.strip():
        return {
            "verdict": "unverifiable",
            "reason": "Empty rewrite string provided.",
            "original_instruction": original_instruction,
            "rewrite": rewrite,
            "before_distinct_sets": None,
            "after_distinct_sets": None,
            "simulator_used": simulator_label
        }

    # Resolve engine
    if engine is not None:
        analyze_fn = engine.analyze_and_branch
    else:
        from ai.ai_engine import analyze_and_branch as default_analyze
        analyze_fn = default_analyze

    # Baseline before_outcomes processing
    before_distinct_sets: Optional[int] = None
    if before_outcomes is not None:
        try:
            coerced_before = SimulationOutcomes.coerce(before_outcomes)
            before_distinct_sets = coerced_before.get_evidence_summary()["distinct_sets"]
        except Exception:
            before_distinct_sets = None
    elif original_instruction and original_instruction.strip():
        try:
            orig_analysis = analyze_fn(original_instruction)
            if orig_analysis.get("status") == "ok" and orig_analysis.get("world") and orig_analysis.get("branches"):
                orig_sim = run_sim(orig_analysis["world"], orig_analysis["branches"])
                coerced_orig = SimulationOutcomes.coerce(orig_sim, branches=orig_analysis["branches"])
                before_distinct_sets = coerced_orig.get_evidence_summary()["distinct_sets"]
        except Exception:
            before_distinct_sets = None

    # Step 1: Analyze rewritten instruction
    try:
        rewrite_analysis = analyze_fn(rewrite)
    except Exception as err:
        return {
            "verdict": "unverifiable",
            "reason": f"analyze_and_branch raised an error: {str(err)}",
            "original_instruction": original_instruction,
            "rewrite": rewrite,
            "before_distinct_sets": before_distinct_sets,
            "after_distinct_sets": None,
            "simulator_used": simulator_label
        }

    if rewrite_analysis.get("status") != "ok":
        reason = (
            rewrite_analysis.get("reason")
            or rewrite_analysis.get("fallback_reason")
            or "Rewritten instruction analysis returned unsupported or non-ok status."
        )
        return {
            "verdict": "unverifiable",
            "reason": reason,
            "original_instruction": original_instruction,
            "rewrite": rewrite,
            "before_distinct_sets": before_distinct_sets,
            "after_distinct_sets": None,
            "simulator_used": simulator_label,
            "rewrite_analysis": {
                "status": rewrite_analysis.get("status"),
                "source": rewrite_analysis.get("source")
            }
        }

    world = rewrite_analysis.get("world")
    branches = rewrite_analysis.get("branches", [])

    if not world or not branches:
        return {
            "verdict": "unverifiable",
            "reason": "Rewritten instruction produced empty world or branches.",
            "original_instruction": original_instruction,
            "rewrite": rewrite,
            "before_distinct_sets": before_distinct_sets,
            "after_distinct_sets": None,
            "simulator_used": simulator_label
        }

    # Step 2: Run simulator
    try:
        sim_results = run_sim(world, branches)
        after_outcomes = SimulationOutcomes.coerce(sim_results, branches=branches)
    except Exception as sim_err:
        return {
            "verdict": "unverifiable",
            "reason": f"Simulation of rewrite branches failed: {str(sim_err)}",
            "original_instruction": original_instruction,
            "rewrite": rewrite,
            "before_distinct_sets": before_distinct_sets,
            "after_distinct_sets": None,
            "simulator_used": simulator_label
        }

    evidence = after_outcomes.get_evidence_summary()
    after_distinct_sets = evidence["distinct_sets"]
    after_branch_count = evidence["total_branches"]

    # Step 3: Compute verdict ONLY from simulator outcomes (Never trust the model's claim)
    if after_distinct_sets == 1 or after_branch_count == 1:
        verdict = "resolved"
    elif before_distinct_sets is not None:
        if after_distinct_sets < before_distinct_sets:
            verdict = "reduced"
        else:
            verdict = "not_improved"
    else:
        # Diverges with multiple distinct sets and no prior baseline to demonstrate reduction
        verdict = "not_improved"

    return {
        "verdict": verdict,
        "original_instruction": original_instruction,
        "rewrite": rewrite,
        "before_distinct_sets": before_distinct_sets,
        "after_distinct_sets": after_distinct_sets,
        "after_branch_count": after_branch_count,
        "simulator_used": simulator_label,
        "evidence_summary": evidence,
        "rewrite_analysis": {
            "status": rewrite_analysis.get("status"),
            "source": rewrite_analysis.get("source"),
            "branches_count": len(branches),
            "warnings": rewrite_analysis.get("warnings", [])
        }
    }
