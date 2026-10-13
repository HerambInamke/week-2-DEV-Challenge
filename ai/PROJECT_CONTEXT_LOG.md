# Semantic Chaos Monkey — AI Project Context & Changelog

> **Tracking Rule**: This document is updated with every change to maintain complete chat context, architecture decisions, code explanations, and a chronological changelog.

---

## 1. Project Background & Core Mission

### The Problem
Operational and database instructions written in natural language (e.g., runbooks, agent skills, deployment checklists) can be grammatically correct English while being dangerously ambiguous:
> *"Delete old user records and restore the latest backup if necessary."*
- Operator A interprets "old" as accounts inactive for 90 days.
- Operator B interprets "old" as accounts created more than 90 days ago (deleting loyal active customers!).
- Operator C deletes accounts with missing activity dates.

### The Solution: Semantic Chaos Monkey
- **AI Discovers**: An open-weight LLM analyzes the instruction, identifies unstated assumptions, and translates competing interpretations into restricted declarative plans.
- **Simulator Verifies**: A deterministic Python simulator (owned by Person 3) executes each plan on identical synthetic data and computes exact row diffs and blast radius.
- **Ambiguity Exposed**: The system highlights the divergence, pinpoints the culprit assumptions, and produces a safe, clarified rewrite.
- **Safety Principle**: **The AI NEVER outputs executable code, SQL, or shell commands.** Its output is strictly validated declarative AST data.

---

## 2. Team Division & Ownership Boundaries

A 5-hour hackathon project with 4 team members:
- **Person 1 & 2**: Frontend (Next.js / UI dashboard, branch visualizers, diff view).
- **Person 3**: Backend orchestrator (FastAPI), deterministic sandbox simulator, divergence comparator.
- **Person 4 (This Codebase)**: **AI Owner**.
  - **Rule**: All code, schemas, tests, and configuration must stay **exclusively inside the `ai/` folder**.
  - No edits to `simulator.py`, `main.py`, `ambiguity.py`, or frontend files.

---

## 3. What Each File in `ai/` Does

| File | Purpose & Responsibilities |
| :--- | :--- |
| **`ai/plan_schema.py`** | **Safe Declarative Plan Language (AST)**.<br>- Strict operation allowlist: `delete`, `archive`, `update`, `flag`, `restore`.<br>- Strict field types: `string`, `int`, `float`, `bool`, `date`.<br>- Predicate AST: `compare`, `older_than_days`, `newer_than_days`, `is_null`, `not_null`, `in`, `and`, `or`, `not`, `term_ref`.<br>- Complexity limits: AST depth ≤ 4, node count ≤ 12.<br>- Schema cross-checks: fields must exist, operators must match field types, no unresolved `term_ref` in executable plans. |
| **`ai/ai_engine.py`** | **Core Hybrid AI Engine & Router**.<br>- **Generic Pipeline**: `ANALYZE` (LLM) → `WORLD` (LLM) → Deterministic Edge-Case Injection (Code) → Branch Permutations (Code, cap 8, dedup) → Plan validation.<br>- **Legacy Demo Fallback**: Hardcoded `user_cleanup` path preserved for 100% demo reliability.<br>- **Automatic Plan Converter**: Converts legacy A/B/C conditions into universal `plan_schema` format so Person 3 only needs one simulator engine.<br>- **Post-Simulation Rewrite**: `generate_rewrite()` clarifying criteria based on simulation outcomes.<br>- **Source Labeling**: Every response carries `"source": "live_generic" \| "live_hardcoded" \| "fixture_fallback"`.<br>- **Safety & Reliability**: Bounded retries, time budget (`LLM_TOTAL_BUDGET_SECONDS`), and demo switch (`CHAOS_FORCE_FALLBACK`). |
| **`ai/prompts.py`** | **Prompt Engineering & Injection Defense**.<br>- Delimits untrusted instructions inside `<instruction>...</instruction>` tags to prevent prompt injection.<br>- System prompts enforcing analyst persona (never an executor).<br>- Few-shot examples across multiple domains (`user_management`, `file_management`).<br>- Synthetic world generator prompt and rewrite prompt. |
| **`ai/fixtures/ai_fixtures.json`** | **Deterministic Local Fixtures**.<br>- Offline canned responses for zero-network demos and test runs.<br>- Covers: `"Delete old user records."`, `"Archive old log files."`, `"Remove inactive users."`, and out-of-scope `"Restore the latest backup if necessary."`. |
| **`ai/schemas.py`** | Legacy Pydantic schemas for the initial hardcoded contract. |
| **`ai/list_models.py`** | Utility script calling `GET {LLM_BASE_URL}/models` to inspect available open-weight models on DigitalOcean or Ollama. |
| **`ai/AI_ENGINE_README.md`** | Comprehensive developer guide, routing architecture diagram, configuration, and simulator integration instructions for Person 3. |
| **`ai/tests/test_ai_engine.py`** | **Pytest Test Suite (31 tests total: 29 offline passed, 2 live skipped)**.<br>- Unit tests mocking OpenAI client.<br>- Plan validation & AST boundary tests.<br>- Deduplication and branch builder tests.<br>- Source labeling and fallback routing tests.<br>- Prompt injection defense tests.<br>- Zero-network fixture mode tests. |
| **`ai/.env.example`** | Environment variable template (DigitalOcean inference primary, Ollama commented alternative). |
| **`ai/requirements.txt`** | Dependency declarations (`openai`, `pydantic`, `pytest`, `httpx`, `fastapi`, `uvicorn`, `python-dotenv`). |
| **`ai/CHANGELOG_CONTEXT.md`** | This file: Tracks complete context, chat decisions, and changes. |

