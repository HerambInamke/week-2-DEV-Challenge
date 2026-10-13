# Semantic Chaos Monkey: AI Engine Technical Audit (Part 1)

**Audit Target**: `ai/ai_engine.py`, `ai/plan_schema.py`, `ai/prompts.py`, `ai/fixtures/ai_fixtures.json`, `ai/tests/test_ai_engine.py`  
**Date**: 2026-10-13  
**Auditor**: Person 4 (AI Owner)  

---

## Audit Findings & Questions

### 1. Is `world.today` a fixed constant or does it come from the system clock (`datetime.now`/`today`)?
- **Answer**: It is a **fixed, reproducible constant** defaulting to `"2026-01-01"`, overridable via the environment variable `CHAOS_WORLD_TODAY`. Neither `datetime.now()` nor `date.today()` is used anywhere in the generation pipeline.
- **File & Line References**:
  - [`ai/plan_schema.py:L18`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L18): Global fallback constant `WORLD_TODAY = os.getenv("CHAOS_WORLD_TODAY", "2026-01-01")`.
  - [`ai/plan_schema.py:L315`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L315): `World.today` field default factory: `Field(default_factory=lambda: os.getenv("CHAOS_WORLD_TODAY", "2026-01-01"))`.
  - [`ai/ai_engine.py:L88-90`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L88-L90): `get_world_today()` utility reading `os.getenv("CHAOS_WORLD_TODAY", "2026-01-01")`.
  - [`ai/ai_engine.py:L294-295`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L294-L295): Edge case calculation anchoring: `ref_today = get_world_today(); today = date.fromisoformat(ref_today)`.
  - [`ai/ai_engine.py:L559`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L559): World instantiation: `World(..., today=get_world_today(), ...)`.
  - [`ai/prompts.py:L262-263`](file:///e:/Monkey/Code-Monkey/ai/prompts.py#L262-L263): Injected reference date in world generation prompt: `ref_today = get_world_today()`.
  - Verified by unit test: [`ai/tests/test_ai_engine.py:L621-638`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L621-L638) (`test_different_mocked_system_dates_produce_identical_worlds`).

---

### 2. Is each LLM call's timeout capped by the REMAINING total budget, or only by `LLM_TIMEOUT_SECONDS`? Can retries push total time past `LLM_TOTAL_BUDGET_SECONDS`?
- **Answer**: 
  - Each LLM call is strictly capped by **`min(self.timeout, remaining)`** where `remaining = deadline - now` and `deadline = start_time + LLM_TOTAL_BUDGET_SECONDS`.
  - **Retries CANNOT push total time past `LLM_TOTAL_BUDGET_SECONDS`**. Before every single LLM call and before every retry attempt, `remaining = deadline - time.time()` is evaluated. If `remaining <= 0`, the live attempt immediately raises `AIEngineError("time budget exceeded")` and routes to `fixture_fallback` with `fallback_reason="time budget exceeded"`.
- **File & Line References**:
  - [`ai/ai_engine.py:L797-802`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L797-L802): Deadline initialization in `analyze_and_branch()`: `deadline = start_time + self.total_budget`.
  - [`ai/ai_engine.py:L495-499`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L495-L499): Generic analyze call budget clamping: `remaining = deadline - time.time()`; if `remaining <= 0: raise AIEngineError("time budget exceeded")`; `call_timeout = min(self.timeout, remaining)`.
  - [`ai/ai_engine.py:L529-533`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L529-L533): World generation call budget clamping: identical `min(self.timeout, remaining)` calculation.
  - [`ai/ai_engine.py:L688-692`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L688-L692): Hardcoded retry loop budget enforcement: before each retry iteration, checks `remaining <= 0` and clamps `call_timeout = min(self.timeout, remaining)`.
  - [`ai/ai_engine.py:L831-837`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L831-L837) & [`L853-859`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L853-L859): Fallback interceptor assigning `fallback_reason = "time budget exceeded"`.
  - Verified by unit tests: [`ai/tests/test_ai_engine.py:L446-467`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L446-L467) (`test_total_time_budget_triggers_fallback`) and [`L640-652`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L640-L652) (`test_slow_client_never_exceeds_budget`).

---

### 3. Does the validator reject `update_set` keys that are not in the entity schema? Does it check value types?
- **Answer**: **YES to both**.
  - Unknown keys not in `field_types` raise a `ValueError`.
  - Primary key `id` cannot be modified (raises `ValueError`).
  - Reserved keys starting with `_` are rejected (raises `ValueError`).
  - Values must strictly match the declared field type via `check_value_matches_type()` (rejects null, type mismatches, and invalid ISO dates).
  - Operations `delete` and `flag` require `update_set` to be `null` / empty; `archive` and `update` require a non-empty `update_set`.
- **File & Line References**:
  - [`ai/plan_schema.py:L31-54`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L31-L54): `check_value_matches_type(val, ftype, field_name)` enforces strict primitive and ISO date types.
  - [`ai/plan_schema.py:L250-280`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L250-L280): `validate_operation_and_update_set()` validates key presence against `field_types`, disallows `id`, rejects prefix `_`, and validates value types.
  - [`ai/ai_engine.py:L383`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L383): Invoked during `build_branches()`.
  - Verified by unit tests: [`ai/tests/test_ai_engine.py:L782-804`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L782-L804) (`test_operation_and_update_set_rules`) and [`L806-832`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L806-L832) (`test_update_set_schema_key_and_type_validation`).

---

### 4. Does validation reject: unknown operation, unknown predicate op, unknown field, operator/type mismatch, depth > 4, nodes > 12, leftover `term_ref` in final branches, duplicate branch IDs?
- **Answer**: **YES, all are strictly rejected and validated**.
  - **Unknown operation**: Enforced by `AllowedOperation = Literal["delete", "archive", "update", "flag"]` in `BranchPlan` and `OperationTemplate` ([`ai/plan_schema.py:L23`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L23), [`L343`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L343), [`L358`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L358)).
  - **Unknown predicate op**: `parse_predicate()` raises `ValueError("Unknown or forbidden predicate operator: ...")` ([`ai/plan_schema.py:L163`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L163)).
  - **Unknown field**: `validate_predicate_schema()` raises `ValueError("Field '...' not defined in entity schema...")` ([`ai/plan_schema.py:L210-211`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L210-L211)).
  - **Operator/type mismatch**: `validate_predicate_schema()` restricts `older_than_days`/`newer_than_days` to `date` fields, validates value types via `check_value_matches_type()`, and limits relational operators (`<`, `<=`, `>`, `>=`) strictly to `int`, `float`, and `date` ([`ai/plan_schema.py:L214-230`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L214-L230)).
  - **Depth > 4 and Nodes > 12**: `validate_predicate_limits()` computes recursive AST metrics and raises `ValueError` if `depth > 4` or `nodes > 12` ([`ai/plan_schema.py:L183-190`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L183-L190)).
  - **Leftover `term_ref`**: `validate_predicate_schema(allow_term_ref=False)` raises `ValueError("Unresolved term_ref('...') found in executable branch plan")` ([`ai/plan_schema.py:L204-207`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L204-L207)).
  - **Duplicate branch IDs**: `build_branches()` allocates branch IDs sequentially from `["A", "B", "C", "D", "E", "F", "G", "H"]` ([`ai/ai_engine.py:L427-454`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L427-L454)) and deduplicates identical predicates using canonicalized JSON keys ([`ai/ai_engine.py:L442-446`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L442-L446)).
  - Verified by unit tests: [`ai/tests/test_ai_engine.py:L469-586`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L469-L586) and [`L860-880`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L860-L880).

---

### 5. How is the model ID configured? Is "qwen2.5:7b" hardcoded anywhere as a default?
- **Answer**: 
  - Model ID is configured via the environment variable `LLM_MODEL` (or explicit constructor argument `model`).
  - **`"qwen2.5:7b"` is NOT hardcoded as a default anywhere** in the codebase.
  - In live mode (`fixture_mode=False`), if `LLM_MODEL` is unset or empty, the engine raises a helpful configuration error: `"LLM_MODEL is unset in live mode. Run 'python -m ai.list_models' to discover available models and set LLM_MODEL in .env"`.
  - Fixture mode continues to function cleanly without any model configured.
- **File & Line References**:
  - [`ai/ai_engine.py:L202`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L202): `self.model = model or os.getenv("LLM_MODEL", "")`.
  - [`ai/ai_engine.py:L221-223`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L221-L223): Initialization-time validation raising `AIEngineError`.
  - [`ai/ai_engine.py:L489-491`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L489-L491): Execution guard in generic pipeline.
  - Verified by unit tests: [`ai/tests/test_ai_engine.py:L654-662`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L654-L662) (`test_missing_model_raises_config_error_in_live_mode`) and [`L664-672`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L664-L672) (`test_fixture_mode_works_without_model`).

---

### 6. What does "restore" do in `plan_schema`, prompts and fixtures?
- **Answer**:
  - In `plan_schema`: **`restore` has been completely removed** from `AllowedOperation` ([`ai/plan_schema.py:L23`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L23)). Passing `restore` fails schema validation.
  - In `prompts.py`: `GENERIC_ANALYZE_PROMPT` explicitly specifies `"restore" is strictly unsupported` ([`ai/prompts.py:L111`](file:///e:/Monkey/Code-Monkey/ai/prompts.py#L111)).
  - In `ai_engine.py`: `analyze_and_branch()` checks for restore instructions and immediately routes them to status `"unsupported"` with the honest explanation that there is no defined source data to restore from ([`ai/ai_engine.py:L804-818`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L804-L818)).
  - In `ai_fixtures.json`: The fixture for `"Restore the latest backup."` returns `status: "unsupported"`, empty branches, and the honest reason.
  - Verified by unit tests: [`ai/tests/test_ai_engine.py:L297-306`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L297-L306) and [`L768-780`](file:///e:/Monkey/Code-Monkey/ai/tests/test_ai_engine.py#L768-L780).

---

### 7. What shape does `generate_rewrite` accept for `outcomes`?
- **Answer**:
  - Accepts an optional dictionary (or `Any`, defaulting to `None`), representing the simulator's output for Competing Branches:  
    `Optional[Dict[str, Any]] = None`
  - When provided, it accepts a mapping of branch IDs to their simulation impact (e.g. `{"A": {"affected_count": 4, "affected_ids": ["U01", "U02"]}, "B": {"affected_count": 7}}`).
  - If omitted or falsy, `build_rewrite_messages()` falls back to a default description string: `"Different branches resulted in conflicting sets of affected records."`
- **File & Line References**:
  - [`ai/ai_engine.py:L912-917`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L912-L917): Method signature `generate_rewrite(self, instruction: str, ambiguous_terms: List[Dict[str, Any]], outcomes: Optional[Dict[str, Any]] = None)`.
  - [`ai/prompts.py:L299-305`](file:///e:/Monkey/Code-Monkey/ai/prompts.py#L299-L305): `build_rewrite_messages(..., outcomes: Any = None)` embedding outcomes into the LLM evidence payload.

---

### 8. Does model output ever reach `eval`, `exec`, `subprocess`, `os.system`, SQL strings or code built from strings? Confirm explicitly yes or no.
- **Answer**: **NO**.
  - Under no circumstances does model output reach dynamic code evaluators or system execution functions.
  - Model responses are strictly parsed into inert JSON objects via `json.loads` ([`ai/ai_engine.py:L268`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L268)) and validated through Pydantic schemas.
  - Downstream evaluation is performed exclusively by the deterministic reference interpreter `evaluate_predicate()` in [`ai/plan_schema.py:L382-460`](file:///e:/Monkey/Code-Monkey/ai/plan_schema.py#L382-L460) using sandboxed AST pattern-matching.

---

### 9. Are secrets kept out of logs and error messages?
- **Answer**: **YES**.
  - All exception messages and error logging pass through `sanitize_secret_text()` ([`ai/ai_engine.py:L93-102`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L93-L102)), which strips:
    1. The configured `api_key` (replaced with `[REDACTED_API_KEY]`)
    2. Bearer authentication tokens (`Bearer [REDACTED]`)
    3. Standard OpenAI-formatted API keys (`sk-[REDACTED]`)
  - The health check CLI runner (`python -m ai.ai_engine --check`) explicitly prints only the base URL and target model, never credentials ([`ai/ai_engine.py:L999-1004`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L999-L1004)).

---

## Prioritized List of Problems / Considerations Found

1. **[Low / Ergonomics] Module-Level Engine Instantiation**:
   - `_engine = AIEngine()` is instantiated at module top-level in [`ai/ai_engine.py:L974`](file:///e:/Monkey/Code-Monkey/ai/ai_engine.py#L974). If imported in an environment where `LLM_MODEL` is not set and `CHAOS_FIXTURE_MODE` is false, it raises an initialization error at import time rather than call time. (Tests currently mitigate this cleanly using an autouse environment fixture).
2. **[Low / Formalization] `outcomes` Type Hinting in `generate_rewrite`**:
   - `outcomes` is typed as `Optional[Dict[str, Any]]` or `Any` rather than a dedicated Pydantic model (`SimulationOutcomes`). Adding a formal schema when Person 3 finalizes simulator output will further tighten the contract.
3. **[Info / Design Principle] Hardcoded Fallback Scope**:
   - The fallback path (`_call_hardcoded_model`) is intentionally constrained to the `user_cleanup` domain with 3 fixed conditions (`inactive_90_days`, `created_90_days`, `inactive_or_unknown`), fulfilling its purpose as a reliable hackathon demo fallback.
