"""
Tests for the Reference Simulator and Outcomes Contract (Part 4).
Verifies:
1. "Delete old user records." fixture divergence and null-date injected record isolation.
2. Exact 90-day threshold boundary matching (older_than_days 90 vs 91).
3. Null-semantics table covering every predicate operator under two-valued logic.
4. 'not' over a null field evaluation.
5. Branch isolation and execution determinism.
6. compare_outcomes summary metrics.
7. generate_rewrite structured outcomes validation and rejection of free-text.
"""

import json
from pathlib import Path
import pytest

from ai.tools.reference_simulator import (
    evaluate_predicate_spec,
    run_branch,
    run_all,
    compare_outcomes
)
from ai.outcomes import BranchOutcome, SimulationOutcomes
from ai.ai_engine import AIEngine, generate_rewrite


def get_fixtures_data():
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "ai_fixtures.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Fixture Divergence & Null-Date Injected Record
# ---------------------------------------------------------------------------

def test_fixture_delete_old_user_records_divergence():
    """
    The 'Delete old user records.' fixture gives different affected sets for A, B and C,
    and the null-date injected record (U09) appears only in the inactive_or_unknown branch among inactivity branches.
    """
    fixtures = get_fixtures_data()
    fixture = fixtures["delete old user records."]
    world = fixture["world"]
    branches = fixture["branches"]

    outcomes = run_all(world, branches)
    assert len(outcomes) == 3

    outcomes_by_id = {o["branch_id"]: o for o in outcomes}
    set_a = set(outcomes_by_id["A"]["affected_ids"])
    set_b = set(outcomes_by_id["B"]["affected_ids"])
    set_c = set(outcomes_by_id["C"]["affected_ids"])

    # All three branches produce distinct sets of affected IDs
    assert set_a != set_b
    assert set_b != set_c
    assert set_a != set_c

    # Specific counts
    assert outcomes_by_id["A"]["affected_count"] == 5
    assert outcomes_by_id["B"]["affected_count"] == 9
    assert outcomes_by_id["C"]["affected_count"] == 6

    # Injected null record U09 has last_active_at=None
    # Between A (inactive_90_days) and C (inactive_or_unknown):
    assert "U09" not in set_a
    assert "U09" in set_c


# ---------------------------------------------------------------------------
# 2. Exact Threshold Boundary
# ---------------------------------------------------------------------------

def test_exact_threshold_boundary_90_vs_91():
    """
    The record exactly at 90 days matches older_than_days 90 and not 91.
    Today: 2026-01-01. Date 90 days ago: 2025-10-03.
    """
    today_str = "2026-01-01"
    record_boundary = {"id": "U-EXACT", "last_active_at": "2025-10-03"}

    # older_than_days 90: (2026-01-01 - 2025-10-03).days == 90 >= 90 -> True
    pred_90 = {"op": "older_than_days", "field": "last_active_at", "days": 90}
    assert evaluate_predicate_spec(pred_90, record_boundary, today_str) is True

    # older_than_days 91: 90 >= 91 -> False
    pred_91 = {"op": "older_than_days", "field": "last_active_at", "days": 91}
    assert evaluate_predicate_spec(pred_91, record_boundary, today_str) is False

    # newer_than_days 90: 90 < 90 -> False
    pred_newer_90 = {"op": "newer_than_days", "field": "last_active_at", "days": 90}
    assert evaluate_predicate_spec(pred_newer_90, record_boundary, today_str) is False

    # newer_than_days 91: 90 < 91 -> True
    pred_newer_91 = {"op": "newer_than_days", "field": "last_active_at", "days": 91}
    assert evaluate_predicate_spec(pred_newer_91, record_boundary, today_str) is True


# ---------------------------------------------------------------------------
# 3. Null-Semantics Table Covering Every Predicate
# ---------------------------------------------------------------------------

