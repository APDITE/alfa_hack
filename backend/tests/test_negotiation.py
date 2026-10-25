"""Negotiation: rounds of proposals and offer versions, the agreement with its SHA-256, and
the history that tells the story."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.models import Agreement
from app.pipeline import PipelineContext, run_until_idle
from test_pipeline import FakeIntegrations

LoginAs = Callable[[str], dict[str, str]]
Approved = tuple[str, dict[str, str], dict[str, str]]


@pytest.fixture
def approved(app: FastAPI, client: TestClient, login_as: LoginAs) -> Approved:
    """Client1's application for 5 000 000 ₽ on 24 months, approved by the pipeline."""
    headers = login_as("client1")
    body = {"product_id": "working_capital", "amount": 5_000_000, "term_months": 24}
    app_id = client.post("/api/applications", json=body, headers=headers).json()["id"]
    client.post(
        f"/api/applications/{app_id}/submit", headers=headers | {"Idempotency-Key": str(uuid4())}
    )
    ctx = PipelineContext(FakeIntegrations(), app.state.products)
    run_until_idle(app.state.session_factory, ctx, datetime.now(UTC))
    assert client.get(f"/api/applications/{app_id}", headers=headers).json()["status"] == "approved"
    return app_id, headers, login_as("analyst")


def propose(client: TestClient, app_id: str, headers: dict[str, str], **terms: Any) -> Any:
    body = {"amount": 6_000_000, "term_months": 24, "comment": "Сезонная выручка"} | terms
    return client.post(f"/api/applications/{app_id}/proposals", json=body, headers=headers)


def counter(client: TestClient, app_id: str, analyst: dict[str, str], rate: float) -> Any:
    body = {
        "outcome": "counter_offer",
        "comment": "Готовы снизить ставку",
        "terms": {
            "product_id": "working_capital",
            "amount": 5_500_000,
            "term_months": 24,
            "rate": rate,
        },
    }
    response = client.post(f"/api/applications/{app_id}/decision", json=body, headers=analyst)
    assert response.status_code == 200, response.text
    return response.json()


def test_rounds_of_proposals_and_versions(client: TestClient, approved: Approved) -> None:
    app_id, headers, analyst = approved
    first = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert first["available_actions"] == ["accept", "propose", "decline"]
    assert [v["version"] for v in first["negotiation"]["versions"]] == [1]

    # Round 1: the client asks for more money at a lower rate.
    response = propose(client, app_id, headers, rate=17.0, comment="Выручка сезонная")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "manual_review"
    assert detail["next_step"].startswith("Кредитный специалист рассматривает ваши условия")
    assert (detail["amount"], detail["term_months"]) == (6_000_000, 24)
    proposal = detail["negotiation"]["proposals"][0]
    assert proposal["round"] == 1 and proposal["offer_version"] == 1
    assert proposal["answered"] is False and proposal["rate"] == 17.0
    assert detail["negotiation"]["rounds_left"] == 2
    step = detail["history"][-1]
    assert step["kind"] == "proposal" and "Выручка сезонная" in step["details"]

    # The employee sees the wish and answers with a new version.
    assert client.get(f"/api/applications/{app_id}", headers=analyst).json()[
        "available_actions"
    ] == ["decide"]
    counter(client, app_id, analyst, rate=18.0)
    detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert detail["status"] == "counter_offer"
    versions = detail["negotiation"]["versions"]
    assert [(v["terms"]["amount"], v["terms"]["rate"]) for v in versions] == [
        (5_000_000, 19.5),
        (5_500_000, 18.0),
    ]
    assert versions[1]["in_reply_to"] == 1
    assert all(v["total_interest"] > 0 for v in versions)
    assert detail["negotiation"]["proposals"][0]["answer_version"] == 2
    assert detail["decision"]["reason"] == "Банк предлагает новые условия в ответ на ваши."

    # Round 2: "approve" accepts the client's terms, the desired rate included.
    propose(client, app_id, headers, rate=17.5, comment="Встретимся посередине")
    decided = client.post(
        f"/api/applications/{app_id}/decision",
        json={"outcome": "approved", "comment": "Согласовано"},
        headers=analyst,
    ).json()
    assert decided["decision"]["terms"]["rate"] == 17.5
    detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert detail["decision"]["reason"] == "Банк принял ваши условия."
    assert [v["version"] for v in detail["negotiation"]["versions"]] == [1, 2, 3]
    kinds = [(h["kind"], h["to_status"]) for h in detail["history"]]
    assert kinds[-4:] == [
        ("proposal", "manual_review"),
        ("offer", "counter_offer"),
        ("proposal", "manual_review"),
        ("offer", "approved"),
    ]
    assert detail["history"][-1]["details"].startswith("Версия 3: 6 000 000 ₽ на 24 мес., 17,5%")


def test_rounds_run_out(client: TestClient, approved: Approved) -> None:
    app_id, headers, analyst = approved
    for round_number in range(1, 4):
        assert propose(client, app_id, headers, rate=17.0).status_code == 200
        counter(client, app_id, analyst, rate=19.0 - round_number / 10)
    detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert detail["negotiation"]["rounds_left"] == 0
    assert "propose" not in detail["available_actions"]
    response = propose(client, app_id, headers, rate=17.0)
    assert response.status_code == 409
    assert response.json()["detail"] == "No negotiation rounds left"


@pytest.mark.parametrize(
    ("terms", "code"),
    [
        ({"amount": 5_000_000, "term_months": 24}, 422),  # the bank's own terms
        ({"amount": 5_000_000, "term_months": 24, "rate": 19.5}, 422),
        ({"amount": 50_000_000}, 422),  # above the product's limit
        ({"term_months": 600}, 422),
        ({"comment": ""}, 422),
        ({"rate": 0}, 422),
    ],
)
def test_proposal_validation(
    client: TestClient, approved: Approved, terms: dict[str, Any], code: int
) -> None:
    app_id, headers, _ = approved
    assert propose(client, app_id, headers, **terms).status_code == code


