"""Smoke tests for the API contract while handlers return stub data."""

from fastapi.testclient import TestClient

from app.statuses import ApplicationStatus


def test_products(client: TestClient) -> None:
    response = client.get("/api/products")
    assert response.status_code == 200
    assert {p["id"] for p in response.json()} == {"working_capital", "equipment"}


def test_recommend_equipment(client: TestClient) -> None:
    response = client.post("/api/products/recommend", json={"purpose_category": "equipment"})
    assert response.status_code == 200
    assert response.json()["product"]["id"] == "equipment"


def test_company_lookup(client: TestClient) -> None:
    response = client.get("/api/companies/lookup/7700000001")
    assert response.status_code == 200
    assert response.json()["legal_form"] == "OOO"
    assert client.get("/api/companies/lookup/7799999999").status_code == 404
    assert client.get("/api/companies/lookup/abc").status_code == 422


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
