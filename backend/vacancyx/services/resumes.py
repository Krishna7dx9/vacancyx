"""Secure local resume storage and candidate-owned metadata lifecycle."""

import hashlib
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vacancyx.models import CandidateProfile, Resume
from vacancyx.repositories import ResumeRepository


class ResumeUploadError(ValueError):
    """Base error for rejected resume uploads."""


class ResumeTooLargeError(ResumeUploadError):
    """Raised when an upload exceeds the configured byte limit."""


class CandidateNotFoundError(LookupError):
    """Raised when an upload references a missing candidate."""


class DuplicateResumeError(ResumeUploadError):
    """Raised when the candidate already owns identical resume bytes."""


class ResumeService:
    """Validate and persist resume files without holding DB transactions during I/O."""

    _MEDIA_TYPES = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }

    def __init__(
        self,
        session: Session,
        *,
        storage_root: Path,
        max_size_bytes: int,
    ) -> None:
        self._session = session
        self._repository = ResumeRepository(session)
        self._storage_root = storage_root
        self._max_size_bytes = max_size_bytes

    def upload(
        self,
        *,
        candidate_id: str,
        file_stream: BinaryIO,
        original_filename: str,
    ) -> Resume:
        """Validate, stage and atomically publish one candidate-owned resume."""
        with self._session.begin():
            candidate = self._session.get(CandidateProfile, candidate_id)
        if candidate is None:
            raise CandidateNotFoundError("Candidate not found.")

        safe_filename, extension = self._sanitize_filename(original_filename)
        storage_root = self._storage_root.expanduser().resolve()
        resumes_directory = storage_root / "resumes"
        if resumes_directory.is_symlink():
            raise ResumeUploadError("The private resume storage directory cannot be a symlink.")
        resumes_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not resumes_directory.resolve().is_relative_to(storage_root):
            raise ResumeUploadError("The private resume storage directory is outside local storage.")
        if os.name == "posix":
            # This is a dedicated private subdirectory, not the caller's whole storage root.
            resumes_directory.chmod(0o700)

        file_id = str(uuid4())
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            dir=resumes_directory,
            prefix=f".{file_id}.",
            suffix=".upload",
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)
        storage_key = f"resumes/{file_id}{extension}"
        final_path = resumes_directory / f"{file_id}{extension}"

        try:
            checksum, file_size = self._write_staged_file(file_stream, temporary_path)
            media_type = self._validate_file(temporary_path, extension)
            resume = Resume(
                candidate_id=candidate_id,
                storage_key=storage_key,
                original_filename=safe_filename,
                media_type=media_type,
                file_size_bytes=file_size,
                checksum_sha256=checksum,
                parse_status="pending",
            )
            try:
                with self._session.begin():
                    self._repository.add(resume)
                    os.replace(temporary_path, final_path)
            except IntegrityError as error:
                final_path.unlink(missing_ok=True)
                raise DuplicateResumeError(
                    "This candidate already has a resume with identical content."
                ) from error
            return resume
        except Exception:
            temporary_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise

    def _write_staged_file(self, file_stream: BinaryIO, destination: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        total_size = 0
        file_stream.seek(0)
        with destination.open("wb") as target:
            while chunk := file_stream.read(64 * 1024):
                total_size += len(chunk)
                if total_size > self._max_size_bytes:
                    raise ResumeTooLargeError("Resume exceeds the configured upload size limit.")
                digest.update(chunk)
                target.write(chunk)
        if total_size == 0:
            raise ResumeUploadError("The uploaded resume is empty.")
        return digest.hexdigest(), total_size

    @staticmethod
    def _sanitize_filename(original_filename: str) -> tuple[str, str]:
        basename = PureWindowsPath(original_filename).name
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
        extension = Path(cleaned).suffix.lower()
        if extension not in ResumeService._MEDIA_TYPES:
            raise ResumeUploadError("Only PDF, DOCX and TXT resume files are supported.")
        stem = Path(cleaned).stem[:200].strip() or "resume"
        return f"{stem}{extension}", extension

    def _validate_file(self, path: Path, extension: str) -> str:
        if extension == ".pdf":
            with path.open("rb") as file_handle:
                signature = file_handle.read(5)
            if signature != b"%PDF-":
                raise ResumeUploadError("The file extension does not match a PDF document.")
        elif extension == ".txt":
            content = path.read_bytes()
            try:
                decoded = content.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise ResumeUploadError("TXT resumes must contain valid UTF-8 text.") from error
            if not decoded.strip() or "\x00" in decoded:
                raise ResumeUploadError("The TXT resume is empty or contains invalid binary data.")
        else:
            self._validate_docx(path)
        return self._MEDIA_TYPES[extension]

    @staticmethod
    def _validate_docx(path: Path) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                names = {entry.filename for entry in entries}
                uncompressed_size = sum(entry.file_size for entry in entries)
                if len(entries) > 100 or uncompressed_size > 25 * 1024 * 1024:
                    raise ResumeUploadError("The DOCX archive exceeds safe extraction limits.")
                for entry in entries:
                    parts = PurePosixPath(entry.filename).parts
                    if PurePosixPath(entry.filename).is_absolute() or ".." in parts:
                        raise ResumeUploadError("The DOCX archive contains an unsafe file path.")
                    if entry.filename.lower().endswith("vbaproject.bin"):
                        raise ResumeUploadError("Macro-enabled documents are not accepted.")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise ResumeUploadError("The DOCX archive is missing required document parts.")
                if archive.testzip() is not None:
                    raise ResumeUploadError("The DOCX archive is corrupted.")
        except zipfile.BadZipFile as error:
            raise ResumeUploadError("The file extension does not match a DOCX document.") from error
