"""API and service tests for durable recurring public discovery schedules."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.config import Settings
from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import AutomationTask, DiscoverySchedule
from vacancyx.services.discovery_scheduler import DiscoveryScheduler


@pytest.fixture
def workspace() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        greenhouse_boards=[{"board_token": "acme", "company_name": "Acme"}],
        lever_sites=[{"site_slug": "beta", "company_name": "Beta"}],
    )


def test_schedule_api_create_pause_resume_and_delete(workspace, monkeypatch) -> None:
    client, _factory = workspace
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery_schedules.get_settings",
        _configured_settings,
    )
    created = client.post(
        "/api/v1/discovery/schedules",
        json={
            "name": "Daily public job refresh",
            "source_keys": ["greenhouse-acme", "lever-beta"],
            "interval_seconds": 86_400,
        },
    )
    assert created.status_code == 201
    schedule = created.json()
    assert schedule["name"] == "Daily public job refresh"
    assert schedule["is_enabled"] is True
    assert schedule["run_number"] == 0
    schedule_id = schedule["id"]

    listed = client.get("/api/v1/discovery/schedules")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert len(listed.json()["items"]) == 1

    paused = client.patch(
        f"/api/v1/discovery/schedules/{schedule_id}", json={"is_enabled": False}
    )
    assert paused.status_code == 200
    assert paused.json()["is_enabled"] is False

    resumed = client.patch(
        f"/api/v1/discovery/schedules/{schedule_id}", json={"is_enabled": True}
    )
    assert resumed.status_code == 200
    assert resumed.json()["is_enabled"] is True

    deleted = client.delete(f"/api/v1/discovery/schedules/{schedule_id}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/discovery/schedules").json()["total"] == 0
    assert client.patch(
        f"/api/v1/discovery/schedules/{schedule_id}", json={"is_enabled": False}
    ).status_code == 404


def test_schedule_api_rejects_unknown_sources_and_duplicate_keys(
    workspace, monkeypatch
) -> None:
    client, _factory = workspace
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery_schedules.get_settings",
        _configured_settings,
    )
    unknown = client.post(
        "/api/v1/discovery/schedules",
        json={
            "name": "Invalid",
            "source_keys": ["greenhouse-unknown"],
            "interval_seconds": 3600,
        },
    )
    assert unknown.status_code == 422

    duplicate = client.post(
        "/api/v1/discovery/schedules",
        json={
            "name": "Duplicate",
            "source_keys": ["greenhouse-acme", "greenhouse-acme"],
            "interval_seconds": 3600,
        },
    )
    assert duplicate.status_code == 422


def test_scheduler_enqueues_due_sources_once_and_advances_schedule(workspace) -> None:
    _client, factory = workspace
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    with factory() as session, session.begin():
        schedule = DiscoverySchedule(
            name="Synthetic schedule",
            source_keys=["greenhouse-acme", "lever-beta"],
            interval_seconds=3600,
            is_enabled=True,
            next_run_at=now - timedelta(seconds=1),
        )
        session.add(schedule)
        session.flush()
        schedule_id = schedule.id

    scheduler = DiscoveryScheduler(
        factory,
        lambda: {"greenhouse-acme", "lever-beta"},
        clock=lambda: now,
    )
    assert scheduler.run_due_once() == 2
    assert scheduler.run_due_once() == 0

    with factory() as session:
        schedule = session.get(DiscoverySchedule, schedule_id)
        assert schedule is not None
        assert schedule.run_number == 1
        assert schedule.last_run_at is not None
        assert schedule.last_run_at.replace(tzinfo=UTC) == now
        assert schedule.next_run_at.replace(tzinfo=UTC) == now + timedelta(seconds=3600)
        tasks = list(
            session.scalars(
                select(AutomationTask).where(
                    AutomationTask.task_type == "jobs.discover_source"
                )
            )
        )
    assert len(tasks) == 2
    assert {task.payload["source_key"] for task in tasks} == {
        "greenhouse-acme",
        "lever-beta",
    }
    assert {task.payload["schedule_run"] for task in tasks} == {1}


def test_scheduler_skips_paused_and_records_missing_source(workspace) -> None:
    _client, factory = workspace
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    with factory() as session, session.begin():
        paused = DiscoverySchedule(
            name="Paused",
            source_keys=["greenhouse-acme"],
            interval_seconds=600,
            is_enabled=False,
            next_run_at=now - timedelta(seconds=1),
        )
        partial = DiscoverySchedule(
            name="Missing source",
            source_keys=["greenhouse-acme", "lever-missing"],
            interval_seconds=600,
            is_enabled=True,
            next_run_at=now - timedelta(seconds=1),
        )
        session.add_all([paused, partial])
        session.flush()
        paused_id = paused.id
        partial_id = partial.id

    scheduler = DiscoveryScheduler(
        factory,
        lambda: {"greenhouse-acme"},
        clock=lambda: now,
    )
    assert scheduler.run_due_once() == 1
    with factory() as session:
        paused = session.get(DiscoverySchedule, paused_id)
        partial = session.get(DiscoverySchedule, partial_id)
        assert paused is not None and paused.run_number == 0
        assert partial is not None and partial.run_number == 1
        assert partial.last_error_code == "source_not_configured"
        tasks = list(session.scalars(select(AutomationTask)))
    assert len(tasks) == 1
    assert tasks[0].payload["source_key"] == "greenhouse-acme"


def test_scheduler_requires_bounded_batch_size(workspace) -> None:
    _client, factory = workspace
    with pytest.raises(ValueError, match="batch_size"):
        DiscoveryScheduler(factory, lambda: set(), batch_size=501)


def test_schedule_can_target_database_managed_source(
    workspace, monkeypatch
) -> None:
    client, _factory = workspace
    def empty_settings() -> Settings:
        return Settings(_env_file=None)
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery.get_settings",
        empty_settings,
    )
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery_schedules.get_settings",
        empty_settings,
    )
    source = client.post(
        "/api/v1/discovery/source-configs",
        json={
            "provider": "lever",
            "external_key": "example-site",
            "company_name": "Example",
        },
    )
    assert source.status_code == 201

    schedule = client.post(
        "/api/v1/discovery/schedules",
        json={
            "name": "Database source schedule",
            "source_keys": ["lever-example-site"],
            "interval_seconds": 3600,
        },
    )
    assert schedule.status_code == 201
    assert schedule.json()["source_keys"] == ["lever-example-site"]
