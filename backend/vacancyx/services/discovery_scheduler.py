"""Durable, idempotent scheduler for recurring public job discovery."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from vacancyx.models import DiscoverySchedule
from vacancyx.repositories import TaskRepository

SessionFactory = Callable[[], Session]
SourceKeysProvider = Callable[[], set[str]]


class DiscoveryScheduler:
    """Advance due schedules and enqueue one durable task per configured source."""

    def __init__(
        self,
        session_factory: SessionFactory,
        enabled_source_keys: SourceKeysProvider,
        *,
        clock: Callable[[], datetime] | None = None,
        batch_size: int = 50,
    ) -> None:
        if batch_size < 1 or batch_size > 500:
            raise ValueError("batch_size must be between 1 and 500.")
        self._session_factory = session_factory
        self._enabled_source_keys = enabled_source_keys
        self._clock = clock or (lambda: datetime.now(UTC))
        self._batch_size = batch_size

    def run_due_once(self) -> int:
        """Enqueue due work once; return the number of source tasks created or reused."""
        now = self._clock()
        enabled = self._enabled_source_keys()
        enqueued = 0
        with self._session_factory() as session, session.begin():
            schedules = list(
                session.scalars(
                    select(DiscoverySchedule)
                    .where(
                        DiscoverySchedule.is_enabled.is_(True),
                        DiscoverySchedule.next_run_at <= now,
                    )
                    .order_by(
                        DiscoverySchedule.next_run_at,
                        DiscoverySchedule.created_at,
                        DiscoverySchedule.id,
                    )
                    .limit(self._batch_size)
                )
            )
            for schedule in schedules:
                expected_next_run = schedule.next_run_at
                expected_run_number = schedule.run_number
                next_run_number = expected_run_number + 1
                next_run_at = now + timedelta(seconds=schedule.interval_seconds)
                missing_sources = sorted(set(schedule.source_keys) - enabled)
                claimed_id = session.scalar(
                    update(DiscoverySchedule)
                    .where(
                        DiscoverySchedule.id == schedule.id,
                        DiscoverySchedule.is_enabled.is_(True),
                        DiscoverySchedule.run_number == expected_run_number,
                        DiscoverySchedule.next_run_at == expected_next_run,
                    )
                    .values(
                        run_number=next_run_number,
                        last_run_at=now,
                        next_run_at=next_run_at,
                        last_error_code="source_not_configured" if missing_sources else None,
                        updated_at=now,
                    )
                    .returning(DiscoverySchedule.id)
                    .execution_options(synchronize_session=False)
                )
                if claimed_id is None:
                    continue

                for source_key in sorted(set(schedule.source_keys) & enabled):
                    TaskRepository(session).enqueue(
                        task_type="jobs.discover_source",
                        payload={
                            "source_key": source_key,
                            "schedule_id": schedule.id,
                            "schedule_run": next_run_number,
                        },
                        idempotency_key=(
                            f"schedule:{schedule.id}:run:{next_run_number}:{source_key}"
                        ),
                        max_attempts=3,
                    )
                    enqueued += 1
        return enqueued
