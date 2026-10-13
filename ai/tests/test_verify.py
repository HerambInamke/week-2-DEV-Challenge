"""
Tests for the Rewrite Verification Loop (Part 6).
Verifies:
1. Verdict 'resolved': all branches produce identical affected sets (distinct_sets == 1) or single branch.
2. Verdict 'reduced': fewer distinct outcome sets than before.
3. Verdict 'not_improved': same or more distinct outcome sets than before.
4. Verdict 'unverifiable': live path unavailable or unsupported.
5. Injected custom simulator attribution.
6. Model claim ignored (never trusting model prose over simulator outcomes).
"""

from unittest.mock import MagicMock
import pytest

from ai.verify import verify_rewrite
from ai.outcomes import BranchOutcome, SimulationOutcomes


# ---------------------------------------------------------------------------
# Helpers for Mocking analyze_and_branch outputs
# ---------------------------------------------------------------------------

def make_analysis_result(status="ok", branches=None, records=None, warnings=None):
    if branches is None:
        branches = [
            {
                "id": "A",
                "title": "Branch A",
                "operation": "delete",
                "update_set": None,
                "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}
            }
        ]
    if records is None:
        records = [
            {"id": "U1", "status": "active"},
            {"id": "U2", "status": "dormant"}
        ]
    return {
        "status": status,
        "source": "live_generic",
        "domain": "user_management",
        "world": {
            "entity": "user",
            "today": "2026-01-01",
            "records": records
        },
        "branches": branches,
        "warnings": warnings or [],
        "reason": "Test reason" if status != "ok" else None
    }


# ---------------------------------------------------------------------------
# Test Verdict 1: 'resolved'
# ---------------------------------------------------------------------------

def test_verdict_resolved_when_all_branches_agree():
    """
    Even if multiple branches were generated, if they all produce identical affected sets
    (after_distinct_sets == 1), verdict is 'resolved'.
    """
    engine = MagicMock()
    # 2 branches that both match U2
    branches = [
        {"id": "A", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}},
        {"id": "B", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}}
    ]
    engine.analyze_and_branch.return_value = make_analysis_result(branches=branches)

    before_outcomes = [
        {"branch_id": "A", "affected_ids": ["U1"], "affected_count": 1},
        {"branch_id": "B", "affected_ids": ["U2"], "affected_count": 1}
    ]

    res = verify_rewrite(
        original_instruction="Delete old users",
        rewrite="Delete accounts strictly with status dormant",
        before_outcomes=before_outcomes,
        engine=engine
    )

    assert res["verdict"] == "resolved"
    assert res["after_distinct_sets"] == 1
    assert res["before_distinct_sets"] == 2
    assert res["simulator_used"] == "reference_simulator"


def test_verdict_resolved_when_single_branch_generated():
    """
    When no remaining ambiguity is found and a single baseline branch is generated (after_branch_count == 1),
    verdict is 'resolved'.
    """
    engine = MagicMock()
    branches = [
        {"id": "A", "operation": "delete", "where": {"op": "compare", "field": "id", "cmp": "eq", "value": "U1"}}
    ]
    engine.analyze_and_branch.return_value = make_analysis_result(
        branches=branches,
        warnings=["no ambiguity found; single baseline branch generated"]
    )

    res = verify_rewrite(
        original_instruction="Delete users",
        rewrite="Delete user U1",
        before_outcomes=[
            {"branch_id": "A", "affected_ids": ["U1", "U2"], "affected_count": 2},
            {"branch_id": "B", "affected_ids": ["U1"], "affected_count": 1}
        ],
        engine=engine
    )

    assert res["verdict"] == "resolved"
    assert res["after_branch_count"] == 1


# ---------------------------------------------------------------------------
# Test Verdict 2: 'reduced'
# ---------------------------------------------------------------------------

def test_verdict_reduced():
    """
    When the rewrite produces fewer distinct outcome sets than before (e.g. 2 instead of 3),
    verdict is 'reduced'.
    """
    engine = MagicMock()
    # 3 branches where A and B produce the same affected set, but C produces a different set (distinct_sets = 2)
    branches = [
        {"id": "A", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}},
        {"id": "B", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}},
        {"id": "C", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "active"}}
    ]
    records = [
        {"id": "U1", "status": "active"},
        {"id": "U2", "status": "dormant"}
    ]
    engine.analyze_and_branch.return_value = make_analysis_result(branches=branches, records=records)

    # Before had 3 distinct sets
    before_outcomes = [
        {"branch_id": "A", "affected_ids": ["U1"], "affected_count": 1},
        {"branch_id": "B", "affected_ids": ["U2"], "affected_count": 1},
        {"branch_id": "C", "affected_ids": ["U1", "U2"], "affected_count": 2}
    ]

    res = verify_rewrite(
        original_instruction="Purge old accounts",
        rewrite="Purge inactive accounts with confirmed dormancy",
        before_outcomes=before_outcomes,
        engine=engine
    )

    assert res["verdict"] == "reduced"
    assert res["before_distinct_sets"] == 3
    assert res["after_distinct_sets"] == 2


