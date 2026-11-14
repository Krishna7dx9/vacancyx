"""Candidate answer library endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vacancyx.api.schemas.answers import (
    CandidateAnswerCreate,
    CandidateAnswerPatch,
    CandidateAnswerRead,
    CandidateAnswerRevisionRead,
)
from vacancyx.db.session import get_session
from vacancyx.models.candidate_answers import CandidateAnswer
from vacancyx.services.answers import CandidateAnswerService

router = APIRouter(prefix="/candidates/{candidate_id}/answers", tags=["candidate-answers"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=CandidateAnswerRead, status_code=status.HTTP_201_CREATED)
def create_answer(
    candidate_id: str, payload: CandidateAnswerCreate, session: SessionDep
) -> CandidateAnswer:
    """Create a reusable answer; duplicate normalized questions return 409."""
    try:
        answer = CandidateAnswerService(session).create(
            candidate_id=candidate_id,
            question=payload.question,
            answer_text=payload.answer_text,
            category=payload.category,
            tags=payload.tags,
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An answer for this normalized question already exists.",
        ) from exc
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return answer


@router.get("", response_model=list[CandidateAnswerRead])
def list_answers(
    candidate_id: str,
    session: SessionDep,
    query: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    active_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CandidateAnswer]:
    """Search a candidate's answers with bounded pagination."""
    answers = CandidateAnswerService(session).list_for_candidate(
        candidate_id,
        query=query,
        category=category,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    if answers is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return answers


@router.patch("/{answer_id}", response_model=CandidateAnswerRead)
def update_answer(
    candidate_id: str,
    answer_id: str,
    payload: CandidateAnswerPatch,
    session: SessionDep,
) -> CandidateAnswer:
    """Update one candidate-owned answer; content edits append a revision."""
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be supplied."
        )
    try:
        answer = CandidateAnswerService(session).update(
            answer_id=answer_id, candidate_id=candidate_id, changes=changes
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An answer for this normalized question already exists.",
        ) from exc
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found.")
    return answer


@router.get("/{answer_id}/revisions", response_model=list[CandidateAnswerRevisionRead])
def list_answer_revisions(
    candidate_id: str, answer_id: str, session: SessionDep
) -> list[CandidateAnswerRevisionRead]:
    """Return immutable revision snapshots for a candidate-owned answer."""
    revisions = CandidateAnswerService(session).list_revisions(
        answer_id=answer_id, candidate_id=candidate_id
    )
    if revisions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found.")
    return revisions
