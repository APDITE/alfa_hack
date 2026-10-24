"""Pipeline worker end to end on the scenarios from docs/scenarios.md (fake external services)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.integrations import JSON, ExternalUnavailableError
from app.models import JobStatus, PipelineJob
from app.pipeline import MAX_ATTEMPTS, PipelineContext, backoff, months_between, run_until_idle

LoginAs = Callable[[str], dict[str, str]]


def _egrul(inn: str, registered: str, status: str = "active") -> JSON:
    return {"inn": inn, "status": status, "registration_date": registered}


def _tb(revenue: int, expenses: int, liabilities: int) -> JSON:
    return {"revenue_year": revenue, "expenses_year": expenses, "liabilities_total": liabilities}


def _bki(loans: int = 1, overdue_days: int = 0) -> JSON:
    return {
        "active_loans": loans,
        "overdue_count": 1 if overdue_days else 0,
        "max_overdue_days": overdue_days,
    }


# INN -> (registry, financials or None, credit history, PD returned by the fake scoring)
DATA: dict[str, tuple[JSON | None, JSON | None, JSON | None, float]] = {
    "7700000001": (
        _egrul("7700000001", "2019-03-15"),
        _tb(24_000_000, 21_000_000, 2_000_000),
        _bki(),
        0.05,
    ),
    "7700000002": (
        _egrul("7700000002", "2020-06-01"),
        _tb(12_000_000, 10_000_000, 5_000_000),
        _bki(),
        0.08,
    ),
    "7700000003": (_egrul("7700000003", "2021-09-10"), None, _bki(0), 0.06),
    "7700000004": (
        _egrul("7700000004", "2018-02-20"),
        _tb(30_000_000, 28_000_000, 9_000_000),
        _bki(4, 120),
        0.32,
    ),
    "7700000005": (
        _egrul("7700000005", "2017-04-05"),
        _tb(20_000_000, 19_000_000, 4_000_000),
        _bki(3),
        0.15,
    ),
    "7700000006": (
        _egrul("7700000006", "2016-11-11", "liquidating"),
        _tb(5_000_000, 6_000_000, 1_000_000),
        _bki(),
        0.20,
    ),
    "7700000007": (
        _egrul("7700000007", "2020-01-20"),
        _tb(30_000_000, 26_000_000, 1_000_000),
        _bki(),
        0.10,
    ),
    "7700000008": (
        _egrul("7700000008", "2026-02-01"),
        _tb(10_000_000, 8_000_000, 0),
        _bki(0),
        0.07,
    ),
}


class FakeIntegrations:
    def __init__(self) -> None:
        self.down: set[str] = set()
        self.score_requests: list[JSON] = []

    def _check(self, service: str) -> None:
        if service in self.down:
            raise ExternalUnavailableError(service, "HTTP 503")

    def egrul(self, inn: str) -> JSON | None:
        self._check("egrul")
        return DATA[inn][0] if inn in DATA else None

    def transparent_business(self, inn: str) -> JSON | None:
        self._check("transparent_business")
        return DATA[inn][1] if inn in DATA else None

    def bki(self, inn: str) -> JSON | None:
        self._check("bki")
        return DATA[inn][2] if inn in DATA else None

    def score(self, payload: JSON) -> JSON:
        self._check("scoring")
        self.score_requests.append(payload)
        pd = DATA[payload["company"]["inn"]][3]
        risk = "low" if pd < 0.10 else "medium" if pd < 0.25 else "high"
        return {
            "score": pd,
            "risk_class": risk,
            "points_total": 600,
            "factors": [
                {
                    "name": "credit_history",
                    "points": 120,
                    "impact": "decreases_risk",
                    "comment": "ok",
                }
            ],
            "model_version": "fake-1",
        }


@pytest.fixture
def fake() -> FakeIntegrations:
    return FakeIntegrations()


@pytest.fixture
def run(app: FastAPI, fake: FakeIntegrations) -> Callable[..., int]:
    ctx = PipelineContext(fake, app.state.products)

    def _run(now: datetime | None = None) -> int:
        return run_until_idle(app.state.session_factory, ctx, now or datetime.now(UTC))

    return _run


def apply(
    client: TestClient, login_as: LoginAs, user: str, product: str, amount: int, term: int
) -> tuple[str, dict[str, str]]:
    headers = login_as(user)
    created = client.post(
        "/api/applications",
        json={"product_id": product, "amount": amount, "term_months": term},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    app_id = created.json()["id"]
    submitted = client.post(
        f"/api/applications/{app_id}/submit", headers=headers | {"Idempotency-Key": str(uuid4())}
    )
    assert submitted.status_code == 200, submitted.text
    return app_id, headers


def card(client: TestClient, app_id: str, headers: dict[str, str]) -> Any:
    return client.get(f"/api/applications/{app_id}", headers=headers).json()


def statuses(body: Any) -> list[str]:
    return [h["to_status"] for h in body["history"]]


# --- Scenarios -----------------------------------------------------------------------


def test_scenario_1_strong_company_is_approved(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, headers = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    assert run() == 5
    body = card(client, app_id, headers)
    assert body["status"] == "approved"
    assert statuses(body) == [
        "draft",
        "submitted",
        "data_check",
        "enrichment",
        "scoring",
        "credit_decision",
        "approved",
    ]
    assert body["decision"]["rule"] == "approved"
    assert body["decision"]["terms"]["amount"] == 1_500_000
    assert body["decision"]["terms"]["rate"] == 19.5


def test_scenario_2_debt_load_gives_counter_offer(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, headers = apply(client, login_as, "client2", "working_capital", 4_000_000, 6)
    run()
    body = card(client, app_id, headers)
    assert body["status"] == "counter_offer"
    assert body["decision"]["rule"].startswith("debt_load")
    terms = body["decision"]["terms"]
    assert terms["term_months"] > 6 or terms["amount"] < 4_000_000


def test_scenario_3_missing_financials_then_client_answers(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, headers = apply(client, login_as, "client3", "working_capital", 800_000, 12)
    run()
    body = card(client, app_id, headers)
    assert body["status"] == "clarification_required"
    assert set(body["clarification"]["requested_fields"]) == {
        "revenue_year",
        "expenses_year",
        "liabilities_total",
    }
    assert "выручка" in body["clarification"]["message"]

    answered = client.put(
        f"/api/applications/{app_id}",
        json={
            "revenue_year": 9_000_000,
            "expenses_year": 7_500_000,
            "liabilities_total": 500_000,
            "clarification_answer": "Данные за последние 12 месяцев",
        },
        headers=headers,
    )
    assert answered.json()["status"] == "data_check"
    run()
    assert card(client, app_id, headers)["status"] == "approved"


def test_scenario_4_overdue_is_rejected(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, headers = apply(client, login_as, "client4", "working_capital", 3_000_000, 12)
    run()
    body = card(client, app_id, headers)
    assert body["status"] == "rejected"
    assert body["decision"]["rule"] == "pd_too_high"


def test_scenario_5_grey_zone_goes_to_employee(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, _ = apply(client, login_as, "client5", "working_capital", 2_000_000, 12)
    run()
    analyst = login_as("analyst")
    body = card(client, app_id, analyst)
    assert body["status"] == "manual_review"
    assert body["available_actions"] == ["decide"]
    assert body["risk_class"] == "medium"
    assert "pd_grey_zone" in body["history"][-1]["comment"]
    assert {c["type"] for c in body["checks"]} >= {"completeness", "egrul", "bki"}


def test_scenario_6_liquidating_company_is_rejected_without_scoring(
    client: TestClient, login_as: LoginAs, run: Callable[..., int], fake: FakeIntegrations
) -> None:
    app_id, headers = apply(client, login_as, "client6", "working_capital", 1_000_000, 12)
    run()
    body = card(client, app_id, headers)
    assert body["status"] == "rejected"
    assert body["decision"]["rule"] == "registry_liquidating"
    assert fake.score_requests == []


def test_scenario_7_unavailable_bureau_is_retried(
    app: FastAPI,
    client: TestClient,
    login_as: LoginAs,
    run: Callable[..., int],
    fake: FakeIntegrations,
) -> None:
    fake.down.add("bki")
    app_id, headers = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    now = datetime.now(UTC)
    run(now)

    body = card(client, app_id, headers)
    assert body["status"] == "enrichment"
    assert body["waiting_external"] is True
    assert body["next_step"].startswith("Ждём ответ от внешней службы")

    run(now + timedelta(seconds=1))  # backoff not over yet: nothing happens
    assert card(client, app_id, headers)["status"] == "enrichment"

    fake.down.clear()
    run(now + backoff(1) + timedelta(seconds=1))
    body = card(client, app_id, headers)
    assert body["status"] == "approved"
    assert body["waiting_external"] is False


def test_scenario_7_gives_up_to_manual_review(
    app: FastAPI,
    client: TestClient,
    login_as: LoginAs,
    run: Callable[..., int],
    fake: FakeIntegrations,
) -> None:
    fake.down.add("bki")
    app_id, _ = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    now = datetime.now(UTC)
    for _ in range(MAX_ATTEMPTS + 2):
        run(now)
        now += timedelta(minutes=2)

    body = card(client, app_id, login_as("analyst"))
    assert body["status"] == "manual_review"
    unavailable = [c for c in body["checks"] if c["outcome"] == "unavailable"]
    assert unavailable and unavailable[0]["attempt"] == MAX_ATTEMPTS


def test_scenario_8_same_score_different_products(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    wc_id, headers = apply(client, login_as, "client7", "working_capital", 2_000_000, 24)
    eq_id, _ = apply(client, login_as, "client7", "equipment", 2_000_000, 24)
    run()
    assert card(client, wc_id, headers)["status"] == "approved"
    assert card(client, eq_id, headers)["status"] == "manual_review"


def test_scenario_11_young_business_gets_other_product(
    client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    app_id, headers = apply(client, login_as, "client8", "equipment", 2_000_000, 24)
    run()
    body = card(client, app_id, headers)
    assert body["status"] == "counter_offer"
    assert body["decision"]["rule"] == "business_age_alternative"
    assert body["decision"]["terms"]["product_id"] == "working_capital"


def test_scoring_request_follows_contract(
    client: TestClient, login_as: LoginAs, run: Callable[..., int], fake: FakeIntegrations
) -> None:
    apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    run()
    (payload,) = fake.score_requests
    assert payload["application"] == {
        "product_id": "working_capital",
        "amount": 1_500_000,
        "term_months": 12,
    }
    assert payload["company"]["revenue_year"] == 24_000_000
    assert payload["company"]["okved"] == "47.11"
    assert payload["credit_history"] == {
        "active_loans": 1,
        "overdue_count": 0,
        "max_overdue_days": 0,
    }


def test_unavailable_scoring_ends_in_manual_review(
    client: TestClient, login_as: LoginAs, run: Callable[..., int], fake: FakeIntegrations
) -> None:
    fake.down.add("scoring")
    app_id, _ = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    now = datetime.now(UTC)
    for _ in range(MAX_ATTEMPTS + 2):
        run(now)
        now += timedelta(minutes=2)
    body = card(client, app_id, login_as("analyst"))
    assert body["status"] == "manual_review"
    assert "scoring_unavailable" in body["history"][-1]["comment"]


def test_jobs_are_closed(
    app: FastAPI, client: TestClient, login_as: LoginAs, run: Callable[..., int]
) -> None:
    apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    run()
    with app.state.session_factory() as session:
        jobs = session.scalars(select(PipelineJob)).all()
        assert len(jobs) == 5
        assert {j.status for j in jobs} == {JobStatus.DONE}


@pytest.mark.parametrize(
    ("start", "end", "months"),
    [
        ("2026-02-01", "2026-10-22", 8),
        ("2025-10-23", "2026-10-22", 11),
        ("2025-10-22", "2026-10-22", 12),
    ],
)
def test_months_between(start: str, end: str, months: int) -> None:
    from datetime import date

    assert months_between(date.fromisoformat(start), date.fromisoformat(end)) == months


# --- Unexpected errors ----------------------------------------------------------------------


def crash_scoring(fake: FakeIntegrations, times: int) -> None:
    """Make the fake scoring raise a non-network error `times` times, then answer."""
    original = fake.score
    left = {"n": times}

    def score(payload: JSON) -> JSON:
        if left["n"] > 0:
            left["n"] -= 1
            raise RuntimeError("bug in the scoring adapter")
        return original(payload)

    fake.score = score  # type: ignore[method-assign]


def test_unexpected_error_is_retried(
    client: TestClient, login_as: LoginAs, run: Callable[..., int], fake: FakeIntegrations
) -> None:
    crash_scoring(fake, times=1)
    app_id, headers = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    run()
    assert card(client, app_id, headers)["status"] == "scoring"
    run(datetime.now(UTC) + timedelta(minutes=2))
    assert card(client, app_id, headers)["status"] == "approved"


def test_repeated_errors_hand_the_application_to_an_employee(
    app: FastAPI,
    client: TestClient,
    login_as: LoginAs,
    run: Callable[..., int],
    fake: FakeIntegrations,
) -> None:
    crash_scoring(fake, times=100)
    app_id, headers = apply(client, login_as, "client1", "working_capital", 1_500_000, 12)
    for minutes in range(0, 10):
        run(datetime.now(UTC) + timedelta(minutes=minutes))
    body = card(client, app_id, headers)
    assert body["status"] == "manual_review"
    assert statuses(body)[-2:] == ["scoring", "manual_review"]
    assert "Техническая ошибка" in body["history"][-1]["comment"]
    with app.state.session_factory() as session:
        jobs = session.scalars(select(PipelineJob).where(PipelineJob.stage == "scoring")).all()
        assert [(j.status, j.attempt) for j in jobs] == [(JobStatus.FAILED, 3)]
