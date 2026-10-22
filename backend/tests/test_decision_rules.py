from dataclasses import replace
from pathlib import Path

import pytest

from app.credit_decision import (
    CompanyFacts,
    LoanRequest,
    RegistryStatus,
    ScoreInput,
    decide,
)
from app.credit_decision import (
    DecisionOutcome as Outcome,
)
from app.products import load_products

PRODUCTS = load_products(Path(__file__).parent.parent / "config" / "products.yaml")
WORKING = PRODUCTS["working_capital"].params
EQUIPMENT = PRODUCTS["equipment"].params
REQUEST = LoanRequest("working_capital", 1_500_000, 12)
SCORE = ScoreInput(0.05, "low", 612)
FACTS = CompanyFacts(RegistryStatus.ACTIVE, 36, 24_000_000, 21_000_000, 2_000_000)


def test_strong_company_is_approved() -> None:
    result = decide(WORKING, REQUEST, SCORE, FACTS)
    assert result.outcome == Outcome.APPROVED
    assert result.rule == "approved"
    assert result.offer is not None
    assert result.offer.monthly_payment == 138_593
    assert result.offer.rate == 19.5


@pytest.mark.parametrize("status", list(RegistryStatus)[1:])
def test_registry_rejection_precedes_missing_data(status: RegistryStatus) -> None:
    result = decide(
        WORKING, REQUEST, SCORE, replace(FACTS, registry_status=status, revenue_year=None)
    )
    assert result.outcome == Outcome.REJECTED
    assert result.rule == f"registry_{status.value}"


def test_missing_data_precedes_pd_rejection_and_is_deduplicated() -> None:
    facts = replace(FACTS, revenue_year=None, missing_fields=("revenue_year", "bki"))
    result = decide(WORKING, REQUEST, replace(SCORE, pd=0.9), facts)
    assert result.outcome == Outcome.CLARIFICATION
    assert result.requested_fields == ("revenue_year", "bki")


@pytest.mark.parametrize(
    "pd,outcome",
    [
        (0.12, Outcome.APPROVED),
        (0.120001, Outcome.MANUAL_REVIEW),
        (0.249999, Outcome.MANUAL_REVIEW),
        (0.25, Outcome.REJECTED),
        (0.3, Outcome.REJECTED),
        (1.0, Outcome.REJECTED),
    ],
)
def test_pd_boundaries(pd: float, outcome: Outcome) -> None:
    assert decide(WORKING, REQUEST, replace(SCORE, pd=pd), FACTS).outcome == outcome


def test_scenario_eight_same_score_different_products() -> None:
    score = replace(SCORE, pd=0.10, risk_class="medium")
    request = replace(REQUEST, amount=2_000_000, term_months=24)
    working = decide(WORKING, request, score, FACTS)
    equipment = decide(EQUIPMENT, replace(request, product_id="equipment"), score, FACTS)
    assert working.outcome == Outcome.APPROVED
    assert working.offer is not None and working.offer.rate == 21.5
    assert equipment.outcome == Outcome.MANUAL_REVIEW
    assert equipment.rule == "pd_grey_zone"


def test_auto_amount_limit_and_pd_priority() -> None:
    request = replace(REQUEST, amount=5_000_001)
    assert decide(WORKING, request, SCORE, FACTS).rule == "amount_above_auto_limit"
    assert decide(WORKING, request, replace(SCORE, pd=0.3), FACTS).rule == "pd_too_high"
    assert (
        decide(WORKING, replace(request, amount=5_000_000), SCORE, FACTS).outcome
        == Outcome.APPROVED
    )


def test_longer_term_is_preferred_to_smaller_amount() -> None:
    facts = replace(FACTS, revenue_year=12_000_000, liabilities_total=3_000_000)
    request = replace(REQUEST, amount=4_000_000, term_months=6)
    result = decide(WORKING, request, SCORE, facts)
    assert result.rule == "debt_load_longer_term"
    assert result.offer is not None
    assert result.offer.amount == request.amount
    assert request.term_months < result.offer.term_months <= WORKING.max_term_months
    assert 3_000_000 + result.offer.monthly_payment * 12 <= 6_000_000


