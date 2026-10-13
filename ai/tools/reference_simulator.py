"""
REFERENCE SIMULATOR SPECIFICATION for Semantic Chaos Monkey.

NOTE: This is a small, readable, dependency-free executable spec of the Part 3 semantics.
It is NOT Person 3's production simulator. It serves as an executable specification
and test harness to verify plan interpretation, branch isolation, and outcomes comparison.

Safety Principle: Evaluates purely declarative AST data without eval, exec, SQL, or dynamic code.
"""

from copy import deepcopy
from datetime import date
from typing import Dict, Any, List, Union, Optional, Set


def evaluate_predicate_spec(pred: Dict[str, Any], record: Dict[str, Any], today_str: str) -> bool:
    """
    Interprets a declarative predicate AST against a record using explicit dispatch on 'op'.
    NO EVAL OR EXEC IS USED.

    Part 3 Semantics:
    1. is_null is True iff value is None or missing; not_null is opposite.
    2. On a null or missing field, EVERY other leaf predicate evaluates to False (including eq, ne).
    3. not over a null field is plain boolean logic: not(False) -> True.
    4. Date math against today_str:
       older_than_days N: (today - val).days >= N
       newer_than_days N: (today - val).days < N
       Future dates have negative age: older_than is False, newer_than is True.
    5. Comparison typing:
       eq, ne: strict equality of same types.
       lt, lte, gt, gte: int, float, date.
    """
    op = pred.get("op")

    if op == "is_null":
        field = pred.get("field", "")
        return record.get(field) is None

    if op == "not_null":
        field = pred.get("field", "")
        return record.get(field) is not None

    if op in ("older_than_days", "newer_than_days", "compare", "in"):
        field = pred.get("field", "")
        val = record.get(field)

        # Two-valued logic: On a null or missing field, EVERY leaf predicate evaluates to False
        if val is None:
            return False

        if op == "older_than_days":
            today = date.fromisoformat(today_str)
            val_date = date.fromisoformat(str(val))
            age = (today - val_date).days
            return age >= int(pred.get("days", 0))

        if op == "newer_than_days":
            today = date.fromisoformat(today_str)
            val_date = date.fromisoformat(str(val))
            age = (today - val_date).days
            return age < int(pred.get("days", 0))

        if op == "in":
            allowed_vals = pred.get("values", [])
            return val in allowed_vals

        if op == "compare":
            cmp_op = pred.get("cmp")
            target_val = pred.get("value")

            # Date comparisons
            if isinstance(val, str) and isinstance(target_val, str):
                try:
                    d_val = date.fromisoformat(val)
                    d_target = date.fromisoformat(target_val)
                    val = d_val
                    target_val = d_target
                except ValueError:
                    pass

            if cmp_op == "eq":
                return val == target_val
            elif cmp_op == "ne":
                return val != target_val
            elif cmp_op == "lt":
                return val < target_val
            elif cmp_op == "lte":
                return val <= target_val
            elif cmp_op == "gt":
                return val > target_val
            elif cmp_op == "gte":
                return val >= target_val
            else:
                raise ValueError(f"Unknown compare operator: '{cmp_op}'")

    if op == "and":
        args = pred.get("args", [])
        return all(evaluate_predicate_spec(a, record, today_str) for a in args)

    if op == "or":
        args = pred.get("args", [])
        return any(evaluate_predicate_spec(a, record, today_str) for a in args)

    if op == "not":
        arg = pred.get("arg", {})
        return not evaluate_predicate_spec(arg, record, today_str)

    if op == "term_ref":
        raise ValueError(f"Cannot evaluate unresolved term_ref('{pred.get('term')}') in simulator")

    raise ValueError(f"Unknown or unsupported predicate operator: '{op}'")


