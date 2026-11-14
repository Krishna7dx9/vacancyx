"""Integration tests for candidate answer ownership and revision invariants."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _candidate_id(client: TestClient) -> str:
    response = client.post(
        "/api/v1/candidates", json={"display_name": "Synthetic Answer Candidate"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_list_update_and_revision_history(client: TestClient) -> None:
    candidate_id = _candidate_id(client)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/answers",
        json={
            "question": "  Why this role? ",
            "answer_text": "I enjoy building reliable APIs.",
            "category": "motivation",
            "tags": ["backend", "python", "backend"],
        },
    )
    assert created.status_code == 201
    answer = created.json()
    assert answer["question"] == "Why this role?"
    assert answer["tags"] == ["backend", "python"]
    assert answer["current_revision"] == 1

    listed = client.get(f"/api/v1/candidates/{candidate_id}/answers?query=reliable")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [answer["id"]]

    updated = client.patch(
        f"/api/v1/candidates/{candidate_id}/answers/{answer['id']}",
        json={"answer_text": "I build reliable backend systems."},
    )
    assert updated.status_code == 200
    assert updated.json()["current_revision"] == 2
    assert updated.json()["question"] == "Why this role?"
    assert updated.json()["tags"] == ["backend", "python"]

    revisions = client.get(
        f"/api/v1/candidates/{candidate_id}/answers/{answer['id']}/revisions"
    )
    assert revisions.status_code == 200
    assert [item["revision"] for item in revisions.json()] == [2, 1]
    assert revisions.json()[1]["answer_snapshot"] == "I enjoy building reliable APIs."


def test_answer_partial_update_does_not_reset_omitted_fields(client: TestClient) -> None:
    candidate_id = _candidate_id(client)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/answers",
        json={
            "question": "Tell me about a project",
            "answer_text": "I built a service.",
            "category": "experience",
            "tags": ["python"],
        },
    )
    answer_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/candidates/{candidate_id}/answers/{answer_id}",
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["tags"] == ["python"]
    assert updated.json()["category"] == "experience"
    assert updated.json()["current_revision"] == 1


def test_duplicate_normalized_questions_conflict(client: TestClient) -> None:
    candidate_id = _candidate_id(client)
    path = f"/api/v1/candidates/{candidate_id}/answers"
    first = client.post(path, json={"question": "Why us?", "answer_text": "First answer"})
    second = client.post(path, json={"question": " WHY   US? ", "answer_text": "Second answer"})
    assert first.status_code == 201
    assert second.status_code == 409


def test_answer_ownership_and_validation(client: TestClient) -> None:
    owner_id = _candidate_id(client)
    other_id = _candidate_id(client)
    created = client.post(
        f"/api/v1/candidates/{owner_id}/answers",
        json={"question": "Strengths?", "answer_text": "Problem solving."},
    )
    answer_id = created.json()["id"]

    foreign_read = client.get(f"/api/v1/candidates/{other_id}/answers/{answer_id}/revisions")
    assert foreign_read.status_code == 404
    foreign_update = client.patch(
        f"/api/v1/candidates/{other_id}/answers/{answer_id}",
        json={"answer_text": "Changed"},
    )
    assert foreign_update.status_code == 404

    empty_patch = client.patch(
        f"/api/v1/candidates/{owner_id}/answers/{answer_id}", json={}
    )
    assert empty_patch.status_code == 400
    null_text = client.patch(
        f"/api/v1/candidates/{owner_id}/answers/{answer_id}",
        json={"answer_text": None},
    )
    assert null_text.status_code == 422
    unknown_field = client.post(
        f"/api/v1/candidates/{owner_id}/answers",
        json={"question": "Question", "answer_text": "Answer", "candidate_name": "hardcoded"},
    )
    assert unknown_field.status_code == 422


def test_unknown_candidate_is_not_created(client: TestClient) -> None:
    response = client.post(
        "/api/v1/candidates/not-a-candidate/answers",
        json={"question": "Question", "answer_text": "Answer"},
    )
    assert response.status_code == 404
