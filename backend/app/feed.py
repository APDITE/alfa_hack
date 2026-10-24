"""Client notifications: events of the client's applications.

Events are written by `lifecycle.transition` whenever an application reaches a status the
client should hear about, so notifications can never disagree with the status history.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Application, FeedItemRecord
from app.schemas import FeedItem, FeedItemType, FeedResponse
from app.statuses import ApplicationStatus

S = ApplicationStatus

# Statuses the client is notified about: (title, text). Internal stages are left out.
_EVENTS: dict[ApplicationStatus, tuple[str, str]] = {
    S.SUBMITTED: (
        "Заявка отправлена",
        "Заявка на {amount} на {term} мес. принята банком. Проверка займёт несколько минут.",
    ),
    S.CLARIFICATION_REQUIRED: (
        "Нужны уточнения",
        "Банку не хватает данных по заявке на {amount}. Ответьте в карточке заявки — "
        "проверка продолжится сразу после ответа.",
    ),
    S.MANUAL_REVIEW: (
        "Заявку смотрит специалист",
        "Заявка на {amount} передана кредитному специалисту. "
        "Обычно это занимает до одного рабочего дня.",
    ),
    S.APPROVED: (
        "Заявка одобрена",
        "Банк готов выдать {amount} на {term} мес. Посмотрите условия в карточке заявки.",
    ),
    S.COUNTER_OFFER: (
        "Банк предлагает другие условия",
        "По заявке на {amount} банк готов выдать кредит на других условиях. "
        "Сумма, срок и платёж — в карточке заявки.",
    ),
    S.REJECTED: (
        "Решение по заявке",
        "К сожалению, банк не может выдать {amount}. Причина указана в карточке заявки.",
    ),
    S.SIGNING: (
        "Документы готовы",
        "Условия приняты: {amount} на {term} мес. Подпишите документы в карточке заявки.",
    ),
    S.ISSUED: ("Кредит выдан", "{amount} поступили на расчётный счёт компании."),
    S.WITHDRAWN: ("Заявка отозвана", "Заявка на {amount} отозвана."),
}


def money(amount: int | None) -> str:
    """1500000 -> '1 500 000 ₽' with non-breaking spaces."""
    if amount is None:
        return "—"
    return f"{amount:,}".replace(",", " ") + " ₽"


def record_event(session: Session, application: Application, status: ApplicationStatus) -> None:
    """Notify the application's client about `status`, if it is one they care about."""
    template = _EVENTS.get(status)
    if template is None:
        return
    title, text = template
    session.add(
        FeedItemRecord(
            user_id=application.client_id,
            application_id=application.id,
            type=FeedItemType.EVENT.value,
            title=title,
            text=text.format(
                amount=money(application.amount), term=application.term_months or "—"
            ),
        )
    )


def build_feed(session: Session, user_id: uuid.UUID, limit: int = 50) -> FeedResponse:
    """The client's notifications, newest first."""
    records = session.scalars(
        select(FeedItemRecord)
        .where(FeedItemRecord.user_id == user_id)
        .order_by(FeedItemRecord.created_at.desc())
        .limit(limit)
    ).all()
    events = [
        FeedItem(
            id=r.id,
            type=FeedItemType(r.type),
            title=r.title,
            text=r.text,
            application_id=r.application_id,
            created_at=r.created_at,
            read=r.read,
        )
        for r in records
    ]
    return FeedResponse(events=events, unread_events=sum(1 for e in events if not e.read))


def mark_all_read(session: Session, user_id: uuid.UUID) -> None:
    session.execute(
        update(FeedItemRecord)
        .where(FeedItemRecord.user_id == user_id, FeedItemRecord.read.is_(False))
        .values(read=True)
    )
    session.commit()
