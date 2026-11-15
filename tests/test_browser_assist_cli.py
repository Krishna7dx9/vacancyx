"""Approval-bound CLI guard tests using an isolated synthetic SQLite database."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.browser_assist_cli import _load_approved_application
from vacancyx.db.base import Base
from vacancyx.models import (
    Application,
    ApplicationApproval,
    ApplicationRevision,
    CandidateProfile,
    Job,
)


@pytest.fixture
def approved_application(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        candidate = CandidateProfile(display_name="Synthetic Candidate")
        job = Job(
            canonical_url="https://jobs.example.test/apply/123",
            company_name="Example Systems",
            title="Backend Engineer",
            status="open",
        )
        session.add_all([candidate, job])
        session.flush()
        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status="approved",
            current_revision=1,
        )
        session.add(application)
        session.flush()
        content_hash = "a" * 64
        session.add(
            ApplicationRevision(
                application_id=application.id,
                revision=1,
                content_hash=content_hash,
                content_snapshot={"candidate": {"display_name": "Synthetic Candidate"}},
            )
        )
        session.add(
            ApplicationApproval(
                application_id=application.id,
                revision=1,
                content_hash=content_hash,
                decision="approved",
                decided_at=datetime.now(UTC),
            )
        )
        candidate_id = candidate.id
        application_id = application.id
    monkeypatch.setattr(
        "vacancyx.browser_assist_cli.get_session_factory", lambda: factory
    )
    yield candidate_id, application_id, factory
    engine.dispose()


def test_cli_loads_exact_current_approved_revision(approved_application) -> None:
    candidate_id, application_id, _factory = approved_application
    url, title, snapshot, revision, content_hash = _load_approved_application(
        candidate_id, application_id
    )
    candidate_snapshot = snapshot.get("candidate")
    assert isinstance(candidate_snapshot, dict)
    assert url == "https://jobs.example.test/apply/123"
    assert title == "Example Systems — Backend Engineer"
    assert candidate_snapshot["display_name"] == "Synthetic Candidate"
    assert revision == 1
    assert content_hash == "a" * 64


def test_cli_refuses_application_without_approved_status(approved_application) -> None:
    candidate_id, application_id, factory = approved_application
    with factory() as session, session.begin():
        application = session.get(Application, application_id)
        assert application is not None
        application.status = "prepared"
    with pytest.raises(ValueError, match="approved status"):
        _load_approved_application(candidate_id, application_id)


def test_cli_refuses_approval_with_stale_content_hash(approved_application) -> None:
    candidate_id, application_id, factory = approved_application
    with factory() as session, session.begin():
        approval = session.scalar(
            select(ApplicationApproval).where(
                ApplicationApproval.application_id == application_id
            )
        )
        assert approval is not None
        approval.content_hash = "b" * 64
    with pytest.raises(ValueError, match="matching approval"):
        _load_approved_application(candidate_id, application_id)
