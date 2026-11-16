"""Background job discovery and local task status endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.api.schemas.discovery import (
    DiscoverySourceRead,
    DiscoverySourcesResponse,
    DiscoveryTaskCreate,
    DiscoveryTaskEnqueueResponse,
    DiscoveryTaskListResponse,
    PublicJobSourceCreate,
    PublicJobSourceRead,
    PublicJobSourceUpdate,
    TaskStatusRead,
)
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import AutomationTask, PublicJobSource
from vacancyx.repositories import TaskRepository
from vacancyx.sources.factory import (
    build_source_registry,
    configured_source_configurations,
    configured_source_descriptors,
)

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
def list_configured_sources(session: SessionDep) -> DiscoverySourcesResponse:
    """List enabled public job boards configured for this local VacancyX instance."""
    settings = get_settings()
    return DiscoverySourcesResponse(
        items=[
            DiscoverySourceRead.model_validate(source)
            for source in configured_source_descriptors(settings, session)
        ]
    )


@router.get("/source-configs", response_model=list[PublicJobSourceRead])
def list_source_configurations(session: SessionDep) -> list[PublicJobSourceRead]:
    """List environment and database source settings, including disabled sources."""
    return [
        PublicJobSourceRead.model_validate(item)
        for item in configured_source_configurations(get_settings(), session)
    ]


@router.post(
    "/source-configs",
    response_model=PublicJobSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source_configuration(
    payload: PublicJobSourceCreate,
    session: SessionDep,
) -> PublicJobSourceRead:
    """Add one validated public Greenhouse or Lever board to the local database."""
    with session.begin():
        existing = session.scalar(
            select(PublicJobSource).where(PublicJobSource.source_key == payload.source_key)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That public source is already configured.",
            )
        configured_keys = {
            item["source_key"]
            for item in configured_source_configurations(get_settings(), session)
        }
        if payload.source_key in configured_keys:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That public source is already configured through environment settings.",
            )
        record = PublicJobSource(
            source_key=payload.source_key,
            provider=payload.provider,
            external_key=payload.external_key,
            company_name=payload.company_name,
            is_enabled=payload.is_enabled,
        )
        session.add(record)
        session.flush()
        return PublicJobSourceRead(
            source_key=record.source_key,
            company_name=record.company_name,
            provider="Greenhouse" if record.provider == "greenhouse" else "Lever",
            is_enabled=record.is_enabled,
            managed_by="database",
        )


@router.patch("/source-configs/{source_key}", response_model=PublicJobSourceRead)
def update_source_configuration(
    source_key: str,
    payload: PublicJobSourceUpdate,
    session: SessionDep,
) -> PublicJobSourceRead:
    """Update a database-managed source; environment entries remain read-only."""
    with session.begin():
        record = session.scalar(
            select(PublicJobSource).where(PublicJobSource.source_key == source_key)
        )
        if record is None:
            configured = {
                item["source_key"]
                for item in configured_source_configurations(get_settings(), session)
            }
            if source_key in configured:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Environment-managed sources must be changed in the .env file.",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database-managed source not found.",
            )
        if payload.company_name is not None:
            record.company_name = payload.company_name
        if payload.is_enabled is not None:
            record.is_enabled = payload.is_enabled
        session.flush()
        return PublicJobSourceRead(
            source_key=record.source_key,
            company_name=record.company_name,
            provider="Greenhouse" if record.provider == "greenhouse" else "Lever",
            is_enabled=record.is_enabled,
            managed_by="database",
        )


@router.delete("/source-configs/{source_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source_configuration(source_key: str, session: SessionDep) -> Response:
    """Remove a database-managed source; environment-managed entries cannot be deleted here."""
    with session.begin():
        record = session.scalar(
            select(PublicJobSource).where(PublicJobSource.source_key == source_key)
        )
        if record is None:
            configured = {
                item["source_key"]
                for item in configured_source_configurations(get_settings(), session)
            }
            if source_key in configured:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Environment-managed sources must be removed from the .env file.",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database-managed source not found.",
            )
        session.delete(record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    tasks: list[AutomationTask] = []
    try:
        with session.begin():
            registry = build_source_registry(get_settings(), session)
            configured = set(registry.enabled_source_keys())
            if not configured:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No public job sources are configured.",
                )
            unknown = sorted(set(payload.source_keys) - configured)
            if unknown:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Unknown or disabled source keys: " + ", ".join(unknown),
                )
            repository = TaskRepository(session)
            request_source_keys = sorted(payload.source_keys)
            for source_key in request_source_keys:
                tasks.append(
                    repository.enqueue(
                        task_type="jobs.discover_source",
                        payload={
                            "source_key": source_key,
                            "request_source_keys": request_source_keys,
                        },
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
        items=[_task_status(task) for task in tasks],
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