def test_scenario_two_reduces_amount_if_longer_term_is_insufficient() -> None:
    facts = replace(FACTS, revenue_year=12_000_000, liabilities_total=5_000_000)
    request = replace(REQUEST, amount=4_000_000, term_months=6)
    result = decide(WORKING, request, SCORE, facts)
    assert result.outcome == Outcome.COUNTER_OFFER
    assert result.rule == "debt_load_smaller_amount"
    assert result.offer is not None
    assert WORKING.min_amount <= result.offer.amount < request.amount
    assert result.offer.term_months == 24
    assert 5_000_000 + result.offer.monthly_payment * 12 <= 6_000_000
    # The resulting offer must itself pass the rules.
    accepted = LoanRequest(result.offer.product_id, result.offer.amount, result.offer.term_months)
    assert decide(WORKING, accepted, SCORE, facts).outcome == Outcome.APPROVED


@pytest.mark.parametrize("revenue,liabilities", [(0, 0), (12_000_000, 6_000_000)])
def test_unaffordable_minimum_is_rejected(revenue: int, liabilities: int) -> None:
    facts = replace(FACTS, revenue_year=revenue, liabilities_total=liabilities)
    result = decide(WORKING, REQUEST, SCORE, facts)
    assert result.rule == "debt_load_too_high"
    assert result.offer is None


def test_exact_debt_limit_is_approved() -> None:
    facts = replace(FACTS, revenue_year=4_000_000, liabilities_total=336_884)
    assert decide(WORKING, REQUEST, SCORE, facts).outcome == Outcome.APPROVED


def test_scenario_eleven_young_business_gets_alternative() -> None:
    request = LoanRequest("equipment", 2_000_000, 24)
    facts = replace(FACTS, business_age_months=8)
    result = decide(EQUIPMENT, request, SCORE, facts, [WORKING])
    assert result.rule == "business_age_alternative"
    assert result.offer is not None and result.offer.product_id == "working_capital"
    assert decide(EQUIPMENT, request, SCORE, facts).rule == "business_too_young"


def test_alternative_must_pass_its_own_pd_rules() -> None:
    result = decide(
        EQUIPMENT,
        LoanRequest("equipment", 2_000_000, 24),
        replace(SCORE, pd=0.3),
        replace(FACTS, business_age_months=8),
        [WORKING],
    )
    assert result.outcome == Outcome.REJECTED


def test_debt_load_can_switch_to_eligible_product() -> None:
    facts = replace(FACTS, revenue_year=3_000_000, liabilities_total=1_150_000)
    result = decide(
        EQUIPMENT, LoanRequest("equipment", 1_000_000, 24), SCORE, facts, [EQUIPMENT, WORKING]
    )
    assert result.rule == "debt_load_alternative"
    assert result.offer is not None and result.offer.product_id == "working_capital"


@pytest.mark.parametrize("pd", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_pd_cannot_be_approved(pd: float) -> None:
    with pytest.raises(ValueError, match="pd"):
        decide(WORKING, REQUEST, replace(SCORE, pd=pd), FACTS)


@pytest.mark.parametrize("amount,months", [(299_999, 12), (1_500_000, 2), (1_500_000, 25)])
def test_out_of_range_terms_are_rejected(amount: int, months: int) -> None:
    result = decide(WORKING, replace(REQUEST, amount=amount, term_months=months), SCORE, FACTS)
    assert result.rule == "terms_out_of_range"


def test_product_mismatch_is_an_integration_error() -> None:
    with pytest.raises(ValueError, match="product_id"):
        decide(EQUIPMENT, REQUEST, SCORE, FACTS)


@pytest.mark.parametrize("amount,months", [(0, 12), (-1, 12), (1_500_000, 0)])
def test_invalid_request_is_an_integration_error(amount: int, months: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        decide(WORKING, replace(REQUEST, amount=amount, term_months=months), SCORE, FACTS)


def test_negative_financial_data_is_an_integration_error() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        decide(WORKING, REQUEST, SCORE, replace(FACTS, liabilities_total=-1))


def test_minimum_business_age_is_eligible() -> None:
    assert (
        decide(WORKING, REQUEST, SCORE, replace(FACTS, business_age_months=6)).outcome
        == Outcome.APPROVED
    )


def test_deterministic_and_does_not_mutate_inputs() -> None:
    before = (replace(WORKING), replace(REQUEST), replace(SCORE), replace(FACTS))
    assert decide(WORKING, REQUEST, SCORE, FACTS) == decide(WORKING, REQUEST, SCORE, FACTS)
    assert (WORKING, REQUEST, SCORE, FACTS) == before
