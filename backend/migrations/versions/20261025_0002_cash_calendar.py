"""cash calendar: payment day and the client's typical month

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("payment_day", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("cash_calendar", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "cash_calendar")
    op.drop_column("applications", "payment_day")
