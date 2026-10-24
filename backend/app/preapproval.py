"""Pre-approved offer: the largest loan the bank would approve automatically right now.

Same sources and rules as the pipeline: the registry, «Прозрачный бизнес», the credit
bureau, the scoring service and `credit_decision.decide`. For every product and a few
terms, the largest amount (in steps of 10 000 ₽) that `decide` approves exactly as asked
is found by binary search: approval only gets harder as the amount grows (debt load,
amount-to-revenue in the scorecard, the auto-decision limit). Nothing is stored; an
application with the offered terms goes through the full pipeline and, while the data
stays the same, gets the same decision (`tests/test_preapproval.py`).
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.credit_decision import (
    CompanyFacts,
    DecisionOutcome,
    LoanRequest,
    Offer,
    ProductParams,
    RegistryStatus,
    ScoreInput,
    decide,
)
from app.integrations import Integrations
from app.models import Company
from app.pipeline import facts_from_sources, missing_financials, scoring_payload
from app.products import ProductConfig

STEP = 10_000
"""Offered amounts are whole tens of thousands of rubles."""

NO_DATA = (
    "Чтобы рассчитать предложение, банку нужны данные о выручке. Подайте заявку — "
    "банк попросит цифры и сразу примет решение."
)
NOT_ACTIVE = "По данным реестра компания не действует, предварительное предложение недоступно."
NO_OFFER = (
    "Сейчас банк не может одобрить кредит заранее. Подайте заявку — её рассмотрят индивидуально."
)

ScoreAt = Callable[[ProductParams, int, int], ScoreInput]


@dataclass(frozen=True)
class Preapproval:
    offers: list[Offer]
    """One per product that can be approved automatically, in catalog order."""
    reason: str | None
    """Why there is no offer, for the client; None when there are offers."""


def preapprove(
    integrations: Integrations, products: dict[str, ProductConfig], company: Company
) -> Preapproval:
    """Raises `ExternalUnavailableError` when a source or the scoring does not answer."""
    egrul = integrations.egrul(company.inn)
    financials = integrations.transparent_business(company.inn)
    bki = integrations.bki(company.inn)
    facts = facts_from_sources(egrul, financials, company.registration_date)
    if facts.registry_status is not RegistryStatus.ACTIVE:
        return Preapproval([], NOT_ACTIVE)
    if missing_financials(facts):
        return Preapproval([], NO_DATA)

    def score_at(product: ProductParams, amount: int, term_months: int) -> ScoreInput:
        result = integrations.score(
            scoring_payload(product.id, amount, term_months, company.inn, company.okved, facts, bki)
        )
        return ScoreInput(
            pd=float(result["score"]),
            risk_class=str(result["risk_class"]),
            points_total=int(result.get("points_total", 0)),
        )

    offers = [
        offer
        for product in products.values()
        if (offer := best_offer(product.params, facts, score_at)) is not None
    ]
    return Preapproval(offers, None if offers else NO_OFFER)


def candidate_terms(product: ProductParams) -> list[int]:
    """A year, three years and the longest term the product allows."""
    terms = {12, 36, product.max_term_months}
    return sorted(t for t in terms if product.min_term_months <= t <= product.max_term_months)


def best_offer(product: ProductParams, facts: CompanyFacts, score_at: ScoreAt) -> Offer | None:
    """The largest approved amount over the candidate terms; on a tie, the longer term
    (the lower monthly payment)."""
    best: Offer | None = None
    for term in candidate_terms(product):
        offer = largest_approved(product, term, facts, score_at)
        if offer is not None and (best is None or offer.amount >= best.amount):
            best = offer
    return best


def largest_approved(
    product: ProductParams, term_months: int, facts: CompanyFacts, score_at: ScoreAt
) -> Offer | None:
    def approved(steps: int) -> Offer | None:
        amount = steps * STEP
        request = LoanRequest(product.id, amount, term_months)
        decision = decide(product, request, score_at(product, amount, term_months), facts)
        return decision.offer if decision.outcome is DecisionOutcome.APPROVED else None

    low = -(-product.min_amount // STEP)  # in steps, rounded up
    high = min(product.max_amount, product.max_auto_amount) // STEP
    if low > high:
        return None
    top = approved(high)
    if top is not None:
        return top
    best = approved(low)
    if best is None:
        return None
    high -= 1
    while low < high:  # approved(low) holds, approved(high + 1) does not
        middle = (low + high + 1) // 2
        offer = approved(middle)
        if offer is not None:
            best, low = offer, middle
        else:
            high = middle - 1
    return best
