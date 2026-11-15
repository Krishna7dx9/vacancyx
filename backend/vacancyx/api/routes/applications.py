"""Candidate-owned application preparation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.applications import (
    ApplicationList,
    ApplicationPrepare,
    ApplicationRead,
    ApplicationUpdate,
)
from vacancyx.db.session import get_session
from vacancyx.services.applications import (
    ApplicationConflictError,
    ApplicationInputError,
    ApplicationNotFoundError,
    ApplicationService,
)

router = APIRouter(prefix="/candidates/{candidate_id}/applications", tags=["applications"])
SessionDep = Annotated[Session, Depends(get_session)]


def _read(application) -> ApplicationRead:
    latest = application.revisions[-1] if application.revisions else None
    return ApplicationRead.model_validate(
        {**{key: getattr(application, key) for key in (
            "id", "candidate_id", "job_id", "resume_id", "status", "current_revision",
            "submitted_at", "created_at", "updated_at"
        )}, "latest_revision": latest}
    )


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def prepare_application(
    candidate_id: str, payload: ApplicationPrepare, session: SessionDep
) -> ApplicationRead:
    """Create a revisioned application snapshot for human review."""
    try:
        application = ApplicationService(session).prepare(
            candidate_id=candidate_id,
            job_id=payload.job_id,
            resume_id=payload.resume_id,
            answer_ids=payload.answer_ids,
            custom_fields=payload.custom_fields,
        )
    except ApplicationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ApplicationInputError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except ApplicationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _read(application)


@router.get("", response_model=ApplicationList)
def list_applications(
    candidate_id: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationList:
    """List one candidate's applications with bounded pagination."""
    result = ApplicationService(session).list_for_candidate(
        candidate_id, limit=limit, offset=offset
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    items, total = result
    return ApplicationList(
        items=[_read(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    candidate_id: str, application_id: str, session: SessionDep
) -> ApplicationRead:
    """Read one application only within its candidate ownership boundary."""
    try:
        return _read(ApplicationService(session).get(candidate_id, application_id))
    except ApplicationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{application_id}", response_model=ApplicationRead)
def revise_application(
    candidate_id: str,
    application_id: str,
    payload: ApplicationUpdate,
    session: SessionDep,
) -> ApplicationRead:
    """Create a new immutable content revision; prior approvals cannot carry forward."""
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes supplied.")
    try:
        application = ApplicationService(session).revise(
            candidate_id=candidate_id,
            application_id=application_id,
            resume_id=changes.get("resume_id"),
            answer_ids=changes.get("answer_ids"),
            custom_fields=changes.get("custom_fields"),
        )
    except ApplicationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ApplicationInputError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except ApplicationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _read(application)
