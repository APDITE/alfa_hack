"""Pipeline health: Prometheus metrics and alerts for the bank workplace."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Application, CheckResultRecord, JobStatus, PipelineJob
from app.statuses import ApplicationStatus

LoginAs = Callable[[str], dict[str, str]]


def submit(client: TestClient, headers: dict[str, str]) -> str:
    created = client.post(
        "/api/applications",
        json={"product_id": "working_capital", "amount": 1_500_000, "term_months": 12},
        headers=headers,
    )
    app_id: str = created.json()["id"]
    key = {"Idempotency-Key": str(uuid4())}
    client.post(f"/api/applications/{app_id}/submit", headers=headers | key)
    return app_id


def summary(client: TestClient, headers: dict[str, str]) -> Any:
    response = client.get("/api/ops/summary", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_is_for_employees(client: TestClient, login_as: LoginAs) -> None:
    assert client.get("/api/ops/summary").status_code == 401
    assert client.get("/api/ops/summary", headers=login_as("client1")).status_code == 403
    body = summary(client, login_as("analyst"))
    assert body["status"] == "ok" and body["alerts"] == []


def test_metrics_expose_the_pipeline(client: TestClient, login_as: LoginAs) -> None:
    submit(client, login_as("client1"))
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert 'credit_applications{status="submitted"} 1' in text
    assert 'credit_pipeline_jobs{state="pending"} 1' in text
    assert "credit_pipeline_ready_jobs 1" in text
    assert "# TYPE credit_decisions_total counter" in text
    assert "/metrics" not in client.get("/api/openapi.json").json()["paths"]


def test_stalled_queue_is_critical(app: FastAPI, client: TestClient, login_as: LoginAs) -> None:
    submit(client, login_as("client1"))
    with app.state.session_factory() as session:
        job = session.scalars(select(PipelineJob)).one()
        job.run_after = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    body = summary(client, login_as("analyst"))
    assert body["status"] == "critical"
    assert "воркер" in body["alerts"][0]["text"]
    assert body["oldest_ready_seconds"] >= 290


def test_external_outage_and_failures_are_warnings(
    app: FastAPI, client: TestClient, login_as: LoginAs
) -> None:
    waiting = submit(client, login_as("client1"))
    crashed = submit(client, login_as("client2"))
    with app.state.session_factory() as session:
        application = session.get(Application, UUID(waiting))
        assert application is not None
        application.status = ApplicationStatus.ENRICHMENT
        application.waiting_external = True
        session.add(
            CheckResultRecord(
                application_id=application.id, type="bki", outcome="unavailable", summary="x"
            )
        )
        job = session.scalars(
            select(PipelineJob).where(PipelineJob.application_id == UUID(crashed))
        ).one()
        job.status = JobStatus.FAILED
        session.commit()

    body = summary(client, login_as("analyst"))
    texts = " | ".join(alert["text"] for alert in body["alerts"])
    assert body["status"] == "warning"
    assert "Ждут ответа (БКИ): 1 заявка" in texts
    assert "Технические ошибки этапов за сутки: 1" in texts
    assert body["waiting_external"] == 1 and body["failed_jobs_24h"] == 1


def test_stuck_application_is_reported(app: FastAPI, client: TestClient, login_as: LoginAs) -> None:
    app_id = submit(client, login_as("client1"))
    with app.state.session_factory() as session:
        application = session.get(Application, UUID(app_id))
        assert application is not None
        application.status = ApplicationStatus.SCORING
        session.flush()
        application.updated_at = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
    body = summary(client, login_as("analyst"))
    assert body["stuck_applications"] == 1
    assert any("Без движения дольше 5 минут: 1 заявка" in a["text"] for a in body["alerts"])
