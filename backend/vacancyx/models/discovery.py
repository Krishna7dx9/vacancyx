"""Persistent schedules for recurring public job discovery."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from vacancyx.db.base import Base, TimestampMixin
from vacancyx.models.entities import new_id


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
