"""
Safe Plan Schema for Semantic Chaos Monkey.
Defines a declarative, sandboxed language for describing entities, worlds,
predicates, and simulation branch plans.

NO CODE, SQL, OR SHELL EXPRESSIONS ALLOWED.
All operations, types, and predicate operators are strictly allowlisted.
"""

import os
from datetime import date
from typing import Dict, Any, List, Optional, Literal, Union, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Global Reference Date
# ---------------------------------------------------------------------------
WORLD_TODAY = os.getenv("CHAOS_WORLD_TODAY", "2026-01-01")

# ---------------------------------------------------------------------------
# Allowlist Definitions (Part 3: "restore" removed)
# ---------------------------------------------------------------------------
AllowedOperation = Literal["delete", "archive", "update", "flag"]
AllowedFieldType = Literal["string", "int", "float", "bool", "date"]
AllowedCompareOp = Literal["eq", "ne", "lt", "lte", "gt", "gte"]


# ---------------------------------------------------------------------------
# Type Validation Helpers
# ---------------------------------------------------------------------------
def check_value_matches_type(val: Any, ftype: AllowedFieldType, field_name: str = "") -> None:
    """Verifies that a value matches the declared AllowedFieldType."""
    if val is None:
        raise ValueError(f"Null value not permitted where typed primitive is required for field '{field_name}'")
    if ftype == "string":
        if not isinstance(val, str):
            raise ValueError(f"Expected string for field '{field_name}', got {type(val).__name__} ({val!r})")
    elif ftype == "int":
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"Expected int for field '{field_name}', got {type(val).__name__} ({val!r})")
    elif ftype == "float":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"Expected float for field '{field_name}', got {type(val).__name__} ({val!r})")
    elif ftype == "bool":
        if not isinstance(val, bool):
            raise ValueError(f"Expected bool for field '{field_name}', got {type(val).__name__} ({val!r})")
    elif ftype == "date":
        if not isinstance(val, str):
            raise ValueError(f"Expected ISO date string for field '{field_name}', got {type(val).__name__} ({val!r})")
        try:
            date.fromisoformat(val)
        except Exception:
            raise ValueError(f"Invalid date format for field '{field_name}': '{val}'. Expected YYYY-MM-DD.")


# ---------------------------------------------------------------------------
# Predicate AST (Allowlisted, bounded depth and node count)
# ---------------------------------------------------------------------------

class ComparePredicate(BaseModel):
    op: Literal["compare"] = "compare"
    field: str
    cmp: AllowedCompareOp
    value: Union[str, int, float, bool]


class OlderThanDaysPredicate(BaseModel):
    op: Literal["older_than_days"] = "older_than_days"
    field: str
    days: int = Field(..., ge=0)


class NewerThanDaysPredicate(BaseModel):
    op: Literal["newer_than_days"] = "newer_than_days"
    field: str
    days: int = Field(..., ge=0)


class IsNullPredicate(BaseModel):
    op: Literal["is_null"] = "is_null"
    field: str


class NotNullPredicate(BaseModel):
    op: Literal["not_null"] = "not_null"
    field: str


class InPredicate(BaseModel):
    op: Literal["in"] = "in"
    field: str
    values: List[Union[str, int, float, bool]] = Field(..., min_length=1, max_length=20)


class TermRefPredicate(BaseModel):
    """Placeholder for ambiguous term references in operation templates."""
    op: Literal["term_ref"] = "term_ref"
    term: str


# Forward declaration for recursive logical predicates
class AndPredicate(BaseModel):
    op: Literal["and"] = "and"
    args: List["Predicate"] = Field(..., min_length=1)


class OrPredicate(BaseModel):
    op: Literal["or"] = "or"
    args: List["Predicate"] = Field(..., min_length=1)


class NotPredicate(BaseModel):
    op: Literal["not"] = "not"
    arg: "Predicate"


Predicate = Union[
    ComparePredicate,
    OlderThanDaysPredicate,
    NewerThanDaysPredicate,
    IsNullPredicate,
    NotNullPredicate,
    InPredicate,
    TermRefPredicate,
    AndPredicate,
    OrPredicate,
    NotPredicate
]

# Update forward refs
AndPredicate.model_rebuild()
OrPredicate.model_rebuild()
NotPredicate.model_rebuild()


