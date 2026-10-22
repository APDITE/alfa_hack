from collections.abc import Callable
from uuid import uuid4

from fastapi.testclient import TestClient

from app.security import create_access_token

LoginAs = Callable[[str], dict[str, str]]


def test_login_client(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "client1", "password": "client1"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"] == body["user"] | {
        "login": "client1",
        "role": "client",
        "company_inn": "7700000001",
    }


def test_login_employee(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "analyst", "password": "analyst"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "employee"
    assert response.json()["user"]["company_inn"] is None


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "client1", "password": "nope"})
    assert response.status_code == 401


def test_login_unknown_user(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"login": "ghost", "password": "ghost"})
    assert response.status_code == 401


def test_me_with_token(client: TestClient, login_as: LoginAs) -> None:
    response = client.get("/api/auth/me", headers=login_as("client2"))
    assert response.status_code == 200
    assert response.json()["company_inn"] == "7700000002"


def test_me_without_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_garbage_token(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_token_signed_with_other_secret_is_rejected(client: TestClient) -> None:
    forged = create_access_token(
        uuid4(), "employee", "another-secret-at-least-32-bytes-long-02", 60
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
