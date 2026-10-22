"""Applications: access rules, client and employee actions, and API views.

Status changes go through `app.lifecycle.transition`; this module decides *who* may do
*what* and turns database rows into API responses.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.credit_decision import annuity_payment
from app.lifecycle import record_created, transition
from app.models import (
    Application,
    CheckResultRecord,
    Clarification,
    DecisionRecord,
    ScoreRecord,
)
from app.products import ProductConfig
from app.schemas import (
    AcceptOfferRequest,
    ApplicationAction,
    ApplicationDetail,
    ApplicationSummary,
    CheckOutcome,
    CheckResult,
    CheckType,
    ClarificationView,
    CompanyResponse,
    CreateApplicationRequest,
    DecisionOutcome,
    DecisionView,
    LegalForm,
    LoanTerms,
    ManualDecisionRequest,
    ProductId,
    PurposeCategory,
    RiskClass,
    ScoreFactor,
    ScoreView,
    StatusHistoryItem,
    UpdateApplicationRequest,
)
from app.security import CurrentUser
from app.statuses import (
    CLIENT_STAGE,
    NEXT_STEPS,
    STAGE_LABELS,
    STATUS_LABELS,
    WAITING_EXTERNAL_STEP,
    Actor,
    ApplicationStatus,
    ClientStage,
    TransitionError,
)

S = ApplicationStatus

_DRAFT_FIELDS = ("product_id", "purpose_category", "amount", "term_months", "purpose")
_FINANCIAL_FIELDS = ("revenue_year", "expenses_year", "liabilities_total")

_OUTCOME_STATUS: dict[DecisionOutcome, ApplicationStatus] = {
    DecisionOutcome.APPROVED: S.APPROVED,
    DecisionOutcome.COUNTER_OFFER: S.COUNTER_OFFER,
    DecisionOutcome.CLARIFICATION: S.CLARIFICATION_REQUIRED,
    DecisionOutcome.REJECTED: S.REJECTED,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _move(
    session: Session,
    application: Application,
    target: ApplicationStatus,
    actor: Actor,
    user: CurrentUser,
    comment: str | None = None,
) -> None:
    try:
        transition(session, application, target, actor, actor_user_id=user.id, comment=comment)
    except TransitionError as exc:
        raise _conflict(str(exc)) from exc


# --- Access -----------------------------------------------------------------


def require_client(user: CurrentUser) -> str:
    """The client's company INN, or 403 for employees."""
    if user.is_employee or user.company_inn is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can do this")
    return user.company_inn


def require_employee(user: CurrentUser) -> None:
    if not user.is_employee:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only bank employees can do this")


def get_for_user(session: Session, application_id: uuid.UUID, user: CurrentUser) -> Application:
    """Clients see their company's applications; employees see everything but drafts."""
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if user.is_employee:
        if application.status is S.DRAFT:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    elif application.company_inn != user.company_inn:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This application belongs to another company"
        )
    return application


def list_for_user(
    session: Session,
    user: CurrentUser,
    status_filter: ApplicationStatus | None,
    stage_filter: ClientStage | None,
) -> list[Application]:
    query = select(Application).order_by(Application.updated_at.desc())
    if user.is_employee:
        query = query.where(Application.status != S.DRAFT)
    else:
        query = query.where(Application.company_inn == user.company_inn)
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
    if stage_filter is not None:
        statuses = [s for s, stage in CLIENT_STAGE.items() if stage is stage_filter]
        query = query.where(Application.status.in_(statuses))
    return list(session.scalars(query).all())


# --- Client actions -----------------------------------------------------------


def create_draft(
    session: Session, user: CurrentUser, body: CreateApplicationRequest
) -> Application:
    company_inn = require_client(user)
    application = Application(
        id=uuid.uuid4(),
        client_id=user.id,
        company_inn=company_inn,
        product_id=body.product_id.value,
        purpose_category=body.purpose_category.value if body.purpose_category else None,
        amount=body.amount,
        term_months=body.term_months,
        purpose=body.purpose,
        status=S.DRAFT,
    )
    session.add(application)
    record_created(session, application, user.id)
    session.commit()
    return application


