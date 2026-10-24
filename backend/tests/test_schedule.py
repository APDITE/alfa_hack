"""Payment schedule: closes the debt, agrees with the offer, shown in the application card."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.credit_decision import annuity_payment
from app.pipeline import PipelineContext, run_until_idle
from app.schedule import annuity_schedule
from test_pipeline import FakeIntegrations

LoginAs = Callable[[str], dict[str, str]]


@pytest.mark.parametrize(
    ("amount", "rate", "term"),
    [(1_500_000, 19.5, 12), (1_645_220, 19.5, 24), (15_000_000, 16.5, 60), (300_000, 21.5, 3)],
)
def test_schedule_closes_the_debt(amount: int, rate: float, term: int) -> None:
    payments = annuity_schedule(amount, rate, term)
    regular = annuity_payment(amount, rate, term)

    assert [p.number for p in payments] == list(range(1, term + 1))
    assert all(p.payment == regular for p in payments[:-1])
    assert abs(payments[-1].payment - regular) <= term  # only the rounding is left over
    assert all(p.payment == p.principal + p.interest for p in payments)
    assert sum(p.principal for p in payments) == amount
    assert payments[-1].balance == 0
    interest = [p.interest for p in payments]
    assert interest == sorted(interest, reverse=True)


def test_stored_payment_is_kept() -> None:
    """An employee's rate is stored rounded; the schedule follows the stored payment."""
    payments = annuity_schedule(1_000_000, 18.33, 12, regular_payment=92_000)
    assert all(p.payment == 92_000 for p in payments[:-1])
    assert payments[-1].balance == 0


@pytest.mark.parametrize(
    ("user", "amount", "term", "status", "payments", "first"),
    [
        ("client1", 1_500_000, 12, "approved", 12, 138_593),
        ("client2", 4_000_000, 6, "counter_offer", 24, 83_333),
    ],
)
def test_offer_comes_with_a_schedule(
    app: FastAPI,
    client: TestClient,
    login_as: LoginAs,
    user: str,
    amount: int,
    term: int,
    status: str,
    payments: int,
    first: int,
) -> None:
    headers = login_as(user)
    body = {"product_id": "working_capital", "amount": amount, "term_months": term}
    created = client.post("/api/applications", json=body, headers=headers).json()
    assert created["schedule"] is None  # no terms yet
    key = {"Idempotency-Key": str(uuid4())}
    client.post(f"/api/applications/{created['id']}/submit", headers=headers | key)
    ctx = PipelineContext(FakeIntegrations(), app.state.products)
    run_until_idle(app.state.session_factory, ctx, datetime.now(UTC))

    detail = client.get(f"/api/applications/{created['id']}", headers=headers).json()
    assert detail["status"] == status
    schedule, terms = detail["schedule"], detail["decision"]["terms"]
    assert len(schedule["payments"]) == payments == terms["term_months"]
    assert schedule["payments"][0]["payment"] == first == terms["monthly_payment"]
    assert schedule["total_paid"] == sum(p["payment"] for p in schedule["payments"])
    assert schedule["overpayment"] == schedule["total_paid"] - terms["amount"]
