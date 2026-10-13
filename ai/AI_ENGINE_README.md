# Semantic Chaos Monkey — AI Engine (Person 4 Documentation)

This module provides the hybrid open-weight AI interpretation and ambiguity analysis engine for Semantic Chaos Monkey.

**Core Principle**: *The AI discovers alternative meanings and structures; the simulator verifies their real-world consequences.*  
**Safety Principle**: The AI never produces code, regex, shell, or SQL. It produces strictly validated, declarative data models. A fixed Python engine interprets it.

## Local HTTP API

Install the packages from `ai/requirements.txt`, then launch the API at the repository root:

```bash
python -m pip install -r ai/requirements.txt
python -m uvicorn ai.api:app --reload --port 8000
```

The React development server proxies `/api` to this service. `GET /api/healthz` is a
readiness check. `POST /api/analyze` accepts `{"instruction":"Delete old user records."}`;
it returns validated interpretation plans, deterministic synthetic outcomes, and a
comparison summary. Unsupported and incomplete analyses are returned as such and
must not be presented by the client as successful runs.

Set `SCM_CORS_ORIGINS` to a comma-separated allowlist of frontend origins when the
API is deployed separately. Set `SCM_API_TARGET` for the Vite development proxy,
or `VITE_API_BASE_URL` for a deployed frontend. Configure model credentials only
in the backend's `ai/.env`; never expose them through `VITE_*` variables.

---

## 1. Hybrid Architecture & Routing Diagram

The engine features a **hybrid pipeline** where a new generic pipeline handles arbitrary operational instructions, with the reliable hardcoded user-cleanup path preserved as an automatic fallback.

```
+-------------------------------------------------------------+
|               User Instruction / API Request                |
+-------------------------------------------------------------+
                              |
       +----------------------+----------------------+
       | Is CHAOS_FORCE_FALLBACK or no API key set?  |
       +----------------------+----------------------+
             YES /                      \ NO
                 v                       v
      +--------------------+   +------------------------------------+
      |  fixture_fallback  |   | Step 1: Generic Pipeline (Live DO) |
      |  (Zero Network)    |   | - LLM: Entity Schema + Meanings    |
      +--------------------+   | - Code: Injects World Edge Cases   |
                               | - Code: Combines & Dedupes Branches|
                               +-----------------+------------------+
                                                 |
                                     Success? ---+--- Failure / Timeout
                                        |                   |
                                        v                   v
                               +----------------+   +-------------------------------+
                               |  live_generic  |   | Is instruction user cleanup?  |
                               +----------------+   +---------------+---------------+
                                                                    |
                                                          YES /           \ NO
                                                              v             v
                                                    +----------------+  +--------------------+
                                                    | live_hardcoded |  |  fixture_fallback  |
                                                    | (Demo Fallback)|  |  or "unsupported"  |
                                                    +----------------+  +--------------------+
```

---

## 2. Source Labeling Contract

Every response from `analyze_and_branch()` or `generate_interpretations()` carries explicit provenance:

| Source Value | Meaning | UI Badge |
| :--- | :--- | :--- |
| `"live_generic"` | Generic pipeline succeeded with live open-weight model | `Live (Generic)` |
| `"live_hardcoded"` | Live model ran through the reliable hardcoded demo fallback | `Live (Hardcoded)` |
| `"fixture_fallback"` | Served deterministically from verified local fixtures (no network call) | `Fixture (Fallback)` |

In addition, each response includes:
- `"model_info"`: `{"model": str, "mode": "live" | "fixture"}`
- `"fallback_reason"`: `str | null` (e.g., `"Generic pipeline failed (timeout)"` or `null` when live generic succeeds)

---

## 3. Public API Contract for Person 3

### Primary Entry Point: `analyze_and_branch`
```python
from ai.ai_engine import analyze_and_branch

result = analyze_and_branch("Delete old user records.", scenario="auto")
```

