"""Persist distillation job status.

Revision ID: 5b74b3c33ec2
Revises: 749a0eb08f31
"""

import sqlalchemy as sa
from alembic import op

revision = "5b74b3c33ec2"
down_revision = "749a0eb08f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "distillation_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(32),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.String(32),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("processed_events", sa.Integer(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("distillation_jobs")