def _apply_fields(
    application: Application, body: UpdateApplicationRequest, fields: tuple[str, ...]
) -> None:
    for name, value in body.model_dump(
        mode="json", exclude_unset=True, include=set(fields)
    ).items():
        setattr(application, name, value)


def update(
    session: Session, user: CurrentUser, application: Application, body: UpdateApplicationRequest
) -> Application:
    require_client(user)
    if application.status is S.DRAFT:
        _apply_fields(application, body, _DRAFT_FIELDS + _FINANCIAL_FIELDS)
    elif application.status is S.CLARIFICATION_REQUIRED:
        _apply_fields(application, body, _DRAFT_FIELDS + _FINANCIAL_FIELDS)
        clarification = _latest(session, Clarification, application.id)
        if clarification is not None and clarification.answered_at is None:
            clarification.answer = body.clarification_answer
            clarification.answered_at = _now()
        _move(session, application, S.DATA_CHECK, Actor.CLIENT, user, body.clarification_answer)
    else:
        raise _conflict(f"Application in status {application.status} cannot be edited")
    session.commit()
    return application


def _submit_problems(application: Application, product: ProductConfig | None) -> list[str]:
    if product is None:
        return [f"Unknown product {application.product_id}"]
    p = product.params
    problems = []
    if application.amount is None:
        problems.append("amount is required")
    elif not p.min_amount <= application.amount <= p.max_amount:
        problems.append(f"amount must be between {p.min_amount} and {p.max_amount}")
    if application.term_months is None:
        problems.append("term_months is required")
    elif not p.min_term_months <= application.term_months <= p.max_term_months:
        problems.append(f"term_months must be between {p.min_term_months} and {p.max_term_months}")
    return problems


def submit(
    session: Session,
    user: CurrentUser,
    application_id: uuid.UUID,
    idempotency_key: str,
    products: dict[str, ProductConfig],
) -> Application:
    """Send a draft to the bank. Repeating with the same key returns the same application."""
    require_client(user)
    previous = session.scalar(
        select(Application).where(Application.idempotency_key == idempotency_key)
    )
    if previous is not None:
        if previous.id != application_id or previous.company_inn != user.company_inn:
            raise _conflict("Idempotency-Key was already used for another application")
        return previous

    application = get_for_user(session, application_id, user)
    if application.status is not S.DRAFT:
        raise _conflict(f"Only a draft can be submitted, status is {application.status}")
    problems = _submit_problems(application, products.get(application.product_id))
    if problems:
        raise HTTPException(422, problems)

    application.idempotency_key = idempotency_key
    application.submitted_at = _now()
    _move(session, application, S.SUBMITTED, Actor.CLIENT, user)
    try:
        session.commit()
    except IntegrityError:
        # A parallel request with the same key won the race: return its result.
        session.rollback()
        winner = session.scalar(
            select(Application).where(Application.idempotency_key == idempotency_key)
        )
        if winner is None or winner.id != application_id:
            raise _conflict("Idempotency-Key was already used for another application") from None
        return winner
    return application


def respond_to_offer(
    session: Session, user: CurrentUser, application: Application, body: AcceptOfferRequest
) -> Application:
    require_client(user)
    if application.status not in (S.APPROVED, S.COUNTER_OFFER):
        raise _conflict("There is no offer to respond to")
    if body.accept:
        decision = _latest(session, DecisionRecord, application.id)
        if decision is not None and decision.offer:
            application.product_id = decision.offer["product_id"]
            application.amount = decision.offer["amount"]
            application.term_months = decision.offer["term_months"]
        _move(session, application, S.SIGNING, Actor.CLIENT, user, "Клиент принял условия")
    else:
        _move(session, application, S.WITHDRAWN, Actor.CLIENT, user, "Клиент отклонил предложение")
    session.commit()
    return application


