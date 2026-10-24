"""HTTP request/response DTOs. Field names here are the API contract for the frontend."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import UserRole
from app.statuses import Actor, ApplicationStatus, ClientStage


class HealthResponse(BaseModel):
    status: str


# --- Auth -------------------------------------------------------------------


class LoginRequest(BaseModel):
    login: str = Field(examples=["client1"])
    password: str = Field(examples=["client1"])


class UserResponse(BaseModel):
    id: UUID
    login: str
    full_name: str
    role: UserRole
    company_inn: str | None = Field(default=None, description="Only for clients")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Products ---------------------------------------------------------------


class ProductId(StrEnum):
    WORKING_CAPITAL = "working_capital"
    EQUIPMENT = "equipment"


class PurposeCategory(StrEnum):
    INVENTORY = "inventory"
    CASH_GAP = "cash_gap"
    EQUIPMENT = "equipment"
    OTHER = "other"


class ProductResponse(BaseModel):
    id: ProductId
    name: str
    description: str = Field(description="Plain-language description for the client")
    purposes: list[PurposeCategory]
    min_amount: int = Field(description="Rubles")
    max_amount: int = Field(description="Rubles")
    min_term_months: int
    max_term_months: int
    base_rate: float = Field(description="Annual rate, percent")
    min_business_age_months: int


class RecommendRequest(BaseModel):
    purpose_category: PurposeCategory


class RecommendResponse(BaseModel):
    product: ProductResponse
    reason: str = Field(description="Why this product fits, in plain language")


# --- Companies --------------------------------------------------------------


class LegalForm(StrEnum):
    OOO = "OOO"
    IP = "IP"


class CompanyResponse(BaseModel):
    inn: str
    name: str
    legal_form: LegalForm
    okved: str
    registration_date: date
    region: str
    director: str


# --- Applications -------------------------------------------------------------


class CreateApplicationRequest(BaseModel):
    product_id: ProductId
    purpose_category: PurposeCategory | None = None
    amount: int | None = Field(default=None, gt=0, description="Rubles")
    term_months: int | None = Field(default=None, gt=0)
    purpose: str | None = Field(default=None, max_length=500)


class UpdateApplicationRequest(BaseModel):
    """Edit a draft or answer a clarification request. Only sent fields are changed."""

    product_id: ProductId | None = None
    purpose_category: PurposeCategory | None = None
    amount: int | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0)
    purpose: str | None = Field(default=None, max_length=500)
    revenue_year: int | None = Field(default=None, ge=0, description="Rubles, last 12 months")
    expenses_year: int | None = Field(default=None, ge=0)
    liabilities_total: int | None = Field(default=None, ge=0)
    clarification_answer: str | None = Field(default=None, max_length=2000)


class StatusHistoryItem(BaseModel):
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    actor: Actor
    comment: str | None = None
    at: datetime


class CheckType(StrEnum):
    COMPLETENESS = "completeness"
    EGRUL = "egrul"
    TRANSPARENT_BUSINESS = "transparent_business"
    BKI = "bki"


class CheckOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


class CheckResult(BaseModel):
    type: CheckType
    outcome: CheckOutcome
    summary: str
    attempt: int = 1


class FactorImpact(StrEnum):
    INCREASES_RISK = "increases_risk"
    DECREASES_RISK = "decreases_risk"


class ScoreFactor(BaseModel):
    name: str
    points: int
    impact: FactorImpact
    comment: str


class RiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScoreView(BaseModel):
    score: float = Field(ge=0, le=1, description="Probability of default")
    risk_class: RiskClass
    points_total: int
    factors: list[ScoreFactor]
    model_version: str


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    COUNTER_OFFER = "counter_offer"
    CLARIFICATION = "clarification"
    REJECTED = "rejected"


class LoanTerms(BaseModel):
    product_id: ProductId
    amount: int
    term_months: int
    rate: float = Field(description="Annual rate, percent")
    monthly_payment: int


class DecisionView(BaseModel):
    outcome: DecisionOutcome
    terms: LoanTerms | None = None
    reason: str = Field(description="Shown to the client in plain language")
    rule: str = Field(description="Which credit rule fired; shown to the employee")
    decided_by: Actor
    comment: str | None = None
    decided_at: datetime


class ClarificationView(BaseModel):
    requested_fields: list[str]
    message: str
    answer: str | None = None


class ApplicationSummary(BaseModel):
    id: UUID
    status: ApplicationStatus
    status_label: str
    client_stage: ClientStage
    stage_label: str
    product_id: ProductId
    amount: int | None
    term_months: int | None
    company_inn: str
    company_name: str
    risk_class: RiskClass | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationAction(StrEnum):
    """What the current user may do with the application right now."""

    EDIT = "edit"
    SUBMIT = "submit"
    ANSWER_CLARIFICATION = "answer_clarification"
    ACCEPT = "accept"
    DECLINE = "decline"
    SIGN = "sign"
    WITHDRAW = "withdraw"
    DECIDE = "decide"


class ApplicationDetail(ApplicationSummary):
    purpose_category: PurposeCategory | None
    purpose: str | None
    revenue_year: int | None = Field(default=None, description="Entered by the client, rubles")
    expenses_year: int | None = None
    liabilities_total: int | None = None
    submitted_at: datetime | None = None
    available_actions: list[ApplicationAction] = Field(
        default_factory=list, description="Buttons to show to the current user"
    )
    next_step: str = Field(description="What happens next, for the client")
    waiting_external: bool = Field(description="An external source is unavailable, retrying")
    company: CompanyResponse
    history: list[StatusHistoryItem]
    checks: list[CheckResult] = Field(description="Empty for clients")
    score: ScoreView | None = Field(default=None, description="Null for clients")
    decision: DecisionView | None = None
    clarification: ClarificationView | None = None


class ProposedTerms(BaseModel):
    """Terms offered by the employee; the monthly payment is calculated by the bank."""

    product_id: ProductId
    amount: int = Field(gt=0, description="Rubles")
    term_months: int = Field(gt=0)
    rate: float | None = Field(
        default=None, gt=0, description="Annual rate, percent; product rate if omitted"
    )


class ManualDecisionRequest(BaseModel):
    outcome: DecisionOutcome
    comment: str = Field(min_length=1, max_length=2000)
    terms: ProposedTerms | None = Field(default=None, description="Required for counter_offer")
    requested_fields: list[str] | None = Field(default=None, description="For clarification")


class AcceptOfferRequest(BaseModel):
    accept: bool


class WithdrawRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


# --- Feed -------------------------------------------------------------------


class FeedItemType(StrEnum):
    EVENT = "event"


class FeedItem(BaseModel):
    id: UUID
    type: FeedItemType
    title: str
    text: str
    application_id: UUID | None = None
    created_at: datetime
    read: bool


class FeedResponse(BaseModel):
    events: list[FeedItem] = Field(description="Events of the client's applications, newest first")
    unread_events: int


# --- Meta -------------------------------------------------------------------


class StatusMeta(BaseModel):
    status: ApplicationStatus
    label: str
    client_stage: ClientStage
    turn_owner: Actor | None
    allowed_next: list[ApplicationStatus]


class StageMeta(BaseModel):
    stage: ClientStage
    label: str


class LifecycleMeta(BaseModel):
    statuses: list[StatusMeta]
    stages: list[StageMeta]
