"""Candidate-owned application batch review and approval endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.application_batches import (
    ApplicationBatchCreate,
    ApplicationBatchDecisionRequest,
    ApplicationBatchDecisionResponse,
    ApplicationBatchRead,
)
from vacancyx.db.session import get_session
from vacancyx.services.application_batches import (
    ApplicationBatchService,
    BatchConflictError,
    BatchInputError,
    BatchNotFoundError,
)

router = APIRouter(
    prefix="/candidates/{candidate_id}/application-batches",
    tags=["application-batches"],
)
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=ApplicationBatchRead, status_code=status.HTTP_201_CREATED)
def create_batch(
    candidate_id: str,
    payload: ApplicationBatchCreate,
    session: SessionDep,
) -> ApplicationBatchRead:
    """Capture the exact current revision/hash for each selected application."""
    try:
        result = ApplicationBatchService(session).create(
            candidate_id=candidate_id,
            name=payload.name,
            application_ids=payload.application_ids,
        )
    except BatchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except BatchInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except BatchConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return ApplicationBatchRead.model_validate(result)


@router.get("", response_model=list[ApplicationBatchRead])
def list_batches(candidate_id: str, session: SessionDep) -> list[ApplicationBatchRead]:
    """List batches owned by one candidate."""
    results = ApplicationBatchService(session).list_for_candidate(candidate_id)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found."
        )
    return [ApplicationBatchRead.model_validate(result) for result in results]


@router.get("/{batch_id}", response_model=ApplicationBatchRead)
def get_batch(
    candidate_id: str,
    batch_id: str,
    session: SessionDep,
) -> ApplicationBatchRead:
    """Read one candidate-owned batch and current/stale revision status."""
    try:
        result = ApplicationBatchService(session).get(candidate_id, batch_id)
    except BatchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return ApplicationBatchRead.model_validate(result)


@router.post(
    "/{batch_id}/decisions",
    response_model=ApplicationBatchDecisionResponse,
)
def decide_batch_items(
    candidate_id: str,
    batch_id: str,
    payload: ApplicationBatchDecisionRequest,
    session: SessionDep,
) -> ApplicationBatchDecisionResponse:
    """Apply explicit decisions only when the reviewed revision/hash is still current."""
    try:
        result = ApplicationBatchService(session).decide(
            candidate_id=candidate_id,
            batch_id=batch_id,
            decisions=[decision.model_dump() for decision in payload.decisions],
        )
    except BatchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except BatchInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except BatchConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return ApplicationBatchDecisionResponse.model_validate(result)
