"""Add task execution and recovery fields."""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ppt_tasks",
        sa.Column(
            "attempt_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="public",
    )

    op.add_column(
        "ppt_tasks",
        sa.Column(
            "execution_token",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
        schema="public",
    )

    op.add_column(
        "ppt_tasks",
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column(
        "ppt_tasks", "lease_expires_at", schema="public"
    )
    op.drop_column(
        "ppt_tasks", "execution_token", schema="public"
    )
    op.drop_column(
        "ppt_tasks", "attempt_count", schema="public"
    )