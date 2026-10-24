"""Automatic stages of the credit pipeline, run by the worker (`python -m app.worker`).

Each job in `pipeline_jobs` names an application and the stage it waits in. A stage does
its work and moves the application on through `lifecycle.transition`, which queues the
next job. External services that do not answer are retried with backoff (scenario 7).
"""

import logging
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.credit_decision import (
    CompanyFacts,
    Decision,
    DecisionOutcome,
    LoanRequest,
    RegistryStatus,
    ScoreInput,
    decide,
)
from app.integrations import JSON, ExternalUnavailableError, Integrations
from app.lifecycle import transition
from app.models import (
    Application,
    CheckResultRecord,
    Clarification,
    Company,
    DecisionRecord,
    JobStatus,
    PipelineJob,
    ScoreRecord,
)
from app.products import ProductConfig
from app.statuses import STATUS_LABELS, Actor, ApplicationStatus, can_transition

log = logging.getLogger("app.pipeline")

S = ApplicationStatus
MAX_ATTEMPTS = 10
# An unexpected error (a bug, bad data) is retried a few times, then an employee takes over.
MAX_CRASH_ATTEMPTS = 3
_BACKOFF_SECONDS = (5, 15, 45)
_RETRY_EVERY_SECONDS = 60

_FIELD_NAMES = {
    "revenue_year": "выручка за последние 12 месяцев",
    "expenses_year": "расходы за последние 12 месяцев",
    "liabilities_total": "текущие обязательства",
    "amount": "сумма кредита",
    "term_months": "срок кредита",
}

_FINANCIAL_FIELDS = ("revenue_year", "expenses_year", "liabilities_total")

_OUTCOME_STATUS = {
    DecisionOutcome.APPROVED: S.APPROVED,
    DecisionOutcome.COUNTER_OFFER: S.COUNTER_OFFER,
    DecisionOutcome.CLARIFICATION: S.CLARIFICATION_REQUIRED,
    DecisionOutcome.MANUAL_REVIEW: S.MANUAL_REVIEW,
    DecisionOutcome.REJECTED: S.REJECTED,
}


@dataclass(frozen=True)
class PipelineContext:
    integrations: Integrations
    products: dict[str, ProductConfig]


def backoff(attempt: int) -> timedelta:
    """Delay before retry number `attempt` (1-based): 5 s, 15 s, 45 s, then every minute."""
    if attempt <= len(_BACKOFF_SECONDS):
        return timedelta(seconds=_BACKOFF_SECONDS[attempt - 1])
    return timedelta(seconds=_RETRY_EVERY_SECONDS)


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - 1 if end.day < start.day else months


# --- Running jobs -----------------------------------------------------------------


