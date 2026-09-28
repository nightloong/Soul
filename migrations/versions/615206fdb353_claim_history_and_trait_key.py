"""claim_history_and_trait_key

Revision ID: 615206fdb353
Revises: 849c0df467ba
Create Date: 2026-09-28 15:11:45.790585
"""

import sqlalchemy as sa
from alembic import op

revision = "615206fdb353"
down_revision = "849c0df467ba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("claims") as batch:
        batch.add_column(sa.Column("superseded_by_id", sa.String(length=32), nullable=True))
        batch.create_foreign_key(
            "fk_claims_superseded_by", "claims", ["superseded_by_id"], ["id"], ondelete="SET NULL"
        )
    with op.batch_alter_table("traits") as batch:
        batch.create_unique_constraint(
            "uq_traits_person_dimension_key", ["person_id", "dimension", "key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("traits") as batch:
        batch.drop_constraint("uq_traits_person_dimension_key", type_="unique")
    with op.batch_alter_table("claims") as batch:
        batch.drop_constraint("fk_claims_superseded_by", type_="foreignkey")
        batch.drop_column("superseded_by_id")
