"""Candidate-owned reusable answers and immutable content revisions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vacancyx.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from vacancyx.models.entities import CandidateProfile


def _new_id() -> str:
    return str(uuid4())


class CandidateAnswer(TimestampMixin, Base):
    """Latest editable version of one candidate's reusable application answer."""

    __tablename__ = "candidate_answers"
    __table_args__ = (
        UniqueConstraint("candidate_id", "question_hash", name="uq_candidate_answer_question"),
        CheckConstraint("current_revision > 0", name="ck_candidate_answer_positive_revision"),
        CheckConstraint(
            "source IN ('manual', 'resume_reviewed', 'imported')",
            name="ck_candidate_answer_source",
        ),
        Index("ix_candidate_answers_candidate_active", "candidate_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    revisions: Mapped[list[CandidateAnswerRevision]] = relationship(
        back_populates="answer", cascade="all, delete-orphan", order_by="CandidateAnswerRevision.revision"
    )


class CandidateAnswerRevision(Base):
    """Append-only snapshot of answer content at a particular revision."""

    __tablename__ = "candidate_answer_revisions"
    __table_args__ = (
        UniqueConstraint("answer_id", "revision", name="uq_candidate_answer_revision"),
        CheckConstraint("revision > 0", name="ck_candidate_answer_revision_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    answer_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    question_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    answer_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    category_snapshot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags_snapshot: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    answer: Mapped[CandidateAnswer] = relationship(back_populates="revisions")
