"""Local operational summary contracts."""

from datetime import datetime

from pydantic import BaseModel


class OperationsSummaryRead(BaseModel):
    """Safe aggregate counts; no candidate or task payloads are exposed."""

    database_status: str
    configured_source_count: int
    enabled_schedule_count: int
    due_schedule_count: int
    next_schedule_at: datetime | None
    task_counts: dict[str, int]
    expired_lease_count: int
    generated_at: datetime
