"""Applications on the database: access rules, client and employee actions (spec, section 14)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models import Application, PipelineJob, ScoreRecord
from app.statuses import ApplicationStatus

LoginAs = Callable[[str], dict[str, str]]
S = ApplicationStatus

GOOD_DRAFT = {
    "product_id": "working_capital",
    "purpose_category": "inventory",
    "amount": 1_500_000,
    "term_months": 12,
    "purpose": "Закупка товара к сезону",
}


def create_draft(client: TestClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/applications", json=GOOD_DRAFT | overrides, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def submit(client: TestClient, headers: dict[str, str], app_id: str, key: str | None = None) -> Any:
    return client.post(
        f"/api/applications/{app_id}/submit",
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
    )


def force_status(app: FastAPI, app_id: str, status: ApplicationStatus) -> None:
    """Put an application where the (not yet written) pipeline worker would leave it."""
    with app.state.session_factory() as session:
        application = session.get(Application, UUID(app_id))
        assert application is not None
        application.status = status
        session.commit()


@pytest.fixture
def client1(login_as: LoginAs) -> dict[str, str]:
    return login_as("client1")


@pytest.fixture
def analyst(login_as: LoginAs) -> dict[str, str]:
    return login_as("analyst")


# --- Drafts ---------------------------------------------------------------------


def test_create_draft(client: TestClient, client1: dict[str, str]) -> None:
    body = create_draft(client, client1)
    assert body["status"] == "draft"
    assert body["stage_label"] == "Заполняете заявку"
    assert body["company_inn"] == "7700000001"
    assert body["company"]["name"] == "ООО «Северный ветер»"
    assert body["available_actions"] == ["edit", "submit", "withdraw"]
    assert [h["to_status"] for h in body["history"]] == ["draft"]
    assert body["checks"] == [] and body["score"] is None


def test_draft_is_saved_and_editable(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1, amount=None)
    response = client.put(
        f"/api/applications/{draft['id']}", json={"amount": 2_000_000}, headers=client1
    )
    assert response.status_code == 200
    again = client.get(f"/api/applications/{draft['id']}", headers=client1).json()
    assert again["amount"] == 2_000_000
    assert again["purpose"] == GOOD_DRAFT["purpose"]


def test_employee_cannot_create(client: TestClient, analyst: dict[str, str]) -> None:
    response = client.post("/api/applications", json=GOOD_DRAFT, headers=analyst)
    assert response.status_code == 403


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/applications").status_code == 401
    assert client.post("/api/applications", json=GOOD_DRAFT).status_code == 401


# --- Submit -----------------------------------------------------------------------


def test_submit_moves_to_bank_and_queues_job(
    app: FastAPI, client: TestClient, client1: dict[str, str]
) -> None:
    draft = create_draft(client, client1)
    response = submit(client, client1, draft["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["client_stage"] == "in_review"
    assert body["submitted_at"] is not None
    assert [h["to_status"] for h in body["history"]] == ["draft", "submitted"]

    with app.state.session_factory() as session:
        jobs = session.scalars(select(PipelineJob)).all()
        assert [(str(j.application_id), j.stage) for j in jobs] == [(draft["id"], S.SUBMITTED)]


def test_submit_is_idempotent(app: FastAPI, client: TestClient, client1: dict[str, str]) -> None:
    """Scenario 9: double submit with one key -> one application, one job."""
    draft = create_draft(client, client1)
    key = str(uuid4())
    first = submit(client, client1, draft["id"], key)
    second = submit(client, client1, draft["id"], key)
    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "submitted"
    assert len(second.json()["history"]) == 2

    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PipelineJob)) == 1


def test_submit_twice_with_new_key_conflicts(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    assert submit(client, client1, draft["id"]).status_code == 200
    assert submit(client, client1, draft["id"]).status_code == 409


def test_submit_requires_key(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    response = client.post(f"/api/applications/{draft['id']}/submit", headers=client1)
    assert response.status_code == 422


def test_submit_validates_product_limits(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1, amount=50_000_000)
    response = submit(client, client1, draft["id"])
    assert response.status_code == 422
    assert "amount" in response.text


def test_submit_requires_amount_and_term(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1, amount=None, term_months=None)
    response = submit(client, client1, draft["id"])
    assert response.status_code == 422
    assert "amount is required" in response.text and "term_months is required" in response.text


# --- Access -------------------------------------------------------------------------


def test_foreign_application_is_forbidden(
    client: TestClient, client1: dict[str, str], login_as: LoginAs
) -> None:
    """Scenario 10: client2 cannot see or touch client1's application."""
    draft = create_draft(client, client1)
    client2 = login_as("client2")
    assert client.get(f"/api/applications/{draft['id']}", headers=client2).status_code == 403
    assert submit(client, client2, draft["id"]).status_code == 403
    assert client.get("/api/applications", headers=client2).json() == []


