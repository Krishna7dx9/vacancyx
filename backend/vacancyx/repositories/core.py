"""Small repositories; use cases own transaction boundaries."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from vacancyx.models import AutomationTask, CandidateProfile, Job


class CandidateRepository:
    """Candidate persistence operations; never commits implicitly."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, candidate: CandidateProfile) -> CandidateProfile:
        self._session.add(candidate)
        self._session.flush()
        return candidate

    def get(self, candidate_id: str) -> CandidateProfile | None:
        return self._session.get(CandidateProfile, candidate_id)

    def list_active(self, *, limit: int = 100, offset: int = 0) -> list[CandidateProfile]:
        statement = (
            select(CandidateProfile)
            .where(CandidateProfile.is_active.is_(True))
            .order_by(CandidateProfile.created_at.desc(), CandidateProfile.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(statement))


class JobRepository:
    """Canonical job persistence operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, job: Job) -> Job:
        self._session.add(job)
        self._session.flush()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._session.get(Job, job_id)

    def find_by_canonical_url(self, canonical_url: str) -> Job | None:
        return self._session.scalar(select(Job).where(Job.canonical_url == canonical_url))


class TaskRepository:
    """Durable task queue primitives; external work must happen outside transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        task_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        available_at: datetime | None = None,
        max_attempts: int = 5,
    ) -> AutomationTask:
        existing = self._session.scalar(
            select(AutomationTask).where(AutomationTask.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        task = AutomationTask(
            task_type=task_type,
            payload=payload,
            idempotency_key=idempotency_key,
            available_at=available_at or datetime.now(UTC),
            max_attempts=max_attempts,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def claim_next(self, *, worker_id: str, lease_seconds: int = 60) -> AutomationTask | None:
        """Atomically claim one available task using a conditional update."""
        now = datetime.now(UTC)
        candidate_id = self._session.scalar(
            select(AutomationTask.id)
            .where(
                AutomationTask.state.in_(("queued", "retry_wait")),
                AutomationTask.available_at <= now,
                AutomationTask.attempts < AutomationTask.max_attempts,
            )
            .order_by(AutomationTask.available_at, AutomationTask.created_at, AutomationTask.id)
            .limit(1)
        )
        if candidate_id is None:
            return None
        token = str(uuid4())
        result = self._session.execute(
            update(AutomationTask)
            .where(
                AutomationTask.id == candidate_id,
                AutomationTask.state.in_(("queued", "retry_wait")),
                AutomationTask.available_at <= now,
            )
            .values(
                state="running",
                lease_owner=worker_id,
                lease_token=token,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                attempts=AutomationTask.attempts + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self._session.get(AutomationTask, candidate_id)
