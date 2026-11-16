"""Local operational diagnostics for the discovery worker and scheduler."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vacancyx.api.schemas.operations import OperationsSummaryRead, ProcessHeartbeatRead
from vacancyx.config import get_settings
from vacancyx.db.session import get_session
from vacancyx.models import AutomationTask, DiscoverySchedule
from vacancyx.process_heartbeat import read_process_heartbeats
from vacancyx.sources.factory import build_source_registry

router = APIRouter(prefix="/operations", tags=["operations"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/summary", response_model=OperationsSummaryRead)
def operations_summary(session: SessionDep) -> OperationsSummaryRead:
    """Return bounded aggregate state for the local API, scheduler, and worker queue."""
    now = datetime.now(UTC)
    settings = get_settings()
    configured_source_count = len(build_source_registry(settings).enabled_source_keys())

    task_rows = session.execute(
        select(AutomationTask.state, func.count())
        .where(AutomationTask.task_type == "jobs.discover_source")
        .group_by(AutomationTask.state)
    ).all()
    task_counts = {str(state): int(count) for state, count in task_rows}

    enabled_schedule_count = session.scalar(
        select(func.count())
        .select_from(DiscoverySchedule)
        .where(DiscoverySchedule.is_enabled.is_(True))
    ) or 0
    due_schedule_count = session.scalar(
        select(func.count())
        .select_from(DiscoverySchedule)
        .where(
            DiscoverySchedule.is_enabled.is_(True),
            DiscoverySchedule.next_run_at <= now,
        )
    ) or 0
    next_schedule_at = session.scalar(
        select(func.min(DiscoverySchedule.next_run_at)).where(
            DiscoverySchedule.is_enabled.is_(True)
        )
    )
    expired_lease_count = session.scalar(
        select(func.count())
        .select_from(AutomationTask)
        .where(
            AutomationTask.task_type == "jobs.discover_source",
            AutomationTask.state == "running",
            AutomationTask.lease_expires_at.is_not(None),
            AutomationTask.lease_expires_at <= now,
        )
    ) or 0

    return OperationsSummaryRead(
        database_status="ready",
        configured_source_count=configured_source_count,
        enabled_schedule_count=enabled_schedule_count,
        due_schedule_count=due_schedule_count,
        next_schedule_at=next_schedule_at,
        task_counts=task_counts,
        expired_lease_count=expired_lease_count,
        processes=[
            ProcessHeartbeatRead.model_validate(item)
            for item in read_process_heartbeats(settings.storage_dir)
        ],
        generated_at=now,
    )
