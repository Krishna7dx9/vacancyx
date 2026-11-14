from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.models import CandidateProfile, Resume
from vacancyx.services.resumes import (
    CandidateNotFoundError,
    DuplicateResumeError,
    ResumeService,
    ResumeTooLargeError,
    ResumeUploadError,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database_session = Session(engine, expire_on_commit=False)
    with database_session.begin():
        database_session.add(CandidateProfile(display_name="Synthetic Resume Candidate"))
    yield database_session
    database_session.close()
    engine.dispose()


def create_candidate_id(session: Session) -> str:
    candidate = session.scalar(select(CandidateProfile))
    assert candidate is not None
    return candidate.id


def test_pdf_upload_stores_generated_key_and_safe_metadata(
    session: Session, tmp_path: Path
) -> None:
    candidate_id = create_candidate_id(session)
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024)
    resume = service.upload(
        candidate_id=candidate_id,
        file_stream=BytesIO(b"%PDF-1.7\nsynthetic resume bytes"),
        original_filename="../../private-folder/Resume.pdf",
    )

    stored_path = tmp_path / resume.storage_key
    assert stored_path.is_file()
    assert stored_path.read_bytes().startswith(b"%PDF-")
    assert resume.original_filename == "Resume.pdf"
    assert resume.media_type == "application/pdf"
    assert resume.file_size_bytes > 0
    assert len(resume.checksum_sha256) == 64
    assert resume.parse_status == "pending"


def test_upload_rejects_mismatched_signature_and_cleans_staging(
    session: Session, tmp_path: Path
) -> None:
    candidate_id = create_candidate_id(session)
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024)

    with pytest.raises(ResumeUploadError, match="does not match"):
        service.upload(
            candidate_id=candidate_id,
            file_stream=BytesIO(b"not a pdf"),
            original_filename="resume.pdf",
        )

    assert list((tmp_path / "resumes").iterdir()) == []


def test_upload_enforces_size_limit(session: Session, tmp_path: Path) -> None:
    candidate_id = create_candidate_id(session)
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=16)

    with pytest.raises(ResumeTooLargeError):
        service.upload(
            candidate_id=candidate_id,
            file_stream=BytesIO(b"%PDF-" + b"x" * 100),
            original_filename="resume.pdf",
        )

    assert list((tmp_path / "resumes").iterdir()) == []


def test_upload_rejects_unsupported_extension(session: Session, tmp_path: Path) -> None:
    candidate_id = create_candidate_id(session)
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024)

    with pytest.raises(ResumeUploadError, match="Only PDF"):
        service.upload(
            candidate_id=candidate_id,
            file_stream=BytesIO(b"content"),
            original_filename="resume.exe",
        )

    assert not (tmp_path / "resumes").exists()


def test_upload_is_candidate_scoped_and_deduplicated(session: Session, tmp_path: Path) -> None:
    candidate_id = create_candidate_id(session)
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024)
    payload = b"%PDF-1.7\nidentical bytes"

    service.upload(
        candidate_id=candidate_id,
        file_stream=BytesIO(payload),
        original_filename="first.pdf",
    )
    with pytest.raises(DuplicateResumeError):
        service.upload(
            candidate_id=candidate_id,
            file_stream=BytesIO(payload),
            original_filename="duplicate.pdf",
        )

    assert len(list((tmp_path / "resumes").glob("*.pdf"))) == 1


def test_upload_requires_existing_candidate(session: Session, tmp_path: Path) -> None:
    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024)
    with pytest.raises(CandidateNotFoundError):
        service.upload(
            candidate_id="missing-candidate",
            file_stream=BytesIO(b"%PDF-1.7\ncontent"),
            original_filename="resume.pdf",
        )
    assert not (tmp_path / "resumes").exists()


def test_docx_validation_and_path_traversal_rejection(
    session: Session, tmp_path: Path
) -> None:
    candidate_id = create_candidate_id(session)
    archive_bytes = BytesIO()
    with ZipFile(archive_bytes, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    archive_bytes.seek(0)

    service = ResumeService(session, storage_root=tmp_path, max_size_bytes=1024 * 1024)
    resume = service.upload(
        candidate_id=candidate_id,
        file_stream=archive_bytes,
        original_filename="resume.docx",
    )
    assert resume.media_type.startswith("application/vnd.openxmlformats")

    unsafe_bytes = BytesIO()
    with ZipFile(unsafe_bytes, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("../escape.txt", "unsafe")
    unsafe_bytes.seek(0)

    with pytest.raises(ResumeUploadError, match="unsafe file path"):
        service.upload(
            candidate_id=candidate_id,
            file_stream=unsafe_bytes,
            original_filename="unsafe.docx",
        )