---

## 4. API & Integration Contract for Person 3

### Primary Router: `analyze_and_branch(instruction, scenario="auto")`
```python
from ai.ai_engine import analyze_and_branch

result = analyze_and_branch("Archive old log files.")
```
**Output Shape:**
```json
{
  "status": "ok",
  "source": "live_generic",
  "fallback_reason": null,
  "domain": "file_management",
  "entity_schema": { "name": "log_file", "fields": [...] },
  "world": { "entity": "log_file", "today": "2026-10-13", "records": [...] },
  "branches": [
    {
      "id": "A",
      "title": "Created 30+ days ago",
      "assumption": "'Old' means created at least 30 days ago.",
      "operation": "archive",
      "update_set": {"is_archived": true},
      "where": {
        "op": "and",
        "args": [
          {"op": "compare", "field": "is_archived", "cmp": "eq", "value": false},
          {"op": "older_than_days", "field": "created_at", "days": 30}
        ]
      },
      "explanation": "..."
    }
  ],
  "suggested_rewrite": "Archive unarchived log files whose creation date is older than 30 days.",
  "model_info": {"model": "qwen2.5:7b", "mode": "live"},
  "warnings": []
}
```

### Legacy Entry Point: `generate_interpretations(instruction, scenario="user_cleanup")`
Preserved for 100% backward compatibility with the initial contract.

---

## 5. Chronological Changelog & Git History

### Entry 1: Initial AI Engine & Allowlist Gate
- Created `ai_engine.py`, `prompts.py`, `schemas.py`.
- Enforced hard allowlist: `type: "delete_users"`, conditions: `inactive_90_days`, `created_90_days`, `inactive_or_unknown`.
- Set up OpenAI SDK client targeting open-weight model (`qwen2.5:7b`).
- Built initial test suite (8 tests).

### Entry 2: Isolation into `ai/` Directory
- Restructured files so that Person 4 works exclusively within the `ai/` folder to prevent merge conflicts with team members owning `backend/` and `frontend/`.
- Committed and pushed to GitHub `main` branch.

### Entry 3: Hybrid Generic Pipeline & Declarative Plan Schema
- Added safe plan language (`ai/plan_schema.py`) supporting recursive predicate ASTs (`compare`, `older_than_days`, `newer_than_days`, `is_null`, `not_null`, `in`, `and`, `or`, `not`).
- Implemented AST complexity limits (depth ≤ 4, nodes ≤ 12) and type cross-checks.
- Built 4-stage generic pipeline:
  1. **Analyze**: Extracts entity schema, ambiguous terms, and operational templates with `term_ref`.
  2. **World**: LLM generates fictional records; code deterministically injects edge cases (null date, boundary record, no-match record).
  3. **Branches**: Pure code combines meanings into branches (cap 8, dedup identical predicates, assign IDs A..H).
  4. **Rewrite**: Post-simulation rewrite generation (`generate_rewrite`).
- Implemented automatic legacy-to-plan bridge (`convert_hardcoded_to_plan`).
- Implemented labeled router (`analyze_and_branch`) with provenance tags (`"live_generic"`, `"live_hardcoded"`, `"fixture_fallback"`).
- Added demo switches: `CHAOS_FORCE_FALLBACK=true` and time budget `LLM_TOTAL_BUDGET_SECONDS`.
- Expanded test suite to 31 tests (29 passed offline, 2 live skipped).
- Committed and pushed commit `a4f60b8` to GitHub.

