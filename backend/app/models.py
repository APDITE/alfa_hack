"""Database tables (spec, section 11). Enum columns store the enum *values* as strings."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.statuses import Actor, ApplicationStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type[StrEnum], length: int = 32) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class UserRole(StrEnum):
    CLIENT = "client"
    EMPLOYEE = "employee"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, 16))
    company_inn: Mapped[str | None] = mapped_column(ForeignKey("companies.inn"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    company: Mapped["Company | None"] = relationship()


class Company(Base):
    __tablename__ = "companies"

    inn: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    legal_form: Mapped[str] = mapped_column(String(8))
    okved: Mapped[str] = mapped_column(String(16))
    registration_date: Mapped[date] = mapped_column(Date)
    region: Mapped[str] = mapped_column(String(8))
    director: Mapped[str] = mapped_column(String(200))
    registry_status: Mapped[str] = mapped_column(String(16), default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class FinancialStatement(Base):
    """Company financials from 'Transparent business' or entered by the client."""

    __tablename__ = "financial_statements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_inn: Mapped[str] = mapped_column(ForeignKey("companies.inn"), index=True)
    period_end: Mapped[date] = mapped_column(Date)
    revenue_year: Mapped[int] = mapped_column(BigInteger)
    expenses_year: Mapped[int] = mapped_column(BigInteger)
    liabilities_total: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    purposes: Mapped[list[str]] = mapped_column(JSON)
    min_amount: Mapped[int] = mapped_column(BigInteger)
    max_amount: Mapped[int] = mapped_column(BigInteger)
    min_term_months: Mapped[int] = mapped_column(Integer)
    max_term_months: Mapped[int] = mapped_column(Integer)
    base_rate: Mapped[float] = mapped_column(Float)
    min_business_age_months: Mapped[int] = mapped_column(Integer)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    company_inn: Mapped[str] = mapped_column(ForeignKey("companies.inn"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    purpose_category: Mapped[str | None] = mapped_column(String(32))
    purpose: Mapped[str | None] = mapped_column(String(500))
    amount: Mapped[int | None] = mapped_column(BigInteger)
    term_months: Mapped[int | None] = mapped_column(Integer)
    # Financials entered by the client when 'Transparent business' has none (scenario 3).
    revenue_year: Mapped[int | None] = mapped_column(BigInteger)
    expenses_year: Mapped[int | None] = mapped_column(BigInteger)
    liabilities_total: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus), default=ApplicationStatus.DRAFT, index=True
    )
    waiting_external: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    product: Mapped[Product] = relationship()
    history: Mapped[list["StatusHistory"]] = relationship(
        order_by="StatusHistory.created_at", cascade="all, delete-orphan"
    )


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    from_status: Mapped[ApplicationStatus | None] = mapped_column(_enum(ApplicationStatus))
    to_status: Mapped[ApplicationStatus] = mapped_column(_enum(ApplicationStatus))
    actor: Mapped[Actor] = mapped_column(_enum(Actor, 16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Clarification(Base):
    __tablename__ = "clarifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    requested_fields: Mapped[list[str]] = mapped_column(JSON)
    message: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[Actor] = mapped_column(_enum(Actor, 16))
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckResultRecord(Base):
    __tablename__ = "check_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScoreRecord(Base):
    __tablename__ = "score_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    pd: Mapped[float] = mapped_column(Float)
    risk_class: Mapped[str] = mapped_column(String(16))
    points_total: Mapped[int] = mapped_column(Integer)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    rule: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    offer: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decided_by: Mapped[Actor] = mapped_column(_enum(Actor, 16))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineJob(Base):
    """Work queue for the pipeline worker (SELECT ... FOR UPDATE SKIP LOCKED)."""

    __tablename__ = "pipeline_jobs"
    __table_args__ = (Index("ix_pipeline_jobs_ready", "status", "run_after"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    stage: Mapped[ApplicationStatus] = mapped_column(_enum(ApplicationStatus))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus, 16), default=JobStatus.PENDING)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class FeedItemRecord(Base):
    __tablename__ = "feed_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id"))
    type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
