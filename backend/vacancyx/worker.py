"""Local durable worker for database-backed automation tasks."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from vacancyx.config import get_settings
from vacancyx.db.session import get_session_factory
from vacancyx.models import AutomationTask
from vacancyx.repositories import TaskRepository
from vacancyx.services.discovery import JobDiscoveryService
from vacancyx.sources.registry import SourceRegistry
from vacancyx.sources.factory import build_source_registry

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class TaskExecutionError(Exception):
    """A task failure with a safe, stable code and user-readable summary."""

    def __init__(self, error_code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.error_code = error_code
        self.public_message = public_message


class RetryableTaskError(TaskExecutionError):
    """A task failure that may succeed on a later bounded retry."""


class PermanentTaskError(TaskExecutionError):
    """A task failure that should not be retried automatically."""


@dataclass(frozen=True)
class TaskClaim:
    """Detached immutable data copied from a claimed database row."""

    id: str
    task_type: str
    payload: dict[str, Any]
    idempotency_key: str
    lease_token: str
    attempts: int


@dataclass(frozen=True)
class TaskContext:
    """Execution context supplied to handlers; no database session is held."""

    task_id: str
    idempotency_key: str
    worker_id: str
    attempt: int
    _heartbeat: Callable[[int], bool] = field(repr=False, compare=False)
    default_lease_seconds: int = 60

    def heartbeat(self, lease_seconds: int | None = None) -> bool:
        """Extend this task's lease, returning false if ownership was lost."""
        return self._heartbeat(lease_seconds or self.default_lease_seconds)


@dataclass(frozen=True)
class TaskOutcome:
    """A JSON result with an explicit terminal success classification."""

    result: dict[str, Any]
    state: Literal["succeeded", "partially_succeeded"] = "succeeded"


TaskHandler = Callable[
    [dict[str, Any], TaskContext],
    dict[str, Any] | TaskOutcome,
]


