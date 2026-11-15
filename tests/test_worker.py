"""Durable worker and lease-fencing integration tests."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.models import AutomationTask
from vacancyx.repositories import TaskRepository
from vacancyx.worker import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskHandlerRegistry,
    TaskWorker,
    build_default_registry,
)


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def enqueue(
    factory: sessionmaker[Session],
    *,
    task_type: str = "test.echo",
    payload: dict[str, object] | None = None,
    idempotency_key: str = "test-task",
    max_attempts: int = 3,
) -> str:
    with factory() as session, session.begin():
        task = TaskRepository(session).enqueue(
            task_type=task_type,
            payload=payload or {},
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
        )
        return task.id


def read_task(factory: sessionmaker[Session], task_id: str) -> AutomationTask:
    with factory() as session:
        task = session.get(AutomationTask, task_id)
        assert task is not None
        return task


def test_lease_heartbeat_and_completion_are_fenced(session_factory) -> None:
    task_id = enqueue(session_factory)
    now = datetime(2026, 1, 1, tzinfo=UTC)

    with session_factory() as session, session.begin():
        task = TaskRepository(session).claim_next(
            worker_id="worker-a", lease_seconds=10, now=now
        )
        assert task is not None
        token = task.lease_token
        assert token is not None
        assert task.attempts == 1

    with session_factory() as session, session.begin():
        repository = TaskRepository(session)
        assert not repository.heartbeat(
            task_id=task_id,
            lease_token="wrong-token",
            lease_seconds=10,
            now=now + timedelta(seconds=2),
        )
        assert repository.heartbeat(
            task_id=task_id,
            lease_token=token,
            lease_seconds=10,
            now=now + timedelta(seconds=5),
        )
        assert not repository.complete(
            task_id=task_id,
            lease_token="wrong-token",
            result={"ok": True},
            now=now + timedelta(seconds=6),
        )
        assert repository.complete(
            task_id=task_id,
            lease_token=token,
            result={"ok": True},
            now=now + timedelta(seconds=14),
        )

    completed = read_task(session_factory, task_id)
    assert completed.state == "succeeded"
    assert completed.result == {"ok": True}
    assert completed.lease_token is None
    assert completed.lease_owner is None
    assert completed.lease_expires_at is None


def test_retryable_failure_uses_bounded_backoff_and_exhausts_attempts(session_factory) -> None:
    task_id = enqueue(session_factory, max_attempts=3)
    now = datetime(2026, 1, 1, tzinfo=UTC)

    with session_factory() as session, session.begin():
        first = TaskRepository(session).claim_next(worker_id="worker-a", now=now)
        assert first is not None
        first_token = first.lease_token
        assert first_token is not None
        assert TaskRepository(session).fail(
            task_id=task_id,
            lease_token=first_token,
            error_code="temporary",
            error_message="temporary failure",
            retryable=True,
            base_delay_seconds=10,
            max_delay_seconds=15,
            now=now + timedelta(seconds=1),
        )

    waiting = read_task(session_factory, task_id)
    assert waiting.state == "retry_wait"
    assert waiting.available_at.replace(tzinfo=UTC) == now + timedelta(seconds=11)
    assert waiting.lease_token is None

    with session_factory() as session, session.begin():
        second = TaskRepository(session).claim_next(
            worker_id="worker-b", now=now + timedelta(seconds=11)
        )
        assert second is not None
        assert second.attempts == 2
        second_token = second.lease_token
        assert second_token is not None
        assert TaskRepository(session).fail(
            task_id=task_id,
            lease_token=second_token,
            error_code="still_temporary",
            error_message="backoff capped at fifteen seconds",
            retryable=True,
            base_delay_seconds=10,
            max_delay_seconds=15,
            now=now + timedelta(seconds=12),
        )

    capped = read_task(session_factory, task_id)
    assert capped.state == "retry_wait"
    assert capped.available_at.replace(tzinfo=UTC) == now + timedelta(seconds=27)

    with session_factory() as session, session.begin():
        assert TaskRepository(session).claim_next(
            worker_id="worker-c", now=now + timedelta(seconds=26)
        ) is None
        third = TaskRepository(session).claim_next(
            worker_id="worker-c", now=now + timedelta(seconds=27)
        )
        assert third is not None
        assert third.attempts == 3
        third_token = third.lease_token
        assert third_token is not None
        assert TaskRepository(session).fail(
            task_id=task_id,
            lease_token=third_token,
            error_code="retry_limit_reached",
            error_message="no attempts remain",
            retryable=True,
            base_delay_seconds=10,
            max_delay_seconds=15,
            now=now + timedelta(seconds=28),
        )

    failed = read_task(session_factory, task_id)
    assert failed.state == "failed"
    assert failed.attempts == 3
    assert failed.last_error_code == "retry_limit_reached"


def test_expired_lease_is_recovered_and_old_worker_is_fenced(session_factory) -> None:
    task_id = enqueue(session_factory)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with session_factory() as session, session.begin():
        claimed = TaskRepository(session).claim_next(
            worker_id="worker-a", lease_seconds=5, now=now
        )
        assert claimed is not None
        old_token = claimed.lease_token
        assert old_token is not None

    with session_factory() as session, session.begin():
        recovered = TaskRepository(session).recover_expired_leases(
            base_delay_seconds=3,
            max_delay_seconds=30,
            now=now + timedelta(seconds=6),
        )
        assert recovered == 1

    waiting = read_task(session_factory, task_id)
    assert waiting.state == "retry_wait"
    assert waiting.available_at.replace(tzinfo=UTC) == now + timedelta(seconds=9)
    assert waiting.lease_token is None

    with session_factory() as session, session.begin():
        assert not TaskRepository(session).complete(
            task_id=task_id,
            lease_token=old_token,
            result={"late": True},
            now=now + timedelta(seconds=7),
        )
        replacement = TaskRepository(session).claim_next(
            worker_id="worker-b", now=now + timedelta(seconds=9)
        )
        assert replacement is not None
        assert replacement.lease_token != old_token


def test_expired_lease_at_attempt_limit_fails_permanently(session_factory) -> None:
    task_id = enqueue(session_factory, max_attempts=1)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with session_factory() as session, session.begin():
        claimed = TaskRepository(session).claim_next(
            worker_id="worker-a", lease_seconds=2, now=now
        )
        assert claimed is not None

    with session_factory() as session, session.begin():
        assert TaskRepository(session).recover_expired_leases(
            now=now + timedelta(seconds=3)
        ) == 1

    task = read_task(session_factory, task_id)
    assert task.state == "failed"
    assert task.last_error_code == "lease_expired_max_attempts"
    assert task.lease_token is None


def test_cancellation_revokes_a_running_workers_lease(session_factory) -> None:
    task_id = enqueue(session_factory)
    with session_factory() as session, session.begin():
        claimed = TaskRepository(session).claim_next(worker_id="worker-a")
        assert claimed is not None
        token = claimed.lease_token
        assert token is not None

    with session_factory() as session, session.begin():
        assert TaskRepository(session).cancel(task_id=task_id)

    with session_factory() as session, session.begin():
        assert not TaskRepository(session).complete(
            task_id=task_id,
            lease_token=token,
            result={"late": True},
        )
    assert read_task(session_factory, task_id).state == "cancelled"


def test_worker_executes_handler_outside_queue_transaction_and_persists_result(
    session_factory,
) -> None:
    task_id = enqueue(session_factory, payload={"source": "fixture"})
    registry = TaskHandlerRegistry()

    def handler(payload: dict[str, object], context: TaskContext) -> dict[str, object]:
        assert context.task_id == task_id
        assert context.attempt == 1
        assert context.heartbeat(30)
        return {"processed": payload["source"]}

    registry.register("test.echo", handler)
    worker = TaskWorker(
        session_factory=session_factory,
        handlers=registry,
        worker_id="worker-test",
        lease_seconds=20,
    )

    assert worker.run_once()
    task = read_task(session_factory, task_id)
    assert task.state == "succeeded"
    assert task.result == {"processed": "fixture"}
    assert task.attempts == 1
    assert not worker.run_once()


def test_worker_retries_retryable_errors_and_stops_on_permanent_errors(
    session_factory,
) -> None:
    retry_id = enqueue(
        session_factory,
        idempotency_key="retryable",
        max_attempts=2,
    )
    registry = TaskHandlerRegistry()

    def retry_handler(
        _payload: dict[str, object], _context: TaskContext
    ) -> dict[str, object]:
        raise RetryableTaskError("remote_timeout", "The source timed out.")

    registry.register("test.echo", retry_handler)
    worker = TaskWorker(
        session_factory=session_factory,
        handlers=registry,
        worker_id="worker-retry",
        retry_base_delay_seconds=0,
        retry_max_delay_seconds=0,
    )
    assert worker.run_once()
    retry_task = read_task(session_factory, retry_id)
    assert retry_task.state == "retry_wait"
    assert retry_task.last_error_code == "remote_timeout"

    permanent_id = enqueue(
        session_factory,
        idempotency_key="permanent",
        task_type="test.permanent",
    )
    permanent_registry = TaskHandlerRegistry()

    def permanent_handler(
        _payload: dict[str, object], _context: TaskContext
    ) -> dict[str, object]:
        raise PermanentTaskError("invalid_request", "The task input is invalid.")

    permanent_registry.register("test.permanent", permanent_handler)
    permanent_worker = TaskWorker(
        session_factory=session_factory,
        handlers=permanent_registry,
        worker_id="worker-permanent",
    )
    assert permanent_worker.run_once()
    permanent_task = read_task(session_factory, permanent_id)
    assert permanent_task.state == "failed"
    assert permanent_task.attempts == 1


def test_unregistered_handler_moves_task_to_needs_attention(session_factory) -> None:
    task_id = enqueue(session_factory, task_type="not.registered")
    worker = TaskWorker(
        session_factory=session_factory,
        handlers=TaskHandlerRegistry(),
        worker_id="worker-unknown",
    )

    assert worker.run_once()
    task = read_task(session_factory, task_id)
    assert task.state == "needs_attention"
    assert task.last_error_code == "unsupported_task_type"


def test_handler_registry_rejects_duplicate_task_types() -> None:
    registry = TaskHandlerRegistry()
    registry.register("test.echo", lambda payload, context: payload)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("test.echo", lambda payload, context: payload)


def test_worker_rejects_non_json_results(session_factory) -> None:
    task_id = enqueue(session_factory, idempotency_key="invalid-result")
    registry = TaskHandlerRegistry()
    registry.register(
        "test.echo",
        lambda _payload, _context: {"not_json": object()},
    )
    worker = TaskWorker(
        session_factory=session_factory,
        handlers=registry,
        worker_id="worker-invalid-result",
    )

    assert worker.run_once()
    task = read_task(session_factory, task_id)
    assert task.state == "failed"
    assert task.last_error_code == "invalid_task_result"



def test_default_registry_exposes_only_diagnostic_echo_handler() -> None:
    registry = build_default_registry()
    handler = registry.get("system.echo")
    assert handler is not None
    context = TaskContext(
        task_id="synthetic-task",
        idempotency_key="synthetic-key",
        worker_id="synthetic-worker",
        attempt=1,
        _heartbeat=lambda _seconds: True,
    )
    assert handler({"message": "hello"}, context) == {
        "task_id": "synthetic-task",
        "echo": {"message": "hello"},
    }
    assert registry.get("job.discovery") is None
