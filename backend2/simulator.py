import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend2.schemas import (
    Action,
    BlastRadius,
    BranchSimulationResult,
    CandidateInterpretation,
    UserRecord,
)

INACTIVITY_THRESHOLD_DAYS = 90
CREATION_THRESHOLD_DAYS = 90
SUPPORTED_ACTION_TYPE = "delete_users"
SUPPORTED_CONDITIONS = {
    "inactive_90_days",
    "created_90_days",
    "inactive_or_unknown",
}

REFERENCE_DATETIME = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

ENTERPRISE_PARTNERS = [
    ("StripeScale", 24000),
    ("Acme Global", 18500),
    ("LinearHQ", 12000),
    ("Datadogma", 15000),
    ("ShopifyMax", 22000),
    ("SnowflakeHub", 20000),
    ("RetoolCore", 9500),
    ("SegmentIQ", 11000),
    ("NotionWorks", 8000),
    ("FigmaSync", 14000),
    ("CloudFlareHQ", 16500),
    ("VercelEdge", 13000),
    ("HashiVault", 10500),
    ("MongoDBGrid", 12500),
    ("PagerAlert", 7500),
    ("RampFinance", 19000),
    ("BrexVault", 17500),
    ("LoomVideo", 6500),
    ("SentryStack", 9000),
    ("PostmanAPI", 8500),
]

PRO_PARTNERS = [
    "TechFlow", "DevPulse", "ByteCraft", "CodeCraft", "WebForge",
    "AppLaunch", "CloudNest", "ScaleGrid", "DataPipe", "SyncWave",
    "FlowLogic", "PixelCraft", "NextLayer", "BitSphere", "QueryFlow",
]


class SimulatorError(Exception):
    """Base error for simulation execution."""
    pass


class UnsupportedActionError(SimulatorError):
    """Raised when an unapproved action type is submitted to the simulator."""
    pass


class UnsupportedConditionError(SimulatorError):
    """Raised when an unapproved condition is submitted to the simulator."""
    pass


def _create_user(
    id: str,
    name: str,
    email: str,
    company: str,
    tier: str,
    mrr: int,
    created_days_ago: int,
    inactivity_days: Optional[int],
    is_active: bool,
) -> UserRecord:
    """Creates a user record with timestamps derived strictly from the anchor datetime."""
    created_dt = REFERENCE_DATETIME - timedelta(days=created_days_ago)
    created_at = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if inactivity_days is not None:
        last_active_dt = REFERENCE_DATETIME - timedelta(days=inactivity_days)
        last_active_at = last_active_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        last_active_at = None

    return UserRecord(
        id=id,
        name=name,
        email=email,
        company=company,
        tier=tier,
        mrr=mrr,
        created_days_ago=created_days_ago,
        inactivity_days=inactivity_days,
        is_active=is_active,
        created_at=created_at,
        last_active_at=last_active_at,
    )


def _generate_500_records() -> List[UserRecord]:
    """
    Deterministically generates 500 enterprise records representing 5 realistic SaaS archetypes:
    - 140 Long-term active enterprise/pro accounts (Branch B wipes them!)
    - 120 True dormant ghost free accounts (Safe to delete)
    - 40 New onboarding accounts with null activity telemetry (Branch C wipes them!)
    - 120 Active new growing accounts
    - 80 Moderately inactive accounts (<90 days inactive)
    """
    records: List[UserRecord] = []

    # Archetype 1: 140 Long-term active accounts (created >90 days ago, active <=25 days ago)
    for i in range(140):
        uid = f"usr_{len(records) + 1:03d}"
        created_days = 100 + ((i * 4) % 620)
        inactivity_days = 1 + (i % 20)
        if i < 40:
            partner, mrr_val = ENTERPRISE_PARTNERS[i % len(ENTERPRISE_PARTNERS)]
            tier = "enterprise"
            company = partner
            mrr = mrr_val
        else:
            tier = "pro"
            company = PRO_PARTNERS[i % len(PRO_PARTNERS)]
            mrr = 299 + ((i % 5) * 50)

        records.append(_create_user(
            id=uid,
            name=f"Customer {uid}",
            email=f"{uid}@{company.lower().replace(' ', '')}.com",
            company=company,
            tier=tier,
            mrr=mrr,
            created_days_ago=created_days,
            inactivity_days=inactivity_days,
            is_active=True,
        ))

    # Archetype 2: 120 True dormant accounts (created >90 days ago, inactive >=95 days ago)
    for i in range(120):
        uid = f"usr_{len(records) + 1:03d}"
        created_days = 200 + (i * 2)
        inactivity_days = 95 + i
        records.append(_create_user(
            id=uid,
            name=f"Dormant User {uid}",
            email=f"{uid}@dormant-test.org",
            company=f"Dormant Corp {i + 1}",
            tier="free",
            mrr=0,
            created_days_ago=created_days,
            inactivity_days=inactivity_days,
            is_active=False,
        ))

    # Archetype 3: 40 New onboarding accounts with null telemetry (created <90 days ago)
    for i in range(40):
        uid = f"usr_{len(records) + 1:03d}"
        created_days = 5 + ((i * 2) % 55)
        if i < 10:
            partner, mrr_val = ENTERPRISE_PARTNERS[(i + 5) % len(ENTERPRISE_PARTNERS)]
            tier = "enterprise"
            company = f"{partner} (Pilot)"
            mrr = mrr_val // 2
        else:
            tier = "pro"
            company = f"Onboarding Pro {i + 1}"
            mrr = 399

        records.append(_create_user(
            id=uid,
            name=f"Onboarding Lead {uid}",
            email=f"{uid}@pilot-enterprise.io",
            company=company,
            tier=tier,
            mrr=mrr,
            created_days_ago=created_days,
            inactivity_days=None,
            is_active=True,
        ))

    # Archetype 4: 120 Active new accounts (<90 days old, active recently)
    for i in range(120):
        uid = f"usr_{len(records) + 1:03d}"
        created_days = 20 + i
        inactivity_days = 1 + (i % 15)
        records.append(_create_user(
            id=uid,
            name=f"Growing User {uid}",
            email=f"{uid}@grower.net",
            company=f"Startup {i + 1}",
            tier="pro" if i % 2 == 0 else "free",
            mrr=199 if i % 2 == 0 else 0,
            created_days_ago=created_days,
            inactivity_days=inactivity_days,
            is_active=True,
        ))

    # Archetype 5: 80 Moderately inactive accounts (<90 days inactive, e.g. 35 to 80 days)
    for i in range(80):
        uid = f"usr_{len(records) + 1:03d}"
        created_days = 60 + i
        inactivity_days = 35 + (i % 45)
        records.append(_create_user(
            id=uid,
            name=f"Trial User {uid}",
            email=f"{uid}@trial.org",
            company=f"Trial Co {i + 1}",
            tier="free",
            mrr=0,
            created_days_ago=created_days,
            inactivity_days=inactivity_days,
            is_active=False,
        ))

    return records