def test_unknown_application_is_404(client: TestClient, client1: dict[str, str]) -> None:
    assert client.get(f"/api/applications/{uuid4()}", headers=client1).status_code == 404


def test_employee_queue_hides_drafts(
    client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    draft = create_draft(client, client1)
    other = create_draft(client, client1)
    submit(client, client1, other["id"])

    queue = client.get("/api/applications", headers=analyst).json()
    assert [a["id"] for a in queue] == [other["id"]]
    assert client.get(f"/api/applications/{draft['id']}", headers=analyst).status_code == 404

    mine = client.get("/api/applications", headers=client1).json()
    assert {a["id"] for a in mine} == {draft["id"], other["id"]}


def test_queue_filters(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    a = create_draft(client, client1)
    b = create_draft(client, client1)
    submit(client, client1, a["id"])
    submit(client, client1, b["id"])
    force_status(app, b["id"], S.MANUAL_REVIEW)

    manual = client.get("/api/applications?status=manual_review", headers=analyst).json()
    assert [x["id"] for x in manual] == [b["id"]]
    in_review = client.get("/api/applications?client_stage=in_review", headers=analyst).json()
    assert {x["id"] for x in in_review} == {a["id"], b["id"]}


# --- Employee decision and the client's answer ------------------------------------------


def to_manual_review(app: FastAPI, client: TestClient, headers: dict[str, str]) -> str:
    draft = create_draft(client, headers)
    submit(client, headers, draft["id"])
    force_status(app, draft["id"], S.MANUAL_REVIEW)
    return str(draft["id"])


def test_full_happy_path_with_manual_approval(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    card = client.get(f"/api/applications/{app_id}", headers=analyst).json()
    assert card["available_actions"] == ["decide"]

    decided = client.post(
        f"/api/applications/{app_id}/decision",
        json={"outcome": "approved", "comment": "Документы в порядке"},
        headers=analyst,
    )
    assert decided.status_code == 200, decided.text
    terms = decided.json()["decision"]["terms"]
    assert terms["rate"] == 19.5 and terms["monthly_payment"] > 0

    client_view = client.get(f"/api/applications/{app_id}", headers=client1).json()
    assert client_view["status"] == "approved"
    assert client_view["available_actions"] == ["accept", "decline"]
    assert client_view["decision"]["comment"] is None  # internal comment stays in the bank

    accepted = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": True}, headers=client1
    )
    assert accepted.json()["status"] == "signing"
    signed = client.post(f"/api/applications/{app_id}/sign", headers=client1)
    assert signed.json()["status"] == "issued"
    assert signed.json()["stage_label"] == "Готово"
    assert [h["to_status"] for h in signed.json()["history"]] == [
        "draft",
        "submitted",
        "approved",
        "signing",
        "issued",
    ]


def test_counter_offer_applies_new_terms_on_accept(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    response = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "outcome": "counter_offer",
            "comment": "Нагрузка высокая, предлагаем дольше",
            "terms": {"product_id": "working_capital", "amount": 1_000_000, "term_months": 24},
        },
        headers=analyst,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "counter_offer"

    accepted = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": True}, headers=client1
    )
    assert accepted.json()["amount"] == 1_000_000
    assert accepted.json()["term_months"] == 24


def test_counter_offer_needs_terms_in_product_range(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    url = f"/api/applications/{app_id}/decision"
    no_terms = {"outcome": "counter_offer", "comment": "x"}
    assert client.post(url, json=no_terms, headers=analyst).status_code == 422
    bad = no_terms | {"terms": {"product_id": "working_capital", "amount": 1, "term_months": 12}}
    assert client.post(url, json=bad, headers=analyst).status_code == 422


def test_decline_offer_withdraws(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    client.post(
        f"/api/applications/{app_id}/decision",
        json={"outcome": "approved", "comment": "ok"},
        headers=analyst,
    )
    declined = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": False}, headers=client1
    )
    assert declined.json()["status"] == "withdrawn"


def test_rejection(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    response = client.post(
        f"/api/applications/{app_id}/decision",
        json={"outcome": "rejected", "comment": "Высокая долговая нагрузка"},
        headers=analyst,
    )
    body = response.json()
    assert body["status"] == "rejected"
    assert body["decision"]["reason"] == "Высокая долговая нагрузка"
    assert (
        client.get(f"/api/applications/{app_id}", headers=client1).json()["available_actions"] == []
    )


def test_clarification_round_trip(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    """Scenario 3 (manual variant): bank asks, client answers, the application goes back."""
    app_id = to_manual_review(app, client, client1)
    asked = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "outcome": "clarification",
            "comment": "Укажите выручку за последние 12 месяцев",
            "requested_fields": ["revenue_year"],
        },
        headers=analyst,
    )
    assert asked.json()["status"] == "clarification_required"

    seen = client.get(f"/api/applications/{app_id}", headers=client1).json()
    assert seen["stage_label"] == "Нужно ваше действие"
    assert seen["clarification"]["requested_fields"] == ["revenue_year"]
    assert seen["available_actions"] == ["answer_clarification", "withdraw"]

    answered = client.put(
        f"/api/applications/{app_id}",
        json={"revenue_year": 24_000_000, "clarification_answer": "Выручка 24 млн"},
        headers=client1,
    )
    body = answered.json()
    assert body["status"] == "data_check"
    assert body["revenue_year"] == 24_000_000
    assert body["clarification"]["answer"] == "Выручка 24 млн"


def test_employee_decides_only_in_manual_review(
    client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    draft = create_draft(client, client1)
    submit(client, client1, draft["id"])
    response = client.post(
        f"/api/applications/{draft['id']}/decision",
        json={"outcome": "approved", "comment": "x"},
        headers=analyst,
    )
    assert response.status_code == 409


def test_client_cannot_decide(app: FastAPI, client: TestClient, client1: dict[str, str]) -> None:
    app_id = to_manual_review(app, client, client1)
    response = client.post(
        f"/api/applications/{app_id}/decision",
        json={"outcome": "approved", "comment": "сам себе одобрю"},
        headers=client1,
    )
    assert response.status_code == 403


# --- Client actions out of turn ---------------------------------------------------


def test_withdraw_draft(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    response = client.post(f"/api/applications/{draft['id']}/withdraw", json={}, headers=client1)
    assert response.json()["status"] == "withdrawn"


def test_cannot_withdraw_while_bank_works(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    submit(client, client1, draft["id"])
    response = client.post(f"/api/applications/{draft['id']}/withdraw", json={}, headers=client1)
    assert response.status_code == 409


def test_cannot_sign_a_draft(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    assert client.post(f"/api/applications/{draft['id']}/sign", headers=client1).status_code == 409


def test_cannot_edit_after_submit(client: TestClient, client1: dict[str, str]) -> None:
    draft = create_draft(client, client1)
    submit(client, client1, draft["id"])
    response = client.put(f"/api/applications/{draft['id']}", json={"amount": 1}, headers=client1)
    assert response.status_code == 409


def test_employee_sees_risk_class(
    app: FastAPI, client: TestClient, client1: dict[str, str], analyst: dict[str, str]
) -> None:
    app_id = to_manual_review(app, client, client1)
    with app.state.session_factory() as session:
        session.add(
            ScoreRecord(
                application_id=UUID(app_id),
                pd=0.15,
                risk_class="medium",
                points_total=480,
                factors=[
                    {
                        "name": "debt_load",
                        "points": 30,
                        "impact": "increases_risk",
                        "comment": "Высокая нагрузка",
                    }
                ],
                model_version="scorecard-0.1.0",
            )
        )
        session.commit()
    employee = client.get(f"/api/applications/{app_id}", headers=analyst).json()
    assert employee["risk_class"] == "medium"
    assert employee["score"]["factors"][0]["name"] == "debt_load"
    client_view = client.get(f"/api/applications/{app_id}", headers=client1).json()
    assert client_view["score"] is None and client_view["risk_class"] is None
