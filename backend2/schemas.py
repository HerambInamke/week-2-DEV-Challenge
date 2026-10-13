from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

SupportedActionType = Literal["delete_users"]
SupportedActionCondition = Literal[
    "inactive_90_days",
    "created_90_days",
    "inactive_or_unknown",
]
VALID_BRANCH_IDS = {"A", "B", "C"}
RiskLevelType = Literal["none", "low", "medium", "high", "critical"]


class Action(BaseModel):
    type: SupportedActionType = Field(
        ...,
        description="Restricted action type (must be 'delete_users' for MVP).",
    )
    condition: SupportedActionCondition = Field(
        ...,
        description="Restricted filter condition ('inactive_90_days', 'created_90_days', 'inactive_or_unknown').",
    )


class UserRecord(BaseModel):
    id: str = Field(..., description="Unique fictional user identifier (e.g. 'usr_001').")
    name: str = Field(..., description="Fictional user display name.")
    email: str = Field(..., description="Fictional user email address.")
    company: str = Field(default="Acme Corp", description="Organization / company name.")
    tier: Literal["enterprise", "pro", "free"] = Field(default="free", description="Subscription tier.")
    mrr: int = Field(default=0, ge=0, description="Monthly recurring revenue in USD.")
    created_days_ago: int = Field(..., ge=0, description="Account age in fixed elapsed days.")
    inactivity_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Elapsed days since last activity; None indicates missing/unknown activity date.",
    )
    is_active: bool = Field(..., description="Current operational active flag.")
    created_at: str = Field(..., description="Deterministic ISO-8601 creation timestamp.")
    last_active_at: Optional[str] = Field(
        default=None,
        description="Deterministic ISO-8601 last activity timestamp or None if missing.",
    )

    @model_validator(mode="after")
    def validate_timestamp_consistency(self) -> "UserRecord":
        if self.inactivity_days is not None:
            if self.last_active_at is None:
                raise ValueError(
                    f"User {self.id} has inactivity_days={self.inactivity_days} but last_active_at is None."
                )
            if self.created_days_ago < self.inactivity_days:
                raise ValueError(
                    f"User {self.id} cannot be active before creation: created_days_ago={self.created_days_ago} "
                    f"< inactivity_days={self.inactivity_days}."
                )
            created_dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            active_dt = datetime.fromisoformat(self.last_active_at.replace("Z", "+00:00"))
            if active_dt < created_dt:
                raise ValueError(
                    f"User {self.id} last_active_at ({self.last_active_at}) is before created_at ({self.created_at})."
                )
        else:
            if self.last_active_at is not None:
                raise ValueError(
                    f"User {self.id} has no inactivity_days but last_active_at is set to {self.last_active_at}."
                )
        return self


class CandidateInterpretation(BaseModel):
    id: Literal["A", "B", "C"] = Field(..., description="Branch identifier: 'A', 'B', or 'C'.")
    title: str = Field(..., min_length=1, description="Concise title for the interpretation.")
    assumption: str = Field(..., min_length=5, description="Unstated operational assumption.")
    action: Action = Field(..., description="Restricted simulated action to execute.")
    explanation: str = Field(..., min_length=5, description="Rationale for this interpretation.")
    risk_level: Optional[RiskLevelType] = Field(
        default="medium",
        description="Estimated initial risk level.",
    )


class CandidateAmbiguity(BaseModel):
    term: str = Field(..., min_length=1, description="Ambiguous word or phrase (e.g. 'old').")
    description: str = Field(..., min_length=5, description="Why the term is ambiguous.")
    interpretation_ids: List[str] = Field(..., min_length=1, description="Relevant interpretation IDs, e.g. ['A', 'B'].")
    impact: Optional[str] = Field(default=None, description="Hypothetical consequence of the ambiguity.")


class BlastRadius(BaseModel):
    mrr_at_risk: int = Field(default=0, ge=0, description="Total Monthly Recurring Revenue at risk in USD.")
    active_users_affected: int = Field(default=0, ge=0, description="Count of currently active accounts deleted.")
    enterprise_accounts_lost: int = Field(default=0, ge=0, description="Count of enterprise accounts deleted.")
    pro_accounts_lost: int = Field(default=0, ge=0, description="Count of pro tier accounts deleted.")
    free_accounts_lost: int = Field(default=0, ge=0, description="Count of free tier accounts deleted.")
    high_value_companies_at_risk: List[str] = Field(
        default_factory=list,
        description="Top high-value company names affected (with MRR).",
    )


class BranchSimulationResult(BaseModel):
    id: Literal["A", "B", "C"] = Field(..., description="Branch identifier.")
    title: str = Field(..., description="Interpretation title.")
    assumption: str = Field(..., description="Interpretation assumption.")
    action: Action = Field(..., description="Action executed.")
    explanation: str = Field(..., description="Interpretation explanation.")
    affected_ids: List[str] = Field(..., description="Record IDs affected by this branch.")
    affected_count: int = Field(..., ge=0, description="Total number of affected records.")
    blast_radius: BlastRadius = Field(
        default_factory=BlastRadius,
        description="Financial and operational blast radius of this branch.",
    )


class VerifiedAmbiguity(BaseModel):
    term: str = Field(..., description="Ambiguous term examined.")
    description: str = Field(..., description="Nature of the ambiguity.")
    interpretation_ids: List[str] = Field(..., description="Branches compared.")
    observed_risk: bool = Field(
        ...,
        description="True only when simulator confirms concrete outcome divergence.",
    )
    risk_level: RiskLevelType = Field(
        ...,
        description="Empirical risk rating based on divergence magnitude and active account impact.",
    )
    evidence: str = Field(
        ...,
        description="Concrete evidence describing which record IDs differed.",
    )


class AnalyzeRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Natural-language instruction to analyze.")
    scenario: str = Field(default="user_cleanup", description="Execution scenario (MVP supports 'user_cleanup').")

    @field_validator("instruction")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Instruction cannot be empty or whitespace.")
        return stripped


class AnalysisResult(BaseModel):
    run_id: str = Field(..., description="Unique run identifier.")
    instruction: str = Field(..., description="Analyzed instruction.")
    scenario: str = Field(default="user_cleanup", description="Evaluation scenario.")
    outcomes_diverge: bool = Field(
        default=False,
        description="True if the simulated interpretations produced different outcomes.",
    )
    suggested_rewrite: str = Field(
        default="",
        description="Recommended unambiguous instruction rewrite.",
    )
    interpretations: List[BranchSimulationResult] = Field(
        default_factory=list,
        description="Simulated execution branches with calculated affected records.",
    )
    ambiguities: List[VerifiedAmbiguity] = Field(
        default_factory=list,
        description="Ambiguities verified against true simulated outcomes.",
    )
    status: Literal["ok", "unsupported", "error"] = Field(
        default="ok",
        description="Analysis execution status.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Explanation when status is unsupported or error.",
    )


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "semantic-chaos-monkey"
    version: str = "0.1.0"
