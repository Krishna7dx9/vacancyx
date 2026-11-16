"""Local operational summary contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProcessHeartbeatRead(BaseModel):
    role: Literal["worker", "scheduler"]
    instance_id: str
    instance_name: str
    pid: int
    hostname: str
    status: Literal["running", "stopped", "stale"]
    started_at: datetime
    last_heartbeat_at: datetime
    age_seconds: int


class OperationsSummaryRead(BaseModel):
    """Safe aggregate counts; no candidate or task payloads are exposed."""

    database_status: str
    configured_source_count: int
    enabled_schedule_count: int
    due_schedule_count: int
    next_schedule_at: datetime | None
    task_counts: dict[str, int]
    expired_lease_count: int
    processes: list[ProcessHeartbeatRead]
    generated_at: datetime
