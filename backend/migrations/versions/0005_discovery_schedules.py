"""Add durable recurring discovery schedules."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_discovery_schedules"
down_revision: str | None = "0004_unique_pending_batch_item"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovery_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_keys", sa.JSON(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "interval_seconds >= 60 AND interval_seconds <= 2592000",
            name="ck_discovery_schedules_interval",
        ),
        sa.CheckConstraint("run_number >= 0", name="ck_discovery_schedules_run_number"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovery_schedules_due",
        "discovery_schedules",
        ["is_enabled", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_schedules_due", table_name="discovery_schedules")
    op.drop_table("discovery_schedules")