def withdraw(
    session: Session, user: CurrentUser, application: Application, reason: str | None
) -> Application:
    require_client(user)
    _move(session, application, S.WITHDRAWN, Actor.CLIENT, user, reason or "Клиент отозвал заявку")
    session.commit()
    return application


def sign(session: Session, user: CurrentUser, application: Application) -> Application:
    """Simulated signing and disbursement."""
    require_client(user)
    _move(session, application, S.ISSUED, Actor.CLIENT, user, "Документы подписаны, кредит выдан")
    session.commit()
    return application


# --- Employee actions -----------------------------------------------------------


def make_offer(
    product: ProductConfig,
    amount: int,
    term_months: int,
    risk_class: str | None,
    rate: float | None,
) -> dict[str, Any]:
    p = product.params
    final_rate = (
        rate if rate is not None else p.base_rate + p.risk_premium.get(risk_class or "", 0.0)
    )
    return {
        "product_id": p.id,
        "amount": amount,
        "term_months": term_months,
        "rate": round(final_rate, 2),
        "monthly_payment": annuity_payment(amount, final_rate, term_months),
    }


def decide_manually(
    session: Session,
    user: CurrentUser,
    application: Application,
    body: ManualDecisionRequest,
    products: dict[str, ProductConfig],
) -> Application:
    require_employee(user)
    if application.status is not S.MANUAL_REVIEW:
        raise _conflict("Only applications in manual review can be decided by an employee")

    score = _latest(session, ScoreRecord, application.id)
    risk_class = score.risk_class if score else None
    offer: dict[str, Any] | None = None
    reason = body.comment

    if body.outcome is DecisionOutcome.APPROVED:
        product = products[application.product_id]
        if application.amount is None or application.term_months is None:
            raise _conflict("Application has no amount or term")
        offer = make_offer(product, application.amount, application.term_months, risk_class, None)
        reason = "Банк одобрил заявку на запрошенных условиях."
    elif body.outcome is DecisionOutcome.COUNTER_OFFER:
        if body.terms is None:
            raise HTTPException(422, "terms are required for counter_offer")
        product = products[body.terms.product_id.value]
        p = product.params
        if not p.min_amount <= body.terms.amount <= p.max_amount:
            raise HTTPException(422, "amount out of product range")
        if not p.min_term_months <= body.terms.term_months <= p.max_term_months:
            raise HTTPException(422, "term out of product range")
        offer = make_offer(
            product, body.terms.amount, body.terms.term_months, risk_class, body.terms.rate
        )
        reason = "Банк готов выдать кредит на других условиях."
    elif body.outcome is DecisionOutcome.CLARIFICATION:
        session.add(
            Clarification(
                application_id=application.id,
                requested_fields=body.requested_fields or [],
                message=body.comment,
                requested_by=Actor.EMPLOYEE,
            )
        )

    session.add(
        DecisionRecord(
            application_id=application.id,
            outcome=body.outcome.value,
            rule="manual_decision",
            reason=reason,
            offer=offer,
            decided_by=Actor.EMPLOYEE,
            decided_by_user_id=user.id,
            comment=body.comment,
        )
    )
    _move(session, application, _OUTCOME_STATUS[body.outcome], Actor.EMPLOYEE, user, body.comment)
    session.commit()
    return application


# --- Views --------------------------------------------------------------------


def _latest(session: Session, model: Any, application_id: uuid.UUID) -> Any:
    return session.scalar(
        select(model)
        .where(model.application_id == application_id)
        .order_by(model.created_at.desc())
        .limit(1)
    )