### Entry 4: Ongoing Context Tracking Protocol
- Created `ai/PROJECT_CONTEXT_LOG.md` to permanently capture all chat history, context, and code explanations.

### Entry 5: Part 1 Audit Completed
- Conducted deep code audit across `ai/ai_engine.py`, `ai/plan_schema.py`, `ai/prompts.py`, `ai/tests/test_ai_engine.py`, and `ai/fixtures/ai_fixtures.json`.
- Produced comprehensive audit artifact at `ai/docs/AUDIT.md` covering all 9 specific architectural, security, and schema validation questions with exact file and line references.
- Verified test suite status: `29 passed, 2 skipped in 1.06s` (100% offline pass rate).

### Entry 6: Part 2 Config and Reliability Improvements
- **Fixed World Date**:
  - Introduced `WORLD_TODAY` constant defaulting to `"2026-01-01"` overridable via `CHAOS_WORLD_TODAY`.
  - Zero `datetime.now()` in pipeline.
  - Aligned edge-case boundary thresholds in `inject_world_edge_cases()` and `convert_hardcoded_to_plan()` to exact offsets from `WORLD_TODAY` (e.g. 90-day threshold is `"2025-10-03"`).
  - Updated all fixture dates in `ai/fixtures/ai_fixtures.json` to be consistent with `"2026-01-01"`.
- **Time Budget & Cumulative Deadlines**:
  - Defaults updated: `LLM_TOTAL_BUDGET_SECONDS=60.0`, `LLM_TIMEOUT_SECONDS=30.0`.
  - In `analyze_and_branch`, sets `deadline = start + self.total_budget`.
  - Computes `remaining = deadline - now` prior to every LLM call; aborts live pipeline and routes to fallback with `fallback_reason="time budget exceeded"` if `remaining <= 0`.
  - Clamps each call's timeout to `min(self.timeout, remaining)`.
  - Added additive field `"timings_ms"` with per-stage latencies (`analyze`, `world`, `branches`, `total`).
- **Model Configuration & CLI Check**:
  - Removed hardcoded default model ID `"qwen2.5:7b"`.
  - If `LLM_MODEL` is unset in live mode, raises clear config error directing user to run `python -m ai.list_models`.
  - Fixture mode continues to work with no model configured.
  - Implemented `python -m ai.ai_engine --check` health check runner (prints base URL, checks GET /models, executes ping chat completion, measures latency, provides human-readable failure messages for 401, 403, 404, 429, timeout, connection errors).
  - Updated `ai/.env.example` with DigitalOcean primary, Ollama commented out, model placeholder, and all timing/budget parameters.
- **Housekeeping**:
  - Updated `ai/.gitignore` to ignore `.env`, `__pycache__`, `.pytest_cache`, and `eval/results/`, `ai/eval/results/`.
- **Testing**:
  - Added 6 new unit tests for mocked system date invariance, budget-bounded execution, model config validation, fixture mode without model, timings_ms validation, and `--check` CLI functionality.
  - Total test suite: 35 passed, 2 skipped (100% pass rate).

### Entry 7: Part 3 Tightened Plan Language (Simulator Contract)
- **Operation Rules (3.1)**:
  - Removed `"restore"` from `AllowedOperation` (`delete`, `archive`, `update`, `flag`). Instructions requesting restore return status `"unsupported"` with honest reason.
  - `delete`: removes matched records; `update_set` must be null.
  - `archive` and `update`: require non-empty `update_set`.
  - `flag`: sets reserved `_flagged: true`; `update_set` must be null.
  - Reserved fields starting with `_` are forbidden in `EntitySchema` and `update_set`.
  - Primary `id` field cannot be modified in `update_set`.
- **Definition of Affected (3.2)**:
  - `affected_ids`: records matched by `where`, in original record order, whether or not a value changed.
  - `affected_count = len(affected_ids)`.