def run_branch(
    world: Union[Dict[str, Any], Any],
    branch: Union[Dict[str, Any], Any]
) -> Dict[str, Any]:
    """
    Executes a single branch plan against a deep copy of the world records.
    Returns:
    {
        "branch_id": str,
        "affected_ids": List[str],
        "affected_count": int,
        "records_after": List[Dict[str, Any]]
    }
    """
    # Extract world properties
    if isinstance(world, dict):
        today_str = world.get("today", "2026-01-01")
        records = deepcopy(world.get("records", []))
    else:
        today_str = getattr(world, "today", "2026-01-01")
        records = deepcopy(getattr(world, "records", []))

    # Extract branch properties
    if isinstance(branch, dict):
        branch_id = branch.get("id", "")
        operation = branch.get("operation", "delete")
        update_set = branch.get("update_set")
        where_pred = branch.get("where", {})
    else:
        branch_id = getattr(branch, "id", "")
        operation = getattr(branch, "operation", "delete")
        update_set = getattr(branch, "update_set", None)
        where_pred = getattr(branch, "where", {})

    # Evaluate 'where' in original record order
    affected_ids: List[str] = []
    matched_indices: Set[int] = set()

    for idx, rec in enumerate(records):
        if evaluate_predicate_spec(where_pred, rec, today_str):
            affected_ids.append(rec["id"])
            matched_indices.add(idx)

    affected_count = len(affected_ids)

    # Apply operation on a fresh copy of records
    records_after: List[Dict[str, Any]] = []
    if operation == "delete":
        for idx, rec in enumerate(records):
            if idx not in matched_indices:
                records_after.append(deepcopy(rec))
    elif operation in ("archive", "update"):
        for idx, rec in enumerate(records):
            new_rec = deepcopy(rec)
            if idx in matched_indices and update_set:
                for k, v in update_set.items():
                    if k != "id" and not k.startswith("_"):
                        new_rec[k] = deepcopy(v)
            records_after.append(new_rec)
    elif operation == "flag":
        for idx, rec in enumerate(records):
            new_rec = deepcopy(rec)
            if idx in matched_indices:
                new_rec["_flagged"] = True
            records_after.append(new_rec)
    else:
        raise ValueError(f"Unknown operation: '{operation}'")

    return {
        "branch_id": branch_id,
        "affected_ids": affected_ids,
        "affected_count": affected_count,
        "records_after": records_after
    }


def run_all(
    world: Union[Dict[str, Any], Any],
    branches: List[Union[Dict[str, Any], Any]]
) -> List[Dict[str, Any]]:
    """
    Executes all branch plans. Each branch executes on an isolated deep copy of world.records.
    """
    outcomes = []
    for b in branches:
        outcome = run_branch(world, b)
        outcomes.append(outcome)
    return outcomes


def compare_outcomes(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compares simulation outcomes across branches:
    returns {"diverges": bool, "distinct_sets": int, "only_in": Dict[str, List[str]], "common_ids": List[str]}
    """
    outcomes_map: Dict[str, Set[str]] = {}
    for o in outcomes:
        bid = o.get("branch_id", "")
        ids = set(o.get("affected_ids", []))
        outcomes_map[bid] = ids

    # Distinct sets
    sets = [frozenset(s) for s in outcomes_map.values()]
    distinct_sets = len(set(sets))
    diverges = distinct_sets > 1

    # Overlap (common across all branches)
    if outcomes_map:
        common_set = set.intersection(*outcomes_map.values())
    else:
        common_set = set()
    common_ids = sorted(list(common_set))

    # Exclusive records per branch ('only_in')
    only_in: Dict[str, List[str]] = {}
    for bid, ids in outcomes_map.items():
        other_ids = set().union(*(ids_o for obid, ids_o in outcomes_map.items() if obid != bid))
        exclusive = ids - other_ids
        only_in[bid] = sorted(list(exclusive))

    return {
        "diverges": diverges,
        "distinct_sets": distinct_sets,
        "only_in": only_in,
        "common_ids": common_ids
    }