def available_actions(application: Application, user: CurrentUser) -> list[ApplicationAction]:
    a = ApplicationAction
    if user.is_employee:
        return [a.DECIDE] if application.status is S.MANUAL_REVIEW else []
    return {
        S.DRAFT: [a.EDIT, a.SUBMIT, a.WITHDRAW],
        S.CLARIFICATION_REQUIRED: [a.ANSWER_CLARIFICATION, a.WITHDRAW],
        S.APPROVED: [a.ACCEPT, a.DECLINE],
        S.COUNTER_OFFER: [a.ACCEPT, a.DECLINE],
        S.SIGNING: [a.SIGN, a.WITHDRAW],
    }.get(application.status, [])


def to_summary(session: Session, application: Application, user: CurrentUser) -> ApplicationSummary:
    stage = CLIENT_STAGE[application.status]
    risk_class = None
    if user.is_employee:
        score = _latest(session, ScoreRecord, application.id)
        risk_class = RiskClass(score.risk_class) if score else None
    return ApplicationSummary(
        id=application.id,
        status=application.status,
        status_label=STATUS_LABELS[application.status],
        client_stage=stage,
        stage_label=STAGE_LABELS[stage],
        product_id=ProductId(application.product_id),
        amount=application.amount,
        term_months=application.term_months,
        company_inn=application.company_inn,
        company_name=application.company.name,
        risk_class=risk_class,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def to_detail(session: Session, application: Application, user: CurrentUser) -> ApplicationDetail:
    summary = to_summary(session, application, user)
    company = application.company

    checks: list[CheckResult] = []
    score_view: ScoreView | None = None
    if user.is_employee:
        records = session.scalars(
            select(CheckResultRecord)
            .where(CheckResultRecord.application_id == application.id)
            .order_by(CheckResultRecord.created_at)
        ).all()
        checks = [
            CheckResult(
                type=CheckType(r.type),
                outcome=CheckOutcome(r.outcome),
                summary=r.summary,
                attempt=r.attempt,
            )
            for r in records
        ]
        score = _latest(session, ScoreRecord, application.id)
        if score is not None:
            score_view = ScoreView(
                score=score.pd,
                risk_class=RiskClass(score.risk_class),
                points_total=score.points_total,
                factors=[ScoreFactor.model_validate(f) for f in score.factors],
                model_version=score.model_version,
            )

    decision = _latest(session, DecisionRecord, application.id)
    decision_view = None
    if decision is not None:
        decision_view = DecisionView(
            outcome=DecisionOutcome(decision.outcome),
            terms=LoanTerms.model_validate(decision.offer) if decision.offer else None,
            reason=decision.reason,
            rule=decision.rule,
            decided_by=decision.decided_by,
            comment=decision.comment if user.is_employee else None,
            decided_at=decision.created_at,
        )

    clarification = _latest(session, Clarification, application.id)
    clarification_view = None
    if clarification is not None:
        clarification_view = ClarificationView(
            requested_fields=clarification.requested_fields,
            message=clarification.message,
            answer=clarification.answer,
        )

    return ApplicationDetail(
        **summary.model_dump(),
        purpose_category=PurposeCategory(application.purpose_category)
        if application.purpose_category
        else None,
        purpose=application.purpose,
        revenue_year=application.revenue_year,
        expenses_year=application.expenses_year,
        liabilities_total=application.liabilities_total,
        submitted_at=application.submitted_at,
        available_actions=available_actions(application, user),
        next_step=WAITING_EXTERNAL_STEP
        if application.waiting_external
        else NEXT_STEPS[application.status],
        waiting_external=application.waiting_external,
        company=CompanyResponse(
            inn=company.inn,
            name=company.name,
            legal_form=LegalForm(company.legal_form),
            okved=company.okved,
            registration_date=company.registration_date,
            region=company.region,
            director=company.director,
        ),
        history=[
            StatusHistoryItem(
                from_status=h.from_status,
                to_status=h.to_status,
                actor=h.actor,
                comment=h.comment,
                at=h.created_at,
            )
            for h in application.history
        ],
        checks=checks,
        score=score_view,
        decision=decision_view,
        clarification=clarification_view,
    )
