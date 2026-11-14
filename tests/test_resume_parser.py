from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.models import CandidateProfile, Resume
from vacancyx.services.resume_parser import (
    ResumeParseError,
    ResumeParser,
    ResumeParseService,
)


def build_parser(*, max_pages: int = 10, max_characters: int = 1000) -> ResumeParser:
    return ResumeParser(
        max_pages=max_pages,
        max_characters=max_characters,
        max_file_bytes=1024 * 1024,
    )


def test_txt_parser_extracts_text_and_contact_suggestions(tmp_path: Path) -> None:
    path = tmp_path / "resume.txt"
    path.write_text(
        "Backend Engineer\nEmail: person@example.com\nPhone: +91 98765 43210\n"
        "Portfolio: https://example.com/profile\n",
        encoding="utf-8",
    )

    result = build_parser().parse(path, "text/plain")
    assert result["status"] == "parsed"
    assert result["suggested_fields"]["emails"] == ["person@example.com"]
    assert "https://example.com/profile" in result["suggested_fields"]["urls"]
    assert "Backend Engineer" in result["extracted_text"]


def test_docx_parser_extracts_paragraphs_and_tables(tmp_path: Path) -> None:
    path = tmp_path / "resume.docx"
    document = Document()
    document.add_paragraph("Backend Engineer")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Python"
    table.cell(0, 1).text = "FastAPI"
    document.save(path)

    result = build_parser().parse(
        path,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert "Backend Engineer" in result["extracted_text"]
    assert "Python | FastAPI" in result["extracted_text"]


def test_pdf_parser_rejects_encrypted_and_scanned_documents(tmp_path: Path) -> None:
    blank_pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with blank_pdf.open("wb") as file_handle:
        writer.write(file_handle)

    with pytest.raises(ResumeParseError, match="No selectable text"):
        build_parser().parse(blank_pdf, "application/pdf")

    encrypted_pdf = tmp_path / "encrypted.pdf"
    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=72, height=72)
    encrypted_writer.encrypt("secret")
    with encrypted_pdf.open("wb") as file_handle:
        encrypted_writer.write(file_handle)

    with pytest.raises(ResumeParseError, match="Encrypted"):
        build_parser().parse(encrypted_pdf, "application/pdf")


def test_pdf_parser_enforces_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "multi-page.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as file_handle:
        writer.write(file_handle)

    with pytest.raises(ResumeParseError, match="page limit"):
        build_parser(max_pages=1).parse(path, "application/pdf")


def test_text_parser_truncates_at_configured_character_limit(tmp_path: Path) -> None:
    path = tmp_path / "long.txt"
    path.write_text("A" * 200, encoding="utf-8")

    result = build_parser(max_characters=40).parse(path, "text/plain")
    assert len(result["extracted_text"]) == 40
    assert "text_truncated_at_character_limit" in result["warnings"]


def test_resume_parse_service_persists_output_and_user_review(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    storage_root = tmp_path / "private"
    resume_directory = storage_root / "resumes"
    resume_directory.mkdir(parents=True)
    stored_file = resume_directory / "synthetic.txt"
    stored_file.write_text(
        "Backend Engineer\nperson@example.com\n",
        encoding="utf-8",
    )

    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            candidate = CandidateProfile(display_name="Synthetic Parser Candidate")
            session.add(candidate)
            session.flush()
            resume = Resume(
                candidate_id=candidate.id,
                storage_key="resumes/synthetic.txt",
                original_filename="resume.txt",
                media_type="text/plain",
                file_size_bytes=stored_file.stat().st_size,
                checksum_sha256="b" * 64,
                parse_status="pending",
            )
            session.add(resume)
            session.flush()
            resume_id = resume.id

        service = ResumeParseService(
            session,
            storage_root=storage_root,
            max_file_bytes=1024,
            max_pages=5,
            max_characters=500,
        )
        parsed = service.parse(resume_id)
        assert parsed is not None
        assert parsed.parse_status == "parsed"
        assert parsed.parsed_content is not None
        assert parsed.parsed_content["suggested_fields"]["emails"] == ["person@example.com"]

        reviewed = service.save_review(
            resume_id,
            {"display_name": "Reviewed Candidate", "skills": ["Python"]},
        )
        assert reviewed is not None
        assert reviewed.parsed_content is not None
        assert reviewed.parsed_content["reviewed_fields"]["display_name"] == "Reviewed Candidate"
        assert reviewed.parsed_content["extracted_text"].startswith("Backend Engineer")

    engine.dispose()


def test_resume_parser_rejects_storage_path_traversal(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            candidate = CandidateProfile(display_name="Synthetic Candidate")
            session.add(candidate)
            session.flush()
            resume = Resume(
                candidate_id=candidate.id,
                storage_key="../outside.txt",
                original_filename="resume.txt",
                media_type="text/plain",
                file_size_bytes=10,
                checksum_sha256="c" * 64,
            )
            session.add(resume)
            session.flush()
            resume_id = resume.id

        service = ResumeParseService(
            session,
            storage_root=tmp_path,
            max_file_bytes=1024,
            max_pages=5,
            max_characters=500,
        )
        with pytest.raises(ResumeParseError, match="invalid"):
            service.parse(resume_id)
        stored = session.get(Resume, resume_id)
        assert stored is not None
        assert stored.parse_status == "failed"

    engine.dispose()