def parse_predicate(data: Dict[str, Any]) -> Predicate:
    """Parses a dictionary into a validated Predicate model."""
    op = data.get("op")
    if op == "compare":
        return ComparePredicate.model_validate(data)
    elif op == "older_than_days":
        return OlderThanDaysPredicate.model_validate(data)
    elif op == "newer_than_days":
        return NewerThanDaysPredicate.model_validate(data)
    elif op == "is_null":
        return IsNullPredicate.model_validate(data)
    elif op == "not_null":
        return NotNullPredicate.model_validate(data)
    elif op == "in":
        return InPredicate.model_validate(data)
    elif op == "term_ref":
        return TermRefPredicate.model_validate(data)
    elif op == "and":
        args = [parse_predicate(a) if isinstance(a, dict) else a for a in data.get("args", [])]
        return AndPredicate(args=args)
    elif op == "or":
        args = [parse_predicate(a) if isinstance(a, dict) else a for a in data.get("args", [])]
        return OrPredicate(args=args)
    elif op == "not":
        arg = parse_predicate(data["arg"]) if isinstance(data.get("arg"), dict) else data.get("arg")
        return NotPredicate(arg=arg)
    else:
        raise ValueError(f"Unknown or forbidden predicate operator: '{op}'")


def count_predicate_nodes_and_depth(p: Predicate, current_depth: int = 1) -> tuple[int, int]:
    """Recursively computes (total_nodes, max_depth) of a predicate tree."""
    if isinstance(p, (AndPredicate, OrPredicate)):
        total_nodes = 1
        max_d = current_depth
        for child in p.args:
            c_nodes, c_depth = count_predicate_nodes_and_depth(child, current_depth + 1)
            total_nodes += c_nodes
            max_d = max(max_d, c_depth)
        return total_nodes, max_d
    elif isinstance(p, NotPredicate):
        c_nodes, c_depth = count_predicate_nodes_and_depth(p.arg, current_depth + 1)
        return 1 + c_nodes, max(current_depth, c_depth)
    else:
        return 1, current_depth


def validate_predicate_limits(p: Predicate, max_depth: int = 4, max_nodes: int = 12) -> None:
    """Enforces AST complexity bounds to prevent denial-of-service / exponential branching."""
    nodes, depth = count_predicate_nodes_and_depth(p)
    if depth > max_depth:
        raise ValueError(f"Predicate exceeds maximum depth {max_depth} (got depth {depth})")
    if nodes > max_nodes:
        raise ValueError(f"Predicate exceeds maximum node limit {max_nodes} (got {nodes} nodes)")


def validate_predicate_schema(
    p: Predicate,
    field_types: Dict[str, str],
    allow_term_ref: bool = False
) -> List[str]:
    """
    Validates that fields exist, operators match field types, value types match schema,
    and term_ref is not present in final plans.
    Returns any non-fatal semantic warnings (e.g., 'not' wrapping a nullable field).
    """
    warnings: List[str] = []

    if isinstance(p, TermRefPredicate):
        if not allow_term_ref:
            raise ValueError(f"Unresolved term_ref('{p.term}') found in executable branch plan")
        return warnings

    if isinstance(p, (ComparePredicate, OlderThanDaysPredicate, NewerThanDaysPredicate, IsNullPredicate, NotNullPredicate, InPredicate)):
        if p.field not in field_types:
            raise ValueError(f"Field '{p.field}' not defined in entity schema. Allowed fields: {list(field_types.keys())}")
        ftype = field_types[p.field]

        if isinstance(p, (OlderThanDaysPredicate, NewerThanDaysPredicate)):
            if ftype != "date":
                raise ValueError(f"Operator '{p.op}' can only be used on date fields (field '{p.field}' is of type '{ftype}')")

        elif isinstance(p, ComparePredicate):
            # Check value type matches field type
            check_value_matches_type(p.value, ftype, field_name=p.field)

            # Operator compatibility: relational comparisons only on int, float, date
            if p.cmp in ("lt", "lte", "gt", "gte") and ftype not in ("int", "float", "date"):
                raise ValueError(f"Relational operator '{p.cmp}' cannot be used on {ftype} field '{p.field}'. Only 'eq' and 'ne' are allowed.")

        elif isinstance(p, InPredicate):
            # Check each value in `in` list matches field type
            for v in p.values:
                check_value_matches_type(v, ftype, field_name=p.field)

    elif isinstance(p, (AndPredicate, OrPredicate)):
        for child in p.args:
            warnings.extend(validate_predicate_schema(child, field_types, allow_term_ref=allow_term_ref))

    elif isinstance(p, NotPredicate):
        # 3.3 Null semantics warning: not wrapping a leaf condition on a nullable field
        if isinstance(p.arg, (ComparePredicate, OlderThanDaysPredicate, NewerThanDaysPredicate, InPredicate)):
            warnings.append(
                f"Predicate uses 'not' wrapping condition on field '{p.arg.field}', which will evaluate to True for null/missing values under two-valued logic."
            )
        warnings.extend(validate_predicate_schema(p.arg, field_types, allow_term_ref=allow_term_ref))

    return warnings


