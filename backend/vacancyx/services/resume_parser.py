"""Deterministic, bounded local resume text extraction and review."""

import re
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader
from sqlalchemy.orm import Session

from vacancyx.models import Resume


class ResumeParseError(ValueError):
    """Raised when a resume cannot be safely or reliably parsed."""


class ResumeParser:
    """Extract text and contact suggestions without external AI services."""

    VERSION = "1"

    def __init__(self, *, max_pages: int, max_characters: int, max_file_bytes: int) -> None:
        self._max_pages = max_pages
        self._max_characters = max_characters
        self._max_file_bytes = max_file_bytes

    def parse(self, path: Path, media_type: str) -> dict[str, Any]:
        """Extract bounded text from an already validated local resume."""
        if not path.is_file():
            raise ResumeParseError("The stored resume file is missing.")
        if path.stat().st_size > self._max_file_bytes:
            raise ResumeParseError("The stored resume exceeds the configured file size limit.")

        warnings: list[str] = []
        page_count: int | None = None
        try:
            if media_type == "application/pdf":
                extracted_text, page_count = self._parse_pdf(path, warnings)
            elif media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                extracted_text = self._parse_docx(path, warnings)
            elif media_type == "text/plain":
                extracted_text = path.read_text(encoding="utf-8-sig")
            else:
                raise ResumeParseError("This resume media type is not supported by the parser.")
        except ResumeParseError:
            raise
        except Exception as error:
            raise ResumeParseError("The resume could not be parsed safely.") from error

        normalized_text = self._normalize_text(extracted_text)
        if not normalized_text:
            raise ResumeParseError(
                "No selectable text was found. Scanned documents require OCR, which is not enabled."
            )

        return {
            "status": "parsed",
            "parser_version": self.VERSION,
            "extracted_text": normalized_text,
            "page_count": page_count,
            "suggested_fields": self._suggest_fields(normalized_text),
            "reviewed_fields": {},
            "warnings": warnings,
        }

    def _parse_pdf(self, path: Path, warnings: list[str]) -> tuple[str, int]:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            raise ResumeParseError("Encrypted PDF resumes are not supported.")
        page_count = len(reader.pages)
        if page_count > self._max_pages:
            raise ResumeParseError("The PDF exceeds the configured page limit.")

        extracted: list[str] = []
        total_characters = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            remaining = self._max_characters - total_characters
            if len(page_text) > remaining:
                extracted.append(page_text[:remaining])
                warnings.append("text_truncated_at_character_limit")
                break
            extracted.append(page_text)
            total_characters += len(page_text)
        return "\n".join(extracted), page_count

    def _parse_docx(self, path: Path, warnings: list[str]) -> str:
        document = Document(str(path))
        extracted: list[str] = []
        total_characters = 0
        truncated = False

        def append_text(value: str) -> bool:
            nonlocal total_characters, truncated
            remaining = self._max_characters - total_characters
            if len(value) > remaining:
                extracted.append(value[:remaining])
                truncated = True
                return False
            extracted.append(value)
            total_characters += len(value)
            return True

        for paragraph in document.paragraphs:
            if paragraph.text and not append_text(paragraph.text):
                break
        if not truncated:
            for table in document.tables:
                for row in table.rows:
                    if not append_text(" | ".join(cell.text for cell in row.cells)):
                        truncated = True
                        break
                if truncated:
                    break
        if truncated:
            warnings.append("text_truncated_at_character_limit")
        return "\n".join(extracted)

    @staticmethod
    def _normalize_text(value: str) -> str:
        lines = (line.strip() for line in value.replace("\x00", "").splitlines())
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _suggest_fields(value: str) -> dict[str, list[str]]:
        email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
        phone_pattern = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{7,}\d)(?!\w)")
        url_pattern = re.compile(r"\b(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
        return {
            "emails": sorted(set(email_pattern.findall(value))),
            "phone_numbers": sorted({match.strip() for match in phone_pattern.findall(value)}),
            "urls": sorted(set(url_pattern.findall(value))),
        }


class ResumeParseService:
    """Coordinate local parsing, status updates and user-reviewed field overrides."""

    def __init__(
        self,
        session: Session,
        *,
        storage_root: Path,
        max_file_bytes: int,
        max_pages: int,
        max_characters: int,
    ) -> None:
        self._session = session
        self._storage_root = storage_root.expanduser().resolve()
        self._parser = ResumeParser(
            max_pages=max_pages,
            max_characters=max_characters,
            max_file_bytes=max_file_bytes,
        )

    def parse(self, resume_id: str) -> Resume | None:
        """Parse outside the transaction, then persist the result in a short transaction."""
        with self._session.begin():
            resume = self._session.get(Resume, resume_id)
            if resume is None:
                return None
            storage_key = resume.storage_key
            media_type = resume.media_type

        try:
            file_path = self._resolve_storage_path(storage_key)
            parsed_content = self._parser.parse(file_path, media_type)
        except ResumeParseError:
            with self._session.begin():
                failed_resume = self._session.get(Resume, resume_id)
                if failed_resume is not None:
                    failed_resume.parse_status = "failed"
                    failed_resume.parsed_content = {
                        "status": "failed",
                        "error_code": "resume_parse_failed",
                    }
            raise

        with self._session.begin():
            parsed_resume = self._session.get(Resume, resume_id)
            if parsed_resume is None:
                return None
            parsed_resume.parsed_content = parsed_content
            parsed_resume.parse_status = "parsed"
        return parsed_resume

    def save_review(self, resume_id: str, reviewed_fields: dict[str, Any]) -> Resume | None:
        """Persist user-confirmed field edits separately from raw extracted suggestions."""
        with self._session.begin():
            resume = self._session.get(Resume, resume_id)
            if resume is None:
                return None
            if resume.parse_status != "parsed" or resume.parsed_content is None:
                raise ResumeParseError("Parse the resume successfully before reviewing its fields.")
            content = dict(resume.parsed_content)
            existing_review = content.get("reviewed_fields", {})
            merged_review = dict(existing_review) if isinstance(existing_review, dict) else {}
            merged_review.update(reviewed_fields)
            content["reviewed_fields"] = merged_review
            resume.parsed_content = content
        return resume

    def _resolve_storage_path(self, storage_key: str) -> Path:
        parts = Path(storage_key).parts
        if Path(storage_key).is_absolute() or ".." in parts:
            raise ResumeParseError("The stored resume reference is invalid.")
        resolved = (self._storage_root / Path(*parts)).resolve()
        if not resolved.is_relative_to(self._storage_root):
            raise ResumeParseError("The stored resume reference is outside private storage.")
        return resolved
