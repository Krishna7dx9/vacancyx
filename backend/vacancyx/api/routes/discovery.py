"""Background job discovery and local task status endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.discovery import (
    DiscoverySourcesResponse,
    DiscoveryTaskCreate,
    DiscoveryTaskEnqueueResponse,
    DiscoveryTaskListResponse,
    DiscoverySourceRead,
    TaskStatusRead,
)
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import AutomationTask
from vacancyx.repositories import TaskRepository
from vacancyx.sources.factory import build_source_registry, configured_source_descriptors

router = APIRouter(prefix="/discovery", tags=["discovery"])
SessionDep = Annotated[Session, Depends(get_session)]


def _task_status(task: AutomationTask) -> TaskStatusRead:
    """Expose the configured source identifier without returning the task payload."""
    source_key = task.payload.get("source_key") if isinstance(task.payload, dict) else None
    status_read = TaskStatusRead.model_validate(task)
    return status_read.model_copy(
        update={"source_key": source_key if isinstance(source_key, str) else None}
    )


@router.get("/sources", response_model=DiscoverySourcesResponse)
def list_configured_sources() -> DiscoverySourcesResponse:
    """List enabled public job boards configured for this local VacancyX instance."""
    settings = get_settings()
    return DiscoverySourcesResponse(
        items=[
            DiscoverySourceRead.model_validate(source)
            for source in configured_source_descriptors(settings)
        ]
    )


@router.post(
    "/tasks",
    response_model=DiscoveryTaskEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_discovery(
    payload: DiscoveryTaskCreate,
    session: SessionDep,
) -> DiscoveryTaskEnqueueResponse:
    """Queue one idempotent discovery task per selected configured public source."""
    registry = build_source_registry(get_settings())
    configured = set(registry.enabled_source_keys())
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No public job sources are configured. Set VACANCYX_GREENHOUSE_BOARDS "
                "or VACANCYX_LEVER_SITES and restart the API."
            ),
        )
    unknown = sorted(set(payload.source_keys) - configured)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown or disabled source keys: " + ", ".join(unknown),
        )

    tasks: list[AutomationTask] = []
    try:
        with session.begin():
            repository = TaskRepository(session)
            for source_key in payload.source_keys:
                tasks.append(
                    repository.enqueue(
                        task_type="jobs.discover_source",
                        payload={"source_key": source_key},
                        idempotency_key=payload.idempotency_key + ":" + source_key,
                        max_attempts=3,
                    )
                )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return DiscoveryTaskEnqueueResponse(
        items=[_task_status(task) for task in tasks]
    )


@router.get("/tasks", response_model=DiscoveryTaskListResponse)
def list_discovery_tasks(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DiscoveryTaskListResponse:
    """Return a bounded newest-first list of discovery task statuses without payloads."""
    tasks = TaskRepository(session).list(
        task_type="jobs.discover_source",
        limit=limit,
        offset=offset,
    )
    return DiscoveryTaskListResponse(
        items=[TaskStatusRead.model_validate(task) for task in tasks],
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusRead)
def get_discovery_task(task_id: str, session: SessionDep) -> TaskStatusRead:
    """Read one discovery task without exposing its original payload or idempotency key."""
    task = TaskRepository(session).get(task_id)
    if task is None or task.task_type != "jobs.discover_source":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery task not found.",
        )
    return _task_status(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskStatusRead)
def cancel_discovery_task(task_id: str, session: SessionDep) -> TaskStatusRead:
    """Cancel queued/running discovery work and revoke the current lease token."""
    repository = TaskRepository(session)
    with session.begin():
        task = repository.get(task_id)
        if task is None or task.task_type != "jobs.discover_source":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discovery task not found.",
            )
        if not repository.cancel(task_id=task_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only queued, retrying or running discovery tasks can be cancelled.",
            )
    refreshed = repository.get(task_id)
    if refreshed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery task not found.",
        )
    return _task_status(refreshed)