class TaskHandlerRegistry:
    """Explicit allowlist of task types that this worker is allowed to execute."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        normalized = task_type.strip()
        if not normalized or len(normalized) > 100:
            raise ValueError("task_type must contain 1 to 100 characters.")
        if normalized in self._handlers:
            raise ValueError(f"A handler is already registered for {normalized}.")
        self._handlers[normalized] = handler

    def get(self, task_type: str) -> TaskHandler | None:
        return self._handlers.get(task_type)


class TaskWorker:
    """Claim tasks briefly, execute outside transactions, then fence the outcome."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        handlers: TaskHandlerRegistry,
        worker_id: str,
        lease_seconds: int = 60,
        retry_base_delay_seconds: int = 5,
        retry_max_delay_seconds: int = 300,
        recovery_batch_size: int = 100,
    ) -> None:
        if not worker_id.strip() or len(worker_id) > 120:
            raise ValueError("worker_id must contain 1 to 120 characters.")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive.")
        if retry_base_delay_seconds < 0 or retry_max_delay_seconds < retry_base_delay_seconds:
            raise ValueError("Retry delay bounds are invalid.")
        if recovery_batch_size < 1:
            raise ValueError("recovery_batch_size must be positive.")
        self._session_factory = session_factory
        self._handlers = handlers
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds
        self.recovery_batch_size = recovery_batch_size

    def run_once(self) -> bool:
        """Run at most one task. Return false when no task was available."""
        claim: TaskClaim | None = None
        with self._session_factory() as session, session.begin():
            repository = TaskRepository(session)
            repository.recover_expired_leases(
                limit=self.recovery_batch_size,
                base_delay_seconds=self.retry_base_delay_seconds,
                max_delay_seconds=self.retry_max_delay_seconds,
            )
            task = repository.claim_next(
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if task is not None:
                claim = self._copy_claim(task)

        if claim is None:
            return False

        logger.info(
            "Claimed task",
            extra={
                "task_id": claim.id,
                "task_type": claim.task_type,
                "attempt": claim.attempts,
                "worker_id": self.worker_id,
            },
        )
        handler = self._handlers.get(claim.task_type)
        if handler is None:
            self._record_failure(
                claim,
                error_code="unsupported_task_type",
                error_message=f"No handler is registered for task type '{claim.task_type}'.",
                retryable=False,
                needs_attention=True,
            )
            return True

        context = TaskContext(
            task_id=claim.id,
            idempotency_key=claim.idempotency_key,
            worker_id=self.worker_id,
            attempt=claim.attempts,
            _heartbeat=lambda seconds: self._heartbeat(claim, seconds),
            default_lease_seconds=self.lease_seconds,
        )
        try:
            outcome = handler(claim.payload, context)
            if isinstance(outcome, TaskOutcome):
                result = outcome.result
                completion_state = outcome.state
            else:
                result = outcome
                completion_state = "succeeded"
            if not isinstance(result, dict):
                raise PermanentTaskError(
                    "invalid_task_result",
                    "Task handlers must return a JSON-compatible object.",
                )
            try:
                json.dumps(result, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise PermanentTaskError(
                    "invalid_task_result",
                    "Task handlers must return JSON-compatible data.",
                ) from error
        except PermanentTaskError as error:
            self._record_failure(
                claim,
                error_code=error.error_code,
                error_message=error.public_message,
                retryable=False,
            )
        except RetryableTaskError as error:
            self._record_failure(
                claim,
                error_code=error.error_code,
                error_message=error.public_message,
                retryable=True,
            )
        except Exception as error:
            logger.error(
                "Task handler raised an unexpected exception",
                extra={"task_id": claim.id, "error_type": type(error).__name__},
            )
            self._record_failure(
                claim,
                error_code="unhandled_task_error",
                error_message=type(error).__name__,
                retryable=True,
            )
        else:
            with self._session_factory() as session, session.begin():
                completed = TaskRepository(session).complete(
                    task_id=claim.id,
                    lease_token=claim.lease_token,
                    result=result,
                    state=completion_state,
                )
            if not completed:
                logger.warning(
                    "Task result discarded because the worker no longer owns a live lease",
                    extra={"task_id": claim.id, "worker_id": self.worker_id},
                )
            else:
                logger.info(
                    "Task completed",
                    extra={"task_id": claim.id, "worker_id": self.worker_id},
                )
        return True

    def run_forever(
        self,
        *,
        poll_interval_seconds: float = 2.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Poll until stopped; idle waits are interruptible for clean shutdown."""
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive.")
        stop = stop_event or threading.Event()
        logger.info("Worker started", extra={"worker_id": self.worker_id})
        while not stop.is_set():
            if not self.run_once():
                stop.wait(poll_interval_seconds)
        logger.info("Worker stopped", extra={"worker_id": self.worker_id})

    def _heartbeat(self, claim: TaskClaim, lease_seconds: int) -> bool:
        with self._session_factory() as session, session.begin():
            return TaskRepository(session).heartbeat(
                task_id=claim.id,
                lease_token=claim.lease_token,
                lease_seconds=lease_seconds,
            )

    def _record_failure(
        self,
        claim: TaskClaim,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
        needs_attention: bool = False,
    ) -> None:
        with self._session_factory() as session, session.begin():
            recorded = TaskRepository(session).fail(
                task_id=claim.id,
                lease_token=claim.lease_token,
                error_code=error_code,
                error_message=error_message,
                retryable=retryable,
                needs_attention=needs_attention,
                base_delay_seconds=self.retry_base_delay_seconds,
                max_delay_seconds=self.retry_max_delay_seconds,
            )
        if not recorded:
            logger.warning(
                "Task failure discarded because the worker no longer owns a live lease",
                extra={"task_id": claim.id, "worker_id": self.worker_id},
            )
        else:
            logger.warning(
                "Task attempt failed",
                extra={
                    "task_id": claim.id,
                    "worker_id": self.worker_id,
                    "error_code": error_code,
                    "retryable": retryable,
                    "needs_attention": needs_attention,
                },
            )

    @staticmethod
    def _copy_claim(task: AutomationTask) -> TaskClaim:
        if task.lease_token is None:
            raise RuntimeError("Claimed task is missing its lease token.")
        return TaskClaim(
            id=task.id,
            task_type=task.task_type,
            payload=dict(task.payload),
            idempotency_key=task.idempotency_key,
            lease_token=task.lease_token,
            attempts=task.attempts,
        )


def _echo_handler(payload: dict[str, Any], context: TaskContext) -> dict[str, Any]:
    """Small local diagnostic handler for verifying the worker installation."""
    return {"task_id": context.task_id, "echo": payload}


def _discovery_handler(
    session_factory: SessionFactory,
    source_registry: SourceRegistry,
) -> TaskHandler:
    """Create a handler for one configured public job source."""

    def handle(payload: dict[str, Any], context: TaskContext) -> dict[str, Any] | TaskOutcome:
        source_key = payload.get("source_key")
        if not isinstance(source_key, str) or not source_key:
            raise PermanentTaskError("invalid_source_key", "A source key is required.")
        try:
            source_registry.get(source_key)
        except (KeyError, ValueError) as error:
            raise PermanentTaskError(
                "unknown_source",
                "The requested public source is not configured.",
            ) from error
        if not context.heartbeat():
            raise PermanentTaskError("lease_lost", "The worker no longer owns this task lease.")

        with session_factory() as session:
            summary = asyncio.run(
                JobDiscoveryService(
                    session,
                    source_registry,
                    heartbeat=lambda: context.heartbeat(),
                ).discover_source(source_key)
            )

        result: dict[str, Any] = {
            "source_key": summary.source_key,
            "status": summary.status,
            "pages_fetched": summary.pages_fetched,
            "listings_seen": summary.listings_seen,
            "jobs_created": summary.jobs_created,
            "observations_created": summary.observations_created,
            "observations_updated": summary.observations_updated,
            "truncated": summary.truncated,
            "error_codes": summary.error_codes,
        }
        transient_codes = {"source_timeout", "source_request_failed", "persistence_failed"}
        permanent_codes = {
            "unsafe_listing_url",
            "unsafe_source_url",
            "invalid_source_response",
            "pagination_cycle",
            "source_page_limit_exceeded",
        }
        if any(code in transient_codes for code in summary.error_codes):
            raise RetryableTaskError(
                "source_discovery_failed",
                "The public source could not be refreshed; the task will retry.",
            )
        if any(code in permanent_codes for code in summary.error_codes):
            raise PermanentTaskError(
                "source_discovery_rejected",
                "The source returned unsafe or invalid data and was stopped.",
            )
        if summary.status == "failed" or summary.error_codes:
            raise PermanentTaskError(
                "source_discovery_rejected",
                "The source returned invalid data or violated source policy.",
            )
        if summary.truncated:
            return TaskOutcome(result=result, state="partially_succeeded")
        return result

    return handle


def build_default_registry(
    *,
    session_factory: SessionFactory | None = None,
    source_registry: SourceRegistry | None = None,
) -> TaskHandlerRegistry:
    """Register the diagnostic handler and configured public job discovery handler."""
    if (session_factory is None) != (source_registry is None):
        raise ValueError("session_factory and source_registry must be provided together.")
    registry = TaskHandlerRegistry()
    registry.register("system.echo", _echo_handler)
    if session_factory is not None and source_registry is not None:
        registry.register(
            "jobs.discover_source",
            _discovery_handler(session_factory, source_registry),
        )
    return registry


def main() -> None:
    """Run a worker process; interrupted tasks are recovered after their leases expire."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the local VacancyX durable task worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one task and exit.",
    )
    parser.add_argument(
        "--worker-id",
        default=f"{socket.gethostname()}:{uuid4().hex[:8]}",
        help="Unique worker identifier (default: generated for this process).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help=(
            "Seconds to wait when the queue is empty "
            "(defaults to VACANCYX_WORKER_POLL_INTERVAL_SECONDS)."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    session_factory = get_session_factory()
    source_registry = build_source_registry(settings)
    worker = TaskWorker(
        session_factory=session_factory,
        handlers=build_default_registry(
            session_factory=session_factory,
            source_registry=source_registry,
        ),
        worker_id=args.worker_id,
        lease_seconds=settings.worker_lease_seconds,
        retry_base_delay_seconds=settings.worker_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.worker_retry_max_delay_seconds,
    )
    if args.once:
        worker.run_once()
        return
    try:
        poll_interval = (
            args.poll_interval
            if args.poll_interval is not None
            else settings.worker_poll_interval_seconds
        )
        worker.run_forever(poll_interval_seconds=poll_interval)
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")


if __name__ == "__main__":
    main()
