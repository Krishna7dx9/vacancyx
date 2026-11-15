"""Enforce one pending review batch item per application."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_unique_pending_batch_item"
down_revision: str | None = "0003_application_batches"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_application_batch_items_pending_application",
        "application_batch_items",
        ["application_id"],
        unique=True,
        sqlite_where=sa.text("decision = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_application_batch_items_pending_application",
        table_name="application_batch_items",
    )
