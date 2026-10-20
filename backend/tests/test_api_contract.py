"""Smoke tests for the API contract while handlers return stub data."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.application_status import ApplicationStatus
from app.main.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_login_ok(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "client1", "password": "client1"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "client"


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "client1", "password": "nope"})
    assert response.status_code == 401


def test_products(client: TestClient) -> None:
    response = client.get("/api/products")
    assert response.status_code == 200
    assert {p["id"] for p in response.json()} == {"working_capital", "equipment"}


def test_recommend_equipment(client: TestClient) -> None:
    response = client.post("/api/products/recommend", json={"purpose_category": "equipment"})
    assert response.status_code == 200
    assert response.json()["product"]["id"] == "equipment"


def test_company_lookup_validates_inn(client: TestClient) -> None:
    assert client.get("/api/companies/lookup/7700000001").status_code == 200
    assert client.get("/api/companies/lookup/abc").status_code == 422


def test_create_and_submit(client: TestClient) -> None:
    created = client.post(
        "/api/applications",
        json={"product_id": "working_capital", "amount": 2_000_000, "term_months": 18},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["amount"] == 2_000_000

    submitted = client.post(
        f"/api/applications/{body['id']}/submit", headers={"Idempotency-Key": str(uuid4())}
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"


def test_submit_requires_idempotency_key(client: TestClient) -> None:
    response = client.post(f"/api/applications/{uuid4()}/submit")
    assert response.status_code == 422


def test_queue_filter(client: TestClient) -> None:
    response = client.get("/api/applications", params={"status": "manual_review"})
    assert response.status_code == 200
    assert [a["status"] for a in response.json()] == ["manual_review"]


def test_manual_decision(client: TestClient) -> None:
    response = client.post(
        f"/api/applications/{uuid4()}/decision",
        json={"outcome": "rejected", "comment": "Высокая долговая нагрузка"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        ("accept", {"accept": True}, "signing"),
        ("accept", {"accept": False}, "withdrawn"),
        ("withdraw", {}, "withdrawn"),
        ("sign", None, "issued"),
    ],
)
def test_client_actions(
    client: TestClient, path: str, payload: dict[str, object] | None, expected: str
) -> None:
    response = client.post(f"/api/applications/{uuid4()}/{path}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == expected


def test_feed(client: TestClient) -> None:
    response = client.get("/api/feed")
    assert response.status_code == 200
    assert {item["type"] for item in response.json()} == {"event", "news"}


def test_lifecycle_meta_covers_every_status(client: TestClient) -> None:
    response = client.get("/api/meta/lifecycle")
    assert response.status_code == 200
    assert {s["status"] for s in response.json()["statuses"]} == set(ApplicationStatus)


def test_openapi_is_published(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    assert "/api/applications/{application_id}/submit" in paths