# ---------------------------------------------------------------------------
# Test Verdict 3: 'not_improved'
# ---------------------------------------------------------------------------

def test_verdict_not_improved():
    """
    When the rewrite produces the same or more distinct outcome sets than before,
    verdict is 'not_improved'.
    """
    engine = MagicMock()
    # 2 branches producing 2 distinct sets
    branches = [
        {"id": "A", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "active"}},
        {"id": "B", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}}
    ]
    records = [
        {"id": "U1", "status": "active"},
        {"id": "U2", "status": "dormant"}
    ]
    engine.analyze_and_branch.return_value = make_analysis_result(branches=branches, records=records)

    # Before had 2 distinct sets
    before_outcomes = [
        {"branch_id": "A", "affected_ids": ["U1"], "affected_count": 1},
        {"branch_id": "B", "affected_ids": ["U2"], "affected_count": 1}
    ]

    res = verify_rewrite(
        original_instruction="Remove old accounts",
        rewrite="Remove accounts if old",
        before_outcomes=before_outcomes,
        engine=engine
    )

    assert res["verdict"] == "not_improved"
    assert res["before_distinct_sets"] == 2
    assert res["after_distinct_sets"] == 2


# ---------------------------------------------------------------------------
# Test Verdict 4: 'unverifiable'
# ---------------------------------------------------------------------------

def test_verdict_unverifiable():
    """
    When analyze_and_branch returns status 'unsupported' or fails,
    verdict is 'unverifiable'.
    """
    engine = MagicMock()
    engine.analyze_and_branch.return_value = {
        "status": "unsupported",
        "reason": "Instruction requested arbitrary shell commands."
    }

    res = verify_rewrite(
        original_instruction="format disk",
        rewrite="rm -rf /",
        engine=engine
    )

    assert res["verdict"] == "unverifiable"
    assert "arbitrary shell commands" in res["reason"]

    # Also test empty rewrite string
    res_empty = verify_rewrite("valid", "", engine=engine)
    assert res_empty["verdict"] == "unverifiable"
    assert "Empty rewrite" in res_empty["reason"]


# ---------------------------------------------------------------------------
# Injected Simulator Attribution
# ---------------------------------------------------------------------------

def test_injected_simulator_attribution():
    """
    When a custom simulator callable is injected, it is executed and labeled.
    """
    engine = MagicMock()
    branches = [{"id": "A", "operation": "delete", "where": {"op": "is_null", "field": "status"}}]
    engine.analyze_and_branch.return_value = make_analysis_result(branches=branches)

    def person3_simulator(world, branches):
        return [
            {"branch_id": "A", "affected_ids": ["U99"], "affected_count": 1}
        ]

    res = verify_rewrite(
        original_instruction="Clean users",
        rewrite="Clean null status users",
        simulate=person3_simulator,
        engine=engine
    )

    assert res["verdict"] == "resolved"
    assert res["simulator_used"] == "person3_simulator"


# ---------------------------------------------------------------------------
# Model Claim Never Trusted
# ---------------------------------------------------------------------------

def test_model_claim_never_trusted():
    """
    Never trust the model's claim that a rewrite is clear.
    Even if the rewrite analysis includes assurances or suggested_rewrite claiming perfection,
    if the branches diverge in simulation, the verdict is governed strictly by outcomes.
    """
    engine = MagicMock()
    # Two divergent branches
    branches = [
        {"id": "A", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "active"}},
        {"id": "B", "operation": "delete", "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}}
    ]
    records = [
        {"id": "U1", "status": "active"},
        {"id": "U2", "status": "dormant"}
    ]
    analysis = make_analysis_result(branches=branches, records=records)
    analysis["suggested_rewrite"] = "Completely resolved and 100% unambiguous instruction."
    engine.analyze_and_branch.return_value = analysis

    before_outcomes = [
        {"branch_id": "A", "affected_ids": ["U1"], "affected_count": 1},
        {"branch_id": "B", "affected_ids": ["U2"], "affected_count": 1}
    ]

    res = verify_rewrite(
        original_instruction="Delete users",
        rewrite="Ambiguous rewrite with false claim of clarity",
        before_outcomes=before_outcomes,
        engine=engine
    )

    # Simulator outcomes show distinct_sets = 2 == before_distinct_sets
    assert res["verdict"] == "not_improved"
