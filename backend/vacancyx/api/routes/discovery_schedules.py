"""CRUD endpoints for local recurring discovery schedules."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vacancyx.api.schemas.discovery_schedules import (
    DiscoveryScheduleCreate,
    DiscoveryScheduleList,
    DiscoveryScheduleRead,
    DiscoveryScheduleUpdate,
)
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import DiscoverySchedule
from vacancyx.sources.factory import build_source_registry

router = APIRouter(prefix="/discovery/schedules", tags=["discovery-schedules"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=DiscoveryScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: DiscoveryScheduleCreate, session: SessionDep) -> DiscoveryScheduleRead:
    """Create a local recurring schedule for currently configured public sources."""
    schedule = DiscoverySchedule(
        name=payload.name,
        source_keys=payload.source_keys,
        interval_seconds=payload.interval_seconds,
        is_enabled=True,
        next_run_at=datetime.now(UTC),
    )
    with session.begin():
        enabled_sources = set(build_source_registry(get_settings(), session).enabled_source_keys())
        unknown = sorted(set(payload.source_keys) - enabled_sources)
        if unknown:
            raise HTTPException(
                status_code=422,
                detail="Unknown or disabled source keys: " + ", ".join(unknown),
            )
        session.add(schedule)
        session.flush()
    session.refresh(schedule)
    return DiscoveryScheduleRead.model_validate(schedule)


@router.get("", response_model=DiscoveryScheduleList)
def list_schedules(session: SessionDep) -> DiscoveryScheduleList:
    """List the newest 200 schedules and report the total count."""
    items = list(
        session.scalars(
            select(DiscoverySchedule).order_by(
                DiscoverySchedule.created_at.desc(), DiscoverySchedule.id
            ).limit(200)
        )
    )
    total = session.scalar(select(func.count()).select_from(DiscoverySchedule)) or 0
    return DiscoveryScheduleList(
        items=[DiscoveryScheduleRead.model_validate(item) for item in items],
        total=total,
    )


@router.patch("/{schedule_id}", response_model=DiscoveryScheduleRead)
def update_schedule(
    schedule_id: str,
    payload: DiscoveryScheduleUpdate,
    session: SessionDep,
) -> DiscoveryScheduleRead:
    """Pause or resume a schedule without deleting its run history."""
    schedule = session.get(DiscoverySchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Discovery schedule not found.")
    schedule.is_enabled = payload.is_enabled
    session.commit()
    session.refresh(schedule)
    return DiscoveryScheduleRead.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: str, session: SessionDep) -> None:
    """Delete one schedule; already-enqueued discovery tasks remain durable."""
    schedule = session.get(DiscoverySchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Discovery schedule not found.")
    session.delete(schedule)
    session.commit()
