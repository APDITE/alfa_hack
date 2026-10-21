import pytest
from app.credit_decision import annuity_payment


def test_annuity_payment_matches_reference() -> None:
    # 1.5M rubles, 19.5% a year, 12 months: standard annuity formula.
    assert annuity_payment(1_500_000, 19.5, 12) == 138_593


def test_annuity_payment_zero_rate() -> None:
    assert annuity_payment(1_200_000, 0, 12) == 100_000


def test_annuity_total_exceeds_principal() -> None:
    assert annuity_payment(1_000_000, 16.5, 36) * 36 > 1_000_000


def test_annuity_rejects_zero_term() -> None:
    with pytest.raises(ValueError):
        annuity_payment(1_000_000, 16.5, 0)
