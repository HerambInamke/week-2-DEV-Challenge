from datetime import datetime, timedelta
from typing import List
import pytest

from backend2.ambiguity import (
    check_outcomes_diverge,
    compare_branch_ids,
    evaluate_ambiguity_risk,
    verify_ambiguities,
)
from backend2.fixtures import BENCHMARK_FIXTURES
from backend2.schemas import (
    Action,
    CandidateAmbiguity,
    CandidateInterpretation,
    UserRecord,
)
from backend2.simulator import (
    DEFAULT_FICTIONAL_USERS,
    REFERENCE_DATETIME,
    UnsupportedActionError,
    UnsupportedConditionError,
    evaluate_condition_match,
    get_default_dataset,
    simulate_all_branches,
    simulate_single_action,
)

EXPECTED_DEFAULT_DATASET_LENGTH = 500
EXPECTED_INACTIVE_90_DAYS_COUNT = 120
EXPECTED_CREATED_90_DAYS_COUNT = 360
EXPECTED_INACTIVE_OR_UNKNOWN_COUNT = 160

EXPECTED_BRANCH_B_MIN_MRR_RISK = 500000
EXPECTED_BRANCH_B_ENTERPRISE_LOST = 40
EXPECTED_BRANCH_C_MIN_MRR_RISK = 50000
EXPECTED_BRANCH_C_ENTERPRISE_LOST = 10

UNSUPPORTED_ACTION_TYPE_NAME = "drop_table"
UNSUPPORTED_CONDITION_NAME = "created_yesterday"

CANONICAL_INSTRUCTION = "delete old user records."


@pytest.fixture
def clean_dataset() -> List[UserRecord]:
    return get_default_dataset()


@pytest.fixture
def canonical_interpretations() -> List[CandidateInterpretation]:
    return list(BENCHMARK_FIXTURES[CANONICAL_INSTRUCTION]["interpretations"])


@pytest.fixture
def canonical_ambiguities() -> List[CandidateAmbiguity]:
    return list(BENCHMARK_FIXTURES[CANONICAL_INSTRUCTION]["candidate_ambiguities"])


def test_fictional_users_have_consistent_timestamps(clean_dataset: List[UserRecord]):
    """Verifies that all 500 dataset records strictly adhere to the reference anchor datetime."""
    assert len(clean_dataset) == EXPECTED_DEFAULT_DATASET_LENGTH
    for user in clean_dataset:
        created_dt = datetime.fromisoformat(user.created_at.replace("Z", "+00:00"))
        expected_created_dt = REFERENCE_DATETIME - timedelta(days=user.created_days_ago)
        assert created_dt == expected_created_dt

        if user.inactivity_days is not None:
            assert user.last_active_at is not None
            active_dt = datetime.fromisoformat(user.last_active_at.replace("Z", "+00:00"))
            expected_active_dt = REFERENCE_DATETIME - timedelta(days=user.inactivity_days)
            assert active_dt == expected_active_dt
            assert user.created_days_ago >= user.inactivity_days
            assert active_dt >= created_dt
        else:
            assert user.last_active_at is None


def test_user_record_validator_rejects_inconsistent_timestamps():
    """Verifies that UserRecord rejects records where last_active_at is before created_at."""
    with pytest.raises(ValueError, match="cannot be active before creation"):
        UserRecord(
            id="usr_err",
            name="Error User",
            email="err@example.org",
            company="Bad Data Inc",
            tier="free",
            mrr=0,
            created_days_ago=10,
            inactivity_days=50,
            is_active=False,
            created_at="2024-12-22T00:00:00Z",
            last_active_at="2024-11-12T00:00:00Z",
        )


def test_condition_inactive_90_days_matches_correct_subset(clean_dataset: List[UserRecord]):
    action = Action(type="delete_users", condition="inactive_90_days")
    result = simulate_single_action(clean_dataset, action)

    assert result["affected_count"] == EXPECTED_INACTIVE_90_DAYS_COUNT
    assert len(result["affected_ids"]) == EXPECTED_INACTIVE_90_DAYS_COUNT


def test_condition_created_90_days_matches_correct_subset(clean_dataset: List[UserRecord]):
    action = Action(type="delete_users", condition="created_90_days")
    result = simulate_single_action(clean_dataset, action)

    assert result["affected_count"] == EXPECTED_CREATED_90_DAYS_COUNT
    assert len(result["affected_ids"]) == EXPECTED_CREATED_90_DAYS_COUNT


def test_condition_inactive_or_unknown_handles_missing_activity_dates(clean_dataset: List[UserRecord]):
    action = Action(type="delete_users", condition="inactive_or_unknown")
    result = simulate_single_action(clean_dataset, action)

    assert result["affected_count"] == EXPECTED_INACTIVE_OR_UNKNOWN_COUNT
    assert len(result["affected_ids"]) == EXPECTED_INACTIVE_OR_UNKNOWN_COUNT


def test_deterministic_repeated_runs_produce_identical_results(clean_dataset: List[UserRecord]):
    action = Action(type="delete_users", condition="inactive_90_days")

    run_1 = simulate_single_action(clean_dataset, action)
    run_2 = simulate_single_action(clean_dataset, action)

    assert run_1["affected_ids"] == run_2["affected_ids"]
    assert run_1["affected_count"] == run_2["affected_count"]


