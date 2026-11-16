"""Persistent schedules for recurring public job discovery."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vacancyx.db.base import Base, TimestampMixin
from vacancyx.models.entities import new_id


class PublicJobSource(TimestampMixin, Base):
    """Candidate-independent public Greenhouse or Lever board configuration."""

    __tablename__ = "public_job_sources"
    __table_args__ = (
        CheckConstraint("provider IN ('greenhouse', 'lever')", name="ck_public_job_sources_provider"),
        UniqueConstraint("source_key", name="uq_public_job_sources_source_key"),
        Index("ix_public_job_sources_enabled", "is_enabled"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_key: Mapped[str] = mapped_column(String(100), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DiscoverySchedule(TimestampMixin, Base):
    """Candidate-independent local schedule for recurring configured source discovery."""

    __tablename__ = "discovery_schedules"
    __table_args__ = (
        CheckConstraint(
            "interval_seconds >= 60 AND interval_seconds <= 2592000",
            name="ck_discovery_schedules_interval",
        ),
        CheckConstraint("run_number >= 0", name="ck_discovery_schedules_run_number"),
        Index("ix_discovery_schedules_due", "is_enabled", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
