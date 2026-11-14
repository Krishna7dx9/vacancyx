"""Candidate profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.candidates import (
    CandidateProfileCreate,
    CandidateProfilePatch,
    CandidateProfileRead,
)
from vacancyx.db.session import get_session
from vacancyx.models import CandidateProfile
from vacancyx.services.candidates import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    payload: CandidateProfileCreate,
    session: SessionDep,
) -> CandidateProfile:
    """Create a candidate profile."""
    return CandidateService(session).create(payload)


@router.get("", response_model=list[CandidateProfileRead])
def list_candidates(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> list[CandidateProfile]:
    """List active candidate profiles with bounded pagination."""
    return CandidateService(session).list_active(limit=limit, offset=offset)


@router.get("/{candidate_id}", response_model=CandidateProfileRead)
def get_candidate(
    candidate_id: str,
    session: Session = Depends(get_session),
) -> CandidateProfile:
    """Fetch one candidate profile."""
    candidate = CandidateService(session).get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateProfileRead)
def update_candidate(
    candidate_id: str,
    payload: CandidateProfilePatch,
    session: Session = Depends(get_session),
) -> CandidateProfile:
    """Update only explicitly supplied candidate fields."""
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be supplied.",
        )
    candidate = CandidateService(session).update(candidate_id, payload)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate
