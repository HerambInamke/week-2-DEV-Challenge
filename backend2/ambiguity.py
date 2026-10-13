import itertools
from typing import Dict, List, Optional, Sequence, Set, Tuple

from backend2.schemas import (
    BranchSimulationResult,
    CandidateAmbiguity,
    RiskLevelType,
    UserRecord,
    VerifiedAmbiguity,
)

ACTIVE_RECENCY_DAYS_THRESHOLD = 30
NEW_ACCOUNT_AGE_DAYS_THRESHOLD = 90
LARGE_DIFFERENCE_THRESHOLD = 3


def check_outcomes_diverge(branches: Sequence[BranchSimulationResult]) -> bool:
    """Returns True if any pair of branches produced differing affected record sets."""
    affected_sets = [set(b.affected_ids) for b in branches]
    for s1, s2 in itertools.combinations(affected_sets, 2):
        if s1 != s2:
            return True
    return False


def compare_branch_ids(
    ids_a: Sequence[str],
    ids_b: Sequence[str],
) -> Tuple[List[str], List[str]]:
    """Returns sorted lists of IDs unique to branch A and unique to branch B."""
    set_a = set(ids_a)
    set_b = set(ids_b)
    return sorted(list(set_a - set_b)), sorted(list(set_b - set_a))


def evaluate_ambiguity_risk(
    discrepancy_ids: Set[str],
    user_lookup: Dict[str, UserRecord],
) -> RiskLevelType:
    """
    Deterministic rule-based risk rating for MVP.
    Note: These are operational divergence heuristics, not formal security ratings.

    Rules:
    - 'none': Affected sets are identical across compared branches.
    - 'critical': A branch erroneously deletes an active user (logged in <= 30 days)
      or a new user (account age < 90 days with missing telemetry) that another branch preserved.
    - 'high': Symmetric difference is >= 3 records.
    - 'medium': Symmetric difference is 1-2 records without active user harm.
    """
    if not discrepancy_ids:
        return "none"

    has_active_user_impact = False
    for uid in discrepancy_ids:
        user = user_lookup.get(uid)
        if not user:
            continue
        if user.is_active and user.inactivity_days is not None and user.inactivity_days <= ACTIVE_RECENCY_DAYS_THRESHOLD:
            has_active_user_impact = True
            break
        if user.created_days_ago < NEW_ACCOUNT_AGE_DAYS_THRESHOLD and user.inactivity_days is None:
            has_active_user_impact = True
            break

    if has_active_user_impact:
        return "critical"

    if len(discrepancy_ids) >= LARGE_DIFFERENCE_THRESHOLD:
        return "high"

    return "medium"


def verify_ambiguities(
    candidate_ambiguities: Sequence[CandidateAmbiguity],
    branch_results: Sequence[BranchSimulationResult],
    initial_dataset: Sequence[UserRecord],
) -> List[VerifiedAmbiguity]:
    """
    Cross-references candidate ambiguities from AI with true simulator outcomes.
    Only marks an ambiguity as an observed risk when the simulator confirms real divergence.
    """
    branch_map: Dict[str, BranchSimulationResult] = {b.id: b for b in branch_results}
    user_lookup: Dict[str, UserRecord] = {u.id: u for u in initial_dataset}
    verified_list: List[VerifiedAmbiguity] = []

    for candidate in candidate_ambiguities:
        relevant_branches = [
            branch_map[bid] for bid in candidate.interpretation_ids if bid in branch_map
        ]

        if len(relevant_branches) < 2:
            verified_list.append(
                VerifiedAmbiguity(
                    term=candidate.term,
                    description=candidate.description,
                    interpretation_ids=candidate.interpretation_ids,
                    observed_risk=False,
                    risk_level="none",
                    evidence=(
                        f"Candidate term references branches {candidate.interpretation_ids}, "
                        "which could not be compared (less than 2 matching branches)."
                    ),
                )
            )
            continue

        diverging = False
        all_discrepancy_ids: Set[str] = set()
        evidence_notes: List[str] = []

        for b1, b2 in itertools.combinations(relevant_branches, 2):
            only_a, only_b = compare_branch_ids(b1.affected_ids, b2.affected_ids)
            diff_ids = set(only_a + only_b)
            if diff_ids:
                diverging = True
                all_discrepancy_ids.update(diff_ids)
                evidence_notes.append(
                    f"Branch {b1.id} ({b1.action.condition}: {len(b1.affected_ids)} records, ${b1.blast_radius.mrr_at_risk:,}/mo MRR at risk) vs "
                    f"Branch {b2.id} ({b2.action.condition}: {len(b2.affected_ids)} records, ${b2.blast_radius.mrr_at_risk:,}/mo MRR at risk) "
                    f"differed by {len(diff_ids)} IDs ({len(only_a)} unique to {b1.id}, {len(only_b)} unique to {b2.id})"
                )

        if diverging:
            risk = evaluate_ambiguity_risk(all_discrepancy_ids, user_lookup)
            verified_list.append(
                VerifiedAmbiguity(
                    term=candidate.term,
                    description=candidate.description,
                    interpretation_ids=candidate.interpretation_ids,
                    observed_risk=True,
                    risk_level=risk,
                    evidence="; ".join(evidence_notes),
                )
            )
        else:
            first_branch = relevant_branches[0]
            verified_list.append(
                VerifiedAmbiguity(
                    term=candidate.term,
                    description=candidate.description,
                    interpretation_ids=candidate.interpretation_ids,
                    observed_risk=False,
                    risk_level="none",
                    evidence=(
                        f"Branches {candidate.interpretation_ids} produced identical outcomes "
                        f"({first_branch.affected_count} affected records). No divergence observed."
                    ),
                )
            )

    return verified_list
