"""
Structured Outcomes Contract for Semantic Chaos Monkey.
Defines models, validation, and evidence calculations for branch simulation outcomes.
"""

from typing import List, Dict, Any, Optional, Set, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class BranchOutcome(BaseModel):
    """
    Simulation result for a single branch plan.
    affected_ids: records matched by where, in original record order.
    affected_count: count of affected records, must strictly equal len(affected_ids).
    """
    branch_id: str = Field(..., min_length=1)
    affected_ids: List[str] = Field(default_factory=list)
    affected_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_count_matches(self) -> "BranchOutcome":
        if self.affected_count != len(self.affected_ids):
            raise ValueError(
                f"BranchOutcome '{self.branch_id}': affected_count ({self.affected_count}) "
                f"must equal len(affected_ids) ({len(self.affected_ids)})"
            )
        return self


class SimulationOutcomes(BaseModel):
    """
    Container for all branch simulation outcomes.
    Enforces unique branch IDs and validates against branch plans if provided.
    """
    outcomes: List[BranchOutcome] = Field(..., min_length=1)

    @field_validator("outcomes")
    @classmethod
    def validate_unique_branch_ids(cls, v: List[BranchOutcome]) -> List[BranchOutcome]:
        branch_ids = [b.branch_id for b in v]
        if len(set(branch_ids)) != len(branch_ids):
            raise ValueError(f"Duplicate branch_id found in SimulationOutcomes: {branch_ids}")
        return v

    def validate_against_branches(self, branches: List[Any]) -> None:
        """Verifies that every outcome's branch_id exists among provided branch plans."""
        valid_ids: Set[str] = set()
        for b in branches:
            if isinstance(b, dict):
                valid_ids.add(b.get("id", ""))
            elif hasattr(b, "id"):
                valid_ids.add(getattr(b, "id"))

        for bo in self.outcomes:
            if bo.branch_id not in valid_ids:
                raise ValueError(
                    f"Outcome branch_id '{bo.branch_id}' does not exist among provided branches: {sorted(valid_ids)}"
                )

    @classmethod
    def coerce(cls, raw: Any, branches: Optional[List[Any]] = None) -> "SimulationOutcomes":
        """
        Coerces input into a validated SimulationOutcomes model.
        Accepts:
        - SimulationOutcomes instance
        - List of BranchOutcome or dicts with keys (branch_id, affected_ids, affected_count)
        - Dict with 'outcomes': [...]
        - Dict mapping branch_id -> dict/list of affected_ids
        Rejects:
        - Free-text / strings
        - None / empty payloads
        - Mismatched counts or duplicate IDs
        """
        if raw is None:
            raise ValueError("Simulation outcomes payload cannot be null or empty.")
        if isinstance(raw, str):
            raise ValueError(
                f"Free-text outcomes are not accepted. Expected structured SimulationOutcomes, got string: {raw!r}"
            )

        if isinstance(raw, SimulationOutcomes):
            obj = raw
        elif isinstance(raw, list):
            items = []
            for item in raw:
                if isinstance(item, BranchOutcome):
                    items.append(item)
                elif isinstance(item, dict):
                    if "branch_id" not in item:
                        raise ValueError(f"Outcome dict missing required 'branch_id': {item}")
                    item_copy = dict(item)
                    if "affected_count" not in item_copy and "affected_ids" in item_copy:
                        item_copy["affected_count"] = len(item_copy["affected_ids"])
                    items.append(BranchOutcome.model_validate(item_copy))
                else:
                    raise ValueError(f"Invalid outcome element type: {type(item).__name__}")
            obj = cls(outcomes=items)
        elif isinstance(raw, dict):
            if "outcomes" in raw and isinstance(raw["outcomes"], list):
                obj = cls.coerce(raw["outcomes"])
            else:
                items = []
                for k, v in raw.items():
                    if isinstance(v, dict):
                        d = dict(v)
                        d.setdefault("branch_id", k)
                        if "affected_ids" in d and "affected_count" not in d:
                            d["affected_count"] = len(d["affected_ids"])
                        items.append(BranchOutcome.model_validate(d))
                    elif isinstance(v, list):
                        items.append(BranchOutcome(branch_id=k, affected_ids=v, affected_count=len(v)))
                    else:
                        raise ValueError(f"Unrecognized outcome structure for branch '{k}': {v}")
                if not items:
                    raise ValueError("Empty outcomes dictionary provided.")
                obj = cls(outcomes=items)
        else:
            raise ValueError(f"Unsupported outcomes type: {type(raw).__name__}")

        if branches is not None:
            obj.validate_against_branches(branches)

        return obj

    def get_evidence_summary(self) -> Dict[str, Any]:
        """
        Computes deterministic evidence metrics:
        - which branches differ
        - which record IDs only some branches select ('only_in')
        - the overlap (common to all branches)
        - empty branches (affected_count == 0)
        """
        outcomes_map = {b.branch_id: set(b.affected_ids) for b in self.outcomes}
        all_branch_ids = [b.branch_id for b in self.outcomes]

        # Distinct sets check
        sets = [frozenset(s) for s in outcomes_map.values()]
        unique_sets = set(sets)
        diverges = len(unique_sets) > 1

        # Overlap across all branches
        if outcomes_map:
            common_set = set.intersection(*outcomes_map.values())
        else:
            common_set = set()
        common_ids = sorted(list(common_set))

        # Empty branches
        empty_branches = [b.branch_id for b in self.outcomes if b.affected_count == 0]

        # Exclusive records per branch
        only_in: Dict[str, List[str]] = {}
        for bid, ids in outcomes_map.items():
            other_ids = set().union(*(ids_other for obid, ids_other in outcomes_map.items() if obid != bid))
            exclusive = ids - other_ids
            only_in[bid] = sorted(list(exclusive))

        # Differing pairs
        differing_pairs = []
        for i, b1 in enumerate(all_branch_ids):
            for b2 in all_branch_ids[i + 1:]:
                if outcomes_map[b1] != outcomes_map[b2]:
                    differing_pairs.append(f"{b1} vs {b2}")

        return {
            "diverges": diverges,
            "distinct_sets": len(unique_sets),
            "total_branches": len(self.outcomes),
            "common_ids": common_ids,
            "common_count": len(common_ids),
            "empty_branches": empty_branches,
            "only_in": only_in,
            "differing_pairs": differing_pairs,
            "branch_summary": {
                b.branch_id: {
                    "affected_count": b.affected_count,
                    "affected_ids": b.affected_ids
                }
                for b in self.outcomes
            }
        }