def test_null_semantics_table_every_predicate():
    """
    Comprehensive table testing two-valued logic on null or missing fields:
    - is_null is True, not_null is False.
    - EVERY other leaf predicate (eq, ne, lt, lte, gt, gte, in, older_than_days, newer_than_days) evaluates to False.
    """
    today_str = "2026-01-01"
    record_null = {"id": "REC-NULL", "val": None}
    record_missing = {"id": "REC-MISSING"}
    record_present = {"id": "REC-OK", "val": "active", "num": 42, "dt": "2025-06-01"}

    for rec in (record_null, record_missing):
        # 1. is_null / not_null
        assert evaluate_predicate_spec({"op": "is_null", "field": "val"}, rec, today_str) is True
        assert evaluate_predicate_spec({"op": "not_null", "field": "val"}, rec, today_str) is False

        # 2. compare eq and ne (both must evaluate to False on null)
        assert evaluate_predicate_spec({"op": "compare", "field": "val", "cmp": "eq", "value": "active"}, rec, today_str) is False
        assert evaluate_predicate_spec({"op": "compare", "field": "val", "cmp": "ne", "value": "active"}, rec, today_str) is False

        # 3. compare relational lt, lte, gt, gte
        for rel_cmp in ("lt", "lte", "gt", "gte"):
            assert evaluate_predicate_spec({"op": "compare", "field": "val", "cmp": rel_cmp, "value": 10}, rec, today_str) is False

        # 4. in predicate
        assert evaluate_predicate_spec({"op": "in", "field": "val", "values": ["active", "pending"]}, rec, today_str) is False

        # 5. older_than_days and newer_than_days
        assert evaluate_predicate_spec({"op": "older_than_days", "field": "val", "days": 30}, rec, today_str) is False
        assert evaluate_predicate_spec({"op": "newer_than_days", "field": "val", "days": 30}, rec, today_str) is False

    # Present values evaluate normally
    assert evaluate_predicate_spec({"op": "is_null", "field": "val"}, record_present, today_str) is False
    assert evaluate_predicate_spec({"op": "not_null", "field": "val"}, record_present, today_str) is True
    assert evaluate_predicate_spec({"op": "compare", "field": "val", "cmp": "eq", "value": "active"}, record_present, today_str) is True
    assert evaluate_predicate_spec({"op": "compare", "field": "val", "cmp": "ne", "value": "dormant"}, record_present, today_str) is True


# ---------------------------------------------------------------------------
# 4. 'not' Over a Null Field
# ---------------------------------------------------------------------------

def test_not_over_null_field_evaluates_to_true():
    """
    Under two-valued logic:
    Since older_than_days evaluates to False on a null field,
    not(older_than_days on null) evaluates to not(False) -> True.
    """
    today_str = "2026-01-01"
    record_null = {"id": "REC-01", "last_active_at": None}

    leaf_pred = {"op": "older_than_days", "field": "last_active_at", "days": 90}
    assert evaluate_predicate_spec(leaf_pred, record_null, today_str) is False

    not_pred = {"op": "not", "arg": leaf_pred}
    assert evaluate_predicate_spec(not_pred, record_null, today_str) is True

    # Similarly for compare eq on null
    eq_leaf = {"op": "compare", "field": "last_active_at", "cmp": "eq", "value": "2025-01-01"}
    assert evaluate_predicate_spec(eq_leaf, record_null, today_str) is False
    assert evaluate_predicate_spec({"op": "not", "arg": eq_leaf}, record_null, today_str) is True


# ---------------------------------------------------------------------------
# 5. Branch Isolation & Determinism
# ---------------------------------------------------------------------------

