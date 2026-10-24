"""Self-registration by INN (scenario 12): registry lookup, account rules, full credit path."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations import JSON, ExternalUnavailableError
from app.models import Company
from app.pipeline import PipelineContext, run_until_idle

NEW_INN = "7712345678"
UNKNOWN_INN = "7799999999"


class FakeRegistry:
    """Registry mock: any INN is a company except UNKNOWN_INN; no financial data."""

    def __init__(self) -> None:
        self.down = False

    def egrul(self, inn: str) -> JSON | None:
        if self.down:
            raise ExternalUnavailableError("egrul", "HTTP 503")
        if inn == UNKNOWN_INN:
            return None
        return {
            "inn": inn,
            "name": "ООО «Новая Волна»",
            "legal_form": "OOO" if len(inn) == 10 else "IP",
            "okved": "47.11",
            "registration_date": "2020-01-15",
            "region": inn[:2],
            "status": "active",
            "director": "Иванов Иван Иванович",
        }

    def transparent_business(self, inn: str) -> JSON | None:
        return None  # like the mock: unknown companies have no financials

    def bki(self, inn: str) -> JSON | None:
        return {"active_loans": 0, "overdue_count": 0, "max_overdue_days": 0}

    def score(self, payload: JSON) -> JSON:
        company = payload["company"]
        profitable = company["revenue_year"] > company["expenses_year"]
        pd = 0.04 if profitable else 0.6
        return {
            "score": pd,
            "risk_class": "low" if pd < 0.1 else "high",
            "points_total": 600,
            "factors": [],
            "model_version": "fake-1",
        }


@pytest.fixture
def registry(app: FastAPI) -> FakeRegistry:
    fake = FakeRegistry()
    app.state.integrations = fake
    return fake


def register(client: TestClient, **overrides: Any) -> Any:
    body = {"inn": NEW_INN, "full_name": "Иван Иванов", "login": "ivanov", "password": "secret-123"}
    return client.post("/api/registration", json=body | overrides)


def test_find_company_in_registry(client: TestClient, registry: FakeRegistry) -> None:
    found = client.get(f"/api/registration/company/{NEW_INN}")
    assert found.status_code == 200
    assert found.json() == found.json() | {"name": "ООО «Новая Волна»", "legal_form": "OOO"}
    assert client.get("/api/registration/company/123").status_code == 422
    assert client.get(f"/api/registration/company/{UNKNOWN_INN}").status_code == 404
    registered = client.get("/api/registration/company/7700000001")  # demo company of client1
    assert registered.status_code == 409
    assert registered.json()["detail"] == "Company is already registered"
    registry.down = True
    assert client.get(f"/api/registration/company/{NEW_INN}").status_code == 503


def test_register_signs_the_client_in(
    app: FastAPI, client: TestClient, registry: FakeRegistry
) -> None:
    response = register(client)
    assert response.status_code == 201, response.text
    body = response.json()
    expected = {"login": "ivanov", "role": "client", "company_inn": NEW_INN}
    assert body["user"] == body["user"] | expected

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["company_inn"] == NEW_INN
    login = client.post("/api/auth/login", json={"login": "ivanov", "password": "secret-123"})
    assert login.status_code == 200
    with app.state.session_factory() as session:
        company = session.get(Company, NEW_INN)
        assert company is not None and company.okved == "47.11"


@pytest.mark.parametrize(
    "overrides",
    [{"password": "short"}, {"login": "bad login"}, {"inn": "12345"}, {"full_name": ""}],
)
def test_register_validates_input(
    client: TestClient, registry: FakeRegistry, overrides: dict[str, str]
) -> None:
    assert register(client, **overrides).status_code == 422


def test_one_account_per_company_and_unique_logins(
    client: TestClient, registry: FakeRegistry
) -> None:
    assert register(client, inn="7700000001").status_code == 409  # demo company of client1
    assert register(client).status_code == 201
    assert register(client, login="another").status_code == 409  # same company again
    assert register(client, inn="771234567890", login="ivanov").status_code == 409  # login taken
    assert register(client, inn=UNKNOWN_INN, login="nobody").status_code == 404


def test_registered_company_goes_through_the_credit_pipeline(
    app: FastAPI, client: TestClient, registry: FakeRegistry
) -> None:
    """Scenario 12: no financials in the registry -> the bank asks -> the answer decides."""
    token = register(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/applications",
        json={"product_id": "working_capital", "amount": 1_000_000, "term_months": 12},
        headers=headers,
    )
    app_id = created.json()["id"]
    client.post(
        f"/api/applications/{app_id}/submit", headers=headers | {"Idempotency-Key": str(uuid4())}
    )
    ctx = PipelineContext(registry, app.state.products)

    def run() -> int:
        return run_until_idle(app.state.session_factory, ctx, datetime.now(UTC))

    run()
    card = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert card["status"] == "clarification_required"
    assert set(card["clarification"]["requested_fields"]) == {
        "revenue_year",
        "expenses_year",
        "liabilities_total",
    }

    client.put(
        f"/api/applications/{app_id}",
        json={"revenue_year": 12_000_000, "expenses_year": 9_000_000, "liabilities_total": 500_000},
        headers=headers,
    )
    run()
    card = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert card["status"] == "approved"
    assert card["decision"]["terms"]["amount"] == 1_000_000