def test_isolated_branches_do_not_mutate_dataset_or_leak_state(
    clean_dataset: List[UserRecord],
    canonical_interpretations: List[CandidateInterpretation],
):
    original_dataset_ids = [u.id for u in clean_dataset]
    branch_results = simulate_all_branches(canonical_interpretations, dataset=clean_dataset)

    after_dataset_ids = [u.id for u in clean_dataset]
    assert original_dataset_ids == after_dataset_ids
    assert len(clean_dataset) == EXPECTED_DEFAULT_DATASET_LENGTH

    assert len(branch_results) == 3
    assert branch_results[0].affected_count == EXPECTED_INACTIVE_90_DAYS_COUNT
    assert branch_results[1].affected_count == EXPECTED_CREATED_90_DAYS_COUNT
    assert branch_results[2].affected_count == EXPECTED_INACTIVE_OR_UNKNOWN_COUNT


def test_branch_blast_radius_measures_financial_and_tier_impact(
    clean_dataset: List[UserRecord],
    canonical_interpretations: List[CandidateInterpretation],
):
    branch_results = simulate_all_branches(canonical_interpretations, dataset=clean_dataset)

    # Branch A: Safe dormant purge -> $0 MRR lost, 0 enterprise accounts
    blast_a = branch_results[0].blast_radius
    assert blast_a.mrr_at_risk == 0
    assert blast_a.active_users_affected == 0
    assert blast_a.enterprise_accounts_lost == 0

    # Branch B: Creation age naive purge -> >$500k MRR lost, 40 enterprise accounts
    blast_b = branch_results[1].blast_radius
    assert blast_b.mrr_at_risk >= EXPECTED_BRANCH_B_MIN_MRR_RISK
    assert blast_b.enterprise_accounts_lost == EXPECTED_BRANCH_B_ENTERPRISE_LOST
    assert len(blast_b.high_value_companies_at_risk) > 0

    # Branch C: Null telemetry purge -> >$50k MRR lost, 10 enterprise pilot accounts
    blast_c = branch_results[2].blast_radius
    assert blast_c.mrr_at_risk >= EXPECTED_BRANCH_C_MIN_MRR_RISK
    assert blast_c.enterprise_accounts_lost == EXPECTED_BRANCH_C_ENTERPRISE_LOST


def test_rejection_of_unsupported_action_type(clean_dataset: List[UserRecord]):
    with pytest.raises(ValueError):
        Action.model_validate({"type": UNSUPPORTED_ACTION_TYPE_NAME, "condition": "inactive_90_days"})


def test_rejection_of_unsupported_condition(clean_dataset: List[UserRecord]):
    with pytest.raises(ValueError):
        Action.model_validate({"type": "delete_users", "condition": UNSUPPORTED_CONDITION_NAME})


def test_simulator_raises_unsupported_condition_on_direct_eval():
    user = DEFAULT_FICTIONAL_USERS[0]
    with pytest.raises(UnsupportedConditionError):
        evaluate_condition_match(user, UNSUPPORTED_CONDITION_NAME)


def test_detection_of_different_affected_id_sets(
    clean_dataset: List[UserRecord],
    canonical_interpretations: List[CandidateInterpretation],
):
    branch_results = simulate_all_branches(canonical_interpretations, dataset=clean_dataset)
    assert check_outcomes_diverge(branch_results) is True

    only_a, only_b = compare_branch_ids(branch_results[0].affected_ids, branch_results[1].affected_ids)
    assert len(only_a) == 0
    assert len(only_b) == 240


def test_ambiguity_verified_as_observed_risk_only_when_outcomes_differ(
    clean_dataset: List[UserRecord],
    canonical_interpretations: List[CandidateInterpretation],
    canonical_ambiguities: List[CandidateAmbiguity],
):
    branch_results = simulate_all_branches(canonical_interpretations, dataset=clean_dataset)
    verified = verify_ambiguities(canonical_ambiguities, branch_results, clean_dataset)

    assert len(verified) == 2
    old_amb = next(v for v in verified if v.term == "old")
    assert old_amb.observed_risk is True
    assert old_amb.risk_level == "critical"
    assert "MRR at risk" in old_amb.evidence


def test_identical_branches_produce_no_observed_risk(clean_dataset: List[UserRecord]):
    identical_interps = [
        CandidateInterpretation(
            id="A",
            title="Inactive 90",
            assumption="Assumption A",
            action=Action(type="delete_users", condition="inactive_90_days"),
            explanation="Explanation A",
        ),
        CandidateInterpretation(
            id="B",
            title="Inactive 90 Copy",
            assumption="Assumption B",
            action=Action(type="delete_users", condition="inactive_90_days"),
            explanation="Explanation B",
        ),
    ]
    cand_amb = [
        CandidateAmbiguity(
            term="pseudo_ambiguous",
            description="A word that has no operational impact",
            interpretation_ids=["A", "B"],
        )
    ]

    branches = simulate_all_branches(identical_interps, dataset=clean_dataset)
    verified = verify_ambiguities(cand_amb, branches, clean_dataset)

    assert len(verified) == 1
    assert verified[0].observed_risk is False
    assert verified[0].risk_level == "none"
    assert "identical outcomes" in verified[0].evidence
