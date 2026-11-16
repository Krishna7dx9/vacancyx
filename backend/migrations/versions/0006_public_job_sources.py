"""Persist local public job source configuration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_public_job_sources"
down_revision: str | None = "0005_discovery_schedules"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_job_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("external_key", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('greenhouse', 'lever')",
            name="ck_public_job_sources_provider",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_public_job_sources_source_key"),
    )
    op.create_index(
        "ix_public_job_sources_enabled",
        "public_job_sources",
        ["is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_public_job_sources_enabled", table_name="public_job_sources")
    op.drop_table("public_job_sources")
