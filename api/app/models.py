"""SQLAlchemy 2 ORM models for Silent Claim (matching docs/ARCHITECTURE.md)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return the current timezone-aware datetime in Asia/Kolkata."""
    return datetime.now(IST)


def to_ist(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware Asia/Kolkata."""
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


class ISTDateTime(TypeDecorator[datetime]):
    """Store timestamps and always return timezone-aware Asia/Kolkata datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        return to_ist(value)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        return to_ist(value)


class Base(DeclarativeBase):
    """Declarative base for all Silent Claim ORM models."""


class Street(Base):
    """A commercial street monitored for correlated shutdowns."""

    __tablename__ = "streets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class Shop(Base):
    """A merchant shop on a monitored street."""

    __tablename__ = "shops"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    owner: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    street_id: Mapped[str] = mapped_column(ForeignKey("streets.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    plan_active: Mapped[bool] = mapped_column(Boolean, default=True)
    staging_order_id: Mapped[str] = mapped_column(String(128))


class PaymentHourly(Base):
    """Hourly synthetic/replayed payment totals for a shop (amounts in integer paise)."""

    __tablename__ = "payments_hourly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id"), index=True)
    ts_hour: Mapped[datetime] = mapped_column(ISTDateTime(), index=True)
    n_payments: Mapped[int] = mapped_column(Integer)
    amount_paise: Mapped[int] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("shop_id", "ts_hour", name="uq_payments_hourly_shop_ts"),)


class Detection(Base):
    """Daily deterministic detector evaluation result for a shop."""

    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    baseline_paise: Mapped[int] = mapped_column(Integer)
    day_income_paise: Mapped[int] = mapped_column(Integer)
    dropped: Mapped[bool] = mapped_column(Boolean)
    eligible: Mapped[bool] = mapped_column(Boolean)
    quorum_share: Mapped[float] = mapped_column(Float)
    rain_mm: Mapped[float] = mapped_column(Float)
    rain_source: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(64))
    rules_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist)

    __table_args__ = (UniqueConstraint("shop_id", "day", name="uq_detections_shop_day"),)


class Ask(Base):
    """Merchant consent or voice-clarification prompt linked to a paused LangGraph thread."""

    __tablename__ = "asks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"), unique=True, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    ask_kind: Mapped[str] = mapped_column(String(16))  # consent | voice
    prompt_text_ta: Mapped[str] = mapped_column(Text)
    prompt_audio_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reply_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # tap | voice
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    simulated_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    answered_at: Mapped[datetime | None] = mapped_column(ISTDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist)


class Batch(Base):
    """Adjuster review batch grouping filed claims."""

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(ISTDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist)


class Claim(Base):
    """Filed income-protection claim backed by a deterministic Detection and PDF evidence pack."""

    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id"), index=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detections.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="filed")
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(ISTDateTime(), nullable=True)
    evidence_pdf_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("batches.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist)


class Refund(Base):
    """Monthly plan-fee refund record (Rs 35 = 3500 paise) with unique monthly and refund ID keys."""

    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("claims.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id"), index=True)
    refund_month: Mapped[str] = mapped_column(String(7), index=True)
    paytm_order_id: Mapped[str] = mapped_column(String(128))
    refund_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    mode_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist)

    __table_args__ = (UniqueConstraint("shop_id", "refund_month", name="uq_refunds_shop_month"),)


class AuditLog(Base):
    """Append-only operational audit trail (PII- and secret-free)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(ISTDateTime(), default=now_ist, index=True)
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
