"""Tests for safe aggregate local operations diagnostics."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import AutomationTask, DiscoverySchedule


def test_operations_summary_reports_queue_and_schedule_health(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(
        "vacancyx.api.routes.operations.get_settings",
        lambda: __import__("vacancyx.config", fromlist=["Settings"]).Settings(_env_file=None),
    )
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        session.add_all(
            [
                DiscoverySchedule(
                    name="Due schedule",
                    source_keys=["greenhouse-demo"],
                    interval_seconds=3600,
                    is_enabled=True,
                    next_run_at=now - timedelta(seconds=1),
                ),
                DiscoverySchedule(
                    name="Future schedule",
                    source_keys=["greenhouse-demo"],
                    interval_seconds=3600,
                    is_enabled=True,
                    next_run_at=now + timedelta(hours=1),
                ),
                DiscoverySchedule(
                    name="Paused schedule",
                    source_keys=["greenhouse-demo"],
                    interval_seconds=3600,
                    is_enabled=False,
                    next_run_at=now - timedelta(seconds=1),
                ),
            ]
        )
        session.add_all(
            [
                AutomationTask(
                    task_type="jobs.discover_source",
                    payload={"source_key": "greenhouse-demo", "private": "never expose"},
                    state="queued",
                    idempotency_key="ops-summary:queued",
                ),
                AutomationTask(
                    task_type="jobs.discover_source",
                    payload={"source_key": "greenhouse-demo"},
                    state="running",
                    idempotency_key="ops-summary:expired",
                    lease_expires_at=now - timedelta(seconds=1),
                ),
                AutomationTask(
                    task_type="jobs.discover_source",
                    payload={"source_key": "greenhouse-demo"},
                    state="failed",
                    idempotency_key="ops-summary:failed",
                ),
                AutomationTask(
                    task_type="system.echo",
                    payload={"message": "excluded"},
                    state="queued",
                    idempotency_key="ops-summary:other-type",
                ),
            ]
        )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/operations/summary")
        assert response.status_code == 200
        payload = response.json()
        assert payload["database_status"] == "ready"
        assert payload["configured_source_count"] == 0
        assert payload["enabled_schedule_count"] == 2
        assert payload["due_schedule_count"] == 1
        assert payload["task_counts"] == {"failed": 1, "queued": 1, "running": 1}
        assert payload["expired_lease_count"] == 1
        assert "payload" not in payload
        assert "private" not in response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
