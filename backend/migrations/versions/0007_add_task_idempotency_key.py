"""Reserve a per-user submission key for idempotent task creation."""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ppt_tasks",
        sa.Column("idempotency_key", sa.Uuid(as_uuid=True), nullable=True),
        schema="public",
    )
    op.create_check_constraint(
        "ck_ppt_tasks_idempotency_requires_owner",
        "ppt_tasks",
        "idempotency_key IS NULL OR owner_id IS NOT NULL",
        schema="public",
    )
    op.create_unique_constraint(
        "uq_ppt_tasks_owner_idempotency_key",
        "ppt_tasks",
        ["owner_id", "idempotency_key"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ppt_tasks_owner_idempotency_key",
        "ppt_tasks",
        type_="unique",
        schema="public",
    )
    op.drop_constraint(
        "ck_ppt_tasks_idempotency_requires_owner",
        "ppt_tasks",
        type_="check",
        schema="public",
    )
    op.drop_column("ppt_tasks", "idempotency_key", schema="public")
