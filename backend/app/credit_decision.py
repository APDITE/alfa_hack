"""Credit decision: turns a risk score and the application terms into an outcome.

Scoring only estimates risk (probability of default). The decision also looks at
the product, the requested amount and term, external checks and bank rules, so the
same score can lead to different outcomes for different products (spec, section 9).

This module is pure: no database, no HTTP. Product parameters and thresholds come
from `backend/config/products.yaml` and are passed in as `ProductParams`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    COUNTER_OFFER = "counter_offer"
    CLARIFICATION = "clarification"
    MANUAL_REVIEW = "manual_review"
    REJECTED = "rejected"


class RegistryStatus(StrEnum):
    ACTIVE = "active"
    LIQUIDATING = "liquidating"
    LIQUIDATED = "liquidated"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ProductParams:
    id: str
    min_amount: int
    max_amount: int
    min_term_months: int
    max_term_months: int
    base_rate: float
    """Annual rate, percent."""
    min_business_age_months: int
    max_debt_load: float
    """Max (existing liabilities + new annual payments) / annual revenue."""
    approve_max_pd: float
    """PD at or below this is approved automatically (if the rest fits)."""
    reject_min_pd: float
    """PD at or above this is rejected. Between the two is the grey zone."""
    max_auto_amount: int
    """Above this amount the application always goes to manual review."""
    risk_premium: dict[str, float] = field(default_factory=dict)
    """Rate add-on by risk class, percentage points: {"low": 0, "medium": 2, ...}."""


@dataclass(frozen=True)
class LoanRequest:
    product_id: str
    amount: int
    term_months: int


@dataclass(frozen=True)
class ScoreInput:
    pd: float
    risk_class: str
    points_total: int


@dataclass(frozen=True)
class CompanyFacts:
    registry_status: RegistryStatus
    business_age_months: int
    revenue_year: int | None
    expenses_year: int | None
    liabilities_total: int | None
    missing_fields: tuple[str, ...] = ()
    """Required fields still unknown after the completeness check."""


@dataclass(frozen=True)
class Offer:
    product_id: str
    amount: int
    term_months: int
    rate: float
    monthly_payment: int


@dataclass(frozen=True)
class Decision:
    outcome: DecisionOutcome
    rule: str
    """Which rule fired, e.g. "registry_liquidating". Shown to the employee and the jury."""
    reason: str
    """Plain-language explanation for the client."""
    offer: Offer | None = None
    requested_fields: tuple[str, ...] = ()


def annuity_payment(amount: int, annual_rate_percent: float, term_months: int) -> int:
    """Monthly annuity payment in rubles, rounded to the nearest ruble."""
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    monthly_rate = annual_rate_percent / 100 / 12
    if monthly_rate == 0:
        return round(amount / term_months)
    payment = amount * monthly_rate / (1 - (1 + monthly_rate) ** -term_months)
    return round(payment)


def decide(
    product: ProductParams,
    request: LoanRequest,
    score: ScoreInput,
    facts: CompanyFacts,
    alternatives: Sequence[ProductParams] = (),
) -> Decision:
    """Apply the credit rules in order; the first one that matches wins.

    1. Company liquidating, liquidated or not found in the registry -> REJECTED.
    2. `facts.missing_fields` is not empty -> CLARIFICATION with those fields.
    3. Business younger than `product.min_business_age_months` -> REJECTED
       (or COUNTER_OFFER with an alternative product that allows it).
    4. `score.pd >= product.reject_min_pd` -> REJECTED.
    5. `score.pd > product.approve_max_pd` (grey zone) or
       `request.amount > product.max_auto_amount` -> MANUAL_REVIEW.
    6. Debt load with the new loan above `product.max_debt_load` -> COUNTER_OFFER:
       first a longer term within the product, then a smaller amount, then an
       alternative product; if nothing fits -> REJECTED.
    7. Otherwise -> APPROVED with rate = base_rate + risk_premium[risk_class].

    Owner: ML Б. Keep the signature; ask the backend owner before changing it.
    """
    raise NotImplementedError