### Full JSON Output Structure (`live_generic` / Universal Plan):
```json
{
  "status": "ok",
  "source": "live_generic",
  "fallback_reason": null,
  "domain": "user_management",
  "entity_schema": {
    "name": "user",
    "fields": [
      {"name": "id", "type": "string", "description": "Unique user ID"},
      {"name": "email", "type": "string", "description": "Email address"},
      {"name": "created_at", "type": "date", "description": "Creation timestamp"},
      {"name": "last_active_at", "type": "date", "description": "Last active timestamp"},
      {"name": "status", "type": "string", "description": "Account status"}
    ]
  },
  "world": {
    "entity": "user",
    "today": "2026-10-13",
    "records": [
      {"id": "U01", "email": "alice@corp.com", "created_at": "2025-01-10", "last_active_at": "2026-10-10", "status": "active"},
      {"id": "U02", "email": "bob@dormant.com", "created_at": "2024-05-01", "last_active_at": "2026-05-01", "status": "dormant"},
      {"id": "INJ-NULL-01", "email": "null@edge.com", "created_at": "2026-06-15", "last_active_at": null, "status": "pending", "_injected": true},
      {"id": "INJ-BOUND-90", "email": "bound@edge.com", "created_at": "2026-07-15", "last_active_at": "2026-07-15", "status": "active", "_injected": true},
      {"id": "INJ-NOMATCH-01", "email": "fresh@active.com", "created_at": "2026-10-13", "last_active_at": "2026-10-13", "status": "active", "_injected": true}
    ]
  },
  "branches": [
    {
      "id": "A",
      "title": "old: Inactive for 90+ days",
      "assumption": "'Old' means no activity recorded in the last 90 days.",
      "operation": "delete",
      "update_set": null,
      "where": {"op": "older_than_days", "field": "last_active_at", "days": 90},
      "chosen_meanings": {"old": "inactive_90"},
      "explanation": "Branch A tests the assumption that old refers to inactivity."
    },
    {
      "id": "B",
      "title": "old: Account created 90+ days ago",
      "assumption": "'Old' means account created more than 90 days ago.",
      "operation": "delete",
      "update_set": null,
      "where": {"op": "older_than_days", "field": "created_at", "days": 90},
      "chosen_meanings": {"old": "created_90"},
      "explanation": "Branch B tests the assumption that old refers to creation date."
    },
    {
      "id": "C",
      "title": "old: Inactive or missing activity date",
      "assumption": "Accounts lacking activity dates are assumed to be inactive.",
      "operation": "delete",
      "update_set": null,
      "where": {
        "op": "or",
        "args": [
          {"op": "older_than_days", "field": "last_active_at", "days": 90},
          {"op": "is_null", "field": "last_active_at"}
        ]
      },
      "chosen_meanings": {"old": "inactive_or_unknown"},
      "explanation": "Branch C tests treating missing telemetry as inactive."
    }
  ],
  "ambiguous_terms": [
    {
      "term": "old",
      "description": "Unspecified age basis: inactivity vs creation date and null handling."
    }
  ],
  "suggested_rewrite": "Delete user accounts whose last activity was more than 90 days ago. Flag accounts with null activity dates for audit.",
  "model_info": {
    "model": "qwen2.5:7b",
    "mode": "live"
  },
  "warnings": []
}
```

### Legacy Backward-Compatible Entry Point: `generate_interpretations`
Preserved for zero-breakage backward compatibility:
```python
from ai.ai_engine import generate_interpretations

res = generate_interpretations("Delete old user records.", scenario="user_cleanup")
```

### Disambiguated Rewrite Generator: `generate_rewrite`
Call after simulation to produce an unambiguous rewrite with evidence:
```python
from ai.ai_engine import generate_rewrite

rewrite_res = generate_rewrite(
    instruction="Delete old user records.",
    ambiguous_terms=[{"term": "old"}],
    outcomes={"divergence": "Branch A deleted 2 records; Branch B deleted 5 records"}
)
```

---

## 4. WHAT PERSON 3 MUST IMPLEMENT (Simulator Semantics)

Person 3's simulator takes `world` and iterates over each `BranchPlan` in `branches`. To ensure deterministic verification, follow these rules:

1. **Deep Copy per Branch**:  
   Always clone `world.records` before executing each branch so execution branches remain strictly isolated.
2. **Date Math against `world.today`**:  
   Do not use system `datetime.now()`. Use `world.today` (e.g., `"2026-10-13"`).
3. **`older_than_days N` Semantics**:  
   A record matches if `(world.today - record[field]).days >= N`.
4. **`newer_than_days N` Semantics**:  
   A record matches if `(world.today - record[field]).days < N`.
5. **Null Handling**:  
   If `record[field] is None`:
   - `is_null` evaluates to `True`.
   - `not_null` evaluates to `False`.
   - `older_than_days`, `newer_than_days`, and numeric comparisons evaluate to `False` (never match nulls).
6. **Per-Operation Behavior**:
   - `"delete"`: Remove matching records from the active record set.
   - `"archive"`: Apply `update_set` (e.g. `{"is_archived": True}`).
   - `"update"`: Update fields specified in `update_set`.
   - `"flag"`: Mark flagged records.
   - `"restore"`: Mark restored records.

*Note: You do not need two separate simulator engines! Our AI engine automatically converts hardcoded fallback results into the universal `world` + `branches` format so you only need ONE simulator interpreter.*

---

## 5. Configuration & Demo Switches

### `.env` Setup
```bash
# DigitalOcean Inference Endpoint
LLM_BASE_URL=https://inference.do-ai.run/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=your_digitalocean_model_access_key
LLM_TIMEOUT_SECONDS=60
LLM_TOTAL_BUDGET_SECONDS=45

# Demo Switch: Force Fixture Fallback (Demonstrates offline resiliency)
CHAOS_FORCE_FALLBACK=false

# Offline Fixture Mode (No network calls)
CHAOS_FIXTURE_MODE=false
```

---

## 6. Run & Test Commands

### 1. Manual CLI Test:
```bash
python -m ai.ai_engine "Delete old user records."
python -m ai.ai_engine "Archive old log files."
```

### 2. Run Test Suite:
```bash
python -m pytest ai/tests/test_ai_engine.py -v
```

### 3. Run Optional Live Test:
```bash
$env:RUN_LIVE_TESTS="1"
$env:LLM_API_KEY="<your-key>"
python -m pytest ai/tests/test_ai_engine.py -k test_live_generic_instructions -v
```
