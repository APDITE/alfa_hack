"""Operational state of the credit pipeline: Prometheus metrics and alerts for employees.

Everything is computed from the database on request, so no extra infrastructure is
needed: `GET /metrics` (inside the compose network, nginx does not proxy it) is ready for
Prometheus with the rules in monitoring/alerts.yml, and `GET /api/ops/summary` feeds the
pipeline health widget of the bank workplace. Thresholds here match those rules.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, CheckResultRecord, DecisionRecord, JobStatus, PipelineJob
from app.schemas import OpsAlert, OpsSummary
from app.statuses import TURN_OWNER, Actor, ApplicationStatus

STUCK_AFTER = timedelta(minutes=5)
QUEUE_LAG_ALERT_SECONDS = 60
FAILED_WINDOW = timedelta(hours=24)

SYSTEM_STATUSES = [s for s, owner in TURN_OWNER.items() if owner is Actor.SYSTEM]
SERVICE_LABELS = {
    "egrul": "ЕГРЮЛ/ЕГРИП",
    "transparent_business": "«Прозрачный бизнес»",
    "bki": "БКИ",
}


@dataclass(frozen=True)
class Snapshot:
    applications: dict[str, int]
    jobs: dict[str, int]
    ready_jobs: int
    oldest_ready_seconds: float
    stuck_applications: int
    waiting_external: int
    unavailable_services: dict[str, int]
    failed_jobs_recent: int
    decisions: dict[tuple[str, str], int]


def _aware(value: datetime) -> datetime:
    # SQLite (tests) returns naive timestamps; everything is stored in UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def collect(session: Session, now: datetime) -> Snapshot:
    # Result has .keys(), so dict(result) would treat it as a mapping: build dicts from rows.
    by_status = {
        status: count
        for status, count in session.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
    }
    by_job_status = {
        status: count
        for status, count in session.execute(
            select(PipelineJob.status, func.count()).group_by(PipelineJob.status)
        ).all()
    }
    ready_count, oldest = session.execute(
        select(func.count(), func.min(PipelineJob.run_after)).where(
            PipelineJob.status == JobStatus.PENDING, PipelineJob.run_after <= now
        )
    ).one()
    in_automatic = Application.status.in_(SYSTEM_STATUSES)
    stuck = session.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            in_automatic,
            Application.waiting_external.is_(False),
            Application.updated_at < now - STUCK_AFTER,
        )
    )
    waiting = session.scalar(
        select(func.count())
        .select_from(Application)
        .where(in_automatic, Application.waiting_external.is_(True))
    )
    unavailable = {
        service: count
        for service, count in session.execute(
            select(
                CheckResultRecord.type,
                func.count(func.distinct(CheckResultRecord.application_id)),
            )
            .join(Application, Application.id == CheckResultRecord.application_id)
            .where(
                CheckResultRecord.outcome == "unavailable",
                Application.waiting_external.is_(True),
            )
            .group_by(CheckResultRecord.type)
        ).all()
    }
    failed_recent = session.scalar(
        select(func.count())
        .select_from(PipelineJob)
        .where(
            PipelineJob.status == JobStatus.FAILED,
            PipelineJob.updated_at >= now - FAILED_WINDOW,
        )
    )
    decisions = {
        (str(outcome), Actor(decided_by).value): count
        for outcome, decided_by, count in session.execute(
            select(DecisionRecord.outcome, DecisionRecord.decided_by, func.count()).group_by(
                DecisionRecord.outcome, DecisionRecord.decided_by
            )
        ).all()
    }
    return Snapshot(
        applications={s.value: by_status.get(s, 0) for s in ApplicationStatus},
        jobs={j.value: by_job_status.get(j, 0) for j in JobStatus},
        ready_jobs=int(ready_count),
        oldest_ready_seconds=(now - _aware(oldest)).total_seconds() if oldest else 0.0,
        stuck_applications=int(stuck or 0),
        waiting_external=int(waiting or 0),
        unavailable_services={str(k): int(v) for k, v in unavailable.items()},
        failed_jobs_recent=int(failed_recent or 0),
        decisions=decisions,
    )


def _applications_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "заявка"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "заявки"
    return "заявок"


def summary(snapshot: Snapshot) -> OpsSummary:
    alerts: list[OpsAlert] = []
    if snapshot.oldest_ready_seconds > QUEUE_LAG_ALERT_SECONDS:
        alerts.append(
            OpsAlert(
                level="critical",
                text=f"Очередь конвейера не разбирается {int(snapshot.oldest_ready_seconds)} с — "
                "проверьте, что воркер запущен",
            )
        )
    if snapshot.stuck_applications:
        n = snapshot.stuck_applications
        word = _applications_word(n)
        alerts.append(OpsAlert(level="warning", text=f"Без движения дольше 5 минут: {n} {word}"))
    if snapshot.waiting_external:
        n = snapshot.waiting_external
        services = ", ".join(
            SERVICE_LABELS.get(s, s) for s in sorted(snapshot.unavailable_services)
        ) or "внешний сервис"
        word = _applications_word(n)
        alerts.append(OpsAlert(level="warning", text=f"Ждут ответа ({services}): {n} {word}"))
    if snapshot.failed_jobs_recent:
        alerts.append(
            OpsAlert(
                level="warning",
                text=f"Технические ошибки этапов за сутки: {snapshot.failed_jobs_recent} — "
                "заявки переданы сотрудникам",
            )
        )
    level: Literal["ok", "warning", "critical"] = "ok"
    if alerts:
        level = "critical" if any(a.level == "critical" for a in alerts) else "warning"
    return OpsSummary(
        status=level,
        ready_jobs=snapshot.ready_jobs,
        oldest_ready_seconds=round(snapshot.oldest_ready_seconds, 1),
        stuck_applications=snapshot.stuck_applications,
        waiting_external=snapshot.waiting_external,
        failed_jobs_24h=snapshot.failed_jobs_recent,
        manual_review=snapshot.applications[ApplicationStatus.MANUAL_REVIEW.value],
        alerts=alerts,
    )


def _sample(name: str, value: float, **labels: str) -> str:
    label_text = ",".join(f'{key}="{val}"' for key, val in labels.items())
    number = str(int(value)) if float(value).is_integer() else f"{value:.3f}"
    return f"{name}{{{label_text}}} {number}" if label_text else f"{name} {number}"


def prometheus(snapshot: Snapshot) -> str:
    """Prometheus text exposition format 0.0.4."""
    lines: list[str] = []

    def metric(name: str, kind: str, help_text: str, samples: list[str]) -> None:
        lines.extend([f"# HELP {name} {help_text}", f"# TYPE {name} {kind}", *samples])

    metric(
        "credit_applications",
        "gauge",
        "Applications by status.",
        [_sample("credit_applications", n, status=s) for s, n in snapshot.applications.items()],
    )
    metric(
        "credit_pipeline_jobs",
        "gauge",
        "Pipeline jobs by state.",
        [_sample("credit_pipeline_jobs", n, state=s) for s, n in snapshot.jobs.items()],
    )
    metric(
        "credit_pipeline_ready_jobs",
        "gauge",
        "Jobs ready to run now.",
        [_sample("credit_pipeline_ready_jobs", snapshot.ready_jobs)],
    )
    metric(
        "credit_pipeline_oldest_ready_job_age_seconds",
        "gauge",
        "How long the oldest ready job has been waiting; grows when no worker runs.",
        [_sample("credit_pipeline_oldest_ready_job_age_seconds", snapshot.oldest_ready_seconds)],
    )
    metric(
        "credit_applications_stuck",
        "gauge",
        "Applications in an automatic status without progress for 5+ minutes.",
        [_sample("credit_applications_stuck", snapshot.stuck_applications)],
    )
    metric(
        "credit_applications_waiting_external",
        "gauge",
        "Applications retrying an unavailable external service.",
        [_sample("credit_applications_waiting_external", snapshot.waiting_external)],
    )
    metric(
        "credit_external_unavailable_applications",
        "gauge",
        "Applications waiting, by unavailable service.",
        [
            _sample("credit_external_unavailable_applications", n, service=s)
            for s, n in sorted(snapshot.unavailable_services.items())
        ],
    )
    metric(
        "credit_decisions_total",
        "counter",
        "Credit decisions by outcome and decision maker.",
        [
            _sample("credit_decisions_total", n, outcome=o, decided_by=d)
            for (o, d), n in sorted(snapshot.decisions.items())
        ],
    )
    return "\n".join(lines) + "\n"
