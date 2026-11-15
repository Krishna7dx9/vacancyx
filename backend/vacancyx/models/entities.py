"""Persistence entities for candidate, job and application workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vacancyx.db.base import Base, TimestampMixin


def new_id() -> str:
    """Create opaque identifiers without exposing sequential record counts."""
    return str(uuid4())


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    links: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    resumes: Mapped[list[Resume]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    search_profiles: Mapped[list[SearchProfile]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(back_populates="candidate")


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="ck_resumes_positive_size"),
        UniqueConstraint("candidate_id", "checksum_sha256", name="uq_resume_candidate_checksum"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    parsed_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    candidate: Mapped[CandidateProfile] = relationship(back_populates="resumes")


class SearchProfile(TimestampMixin, Base):
    __tablename__ = "search_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    candidate: Mapped[CandidateProfile] = relationship(back_populates="search_profiles")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_company_title", "company_name", "title"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, unique=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    first_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")

    observations: Mapped[list[JobObservation]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(back_populates="job")


class JobObservation(TimestampMixin, Base):
    __tablename__ = "job_observations"
    __table_args__ = (
        UniqueConstraint("source_key", "external_id", name="uq_job_observation_source_external"),
        Index("ix_job_observations_job_seen", "job_id", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped[Job] = relationship(back_populates="observations")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
        CheckConstraint(
            "status IN ('draft', 'prepared', 'approved', 'submitting', 'submitted', "
            "'uncertain', 'blocked', 'rejected', 'withdrawn')",
            name="ck_applications_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    resume_id: Mapped[str | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate: Mapped[CandidateProfile] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    revisions: Mapped[list[ApplicationRevision]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[ApplicationApproval]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationRevision(TimestampMixin, Base):
    __tablename__ = "application_revisions"
    __table_args__ = (
        UniqueConstraint("application_id", "revision", name="uq_application_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    resume_id: Mapped[str | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))

    application: Mapped[Application] = relationship(back_populates="revisions")


class ApplicationApproval(TimestampMixin, Base):
    __tablename__ = "application_approvals"
    __table_args__ = (
        UniqueConstraint("application_id", "revision", name="uq_approval_application_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    application: Mapped[Application] = relationship(back_populates="approvals")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    application: Mapped[Application] = relationship(back_populates="events")


class AutomationTask(TimestampMixin, Base):
    __tablename__ = "automation_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_automation_task_idempotency"),
        CheckConstraint(
            "state IN ('queued', 'running', 'retry_wait', 'succeeded', "
            "'partially_succeeded', 'failed', 'cancelled', 'needs_attention')",
            name="ck_automation_tasks_state",
        ),
        Index("ix_automation_tasks_claim", "state", "available_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ApplicationBatch(TimestampMixin, Base):
    """Candidate-owned review batch containing revision-bound application items."""

    __tablename__ = "application_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reviewing', 'completed', 'cancelled')",
            name="ck_application_batches_status",
        ),
        Index("ix_application_batches_candidate_created", "candidate_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="reviewing")

    items: Mapped[list[ApplicationBatchItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="ApplicationBatchItem.created_at",
    )


class ApplicationBatchItem(TimestampMixin, Base):
    """Immutable reference to the exact application revision reviewed in a batch."""

    __tablename__ = "application_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "application_id", name="uq_batch_application_item"),
        CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected', 'stale')",
            name="ck_application_batch_items_decision",
        ),
        CheckConstraint("revision > 0", name="ck_application_batch_items_revision"),
        Index("ix_application_batch_items_batch_decision", "batch_id", "decision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("application_batches.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[ApplicationBatch] = relationship(back_populates="items")
    application: Mapped[Application] = relationship()
