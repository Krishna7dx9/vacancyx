"""Add candidate-owned application batches and immutable batch items."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_application_batches"
down_revision: str | None = "0002_candidate_answers"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
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
            "status IN ('reviewing', 'completed', 'cancelled')",
            name="ck_application_batches_status",
        ),
    )
    op.create_index(
        "ix_application_batches_candidate_created",
        "application_batches",
        ["candidate_id", "created_at"],
    )
    op.create_table(
        "application_batch_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("application_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
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
        sa.UniqueConstraint("batch_id", "application_id", name="uq_batch_application_item"),
        sa.CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected', 'stale')",
            name="ck_application_batch_items_decision",
        ),
        sa.CheckConstraint("revision > 0", name="ck_application_batch_items_revision"),
    )
    op.create_index(
        "ix_application_batch_items_batch_decision",
        "application_batch_items",
        ["batch_id", "decision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_batch_items_batch_decision",
        table_name="application_batch_items",
    )
    op.drop_table("application_batch_items")
    op.drop_index(
        "ix_application_batches_candidate_created",
        table_name="application_batches",
    )
    op.drop_table("application_batches")
