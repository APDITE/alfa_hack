"""Smoke tests for the API contract."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.statuses import ApplicationStatus

LoginAs = Callable[[str], dict[str, str]]


def test_products(client: TestClient) -> None:
    response = client.get("/api/products")
    assert response.status_code == 200
    assert {p["id"] for p in response.json()} == {"working_capital", "equipment"}


def test_recommend_equipment(client: TestClient) -> None:
    response = client.post("/api/products/recommend", json={"purpose_category": "equipment"})
    assert response.status_code == 200
    assert response.json()["product"]["id"] == "equipment"


def test_company_lookup(client: TestClient, login_as: LoginAs) -> None:
    headers = login_as("client1")
    response = client.get("/api/companies/lookup/7700000001", headers=headers)
    assert response.status_code == 200
    assert response.json()["legal_form"] == "OOO"
    assert client.get("/api/companies/lookup/7799999999", headers=headers).status_code == 404
    assert client.get("/api/companies/lookup/abc", headers=headers).status_code == 422


def test_company_lookup_requires_login(client: TestClient) -> None:
    assert client.get("/api/companies/lookup/7700000001").status_code == 401


def test_feed(client: TestClient, login_as: LoginAs) -> None:
    response = client.get("/api/feed", headers=login_as("client1"))
    assert response.status_code == 200
    assert response.json() == {"events": [], "unread_events": 0}


def test_lifecycle_meta_covers_every_status(client: TestClient) -> None:
    response = client.get("/api/meta/lifecycle")
    assert response.status_code == 200
    assert {s["status"] for s in response.json()["statuses"]} == set(ApplicationStatus)


def test_openapi_is_published(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    assert "/api/applications/{application_id}/submit" in paths