# ---------------------------------------------------------------------------
# Operation and UpdateSet Validation
# ---------------------------------------------------------------------------

def validate_operation_and_update_set(
    operation: AllowedOperation,
    update_set: Optional[Dict[str, Any]],
    field_types: Optional[Dict[str, str]] = None
) -> None:
    """
    Enforces operational rules:
    - delete: update_set must be null
    - archive and update: update_set is required (non-empty)
    - flag: update_set must be null (sets reserved '_flagged': true)
    - update_set keys must exist in entity schema, cannot be 'id', cannot start with '_'
    - update_set values must match declared field types
    """
    if operation in ("delete", "flag"):
        if update_set is not None and len(update_set) > 0:
            raise ValueError(f"Operation '{operation}' does not permit 'update_set' (must be null)")
    elif operation in ("archive", "update"):
        if update_set is None or len(update_set) == 0:
            raise ValueError(f"Operation '{operation}' requires a non-empty 'update_set'")

    if update_set is not None:
        for k, v in update_set.items():
            if k == "id":
                raise ValueError("update_set cannot modify the primary 'id' field")
            if k.startswith("_"):
                raise ValueError(f"update_set key '{k}' cannot use reserved prefix '_'")
            if field_types is not None:
                if k not in field_types:
                    raise ValueError(f"update_set key '{k}' does not exist in entity schema. Allowed fields: {list(field_types.keys())}")
                check_value_matches_type(v, field_types[k], field_name=k)


# ---------------------------------------------------------------------------
# Schema Models
# ---------------------------------------------------------------------------

class FieldDefinition(BaseModel):
    name: str = Field(..., min_length=1)
    type: AllowedFieldType
    description: Optional[str] = ""

    @field_validator("name")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        if v.startswith("_"):
            raise ValueError(f"Field name '{v}' is invalid: reserved fields starting with '_' cannot be defined in entity schema")
        return v


class EntitySchema(BaseModel):
    name: str = Field(..., min_length=1)
    fields: List[FieldDefinition] = Field(..., min_length=1)

    def get_field_types(self) -> Dict[str, str]:
        return {f.name: f.type for f in self.fields}


class WorldRecord(BaseModel):
    id: str
    data: Dict[str, Any]
    _injected: bool = False


