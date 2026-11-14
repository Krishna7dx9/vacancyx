"""Create the candidate-owned answer library and immutable revision history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_candidate_answers"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("candidate_id", "question_hash", name="uq_candidate_answer_question"),
        sa.CheckConstraint("current_revision > 0", name="ck_candidate_answer_positive_revision"),
        sa.CheckConstraint(
            "source IN ('manual', 'resume_reviewed', 'imported')",
            name="ck_candidate_answer_source",
        ),
    )
    op.create_index(
        "ix_candidate_answers_candidate_active",
        "candidate_answers",
        ["candidate_id", "is_active"],
    )
    op.create_table(
        "candidate_answer_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "answer_id",
            sa.String(36),
            sa.ForeignKey("candidate_answers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("question_snapshot", sa.String(500), nullable=False),
        sa.Column("answer_snapshot", sa.Text(), nullable=False),
        sa.Column("category_snapshot", sa.String(80), nullable=True),
        sa.Column("tags_snapshot", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("answer_id", "revision", name="uq_candidate_answer_revision"),
        sa.CheckConstraint("revision > 0", name="ck_candidate_answer_revision_positive"),
    )
    op.create_index(
        "ix_candidate_answer_revisions_answer_id",
        "candidate_answer_revisions",
        ["answer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_answer_revisions_answer_id", table_name="candidate_answer_revisions"
    )
    op.drop_table("candidate_answer_revisions")
    op.drop_index("ix_candidate_answers_candidate_active", table_name="candidate_answers")
    op.drop_table("candidate_answers")
