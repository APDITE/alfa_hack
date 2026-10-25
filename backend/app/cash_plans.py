"""Cash calendar of an application: preview, save, and the view in the application card.

The loan terms come from the bank's latest offer; the client's typical month and the
chosen payment day are stored on the application. Until the loan is issued, payment
dates count from today; after the issue, from the actual issue date.
"""

import math
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cash_calendar as cc
from app.models import Application, DecisionRecord, StatusHistory
from app.pipeline import company_facts
from app.schedule import annuity_schedule
from app.schemas import (
    BalancePoint,
    CashCalendarIn,
    CashPlanRequest,
    CashPlanView,
    CashPreviewRequest,
    CashPreviewResponse,
    CashSimulationView,
    PaymentDayOption,
)
from app.security import CurrentUser
from app.statuses import ApplicationStatus

S = ApplicationStatus
EDITABLE = (S.APPROVED, S.COUNTER_OFFER, S.SIGNING)
CHART_POINTS = 750
"""Points per chart line: every day of a loan up to two years, a few days per point beyond."""


def issue_date(session: Session, application: Application) -> date:
    issued = session.scalar(
        select(StatusHistory.created_at)
        .where(
            StatusHistory.application_id == application.id,
            StatusHistory.to_status == S.ISSUED,
        )
        .limit(1)
    )
    return issued.date() if issued is not None else datetime.now(UTC).date()


def offer_terms(session: Session, application: Application) -> dict[str, Any] | None:
    decision = session.scalar(
        select(DecisionRecord)
        .where(DecisionRecord.application_id == application.id)
        .order_by(DecisionRecord.created_at.desc())
        .limit(1)
    )
    return decision.offer if decision is not None and decision.offer else None


def _editable_terms(
    application: Application, user: CurrentUser, session: Session
) -> dict[str, Any]:
    if user.is_employee:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can do this")
    if application.status not in EDITABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The payment day is chosen for an offer, before signing"
        )
    terms = offer_terms(session, application)
    if terms is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no offer to plan payments for")
    return terms


def to_calendar(body: CashCalendarIn) -> cc.CashCalendar:
    return cc.CashCalendar(
        opening_balance=body.opening_balance,
        reserve=body.reserve,
        events=tuple(cc.CashEvent(e.day, e.amount, e.label) for e in body.events if e.amount),
    )


def to_body(calendar: cc.CashCalendar) -> CashCalendarIn:
    return CashCalendarIn.model_validate(
        {
            "opening_balance": calendar.opening_balance,
            "reserve": calendar.reserve,
            "events": [
                {"day": e.day, "amount": e.amount, "label": e.label} for e in calendar.events
            ],
        }
    )


def to_view(simulation: cc.Simulation) -> CashSimulationView:
    return CashSimulationView(
        min_balance=simulation.min_balance,
        min_date=simulation.min_date,
        first_gap=simulation.first_gap,
        shortfall=simulation.shortfall,
    )


def chart(lows: list[tuple[date, int]]) -> list[BalancePoint]:
    """The whole term; for long loans every point is the lowest balance of a few days."""
    step = max(1, math.ceil(len(lows) / CHART_POINTS))
    return [
        BalancePoint(day=lows[i][0], balance=min(b for _, b in lows[i : i + step]))
        for i in range(0, len(lows), step)
    ]


def preview(
    session: Session, user: CurrentUser, application: Application, body: CashPreviewRequest
) -> CashPreviewResponse:
    """Compare payment days against the cash flow; nothing is saved."""
    terms = _editable_terms(application, user, session)
    template = False
    if body.calendar is not None:
        calendar = to_calendar(body.calendar)
    elif application.cash_calendar is not None:
        calendar = to_calendar(CashCalendarIn.model_validate(application.cash_calendar))
    else:
        facts = company_facts(session, application)
        calendar = cc.template(facts.revenue_year, facts.expenses_year)
        template = True

    issue = issue_date(session, application)

    def compare(days: tuple[int, ...]) -> list[cc.DayOption]:
        return cc.compare_days(
            calendar,
            int(terms["amount"]),
            float(terms["rate"]),
            int(terms["term_months"]),
            int(terms["monthly_payment"]),
            issue,
            days,
        )

    options = compare(cc.COMPARED_DAYS)
    recommended, recommendation = cc.recommend(options)
    chosen = body.payment_day or application.payment_day or recommended or cc.COMPARED_DAYS[-1]
    if all(o.payment_day != chosen for o in options):
        options = sorted(options + compare((chosen,)), key=lambda o: o.payment_day)
    cheapest = min(o.total_interest for o in options)
    selected = next(o for o in options if o.payment_day == chosen)
    return CashPreviewResponse(
        calendar=to_body(calendar),
        template=template,
        payment_day=chosen,
        recommended_day=recommended,
        recommendation=recommendation,
        options=[
            PaymentDayOption(
                payment_day=o.payment_day,
                first_payment_date=o.first_payment_date,
                first_payment=o.first_payment,
                extra_cost=o.total_interest - cheapest,
                base=to_view(o.base),
                delayed=to_view(o.delayed),
            )
            for o in options
        ],
        chart_base=chart(selected.base.lows),
        chart_delayed=chart(selected.delayed.lows),
    )


def save(
    session: Session, user: CurrentUser, application: Application, body: CashPlanRequest
) -> Application:
    _editable_terms(application, user, session)
    application.payment_day = body.payment_day
    application.cash_calendar = body.calendar.model_dump()
    session.commit()
    return application


def plan_view(session: Session, application: Application) -> CashPlanView | None:
    """The saved choice checked against the current offer, for both sides."""
    terms = offer_terms(session, application)
    if application.payment_day is None or application.cash_calendar is None or terms is None:
        return None
    body = CashCalendarIn.model_validate(application.cash_calendar)
    schedule = annuity_schedule(
        int(terms["amount"]),
        float(terms["rate"]),
        int(terms["term_months"]),
        int(terms["monthly_payment"]),
        issue_date(session, application),
        application.payment_day,
    )
    payments = [(p.due_date, p.payment) for p in schedule if p.due_date is not None]
    calendar = to_calendar(body)
    return CashPlanView(
        payment_day=application.payment_day,
        calendar=body,
        base=to_view(cc.simulate(calendar, payments)),
        delayed=to_view(cc.simulate(calendar, payments, cc.DELAY_DAYS)),
    )
