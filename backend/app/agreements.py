"""Loan agreement: the text the client signs and its SHA-256.

A version of the agreement is made when the client accepts an offer, and again whenever
what it says changes before signing: a new payment day, or signing on another day than the
version was made (the schedule counts from the issue). Every version is stored with the
SHA-256 of its text. The client signs a particular hash, and anyone can recompute it from
the stored text to check that the document has not changed since. A demo document, not a
legal one: the lender is "Банк", and no signature is made.
"""

import hashlib
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import negotiation
from app.cash_calendar import money
from app.models import Agreement, Application
from app.schedule import MAX_PAYMENT_DAY, annuity_schedule
from app.schemas import AgreementDocument, AgreementSummary, LoanTerms


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def versions(session: Session, application_id: uuid.UUID) -> list[Agreement]:
    return list(
        session.scalars(
            select(Agreement)
            .where(Agreement.application_id == application_id)
            .order_by(Agreement.version)
        ).all()
    )


def latest(session: Session, application_id: uuid.UUID) -> Agreement | None:
    made = versions(session, application_id)
    return made[-1] if made else None


def is_current(agreement: Agreement, today: date) -> bool:
    """Made today (UTC): the dates in its schedule are the ones the loan will get."""
    made = agreement.created_at
    return (made.astimezone(UTC) if made.tzinfo else made).date() == today


def refresh(session: Session, application: Application, reason: str) -> Agreement:
    """A new version from the latest offer and the payment day, for a loan issued today.

    Without a chosen payment day, payments fall on the day of the issue (28th at most).
    """
    records = negotiation.offers(session, application.id)
    if not records:
        raise ValueError("An agreement needs an offer")
    terms = LoanTerms.model_validate(records[-1].offer)
    issue = datetime.now(UTC).date()
    if application.payment_day is None:
        application.payment_day = min(issue.day, MAX_PAYMENT_DAY)
    previous = latest(session, application.id)
    version = previous.version + 1 if previous is not None else 1
    number = f"КД-{application.id.hex[:8].upper()}"
    rounds = len(negotiation.proposals(session, application.id))
    text = render(application, terms, number, version, len(records), rounds, issue)
    agreement = Agreement(
        application_id=application.id,
        version=version,
        offer_version=len(records),
        number=number,
        reason=reason,
        text=text,
        sha256=sha256(text),
    )
    session.add(agreement)
    session.flush()
    return agreement


def render(
    application: Application,
    terms: LoanTerms,
    number: str,
    version: int,
    offer_version: int,
    rounds: int,
    issue: date,
) -> str:
    """The agreement as plain text; the hash is taken of exactly this text."""
    company = application.company
    day = application.payment_day
    schedule = annuity_schedule(
        terms.amount, terms.rate, terms.term_months, terms.monthly_payment, issue, day
    )
    total = sum(p.payment for p in schedule)
    rate = f"{terms.rate:g}".replace(".", ",")
    basis = f"Предложение банка, версия {offer_version}"
    if rounds:
        word = "раунда" if rounds % 10 == 1 and rounds % 100 != 11 else "раундов"
        basis += f", после {rounds} {word} переговоров"
    first = schedule[0].due_date
    lines = [
        f"КРЕДИТНЫЙ ДОГОВОР № {number}",
        f"Редакция {version} от {issue:%d.%m.%Y}",
        "Демонстрационный документ прототипа, юридической силы не имеет.",
        "",
        f"Заёмщик: {company.name}, ИНН {company.inn}, руководитель — {company.director}.",
        "Кредитор: Банк.",
        "",
        "1. Условия кредита",
        f"Продукт: {application.product.name}.",
        f"Сумма кредита: {money(terms.amount)}.",
        f"Срок: {terms.term_months} мес.",
        f"Процентная ставка: {rate}% годовых.",
        f"Ежемесячный платёж: {money(terms.monthly_payment)}, аннуитетный.",
        f"Дата платежа: {day}-е число каждого месяца"
        + (f", первый платёж — {first:%d.%m.%Y}." if first is not None else "."),
        f"Всего к выплате: {money(total)}, в том числе проценты — {money(total - terms.amount)}.",
    ]
    if application.purpose:
        lines.append(f"Цель кредита: {application.purpose.rstrip('.')}.")
    lines += [
        "",
        "2. Основание",
        f"{basis}.",
        "",
        "3. График платежей",
        "№ | Дата | Платёж | Основной долг | Проценты | Остаток долга",
    ]
    for p in schedule:
        due = f"{p.due_date:%d.%m.%Y}" if p.due_date is not None else "—"
        lines.append(
            f"{p.number} | {due} | {money(p.payment)} | {money(p.principal)} | "
            f"{money(p.interest)} | {money(p.balance)}"
        )
    lines += [
        "",
        "Подписывая договор, заёмщик подтверждает, что ознакомился с условиями и графиком.",
    ]
    return "\n".join(lines) + "\n"


def summary(agreement: Agreement) -> AgreementSummary:
    return AgreementSummary(
        number=agreement.number,
        version=agreement.version,
        offer_version=agreement.offer_version,
        reason=agreement.reason,
        sha256=agreement.sha256,
        created_at=agreement.created_at,
        signed_at=agreement.signed_at,
    )


def document(agreement: Agreement) -> AgreementDocument:
    return AgreementDocument(
        **summary(agreement).model_dump(),
        text=agreement.text,
        verified=sha256(agreement.text) == agreement.sha256,
    )