def run_once(factory: sessionmaker[Session], ctx: PipelineContext, now: datetime) -> bool:
    """Process one ready job. Returns False when there is nothing to do."""
    with factory() as session:
        job = session.scalar(
            select(PipelineJob)
            .where(PipelineJob.status == JobStatus.PENDING, PipelineJob.run_after <= now)
            .order_by(PipelineJob.run_after)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        job_id, application_id, stage = job.id, job.application_id, job.stage
        try:
            process_job(session, job, ctx, now)
            session.commit()
        except Exception as exc:
            session.rollback()
            log.exception("application=%s stage=%s job crashed", application_id, stage)
            try:
                handle_crash(session, job_id, exc, now)
            except Exception:
                session.rollback()
                log.exception("application=%s stage=%s crash not recorded", application_id, stage)
        return True


def handle_crash(session: Session, job_id: uuid.UUID, exc: Exception, now: datetime) -> None:
    """Unexpected error in a stage: retry with backoff, then hand the application to an
    employee, so it never hangs in an automatic status (the attempt of the crashed run
    was rolled back with the rest of its transaction)."""
    job = session.get(PipelineJob, job_id)
    if job is None:
        return
    job.attempt += 1
    job.last_error = repr(exc)[:2000]
    if job.attempt < MAX_CRASH_ATTEMPTS:
        job.status = JobStatus.PENDING
        job.run_after = now + backoff(job.attempt)
        session.commit()
        return

    job.status = JobStatus.FAILED
    application = session.get(Application, job.application_id)
    if (
        application is not None
        and application.status is job.stage
        and can_transition(application.status, S.MANUAL_REVIEW)
    ):
        reason = (
            f"Техническая ошибка на этапе «{STATUS_LABELS[job.stage]}» после "
            f"{job.attempt} попыток, заявку проверит сотрудник"
        )
        transition(session, application, S.MANUAL_REVIEW, Actor.SYSTEM, comment=reason)
        log.error(
            "application=%s stage=%s handed to an employee after crashes", application.id, job.stage
        )
    session.commit()


def run_until_idle(
    factory: sessionmaker[Session], ctx: PipelineContext, now: datetime, limit: int = 1000
) -> int:
    """Process every job that is ready at `now` (used by tests and demos)."""
    processed = 0
    # Jobs queued during the run are stamped with the wall clock, so never look earlier.
    while processed < limit and run_once(factory, ctx, max(now, datetime.now(UTC))):
        processed += 1
    return processed


def process_job(session: Session, job: PipelineJob, ctx: PipelineContext, now: datetime) -> None:
    application = session.get(Application, job.application_id)
    if application is None or application.status is not job.stage:
        log.info("application=%s stage=%s skipped: status moved on", job.application_id, job.stage)
        job.status = JobStatus.DONE
        return

    job.status = JobStatus.RUNNING
    job.attempt += 1
    log.info("application=%s stage=%s attempt=%d", application.id, job.stage, job.attempt)
    try:
        handler = _HANDLERS[job.stage]
        handler(session, application, ctx)
    except ExternalUnavailableError as exc:
        _retry_later(session, job, application, exc, now)
        return
    job.status = JobStatus.DONE


def _retry_later(
    session: Session,
    job: PipelineJob,
    application: Application,
    exc: ExternalUnavailableError,
    now: datetime,
) -> None:
    job.last_error = str(exc)
    if exc.service != "scoring":
        _record_unavailable(session, application, exc.service, job.attempt)
    if job.attempt >= MAX_ATTEMPTS:
        log.warning(
            "application=%s %s: giving up after %d attempts", application.id, exc, job.attempt
        )
        job.status = JobStatus.DONE
        reason = f"Внешний сервис недоступен после {job.attempt} попыток ({exc.service})"
        if application.status is S.ENRICHMENT:
            transition(session, application, S.MANUAL_REVIEW, Actor.SYSTEM, comment=reason)
        else:  # scoring: let the decision stage route it to an employee
            transition(session, application, S.CREDIT_DECISION, Actor.SYSTEM, comment=reason)
        return
    delay = backoff(job.attempt)
    log.info("application=%s %s, retry %d in %ss", application.id, exc, job.attempt, delay.seconds)
    job.status = JobStatus.PENDING
    job.run_after = now + delay
    application.waiting_external = True


def _record_unavailable(
    session: Session, application: Application, service: str, attempt: int
) -> None:
    record = session.scalar(
        select(CheckResultRecord).where(
            CheckResultRecord.application_id == application.id,
            CheckResultRecord.type == service,
            CheckResultRecord.outcome == "unavailable",
        )
    )
    if record is None:
        record = CheckResultRecord(
            application_id=application.id, type=service, outcome="unavailable", summary=""
        )
        session.add(record)
    record.attempt = attempt
    record.summary = f"Сервис не отвечает, попытка {attempt} из {MAX_ATTEMPTS}"


# --- Stages -------------------------------------------------------------------------


def _submitted(session: Session, application: Application, ctx: PipelineContext) -> None:
    transition(session, application, S.DATA_CHECK, Actor.SYSTEM)


def _data_check(session: Session, application: Application, ctx: PipelineContext) -> None:
    missing = [f for f in ("amount", "term_months") if getattr(application, f) is None]
    _add_check(
        session,
        application,
        "completeness",
        "failed" if missing else "passed",
        "Не заполнено: " + ", ".join(_FIELD_NAMES[f] for f in missing)
        if missing
        else "Все обязательные поля заявки заполнены",
    )
    if missing:
        _ask_client(session, application, missing)
        transition(
            session, application, S.CLARIFICATION_REQUIRED, Actor.SYSTEM, comment="missing_data"
        )
        return
    transition(session, application, S.ENRICHMENT, Actor.SYSTEM)


def _enrichment(session: Session, application: Application, ctx: PipelineContext) -> None:
    inn = application.company_inn
    # All three calls first: a retry must not leave half of the results behind.
    egrul = ctx.integrations.egrul(inn)
    financials = ctx.integrations.transparent_business(inn)
    bki = ctx.integrations.bki(inn)

    session.execute(
        delete(CheckResultRecord).where(
            CheckResultRecord.application_id == application.id,
            CheckResultRecord.type.in_(("egrul", "transparent_business", "bki")),
        )
    )

    if egrul is None:
        _add_check(session, application, "egrul", "failed", "Компания не найдена в реестре")
    else:
        status = str(egrul.get("status", "active"))
        company = session.get(Company, inn)
        if company is not None:
            company.registry_status = status
        active = status == RegistryStatus.ACTIVE
        summary = "Компания действует" if active else f"Статус в реестре: {status}"
        _add_check(session, application, "egrul", "passed" if active else "failed", summary, egrul)

    if financials is None:
        _add_check(
            session,
            application,
            "transparent_business",
            "failed",
            "Нет данных о выручке и обязательствах",
        )
    else:
        revenue = int(financials.get("revenue_year", 0))
        _add_check(
            session,
            application,
            "transparent_business",
            "passed",
            f"Выручка за год: {revenue:,} ₽".replace(",", " "),
            financials,
        )

    if bki is None:
        _add_check(session, application, "bki", "passed", "Кредитной истории нет")
    else:
        overdue = int(bki.get("max_overdue_days", 0))
        summary = (
            "Просрочек нет" if overdue == 0 else f"Просрочки есть, максимальная — {overdue} дн."
        )
        _add_check(
            session, application, "bki", "passed" if overdue == 0 else "failed", summary, bki
        )

    transition(session, application, S.SCORING, Actor.SYSTEM)


def _scoring(session: Session, application: Application, ctx: PipelineContext) -> None:
    facts = company_facts(session, application)
    if facts.registry_status is RegistryStatus.ACTIVE and not missing_financials(facts):
        result = ctx.integrations.score(
            scoring_payload(
                application.product_id,
                application.amount,
                application.term_months,
                application.company_inn,
                application.company.okved,
                facts,
                _payload(session, application, "bki"),
            )
        )
        session.add(
            ScoreRecord(
                application_id=application.id,
                pd=float(result["score"]),
                risk_class=str(result["risk_class"]),
                points_total=int(result.get("points_total", 0)),
                factors=list(result.get("factors", [])),
                model_version=str(result.get("model_version", "unknown")),
            )
        )
    # Otherwise the decision rules reject or ask for data without a score.
    transition(session, application, S.CREDIT_DECISION, Actor.SYSTEM)


def _credit_decision(session: Session, application: Application, ctx: PipelineContext) -> None:
    facts = company_facts(session, application)
    product = ctx.products[application.product_id]
    score = session.scalar(
        select(ScoreRecord)
        .where(ScoreRecord.application_id == application.id)
        .order_by(ScoreRecord.created_at.desc())
        .limit(1)
    )
    needs_score = facts.registry_status is RegistryStatus.ACTIVE and not missing_financials(facts)
    if score is None and needs_score:
        decision = Decision(
            DecisionOutcome.MANUAL_REVIEW,
            "scoring_unavailable",
            "Оценка риска недоступна, заявку проверит сотрудник.",
        )
    else:
        assert application.amount is not None and application.term_months is not None
        score_input = (
            ScoreInput(pd=score.pd, risk_class=score.risk_class, points_total=score.points_total)
            if score is not None
            # Not used: without registry or data the rules stop before looking at the score.
            else ScoreInput(pd=0.0, risk_class="low", points_total=0)
        )
        decision = decide(
            product.params,
            LoanRequest(application.product_id, application.amount, application.term_months),
            score_input,
            facts,
            # Every other product may be offered instead (scenario 11).
            [p.params for pid, p in ctx.products.items() if pid != application.product_id],
        )
    apply_decision(session, application, decision)


_HANDLERS = {
    S.SUBMITTED: _submitted,
    S.DATA_CHECK: _data_check,
    S.ENRICHMENT: _enrichment,
    S.SCORING: _scoring,
    S.CREDIT_DECISION: _credit_decision,
}


# --- Helpers ---------------------------------------------------------------------


def apply_decision(session: Session, application: Application, decision: Decision) -> None:
    log.info("application=%s decision=%s rule=%s", application.id, decision.outcome, decision.rule)
    if decision.outcome is DecisionOutcome.CLARIFICATION:
        _ask_client(session, application, list(decision.requested_fields))
    if decision.outcome is not DecisionOutcome.MANUAL_REVIEW:
        session.add(
            DecisionRecord(
                application_id=application.id,
                outcome=decision.outcome.value,
                rule=decision.rule,
                reason=decision.reason,
                offer=asdict(decision.offer) if decision.offer else None,
                decided_by=Actor.SYSTEM,
            )
        )
    transition(
        session,
        application,
        _OUTCOME_STATUS[decision.outcome],
        Actor.SYSTEM,
        comment=f"{decision.reason} [{decision.rule}]",
    )


def company_facts(session: Session, application: Application) -> CompanyFacts:
    return facts_from_sources(
        _payload(session, application, "egrul"),
        _payload(session, application, "transparent_business"),
        application.company.registration_date,
        {name: getattr(application, name) for name in _FINANCIAL_FIELDS},
    )


def facts_from_sources(
    egrul: JSON | None,
    financials: JSON | None,
    registered_fallback: date,
    entered: Mapping[str, int | None] | None = None,
) -> CompanyFacts:
    """Facts for the credit rules: the registry, then «Прозрачный бизнес», then what the
    client entered in answer to a clarification. Pre-approval uses the same function."""
    if egrul is None:
        registry_status = RegistryStatus.NOT_FOUND
        registered = registered_fallback
    else:
        registry_status = RegistryStatus(str(egrul.get("status", "active")))
        raw_date = egrul.get("registration_date")
        registered = date.fromisoformat(str(raw_date)) if raw_date else registered_fallback
    client_values = entered or {}

    def value(name: str) -> int | None:
        if financials is not None and financials.get(name) is not None:
            return int(financials[name])
        return client_values.get(name)

    return CompanyFacts(
        registry_status=registry_status,
        business_age_months=max(0, months_between(registered, datetime.now(UTC).date())),
        revenue_year=value("revenue_year"),
        expenses_year=value("expenses_year"),
        liabilities_total=value("liabilities_total"),
    )


def scoring_payload(
    product_id: str,
    amount: int | None,
    term_months: int | None,
    inn: str,
    okved: str,
    facts: CompanyFacts,
    bki: JSON | None,
) -> JSON:
    """Request to the scoring service; the pipeline and pre-approval send the same one."""
    history = bki or {}
    return {
        "application": {"product_id": product_id, "amount": amount, "term_months": term_months},
        "company": {
            "inn": inn,
            "okved": okved,
            "age_months": facts.business_age_months,
            "revenue_year": facts.revenue_year,
            "expenses_year": facts.expenses_year,
            "liabilities_total": facts.liabilities_total,
        },
        "credit_history": {
            "active_loans": int(history.get("active_loans", 0)),
            "overdue_count": int(history.get("overdue_count", 0)),
            "max_overdue_days": int(history.get("max_overdue_days", 0)),
        },
    }


def missing_financials(facts: CompanyFacts) -> bool:
    return None in (facts.revenue_year, facts.expenses_year, facts.liabilities_total)


def _payload(session: Session, application: Application, check_type: str) -> JSON | None:
    record = session.scalar(
        select(CheckResultRecord)
        .where(
            CheckResultRecord.application_id == application.id,
            CheckResultRecord.type == check_type,
            CheckResultRecord.outcome != "unavailable",
        )
        .order_by(CheckResultRecord.created_at.desc())
        .limit(1)
    )
    return record.payload if record is not None else None


def _add_check(
    session: Session,
    application: Application,
    check_type: str,
    outcome: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        CheckResultRecord(
            application_id=application.id,
            type=check_type,
            outcome=outcome,
            summary=summary,
            payload=payload,
        )
    )


def _ask_client(session: Session, application: Application, fields: list[str]) -> None:
    names = ", ".join(_FIELD_NAMES.get(f, f) for f in fields)
    session.add(
        Clarification(
            application_id=application.id,
            requested_fields=fields,
            message=f"Чтобы продолжить, укажите: {names}.",
            requested_by=Actor.SYSTEM,
        )
    )
