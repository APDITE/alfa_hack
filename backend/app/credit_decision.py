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
from math import isfinite


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
    if amount <= 0 or not isfinite(annual_rate_percent) or annual_rate_percent < 0:
        raise ValueError("amount must be positive and rate finite and non-negative")
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
    if request.product_id != product.id:
        raise ValueError("request.product_id must match product.id")
    if request.amount <= 0 or request.term_months <= 0:
        raise ValueError("amount and term_months must be positive")

    if facts.registry_status != RegistryStatus.ACTIVE:
        return Decision(
            DecisionOutcome.REJECTED,
            f"registry_{facts.registry_status.value}",
            "Компания ликвидируется, ликвидирована или не найдена в реестре.",
        )

    missing = tuple(
        dict.fromkeys(
            (
                *facts.missing_fields,
                *(
                    name
                    for name in ("revenue_year", "expenses_year", "liabilities_total")
                    if getattr(facts, name) is None
                ),
            )
        )
    )
    if missing:
        return Decision(
            DecisionOutcome.CLARIFICATION,
            "missing_data",
            "Для решения необходимо дополнить данные.",
            requested_fields=missing,
        )
    assert facts.revenue_year is not None
    assert facts.expenses_year is not None
    assert facts.liabilities_total is not None
    if (
        min(
            facts.revenue_year,
            facts.expenses_year,
            facts.liabilities_total,
            facts.business_age_months,
        )
        < 0
    ):
        raise ValueError("company financial values and age must be non-negative")
    if not isfinite(score.pd) or not 0 <= score.pd <= 1:
        raise ValueError("pd must be finite and between 0 and 1")
    if score.risk_class not in {"low", "medium", "high"}:
        raise ValueError("unknown risk_class")

    if facts.business_age_months < product.min_business_age_months:
        offer = _alternative_offer(product, request, score, facts, alternatives)
        if offer is not None:
            return Decision(
                DecisionOutcome.COUNTER_OFFER,
                "business_age_alternative",
                "Предлагаем продукт с меньшим требованием к возрасту бизнеса.",
                offer,
            )
        return Decision(
            DecisionOutcome.REJECTED,
            "business_too_young",
            "Возраст бизнеса меньше минимального для продукта.",
        )
    if score.pd >= product.reject_min_pd:
        return Decision(
            DecisionOutcome.REJECTED,
            "pd_too_high",
            "Оценка риска превышает допустимый уровень продукта.",
        )
    if score.pd > product.approve_max_pd:
        return Decision(
            DecisionOutcome.MANUAL_REVIEW,
            "pd_grey_zone",
            "Оценка риска требует проверки сотрудником.",
        )
    if request.amount > product.max_auto_amount:
        return Decision(
            DecisionOutcome.MANUAL_REVIEW,
            "amount_above_auto_limit",
            "Сумма превышает лимит автоматического решения.",
        )
    if not (
        product.min_amount <= request.amount <= product.max_amount
        and product.min_term_months <= request.term_months <= product.max_term_months
    ):
        return Decision(
            DecisionOutcome.REJECTED,
            "terms_out_of_range",
            "Сумма или срок вне допустимого диапазона продукта.",
        )

    rate = product.base_rate + product.risk_premium.get(score.risk_class, 0.0)
    liabilities = facts.liabilities_total
    revenue = facts.revenue_year

    def make_offer(amount: int, months: int) -> Offer:
        return Offer(product.id, amount, months, rate, annuity_payment(amount, rate, months))

    def fits(offer: Offer) -> bool:
        # Compare without division: zero revenue cannot finance a positive payment.
        return liabilities + offer.monthly_payment * 12 <= product.max_debt_load * revenue

    requested_offer = make_offer(request.amount, request.term_months)
    if fits(requested_offer):
        return Decision(
            DecisionOutcome.APPROVED,
            "approved",
            "Заявка соответствует условиям продукта.",
            requested_offer,
        )

    for months in range(request.term_months + 1, product.max_term_months + 1):
        offer = make_offer(request.amount, months)
        if fits(offer):
            return Decision(
                DecisionOutcome.COUNTER_OFFER,
                "debt_load_longer_term",
                "Предлагаем увеличить срок для снижения платежа.",
                offer,
            )

    # At the longest term, find the largest affordable whole-ruble principal.
    low, high = product.min_amount, request.amount - 1
    smaller_offer = None
    while low <= high:
        amount = (low + high) // 2
        offer = make_offer(amount, product.max_term_months)
        if fits(offer):
            smaller_offer = offer
            low = amount + 1
        else:
            high = amount - 1
    if smaller_offer is not None:
        return Decision(
            DecisionOutcome.COUNTER_OFFER,
            "debt_load_smaller_amount",
            "Предлагаем меньшую сумму на максимальный срок продукта.",
            smaller_offer,
        )
    offer = _alternative_offer(product, request, score, facts, alternatives)
    if offer is not None:
        return Decision(
            DecisionOutcome.COUNTER_OFFER,
            "debt_load_alternative",
            "Предлагаем другой продукт с допустимой долговой нагрузкой.",
            offer,
        )
    return Decision(
        DecisionOutcome.REJECTED,
        "debt_load_too_high",
        "Не удалось подобрать условия с допустимой долговой нагрузкой.",
    )


def _alternative_offer(
    product: ProductParams,
    request: LoanRequest,
    score: ScoreInput,
    facts: CompanyFacts,
    alternatives: Sequence[ProductParams],
) -> Offer | None:
    """Evaluate eligible alternatives in caller order, without recursive switching."""
    for alternative in alternatives:
        if alternative.id == product.id:
            continue
        candidate = LoanRequest(alternative.id, request.amount, request.term_months)
        result = decide(alternative, candidate, score, facts)
        if result.outcome in {DecisionOutcome.APPROVED, DecisionOutcome.COUNTER_OFFER}:
            return result.offer
    return None
