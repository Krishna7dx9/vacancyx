"""Discovery task enqueue, status and cancellation API tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.config import Settings
from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app


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


def test_discovery_sources_and_idempotent_enqueue(workspace, monkeypatch) -> None:
    client, _factory = workspace
    settings = _configured_settings()
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery.get_settings",
        lambda: settings,
    )

    sources = client.get("/api/v1/discovery/sources")
    assert sources.status_code == 200
    assert [item["source_key"] for item in sources.json()["items"]] == [
        "greenhouse-acme",
        "lever-beta",
    ]

    payload = {
        "source_keys": ["greenhouse-acme", "lever-beta"],
        "idempotency_key": "manual-refresh-001",
    }
    created = client.post("/api/v1/discovery/tasks", json=payload)
    assert created.status_code == 202
    items = created.json()["items"]
    assert len(items) == 2
    assert {item["task_type"] for item in items} == {"jobs.discover_source"}
    assert {item["state"] for item in items} == {"queued"}
    assert "payload" not in items[0]
    assert "idempotency_key" not in items[0]
    assert items[0]["source_key"] == "greenhouse-acme"

    repeated = client.post("/api/v1/discovery/tasks", json=payload)
    assert repeated.status_code == 202
    assert {item["id"] for item in repeated.json()["items"]} == {
        item["id"] for item in items
    }
    conflicting_reuse = client.post(
        "/api/v1/discovery/tasks",
        json={
            "source_keys": ["greenhouse-acme"],
            "idempotency_key": "manual-refresh-001",
        },
    )
    assert conflicting_reuse.status_code == 409

    listed = client.get("/api/v1/discovery/tasks")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2
    assert {item["source_key"] for item in listed.json()["items"]} == {
        "greenhouse-acme",
        "lever-beta",
    }


def test_discovery_enqueue_rejects_unknown_and_unconfigured_sources(
    workspace, monkeypatch
) -> None:
    client, _factory = workspace
    settings = _configured_settings()
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery.get_settings",
        lambda: settings,
    )
    unknown = client.post(
        "/api/v1/discovery/tasks",
        json={"source_keys": ["greenhouse-unknown"], "idempotency_key": "unknown-source-001"},
    )
    assert unknown.status_code == 422

    monkeypatch.setattr(
        "vacancyx.api.routes.discovery.get_settings",
        lambda: Settings(_env_file=None),
    )
    no_sources = client.post(
        "/api/v1/discovery/tasks",
        json={"source_keys": ["greenhouse-acme"], "idempotency_key": "no-source-config-001"},
    )
    assert no_sources.status_code == 409


def test_discovery_task_status_and_cancel_are_candidate_independent(workspace, monkeypatch) -> None:
    client, _factory = workspace
    monkeypatch.setattr(
        "vacancyx.api.routes.discovery.get_settings",
        lambda: _configured_settings(),
    )
    created = client.post(
        "/api/v1/discovery/tasks",
        json={"source_keys": ["greenhouse-acme"], "idempotency_key": "cancel-task-001"},
    )
    assert created.status_code == 202
    task_id = created.json()["items"][0]["id"]

    status_response = client.get(f"/api/v1/discovery/tasks/{task_id}")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "queued"

    cancelled = client.post(f"/api/v1/discovery/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"

    repeated = client.post(f"/api/v1/discovery/tasks/{task_id}/cancel")
    assert repeated.status_code == 409

    missing = client.get("/api/v1/discovery/tasks/not-a-task")
    assert missing.status_code == 404
