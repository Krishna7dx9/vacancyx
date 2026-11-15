"""Candidate-owned application status and timeline endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.application_tracking import (
    ApplicationStatusTransition,
    ApplicationTimelineEventCreate,
    ApplicationTimelineEventRead,
)
from vacancyx.db.session import get_session
from vacancyx.services.application_tracking import (
    ApplicationTrackingService,
    TrackingConflictError,
    TrackingNotFoundError,
)

router = APIRouter(
    prefix="/candidates/{candidate_id}/applications",
    tags=["application-tracking"],
)
SessionDep = Annotated[Session, Depends(get_session)]


@router.patch("/{application_id}/status", response_model=dict[str, str])
def transition_application_status(
    candidate_id: str,
    application_id: str,
    payload: ApplicationStatusTransition,
    session: SessionDep,
) -> dict[str, str]:
    """Record an allowed lifecycle transition; submission requires confirmation evidence."""
    try:
        application = ApplicationTrackingService(session).transition(
            candidate_id=candidate_id,
            application_id=application_id,
            target_status=payload.status,
            confirmation_reference=payload.confirmation_reference,
        )
    except TrackingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TrackingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": application.id, "status": application.status}


@router.post(
    "/{application_id}/events",
    response_model=ApplicationTimelineEventRead,
    status_code=status.HTTP_201_CREATED,
)
def add_application_timeline_event(
    candidate_id: str,
    application_id: str,
    payload: ApplicationTimelineEventCreate,
    session: SessionDep,
) -> ApplicationTimelineEventRead:
    """Append a bounded assessment, interview, offer or follow-up event."""
    try:
        event = ApplicationTrackingService(session).add_event(
            candidate_id=candidate_id,
            application_id=application_id,
            event_type=payload.event_type,
            summary=payload.summary,
        )
    except TrackingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TrackingConflictError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ApplicationTimelineEventRead.model_validate(event)


@router.get(
    "/{application_id}/events",
    response_model=list[ApplicationTimelineEventRead],
)
def list_application_timeline_events(
    candidate_id: str,
    application_id: str,
    session: SessionDep,
) -> list[ApplicationTimelineEventRead]:
    """Read the append-only timeline within the candidate ownership boundary."""
    try:
        events = ApplicationTrackingService(session).list_events(
            candidate_id=candidate_id,
            application_id=application_id,
        )
    except TrackingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [ApplicationTimelineEventRead.model_validate(event) for event in events]
