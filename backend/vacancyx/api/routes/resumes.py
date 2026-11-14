"""Candidate-owned resume upload and listing endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.resumes import ResumeRead
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import CandidateProfile
from vacancyx.repositories import ResumeRepository
from vacancyx.services.resumes import (
    CandidateNotFoundError,
    DuplicateResumeError,
    ResumeService,
    ResumeTooLargeError,
    ResumeUploadError,
)

router = APIRouter(tags=["resumes"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "/candidates/{candidate_id}/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_resume(
    candidate_id: str,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> ResumeRead:
    """Validate and store one candidate-owned resume outside the web root."""
    settings = get_settings()
    try:
        resume = ResumeService(
            session,
            storage_root=settings.storage_dir,
            max_size_bytes=settings.max_resume_size_bytes,
        ).upload(
            candidate_id=candidate_id,
            file_stream=file.file,
            original_filename=file.filename or "resume",
        )
    except CandidateNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResumeTooLargeError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error
    except DuplicateResumeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ResumeUploadError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        file.file.close()
    return ResumeRead.model_validate(resume)


@router.get(
    "/candidates/{candidate_id}/resumes",
    response_model=list[ResumeRead],
)
def list_resumes(candidate_id: str, session: SessionDep) -> list[ResumeRead]:
    """List safe resume metadata for an existing candidate."""
    candidate = session.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return [
        ResumeRead.model_validate(resume)
        for resume in ResumeRepository(session).list_for_candidate(candidate_id)
    ]
