"""Negotiation: offer versions and the client's proposals.

Every offer the bank makes is a version: the pipeline's decision is version 1, and every
offer of an employee adds one. The client may answer an offer with their own terms —
amount, term, an optional rate and a comment — up to MAX_ROUNDS times. The application then
goes back to an employee, who accepts the client's terms, offers others or keeps the
previous ones; the answer becomes the next version. Accepting an offer ends the
negotiation and produces the loan agreement (`app.agreements`).

The actions live in `app.applications`; this module reads the negotiation state.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cash_calendar import money
from app.credit_decision import annuity_payment
from app.models import DecisionRecord, Proposal
from app.schedule import annuity_schedule
from app.schemas import LoanTerms, NegotiationView, OfferVersionView, ProposalView

MAX_ROUNDS = 3


def offers(session: Session, application_id: uuid.UUID) -> list[DecisionRecord]:
    """Decisions with an offer, oldest first: version N is the N-th of them."""
    decisions = session.scalars(
        select(DecisionRecord)
        .where(DecisionRecord.application_id == application_id)
        .order_by(DecisionRecord.created_at)
    ).all()
    return [d for d in decisions if d.offer]


def proposals(session: Session, application_id: uuid.UUID) -> list[Proposal]:
    return list(
        session.scalars(
            select(Proposal)
            .where(Proposal.application_id == application_id)
            .order_by(Proposal.round)
        ).all()
    )


def open_proposal(session: Session, application_id: uuid.UUID) -> Proposal | None:
    """The client's proposal waiting for the employee's answer."""
    rounds = proposals(session, application_id)
    return rounds[-1] if rounds and rounds[-1].answered_at is None else None


def total_interest(terms: LoanTerms) -> int:
    schedule = annuity_schedule(terms.amount, terms.rate, terms.term_months, terms.monthly_payment)
    return sum(p.interest for p in schedule)


def terms_text(amount: int, term_months: int, rate: float | None, payment: int | None) -> str:
    """'4 000 000 ₽ на 24 мес., 17,5%, платёж 197 600 ₽' for the history."""
    parts = [f"{money(amount)} на {term_months} мес."]
    if rate is not None:
        parts.append(f"{rate:g}%".replace(".", ","))
    if payment is not None:
        parts.append(f"платёж {money(payment)}")
    return ", ".join(parts)


def offer_text(offer: dict[str, Any]) -> str:
    return terms_text(
        int(offer["amount"]),
        int(offer["term_months"]),
        float(offer["rate"]),
        int(offer["monthly_payment"]),
    )


def view(records: list[DecisionRecord], rounds: list[Proposal]) -> NegotiationView | None:
    """Versions (`offers`) and proposals for the card; None until the bank makes an offer."""
    if not records:
        return None
    answered = {p.answer_version: p.round for p in rounds if p.answer_version is not None}
    versions = []
    for number, record in enumerate(records, start=1):
        terms = LoanTerms.model_validate(record.offer)
        versions.append(
            OfferVersionView(
                version=number,
                terms=terms,
                total_interest=total_interest(terms),
                decided_by=record.decided_by,
                reason=record.reason,
                created_at=record.created_at,
                in_reply_to=answered.get(number),
            )
        )
    views = []
    for p in rounds:
        rate = p.rate if p.rate is not None else versions[p.offer_version - 1].terms.rate
        views.append(
            ProposalView(
                round=p.round,
                offer_version=p.offer_version,
                amount=p.amount,
                term_months=p.term_months,
                rate=p.rate,
                monthly_payment=annuity_payment(p.amount, rate, p.term_months),
                comment=p.comment,
                created_at=p.created_at,
                answered=p.answered_at is not None,
                answer_version=p.answer_version,
            )
        )
    return NegotiationView(
        versions=versions,
        proposals=views,
        max_rounds=MAX_ROUNDS,
        rounds_left=max(0, MAX_ROUNDS - len(rounds)),
    )
