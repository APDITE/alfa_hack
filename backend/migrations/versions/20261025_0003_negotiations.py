"""negotiations: the client's proposals and versions of the loan agreement

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("offer_version", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_version", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "round", name="uq_proposals_round"),
    )
    op.create_index(
        op.f("ix_proposals_application_id"), "proposals", ["application_id"], unique=False
    )
    op.create_table(
        "agreements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("offer_version", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "version", name="uq_agreements_version"),
    )
    op.create_index(
        op.f("ix_agreements_application_id"), "agreements", ["application_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agreements_application_id"), table_name="agreements")
    op.drop_table("agreements")
    op.drop_index(op.f("ix_proposals_application_id"), table_name="proposals")
    op.drop_table("proposals")