def test_branch_isolation_and_determinism():
    """
    Running branch A (e.g. delete) must never mutate world.records or affect branch B.
    Repeated runs under the same inputs must yield identical results.
    """
    world = {
        "entity": "user",
        "today": "2026-01-01",
        "records": [
            {"id": "U1", "status": "active", "created_at": "2025-01-01"},
            {"id": "U2", "status": "dormant", "created_at": "2025-01-01"},
            {"id": "U3", "status": "pending", "created_at": "2025-01-01"}
        ]
    }
    branches = [
        {
            "id": "A",
            "operation": "delete",
            "update_set": None,
            "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "dormant"}
        },
        {
            "id": "B",
            "operation": "flag",
            "update_set": None,
            "where": {"op": "compare", "field": "status", "cmp": "eq", "value": "active"}
        }
    ]

    outcomes_1 = run_all(world, branches)
    outcomes_2 = run_all(world, branches)

    # Determinism
    assert outcomes_1 == outcomes_2

    # Branch A deleted U2
    assert outcomes_1[0]["affected_ids"] == ["U2"]
    assert len(outcomes_1[0]["records_after"]) == 2
    assert [r["id"] for r in outcomes_1[0]["records_after"]] == ["U1", "U3"]

    # Branch B flagged U1
    assert outcomes_1[1]["affected_ids"] == ["U1"]
    assert len(outcomes_1[1]["records_after"]) == 3
    assert outcomes_1[1]["records_after"][0]["_flagged"] is True

    # Original world records were NOT mutated
    assert len(world["records"]) == 3
    assert "_flagged" not in world["records"][0]


# ---------------------------------------------------------------------------
# 6. compare_outcomes Summary Metrics
# ---------------------------------------------------------------------------

def test_compare_outcomes_summary():
    """
    Tests compare_outcomes: diverges, distinct_sets, only_in, and common_ids.
    """
    outcomes = [
        {"branch_id": "A", "affected_ids": ["U1", "U2"], "affected_count": 2},
        {"branch_id": "B", "affected_ids": ["U2", "U3"], "affected_count": 2},
        {"branch_id": "C", "affected_ids": ["U2"], "affected_count": 1}
    ]
    summary = compare_outcomes(outcomes)

    assert summary["diverges"] is True
    assert summary["distinct_sets"] == 3
    assert summary["common_ids"] == ["U2"]
    assert summary["only_in"] == {
        "A": ["U1"],
        "B": ["U3"],
        "C": []
    }


# ---------------------------------------------------------------------------
# 7. generate_rewrite Structured Outcomes Validation
# ---------------------------------------------------------------------------

def test_generate_rewrite_accepts_structured_outcomes_and_rejects_free_text():
    """
    generate_rewrite must accept structured outcomes (models or dicts)
    and reject free-text or malformed shapes with a clear ValueError.
    """
    engine = AIEngine(fixture_mode=True)
    terms = [{"term": "old", "description": "ambiguous threshold"}]
    branches = [{"id": "A"}, {"id": "B"}]

    valid_dict_outcomes = [
        {"branch_id": "A", "affected_ids": ["U1"], "affected_count": 1},
        {"branch_id": "B", "affected_ids": ["U1", "U2"], "affected_count": 2}
    ]

    # 1. Valid list of dicts succeeds
    res1 = engine.generate_rewrite("Delete old users", terms, valid_dict_outcomes, branches=branches)
    assert "suggested_rewrite" in res1

    # 2. Valid SimulationOutcomes instance succeeds
    so = SimulationOutcomes.coerce(valid_dict_outcomes, branches=branches)
    res2 = engine.generate_rewrite("Delete old users", terms, so, branches=branches)
    assert "suggested_rewrite" in res2

    # 3. Free-text string is strictly rejected
    with pytest.raises(ValueError, match="Free-text outcomes are not accepted"):
        engine.generate_rewrite("Delete old users", terms, "Branch A affected 5 rows, branch B affected 9 rows")

    # 4. Unknown branch_id rejected against provided branches
    invalid_branch_outcomes = [
        {"branch_id": "Z", "affected_ids": ["U1"], "affected_count": 1}
    ]
    with pytest.raises(ValueError, match="does not exist among provided branches"):
        engine.generate_rewrite("Delete old users", terms, invalid_branch_outcomes, branches=branches)

    # 5. Mismatched affected_count vs affected_ids rejected
    mismatched_count = [
        {"branch_id": "A", "affected_ids": ["U1", "U2"], "affected_count": 5}
    ]
    with pytest.raises(ValueError, match="must equal len\\(affected_ids\\)"):
        engine.generate_rewrite("Delete old users", terms, mismatched_count, branches=branches)
