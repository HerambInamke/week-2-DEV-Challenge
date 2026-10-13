from typing import Any, Dict, List, Optional
from backend2.schemas import (
    Action,
    CandidateAmbiguity,
    CandidateInterpretation,
)

BENCHMARK_FIXTURES: Dict[str, Dict[str, Any]] = {
    "delete old user records.": {
        "status": "ok",
        "interpretations": [
            CandidateInterpretation(
                id="A",
                title="Inactive for 90 days",
                assumption="'Old' means inactive for at least 90 days based on last recorded activity.",
                action=Action(type="delete_users", condition="inactive_90_days"),
                explanation="Interprets 'old' as dormant accounts based on last recorded activity timestamp.",
                risk_level="low",
            ),
            CandidateInterpretation(
                id="B",
                title="Account created 90+ days ago",
                assumption="'Old' means created more than 90 days ago, regardless of recent activity.",
                action=Action(type="delete_users", condition="created_90_days"),
                explanation="Interprets 'old' strictly by account creation date, endangering active long-term customers.",
                risk_level="critical",
            ),
            CandidateInterpretation(
                id="C",
                title="Inactive or missing activity dates",
                assumption="Accounts lacking an activity timestamp are assumed to be old and dormant.",
                action=Action(type="delete_users", condition="inactive_or_unknown"),
                explanation="Treats missing telemetry as inactivity without verifying account status.",
                risk_level="high",
            ),
        ],
        "candidate_ambiguities": [
            CandidateAmbiguity(
                term="old",
                description="Could refer to elapsed time since creation or elapsed time since last active login.",
                interpretation_ids=["A", "B"],
                impact="Active long-term users are deleted if interpreted as account age.",
            ),
            CandidateAmbiguity(
                term="missing activity dates",
                description="Does not specify whether accounts with null activity dates are preserved or purged.",
                interpretation_ids=["A", "C"],
                impact="Newly created users without initial activity logs are prematurely purged.",
            ),
        ],
        "suggested_rewrite": "Delete user accounts inactive for at least 90 days based on last recorded activity. Preserve accounts with missing activity dates and flag them for audit.",
    },
    "remove inactive users.": {
        "status": "ok",
        "interpretations": [
            CandidateInterpretation(
                id="A",
                title="Inactive for at least 90 days",
                assumption="Inactivity requires at least 90 days since last recorded activity timestamp.",
                action=Action(type="delete_users", condition="inactive_90_days"),
                explanation="Applies standard 90-day inactivity threshold based on last_active_at.",
                risk_level="low",
            ),
            CandidateInterpretation(
                id="B",
                title="Inactive based on creation age",
                assumption="Accounts created over 90 days ago without activity checks are considered inactive.",
                action=Action(type="delete_users", condition="created_90_days"),
                explanation="Assumes account creation age over 90 days implies dormancy.",
                risk_level="critical",
            ),
            CandidateInterpretation(
                id="C",
                title="Inactive or missing activity telemetry",
                assumption="Accounts lacking an activity timestamp are treated as inactive and deleted.",
                action=Action(type="delete_users", condition="inactive_or_unknown"),
                explanation="Purges users where last_active_at is null without manual verification.",
                risk_level="high",
            ),
        ],
        "candidate_ambiguities": [
            CandidateAmbiguity(
                term="inactivity threshold",
                description="Does not define whether inactivity is measured from creation or last login.",
                interpretation_ids=["A", "B"],
                impact="Active accounts are removed if creation age is substituted for login telemetry.",
            ),
            CandidateAmbiguity(
                term="missing telemetry",
                description="Fails to define how accounts with null activity timestamps should be handled.",
                interpretation_ids=["A", "C"],
                impact="Unverified newer accounts may be destroyed.",
            ),
        ],
        "suggested_rewrite": "Delete user accounts with recorded inactivity exceeding 90 days. Flag accounts with null activity dates for audit without deleting.",
    },
}

UNSUPPORTED_KEYWORDS = [
    "backup",
    "restore",
    "drop table",
    "drop database",
    "restart",
    "deploy",
    "server",
    "payment",
    "rm -rf",
]


def normalize_instruction(instruction: str) -> str:
    """Normalizes natural language instruction for fixture lookup."""
    lowered = instruction.lower().strip()
    if not lowered.endswith("."):
        return lowered + "."
    return lowered


def get_fixture_analysis(instruction: str, scenario: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves deterministic interpretations and ambiguities for known instructions,
    or returns an unsupported payload for out-of-scope requests.
    """
    if scenario != "user_cleanup":
        return {
            "status": "unsupported",
            "reason": f"Scenario '{scenario}' is unsupported. Only 'user_cleanup' is supported for MVP simulation.",
            "interpretations": [],
            "candidate_ambiguities": [],
            "suggested_rewrite": "",
        }

    lowered = instruction.lower().strip()
    for kw in UNSUPPORTED_KEYWORDS:
        if kw in lowered:
            return {
                "status": "unsupported",
                "reason": f"Instruction contains unsupported operation ('{kw}'). Only user cleanup ('delete_users') is permitted.",
                "interpretations": [],
                "candidate_ambiguities": [],
                "suggested_rewrite": "",
            }

    normalized = normalize_instruction(instruction)
    if normalized in BENCHMARK_FIXTURES:
        return BENCHMARK_FIXTURES[normalized]

    # For user cleanup instructions without an exact match, provide the canonical benchmark
    user_cleanup_indicators = ["user", "account", "record", "delete", "remove", "clean", "purge", "inactive", "old"]
    if any(ind in lowered for ind in user_cleanup_indicators):
        # Default to canonical user cleanup fixture
        return BENCHMARK_FIXTURES["delete old user records."]

    return {
        "status": "unsupported",
        "reason": f"Instruction '{instruction}' is outside the user cleanup scope supported by the MVP simulator.",
        "interpretations": [],
        "candidate_ambiguities": [],
        "suggested_rewrite": "",
    }
