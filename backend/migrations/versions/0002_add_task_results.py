"""Add PPT task result fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ppt_tasks",
        sa.Column("outline_json", postgresql.JSONB(), nullable=True),
        schema="public",
    )
    op.add_column(
        "ppt_tasks",
        sa.Column("artifact_path", sa.String(512), nullable=True),
        schema="public",
    )
    op.add_column(
        "ppt_tasks",
        sa.Column("error_message", sa.String(1000), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("ppt_tasks", "error_message", schema="public")
    op.drop_column("ppt_tasks", "artifact_path", schema="public")
    op.drop_column("ppt_tasks", "outline_json", schema="public")