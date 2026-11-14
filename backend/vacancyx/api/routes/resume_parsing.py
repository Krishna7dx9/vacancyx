"""Resume parsing and user-review endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.resume_parsing import ResumeParseResult, ResumeReviewPatch
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import Resume
from vacancyx.services.resume_parser import ResumeParseError, ResumeParseService

router = APIRouter(prefix="/resumes", tags=["resume parsing"])
SessionDep = Annotated[Session, Depends(get_session)]


def build_parser_service(session: Session) -> ResumeParseService:
    settings = get_settings()
    return ResumeParseService(
        session,
        storage_root=settings.storage_dir,
        max_file_bytes=settings.max_resume_size_bytes,
        max_pages=settings.max_resume_pages,
        max_characters=settings.max_extracted_chars,
    )


@router.post("/{resume_id}/parse", response_model=ResumeParseResult)
def parse_resume(resume_id: str, session: SessionDep) -> ResumeParseResult:
    """Extract text locally and store deterministic suggestions for user review."""
    try:
        resume = build_parser_service(session).parse(resume_id)
    except ResumeParseError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return ResumeParseResult.model_validate(resume)


@router.get("/{resume_id}/parse", response_model=ResumeParseResult)
def get_resume_parse(resume_id: str, session: SessionDep) -> ResumeParseResult:
    """Read the latest parser output without exposing the local storage path."""
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return ResumeParseResult.model_validate(resume)


@router.patch("/{resume_id}/parse/review", response_model=ResumeParseResult)
def review_resume_parse(
    resume_id: str,
    payload: ResumeReviewPatch,
    session: SessionDep,
) -> ResumeParseResult:
    """Save user-confirmed corrections separately from extracted source text."""
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one reviewed field must be supplied.",
        )
    try:
        resume = build_parser_service(session).save_review(
            resume_id, payload.model_dump(exclude_unset=True)
        )
    except ResumeParseError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return ResumeParseResult.model_validate(resume)
