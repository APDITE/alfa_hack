"""TEMPORARY sample data for the client feed. Delete once the feed reads from the database."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.schemas import FeedItem, FeedItemType

NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
SAMPLE_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000001")

SAMPLE_FEED: list[FeedItem] = [
    FeedItem(
        id=UUID("00000000-0000-0000-0000-0000000000f1"),
        type=FeedItemType.EVENT,
        title="Решение готово",
        text="Банк одобрил заявку на 1 500 000 ₽ на 12 месяцев.",
        application_id=SAMPLE_APPLICATION_ID,
        created_at=NOW,
        read=False,
    ),
    FeedItem(
        id=UUID("00000000-0000-0000-0000-0000000000f2"),
        type=FeedItemType.NEWS,
        title="Сниженная ставка для розницы",
        text="Для магазинов (ОКВЭД 47) оборотный кредит до конца года — от 17,9%.",
        created_at=NOW - timedelta(days=1),
        read=True,
    ),
]