def test_only_the_client_and_only_for_an_offer(
    client: TestClient, approved: Approved, login_as: LoginAs
) -> None:
    app_id, headers, analyst = approved
    assert propose(client, app_id, analyst).status_code == 403
    assert propose(client, app_id, login_as("client2")).status_code == 403
    assert propose(client, app_id, headers).status_code == 200
    # Waiting for the employee: no second proposal.
    assert propose(client, app_id, headers, amount=4_000_000).status_code == 409


def test_feed_tells_the_client_their_terms_went_to_the_bank(
    client: TestClient, approved: Approved
) -> None:
    app_id, headers, _ = approved
    propose(client, app_id, headers)
    titles = [e["title"] for e in client.get("/api/feed", headers=headers).json()["events"]]
    assert titles[0] == "Ваши условия переданы банку"


def test_agreement_is_signed_by_its_hash(client: TestClient, approved: Approved) -> None:
    app_id, headers, analyst = approved
    accepted = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": True}, headers=headers
    ).json()
    assert accepted["status"] == "signing"
    [summary] = accepted["agreements"]
    assert summary["version"] == 1 and summary["signed_at"] is None
    assert summary["reason"] == "Клиент принял условия"

    document = client.get(f"/api/applications/{app_id}/agreement", headers=headers).json()
    assert document["verified"] is True
    assert hashlib.sha256(document["text"].encode()).hexdigest() == summary["sha256"]
    first = accepted["schedule"]["payments"][0]
    due = datetime.fromisoformat(first["due_date"]).strftime("%d.%m.%Y")
    assert f"1 | {due} | " in document["text"]
    assert "Сумма кредита: 5 000 000 ₽." in document["text"]
    # Without a chosen day, payments fall on the day of the issue.
    assert accepted["schedule"]["payment_day"] == min(datetime.now(UTC).day, 28)
    # The employee reads the same document.
    employee = client.get(f"/api/applications/{app_id}/agreement", headers=analyst).json()
    assert employee["sha256"] == summary["sha256"]

    wrong = client.post(
        f"/api/applications/{app_id}/sign", json={"agreement_sha256": "0" * 64}, headers=headers
    )
    assert wrong.status_code == 409
    issued = client.post(
        f"/api/applications/{app_id}/sign",
        json={"agreement_sha256": summary["sha256"]},
        headers=headers,
    ).json()
    assert issued["status"] == "issued"
    assert issued["agreements"][0]["signed_at"] is not None
    last = issued["history"][-1]
    assert last["kind"] == "agreement" and summary["sha256"][:16] in last["details"]


def test_new_payment_day_makes_a_new_version(client: TestClient, approved: Approved) -> None:
    app_id, headers, _ = approved
    accepted = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": True}, headers=headers
    ).json()
    old = client.get(f"/api/applications/{app_id}/agreement", headers=headers).json()
    calendar = client.post(
        f"/api/applications/{app_id}/cash-calendar/preview", json={}, headers=headers
    ).json()["calendar"]
    day = 6 if accepted["schedule"]["payment_day"] == 5 else 5
    saved = client.put(
        f"/api/applications/{app_id}/cash-calendar",
        json={"calendar": calendar, "payment_day": day},
        headers=headers,
    ).json()
    assert [a["version"] for a in saved["agreements"]] == [1, 2]
    new = saved["agreements"][1]
    assert new["reason"] == "Изменилась дата платежа" and new["sha256"] != old["sha256"]
    reissue = [h for h in saved["history"] if h["from_status"] == h["to_status"] == "signing"]
    assert reissue and reissue[0]["kind"] == "agreement"

    stale = client.post(
        f"/api/applications/{app_id}/sign",
        json={"agreement_sha256": old["sha256"]},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "The agreement has changed, review the new version"
    signed = client.post(
        f"/api/applications/{app_id}/sign",
        json={"agreement_sha256": new["sha256"]},
        headers=headers,
    )
    assert signed.status_code == 200 and signed.json()["status"] == "issued"
    # The old version stays as it was: its text still matches its hash.
    first = client.get(f"/api/applications/{app_id}/agreement?version=1", headers=headers).json()
    assert first["verified"] is True and first["signed_at"] is None


def test_agreement_from_another_day_is_made_again(
    app: FastAPI, client: TestClient, approved: Approved
) -> None:
    app_id, headers, _ = approved
    accepted = client.post(
        f"/api/applications/{app_id}/accept", json={"accept": True}, headers=headers
    ).json()
    old_hash = accepted["agreements"][0]["sha256"]
    with app.state.session_factory() as session:
        session.execute(update(Agreement).values(created_at=datetime.now(UTC) - timedelta(days=3)))
        session.commit()
    response = client.post(
        f"/api/applications/{app_id}/sign", json={"agreement_sha256": old_hash}, headers=headers
    )
    assert response.status_code == 409
    detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert [a["reason"] for a in detail["agreements"]] == [
        "Клиент принял условия",
        "Новая дата выдачи",
    ]
    # Without a hash (the API without a screen) the latest version is signed.
    assert client.post(f"/api/applications/{app_id}/sign", headers=headers).status_code == 200


def test_no_agreement_before_the_offer_is_accepted(client: TestClient, approved: Approved) -> None:
    app_id, headers, _ = approved
    response = client.get(f"/api/applications/{app_id}/agreement", headers=headers)
    assert response.status_code == 404
    assert client.post(f"/api/applications/{app_id}/sign", headers=headers).status_code == 409