DEFAULT_FICTIONAL_USERS: List[UserRecord] = _generate_500_records()


def get_default_dataset() -> List[UserRecord]:
    """Returns an isolated, deep copy of the 500-record benchmark dataset."""
    return [copy.deepcopy(user) for user in DEFAULT_FICTIONAL_USERS]


def evaluate_condition_match(user: UserRecord, condition: str) -> bool:
    """Evaluates whether a user record matches the deletion condition."""
    if condition == "inactive_90_days":
        return user.inactivity_days is not None and user.inactivity_days >= INACTIVITY_THRESHOLD_DAYS
    elif condition == "created_90_days":
        return user.created_days_ago >= CREATION_THRESHOLD_DAYS
    elif condition == "inactive_or_unknown":
        return user.inactivity_days is None or user.inactivity_days >= INACTIVITY_THRESHOLD_DAYS
    else:
        raise UnsupportedConditionError(
            f"Unsupported condition '{condition}'. Allowed: {sorted(list(SUPPORTED_CONDITIONS))}"
        )


def validate_action(action: Action) -> None:
    """Ensures action matches the strict MVP safety bounds."""
    if action.type != SUPPORTED_ACTION_TYPE:
        raise UnsupportedActionError(
            f"Unsupported action type '{action.type}'. Only '{SUPPORTED_ACTION_TYPE}' is allowed."
        )
    if action.condition not in SUPPORTED_CONDITIONS:
        raise UnsupportedConditionError(
            f"Unsupported action condition '{action.condition}'. Allowed: {sorted(list(SUPPORTED_CONDITIONS))}"
        )


def calculate_blast_radius(affected_users: Sequence[UserRecord]) -> BlastRadius:
    """Calculates the financial and operational blast radius for a set of affected users."""
    mrr_total = sum(u.mrr for u in affected_users)
    active_count = sum(1 for u in affected_users if u.is_active)
    enterprise_count = sum(1 for u in affected_users if u.tier == "enterprise")
    pro_count = sum(1 for u in affected_users if u.tier == "pro")
    free_count = sum(1 for u in affected_users if u.tier == "free")

    high_value = [
        f"{u.company} (${u.mrr:,}/mo)"
        for u in sorted(affected_users, key=lambda x: x.mrr, reverse=True)
        if u.mrr > 0
    ][:5]

    return BlastRadius(
        mrr_at_risk=mrr_total,
        active_users_affected=active_count,
        enterprise_accounts_lost=enterprise_count,
        pro_accounts_lost=pro_count,
        free_accounts_lost=free_count,
        high_value_companies_at_risk=high_value,
    )


def simulate_single_action(
    dataset: Sequence[UserRecord],
    action: Action,
) -> Dict[str, Any]:
    """Computes affected IDs and counts without mutating input dataset."""
    validate_action(action)
    affected_ids = [u.id for u in dataset if evaluate_condition_match(u, action.condition)]
    return {
        "affected_ids": affected_ids,
        "affected_count": len(affected_ids),
    }


def simulate_interpretation(
    interpretation: CandidateInterpretation,
    dataset: Optional[Sequence[UserRecord]] = None,
) -> BranchSimulationResult:
    """Simulates one interpretation branch against an independent copy of dataset."""
    base_data = dataset if dataset is not None else get_default_dataset()
    outcome = simulate_single_action(base_data, interpretation.action)

    affected_set = set(outcome["affected_ids"])
    affected_users = [u for u in base_data if u.id in affected_set]
    blast = calculate_blast_radius(affected_users)

    return BranchSimulationResult(
        id=interpretation.id,
        title=interpretation.title,
        assumption=interpretation.assumption,
        action=interpretation.action,
        explanation=interpretation.explanation,
        affected_ids=outcome["affected_ids"],
        affected_count=outcome["affected_count"],
        blast_radius=blast,
    )


def simulate_all_branches(
    interpretations: Sequence[CandidateInterpretation],
    dataset: Optional[Sequence[UserRecord]] = None,
) -> List[BranchSimulationResult]:
    """Executes multiple interpretation branches across isolated dataset copies."""
    base_data = dataset if dataset is not None else get_default_dataset()
    results: List[BranchSimulationResult] = []

    for interp in interpretations:
        branch_copy = [copy.deepcopy(u) for u in base_data]
        results.append(simulate_interpretation(interp, dataset=branch_copy))

    return results
