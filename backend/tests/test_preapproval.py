"""Pre-approved offer: the limits the rules approve automatically, and the pipeline agrees."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.credit_decision import annuity_payment
from app.pipeline import PipelineContext, run_until_idle
from app.preapproval import NO_DATA, NO_OFFER, NOT_ACTIVE, STEP
from test_pipeline import FakeIntegrations

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def fake(app: FastAPI) -> FakeIntegrations:
    integrations = FakeIntegrations()
    app.state.integrations = integrations
    return integrations


def preapproved(client: TestClient, login_as: LoginAs, user: str) -> Any:
    response = client.get("/api/offers/preapproved", headers=login_as(user))
    assert response.status_code == 200, response.text
    return response.json()


def test_reliable_client_gets_the_auto_decision_limits(
    client: TestClient, login_as: LoginAs, fake: FakeIntegrations
) -> None:
    body = preapproved(client, login_as, "client1")
    assert body["reason"] is None
    offers = {o["product_id"]: o for o in body["offers"]}
    # Low risk and a light debt load: the limits of automatic decisions are the ceiling,
    # the longest term that reaches it gives the lowest payment.
    assert offers["working_capital"] == {
        "product_id": "working_capital",
        "amount": 5_000_000,
        "term_months": 24,
        "rate": 19.5,
        "monthly_payment": annuity_payment(5_000_000, 19.5, 24),
    }
    assert (offers["equipment"]["amount"], offers["equipment"]["term_months"]) == (15_000_000, 60)


def test_debt_load_sets_the_amount(
    client: TestClient, login_as: LoginAs, fake: FakeIntegrations
) -> None:
    [offer] = preapproved(client, login_as, "client2")["offers"]  # no room for equipment
    assert (offer["product_id"], offer["term_months"]) == ("working_capital", 24)
    assert offer["amount"] % STEP == 0
    budget = 0.5 * 12_000_000 - 5_000_000  # debt-load limit minus current liabilities, a year
    assert 12 * offer["monthly_payment"] <= budget
    assert 12 * annuity_payment(offer["amount"] + STEP, 19.5, 24) > budget
    assert len(fake.score_requests) < 40  # binary search, not a scan of every amount


@pytest.mark.parametrize(
    ("user", "reason"),
    [
        ("client3", NO_DATA),  # no financials in «Прозрачный бизнес»
        ("client4", NO_OFFER),  # overdue in the credit history: risk too high
        ("client5", NO_OFFER),  # grey zone: only an employee decides
        ("client6", NOT_ACTIVE),  # liquidating
    ],
)
def test_no_offer_says_why(
    client: TestClient, login_as: LoginAs, fake: FakeIntegrations, user: str, reason: str
) -> None:
    assert preapproved(client, login_as, user) == {"offers": [], "reason": reason}


@pytest.mark.parametrize("user", ["client1", "client2", "client7"])
def test_application_with_the_offer_is_approved_as_offered(
    app: FastAPI, client: TestClient, login_as: LoginAs, fake: FakeIntegrations, user: str
) -> None:
    headers = login_as(user)
    offers = preapproved(client, login_as, user)["offers"]
    assert offers
    ctx = PipelineContext(fake, app.state.products)
    for offer in offers:
        body = {k: offer[k] for k in ("product_id", "amount", "term_months")}
        app_id = client.post("/api/applications", json=body, headers=headers).json()["id"]
        key = {"Idempotency-Key": str(uuid4())}
        client.post(f"/api/applications/{app_id}/submit", headers=headers | key)
        run_until_idle(app.state.session_factory, ctx, datetime.now(UTC))

        detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
        assert detail["status"] == "approved"
        assert detail["decision"]["terms"] == offer


def test_only_clients_and_sources_must_answer(
    client: TestClient, login_as: LoginAs, fake: FakeIntegrations
) -> None:
    assert client.get("/api/offers/preapproved").status_code == 401
    assert client.get("/api/offers/preapproved", headers=login_as("analyst")).status_code == 403
    fake.down.add("scoring")
    response = client.get("/api/offers/preapproved", headers=login_as("client1"))
    assert response.status_code == 503