class World(BaseModel):
    entity: str
    today: str = Field(default_factory=lambda: os.getenv("CHAOS_WORLD_TODAY", "2026-01-01"), description="Fixed reference date for reproducibility (YYYY-MM-DD)")
    records: List[Dict[str, Any]] = Field(..., min_length=1, max_length=14)

    @field_validator("records")
    @classmethod
    def validate_record_ids(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ids = [r.get("id") for r in v]
        if any(not i for i in ids):
            raise ValueError("Every record in world must have a non-empty 'id' field")
        if len(set(ids)) != len(ids):
            raise ValueError("Record IDs must be unique in world: duplicates found")
        return v


class MeaningDefinition(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    assumption: str = Field(..., min_length=5)
    predicate: Dict[str, Any]  # Serializable Predicate representation


class AmbiguousTerm(BaseModel):
    term: str = Field(..., min_length=1)
    description: str = Field(..., min_length=5)
    meanings: List[MeaningDefinition] = Field(..., min_length=2, max_length=4)


class OperationTemplate(BaseModel):
    operation: AllowedOperation
    target_entity: str
    update_set: Optional[Dict[str, Any]] = None
    where_template: Dict[str, Any]  # Predicate tree containing term_ref nodes

    @model_validator(mode="after")
    def validate_op_rules(self) -> "OperationTemplate":
        validate_operation_and_update_set(self.operation, self.update_set)
        return self


class BranchPlan(BaseModel):
    id: str = Field(..., min_length=1, max_length=4)
    title: str = Field(..., min_length=1)
    assumption: str = Field(..., min_length=5)
    operation: AllowedOperation
    update_set: Optional[Dict[str, Any]] = None
    where: Dict[str, Any]  # Fully resolved Predicate tree
    chosen_meanings: Dict[str, str] = Field(default_factory=dict)
    explanation: str = Field(..., min_length=5)

    @model_validator(mode="after")
    def validate_op_rules(self) -> "BranchPlan":
        validate_operation_and_update_set(self.operation, self.update_set)
        return self


class GenericAnalysisOutput(BaseModel):
    domain: str
    entity_schema: EntitySchema
    ambiguous_terms: List[AmbiguousTerm]
    operation_template: OperationTemplate
    suggested_rewrite: Optional[str] = ""


# ---------------------------------------------------------------------------
# Simulator Reference Evaluator (Simulator Contract for Person 3)
# ---------------------------------------------------------------------------

def evaluate_predicate(p: Predicate, record: Dict[str, Any], today_str: str = WORLD_TODAY) -> bool:
    """
    Evaluates a predicate AST against a record under two-valued logic with null safety.
    Defines the reference interpreter for Person 3's simulator:
    - is_null is True iff value is None or missing; not_null is opposite.
    - On null/missing, ALL other leaf predicates evaluate to False (including eq, ne).
    - not(leaf) over null evaluates to True (since leaf is False).
    - older_than_days N: (today - val).days >= N. Future dates have negative age (False).
    - newer_than_days N: (today - val).days < N. Future dates have negative age (True).
    """
    if isinstance(p, IsNullPredicate):
        val = record.get(p.field)
        return val is None

    if isinstance(p, NotNullPredicate):
        val = record.get(p.field)
        return val is not None

    if isinstance(p, (ComparePredicate, OlderThanDaysPredicate, NewerThanDaysPredicate, InPredicate)):
        val = record.get(p.field)
        # On a null or missing field, EVERY other leaf predicate evaluates to False
        if val is None:
            return False

        if isinstance(p, OlderThanDaysPredicate):
            today = date.fromisoformat(today_str)
            val_date = date.fromisoformat(str(val))
            age_days = (today - val_date).days
            return age_days >= p.days

        if isinstance(p, NewerThanDaysPredicate):
            today = date.fromisoformat(today_str)
            val_date = date.fromisoformat(str(val))
            age_days = (today - val_date).days
            return age_days < p.days

        if isinstance(p, InPredicate):
            return val in p.values

        if isinstance(p, ComparePredicate):
            # Parse dates for comparison if field is date
            if isinstance(val, str) and isinstance(p.value, str):
                try:
                    val_d = date.fromisoformat(val)
                    cmp_d = date.fromisoformat(p.value)
                    val = val_d
                    p_val = cmp_d
                except ValueError:
                    p_val = p.value
            else:
                p_val = p.value

            if p.cmp == "eq":
                return val == p_val
            elif p.cmp == "ne":
                return val != p_val
            elif p.cmp == "lt":
                return val < p_val
            elif p.cmp == "lte":
                return val <= p_val
            elif p.cmp == "gt":
                return val > p_val
            elif p.cmp == "gte":
                return val >= p_val

    if isinstance(p, AndPredicate):
        return all(evaluate_predicate(a, record, today_str) for a in p.args)

    if isinstance(p, OrPredicate):
        return any(evaluate_predicate(a, record, today_str) for a in p.args)

    if isinstance(p, NotPredicate):
        return not evaluate_predicate(p.arg, record, today_str)

    if isinstance(p, TermRefPredicate):
        raise ValueError(f"Cannot evaluate unresolved term_ref('{p.term}')")

    raise ValueError(f"Unknown predicate type: {type(p).__name__}")


def compute_affected(
    where_pred: Predicate,
    records: List[Dict[str, Any]],
    today_str: str = WORLD_TODAY
) -> Tuple[List[str], int]:
    """
    Computes affected_ids and affected_count in original record order.
    Definition of affected: IDs of records matched by 'where', whether or not a value changed.
    """
    affected_ids = [r["id"] for r in records if evaluate_predicate(where_pred, r, today_str)]
    return affected_ids, len(affected_ids)


# Re-export outcomes models
try:
    from ai.outcomes import BranchOutcome, SimulationOutcomes
except ImportError:
    from outcomes import BranchOutcome, SimulationOutcomes