- **Null Semantics / Two-Valued Logic (3.3)**:
  - `is_null` is true iff None or missing; `not_null` is opposite.
  - On null or missing values, all other leaf predicates (`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `older_than_days`, `newer_than_days`) evaluate to `False`.
  - Boolean `not(leaf)` over null evaluates to `True`.
  - Validator issues warning when `not` wraps a leaf over a nullable field.
- **Date & Comparison Semantics (3.4 & 3.5)**:
  - Calendar days against `world.today`: `older_than_days N` is `(today - val).days >= N`, `newer_than_days N` is `(today - val).days < N`.
  - Future-dated values have negative age: `older_than` is False, `newer_than` is True.
  - `eq` and `ne` strictly compare same-typed primitives. Relational comparisons (`lt`, `lte`, `gt`, `gte`) only allowed for `int`, `float`, and `date`. `string` and `bool` support only `eq`, `ne`, and `in`.
- **Validator Hardening (3.6)**:
  - `in` predicate capped at max 20 items with primitive type checking.
  - `compare` value type matches declared field type.
  - Built simulator reference interpreter `evaluate_predicate` and `compute_affected` in `ai/plan_schema.py`.
- **Local Environment Configuration**:
  - Created uncommitted `ai/.env` configured with Ollama endpoint and user-provided API key.
- **Testing**:
  - Expanded test suite from 37 to 47 tests (45 passed, 2 skipped in 1.00s).

### Entry 8: Model Configuration Update
- Updated `ai/.env` to configure `LLM_MODEL=gpt-oss:20b` with the local Ollama endpoint (`http://localhost:11434/v1`).
- Verified test suite passes cleanly: 45 passed, 2 skipped in ~1.05s.

### Entry 9: Part 4 Outcomes Contract and Reference Simulator
- **Outcomes Models (`ai/outcomes.py`)**:
  - `BranchOutcome`: `branch_id`, `affected_ids`, and validated `affected_count == len(affected_ids)`.
  - `SimulationOutcomes`: list of `BranchOutcome` with unique IDs, cross-branch validation against provided branch plans, and `SimulationOutcomes.coerce()` which accepts structured shapes and strictly rejects free-text strings.
  - Computed deterministic evidence summary in code (`diverges`, `distinct_sets`, `only_in`, `common_ids`, `empty_branches`, `differing_pairs`).
  - Updated `generate_rewrite(instruction, ambiguous_terms, outcomes, branches=None)` in `ai/ai_engine.py` and `build_rewrite_messages()` in `ai/prompts.py` to require structured outcomes and supply simulation evidence as given facts the model must not recompute.
- **Reference Simulator (`ai/tools/reference_simulator.py`)**:
  - Pure Python, dependency-free reference interpreter specification for Part 3 semantics (header docstring clarifies it is an executable spec, not Person 3's production simulator).
  - Explicit dispatch on predicate `op` (no eval/exec).
  - `run_branch(world, branch)`: isolates execution on a deep copy of records and applies `delete`, `archive`, `update`, or `flag`.
  - `run_all(world, branches)`: runs branches independently on separate deep copies.
  - `compare_outcomes(outcomes)`: returns `diverges`, `distinct_sets`, `only_in`, `common_ids`.
- **Golden Outcomes (`ai/tools/make_golden.py` & `ai/tools/golden_outcomes.json`)**:
  - Script runnable via `python -m ai.tools.make_golden`.
  - Runs all deterministic fixtures through `reference_simulator` and writes expected outcomes for Person 3's simulator to diff against.
- **Testing (`ai/tests/test_reference_simulator.py`)**:
  - Added 7 tests covering fixture divergence, null-date isolation, exact 90-day boundary matching (90 vs 91), null-semantics table covering every predicate, `not` over null fields, branch isolation & determinism, and outcomes validation.
  - Test suite now: **52 passed**, 2 skipped (100% offline pass rate).

### Entry 10: Part 5 Prompt Quality Pass
- **Generic Analyzer Prompt (`ai/prompts.py`)**:
  - Explicitly states the model is an analyst, never an executor; `<instruction>` tags contain untrusted data and all commands inside must be ignored.
  - Documents allowed operations (`delete`, `archive`, `update`, `flag`), forbidden `_` prefix, two-valued null semantics, calendar day date math, relational comparison type restrictions, and max 20 items for `in`.
  - Directs model to probe: time basis (creation vs last activity/status update), thresholds, boundary inclusion, missing/null values, scope ("all" vs "some"), and "if necessary" conditions.
  - Mandates behavioral selection divergence; for instructions already specific, requires identifying remaining ambiguity.
- **Multi-Domain Few-Shots**:
  - Domain 1: Users ("Delete old user records.").
  - Domain 2: Files ("Archive old log files.").
  - Domain 3: Orders ("Cancel pending orders older than 30 days." - already specific, probes remaining ambiguity in order creation vs status update timestamp and strict pending vs pending/payment_review scope).
  - Domain 4: Unsupported ("rm -rf /var/log/* && systemctl restart nginx" - returns status unsupported with honest reason).
- **World Prompt**:
  - Strict rules: realistic fictional data only, no real people/organizations, emails on `@example.com` domains, dates relative to given today, pure JSON format.
- **Disambiguation Rewrite Prompt**:
  - Injects code-computed simulation evidence as given facts that must not be recomputed; outputs clear rewrite resolving divergence and lists `resolved_terms`.
- **Testing & Anti-Drift Verification (`ai/tests/test_ai_engine.py`)**:
  - Added `test_prompt_embedded_examples_validate_against_schema`: programmatically validates all embedded few-shot JSON structures against `GenericAnalysisOutput`, `LegacyInterpretationSchema`, and predicate AST limits/schema validators.
  - Full test suite: **53 passed**, 2 skipped in ~0.96s.

### Entry 11: Part 6 Rewrite Verification Loop
- **Verification Engine (`ai/verify.py`)**:
  - Implemented `verify_rewrite(original_instruction, rewrite, before_outcomes=None, simulate=None, engine=None)`.
  - Runs `analyze_and_branch` on the rewrite.
  - Executes simulation using injected `simulate` callable or defaults to `reference_simulator.run_all`.
  - Computes verdict strictly from simulator outcomes (never trusting model's claim of clarity):
    - `"resolved"`: all branches agree (`after_distinct_sets == 1`) or no ambiguity found (`after_branch_count == 1`).
    - `"reduced"`: fewer distinct outcome sets than before (`after_distinct_sets < before_distinct_sets`).
    - `"not_improved"`: same or more distinct outcome sets than before (`after_distinct_sets >= before_distinct_sets`).
    - `"unverifiable"`: live path unavailable, analysis failed, or unsupported.
  - Labels which simulator was used (`"simulator_used": simulator_label`).
- **Testing (`ai/tests/test_verify.py`)**:
  - Created 7 mocked unit tests covering all 4 verdicts (`resolved` via agreement and single branch, `reduced`, `not_improved`, `unverifiable`), injected simulator callable attribution, and verification that model claims are never trusted over simulator outcomes.
  - Test suite now: **60 passed**, 2 skipped (100% offline pass rate).

### Entry 12: Part 7 Evaluation Harness
- **Evaluation Benchmark (`ai/eval/instructions.json`)**:
  - Created 20 labeled benchmark instructions with metadata (`id`, `text`, `domain_hint`, `expected`, `notes`).
  - Covers supported ambiguous (8), already specific (2), vague (2), unsupported (4), adversarial prompt injections (2), multilingual (1), and empty/whitespace (1).
- **Harness Runner (`ai/eval/run_eval.py`)**:
  - Implemented evaluation runner with flags `--mode` (live or fixture), `--limit`, and `--out`.
  - Executes `analyze_and_branch`, runs reference simulator on supported results, and triggers `verify_rewrite` on divergent results.
  - Generates machine-readable `results.json` and human-readable `report.md`.
  - Reports all required metrics: first-attempt validity, success after retries, source distribution, average branches, divergence rate, correct unsupported rate, false-support rate (0%), injection resistance violations (0%), rewrite verdict distribution, latencies (p50, max), and failures list.
- **Testing & Verification (`ai/tests/test_eval_metrics.py`)**:
  - Unit-tested metrics arithmetic on a deterministic synthetic result set.
  - Verified harness in `--mode fixture` over all 20 instructions: 100% schema validity, 0% false-support rate, 0 injection violations.
  - Full test suite: **61 passed**, 2 skipped in ~1.05s.

### Entry 13: Endpoint Update to Ollama Cloud
- Updated `ai/.env` to configure `LLM_BASE_URL=https://ollama.com/v1`.
- Ran `python -m ai.ai_engine --check`: confirmed connection, model `gpt-oss:20b` discovered, test chat completion succeeded with latency 705.92ms (`PASS`).
- Ran `python -m ai.list_models`: discovered 18 models available on the endpoint.
- Executed end-to-end live analysis on "Delete old user records.": succeeded with `status: ok`, `source: live_generic`, and 3 generated branches (`A: old: Created 90+ days ago`, `B: old: Inactive 90+ days`, `C: old: Inactive 90+ days or missing activity date`).
- Full test suite: **61 passed**, 2 skipped in ~1.11s.
