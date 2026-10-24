"""Client notifications: written on status changes, private, can be marked as read."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.lifecycle import transition
from app.models import Application
from app.statuses import Actor, ApplicationStatus

LoginAs = Callable[[str], dict[str, str]]
S = ApplicationStatus

TO_DECISION = (S.DATA_CHECK, S.ENRICHMENT, S.SCORING, S.CREDIT_DECISION)


def get_feed(client: TestClient, headers: dict[str, str]) -> Any:
    response = client.get("/api/feed", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def titles(body: Any) -> list[str]:
    return [event["title"] for event in body["events"]]


def submit(client: TestClient, headers: dict[str, str], amount: int = 1_500_000) -> str:
    created = client.post(
        "/api/applications",
        json={"product_id": "working_capital", "amount": amount, "term_months": 12},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    app_id: str = created.json()["id"]
    submitted = client.post(
        f"/api/applications/{app_id}/submit", headers=headers | {"Idempotency-Key": str(uuid4())}
    )
    assert submitted.status_code == 200, submitted.text
    return app_id


def move(app: FastAPI, app_id: str, *path: ApplicationStatus) -> None:
    """Drive the application through `path` the way the pipeline worker would."""
    with app.state.session_factory() as session:
        application = session.get(Application, UUID(app_id))
        assert application is not None
        for target in path:
            transition(session, application, target, Actor.SYSTEM)
        session.commit()


def test_feed_requires_a_client(client: TestClient, login_as: LoginAs) -> None:
    assert client.get("/api/feed").status_code == 401
    assert client.get("/api/feed", headers=login_as("analyst")).status_code == 403
    assert client.post("/api/feed/read", headers=login_as("analyst")).status_code == 403


def test_events_follow_status_changes(app: FastAPI, client: TestClient, login_as: LoginAs) -> None:
    headers = login_as("client1")
    app_id = submit(client, headers)
    body = get_feed(client, headers)
    assert titles(body) == ["Заявка отправлена"]
    assert body["events"][0]["application_id"] == app_id
    assert body["unread_events"] == 1

    move(app, app_id, *TO_DECISION, S.APPROVED)
    body = get_feed(client, headers)
    # Internal stages (data check, enrichment, scoring) are not announced.
    assert titles(body) == ["Заявка одобрена", "Заявка отправлена"]
    assert "1 500 000 ₽ на 12 мес." in body["events"][0]["text"]

    assert client.post("/api/feed/read", headers=headers).status_code == 204
    body = get_feed(client, headers)
    assert body["unread_events"] == 0
    assert all(event["read"] for event in body["events"])


def test_clarification_and_rejection_are_announced(
    app: FastAPI, client: TestClient, login_as: LoginAs
) -> None:
    headers = login_as("client3")
    asked = submit(client, headers, amount=800_000)
    move(app, asked, S.DATA_CHECK, S.CLARIFICATION_REQUIRED)
    rejected = submit(client, headers, amount=900_000)
    move(app, rejected, *TO_DECISION, S.REJECTED)

    body = get_feed(client, headers)
    assert titles(body) == [
        "Решение по заявке",
        "Заявка отправлена",
        "Нужны уточнения",
        "Заявка отправлена",
    ]
    assert body["unread_events"] == 4


def test_feed_is_private(client: TestClient, login_as: LoginAs) -> None:
    submit(client, login_as("client1"))
    assert get_feed(client, login_as("client2"))["events"] == []
