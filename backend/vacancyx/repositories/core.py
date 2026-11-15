"""Small repositories; use cases own transaction boundaries."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vacancyx.models import AutomationTask, CandidateProfile, Job, Resume


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
        normalized_type = task_type.strip()
        normalized_key = idempotency_key.strip()
        if not normalized_type or len(normalized_type) > 100:
            raise ValueError("task_type must contain 1 to 100 characters.")
        if not normalized_key or len(normalized_key) > 255:
            raise ValueError("idempotency_key must contain 1 to 255 characters.")
        if not 1 <= max_attempts <= 20:
            raise ValueError("max_attempts must be between 1 and 20.")

        existing = self._session.scalar(
            select(AutomationTask).where(AutomationTask.idempotency_key == normalized_key)
        )
        if existing is not None:
            if (
                existing.task_type != normalized_type
                or existing.payload != payload
                or existing.max_attempts != max_attempts
            ):
                raise ValueError(
                    "idempotency_key is already used for a different task request."
                )
            return existing

        task = AutomationTask(
            task_type=normalized_type,
            payload=payload,
            idempotency_key=normalized_key,
            available_at=available_at or datetime.now(UTC),
            max_attempts=max_attempts,
        )
        try:
            with self._session.begin_nested():
                self._session.add(task)
                self._session.flush()
            return task
        except IntegrityError:
            existing = self._session.scalar(
                select(AutomationTask).where(AutomationTask.idempotency_key == normalized_key)
            )
            if existing is None:
                raise
            if (
                existing.task_type != normalized_type
                or existing.payload != payload
                or existing.max_attempts != max_attempts
            ):
                raise ValueError(
                    "idempotency_key is already used for a different task request."
                )
            return existing

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> AutomationTask | None:
        """Atomically claim one available task using a conditional update."""
        if not worker_id.strip() or len(worker_id) > 120:
            raise ValueError("worker_id must contain 1 to 120 characters.")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive.")
        worker_id = worker_id.strip()
        claimed_at = now or datetime.now(UTC)
        candidate_id = self._session.scalar(
            select(AutomationTask.id)
            .where(
                AutomationTask.state.in_(("queued", "retry_wait")),
                AutomationTask.available_at <= claimed_at,
                AutomationTask.attempts < AutomationTask.max_attempts,
            )
            .order_by(
                AutomationTask.available_at,
                AutomationTask.created_at,
                AutomationTask.id,
            )
            .limit(1)
        )
        if candidate_id is None:
            return None
        token = str(uuid4())
        claimed_id = self._session.scalar(
            update(AutomationTask)
            .where(
                AutomationTask.id == candidate_id,
                AutomationTask.state.in_(("queued", "retry_wait")),
                AutomationTask.available_at <= claimed_at,
                AutomationTask.attempts < AutomationTask.max_attempts,
            )
            .values(
                state="running",
                lease_owner=worker_id,
                lease_token=token,
                lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                attempts=AutomationTask.attempts + 1,
                updated_at=claimed_at,
            )
            .returning(AutomationTask.id)
        )
        if claimed_id is None:
            return None
        self._session.flush()
        return self._session.get(AutomationTask, claimed_id, populate_existing=True)

    def heartbeat(
        self,
        *,
        task_id: str,
        lease_token: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> bool:
        """Extend a live lease only when the caller still owns its fencing token."""
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive.")
        current_time = now or datetime.now(UTC)
        renewed_id = self._session.scalar(
            update(AutomationTask)
            .where(
                AutomationTask.id == task_id,
                AutomationTask.state == "running",
                AutomationTask.lease_token == lease_token,
                AutomationTask.lease_expires_at > current_time,
            )
            .values(
                lease_expires_at=current_time + timedelta(seconds=lease_seconds),
                updated_at=current_time,
            )
            .returning(AutomationTask.id)
        )
        return renewed_id is not None

    def complete(
        self,
        *,
        task_id: str,
        lease_token: str,
        result: dict[str, Any],
        state: str = "succeeded",
        now: datetime | None = None,
    ) -> bool:
        """Finish a task only while its lease is live and still owned by this worker."""
        if state not in {"succeeded", "partially_succeeded"}:
            raise ValueError("A completed task must be succeeded or partially_succeeded.")
        current_time = now or datetime.now(UTC)
        completed_id = self._session.scalar(
            update(AutomationTask)
            .where(
                AutomationTask.id == task_id,
                AutomationTask.state == "running",
                AutomationTask.lease_token == lease_token,
                AutomationTask.lease_expires_at > current_time,
            )
            .values(
                state=state,
                result=result,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                last_error_code=None,
                last_error_message=None,
                updated_at=current_time,
            )
            .returning(AutomationTask.id)
        )
        return completed_id is not None

    def fail(
        self,
        *,
        task_id: str,
        lease_token: str,
        error_code: str,
        error_message: str,
        retryable: bool = True,
        needs_attention: bool = False,
        base_delay_seconds: int = 5,
        max_delay_seconds: int = 300,
        now: datetime | None = None,
    ) -> bool:
        """Record a failure, applying bounded exponential backoff when retryable."""
        if base_delay_seconds < 0 or max_delay_seconds < 0:
            raise ValueError("Retry delays cannot be negative.")
        current_time = now or datetime.now(UTC)
        task = self._session.scalar(
            select(AutomationTask).where(
                AutomationTask.id == task_id,
                AutomationTask.state == "running",
                AutomationTask.lease_token == lease_token,
                AutomationTask.lease_expires_at > current_time,
            )
        )
        if task is None:
            return False

        if needs_attention:
            next_state = "needs_attention"
            available_at = current_time
        elif retryable and task.attempts < task.max_attempts:
            next_state = "retry_wait"
            exponent = max(task.attempts - 1, 0)
            delay = min(max_delay_seconds, base_delay_seconds * (2**exponent))
            available_at = current_time + timedelta(seconds=delay)
        else:
            next_state = "failed"
            available_at = current_time

        failed_id = self._session.scalar(
            update(AutomationTask)
            .where(
                AutomationTask.id == task_id,
                AutomationTask.state == "running",
                AutomationTask.lease_token == lease_token,
                AutomationTask.lease_expires_at > current_time,
            )
            .values(
                state=next_state,
                available_at=available_at,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                last_error_code=error_code[:100],
                last_error_message=error_message[:4000],
                updated_at=current_time,
            )
            .returning(AutomationTask.id)
        )
        return failed_id is not None

    def recover_expired_leases(
        self,
        *,
        limit: int = 100,
        base_delay_seconds: int = 5,
        max_delay_seconds: int = 300,
        now: datetime | None = None,
    ) -> int:
        """Requeue expired work or fail exhausted tasks, fenced by the expired lease."""
        if limit < 1 or base_delay_seconds < 0 or max_delay_seconds < 0:
            raise ValueError("Recovery limits and retry delays must be non-negative.")
        current_time = now or datetime.now(UTC)
        expired = list(
            self._session.execute(
                select(AutomationTask.id, AutomationTask.attempts, AutomationTask.max_attempts)
                .where(
                    AutomationTask.state == "running",
                    AutomationTask.lease_expires_at <= current_time,
                )
                .order_by(AutomationTask.lease_expires_at, AutomationTask.id)
                .limit(limit)
            )
        )
        recovered = 0
        for task_id, attempts, max_attempts in expired:
            exhausted = attempts >= max_attempts
            if exhausted:
                next_state = "failed"
                available_at = current_time
                error_code = "lease_expired_max_attempts"
                error_message = "The worker lease expired and the retry limit was reached."
            else:
                next_state = "retry_wait"
                exponent = max(attempts - 1, 0)
                delay = min(max_delay_seconds, base_delay_seconds * (2**exponent))
                available_at = current_time + timedelta(seconds=delay)
                error_code = "lease_expired"
                error_message = "The worker lease expired before the task was completed."

            recovered_id = self._session.scalar(
                update(AutomationTask)
                .where(
                    AutomationTask.id == task_id,
                    AutomationTask.state == "running",
                    AutomationTask.lease_expires_at <= current_time,
                )
                .values(
                    state=next_state,
                    available_at=available_at,
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    last_error_code=error_code,
                    last_error_message=error_message,
                    updated_at=current_time,
                )
                .returning(AutomationTask.id)
            )
            if recovered_id is not None:
                recovered += 1
        self._session.flush()
        return recovered

    def cancel(self, *, task_id: str, now: datetime | None = None) -> bool:
        """Cancel queued or running work and revoke any active worker fencing token."""
        current_time = now or datetime.now(UTC)
        cancelled_id = self._session.scalar(
            update(AutomationTask)
            .where(
                AutomationTask.id == task_id,
                AutomationTask.state.in_(("queued", "retry_wait", "running")),
            )
            .values(
                state="cancelled",
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                updated_at=current_time,
            )
            .returning(AutomationTask.id)
        )
        return cancelled_id is not None



class ResumeRepository:
    """Candidate-owned resume metadata operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, resume: Resume) -> Resume:
        self._session.add(resume)
        self._session.flush()
        return resume

    def get(self, resume_id: str) -> Resume | None:
        return self._session.get(Resume, resume_id)

    def list_for_candidate(self, candidate_id: str) -> list[Resume]:
        statement = (
            select(Resume)
            .where(Resume.candidate_id == candidate_id)
            .order_by(Resume.created_at.desc(), Resume.id)
        )
        return list(self._session.scalars(statement))
