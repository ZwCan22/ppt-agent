"""Create the initial PPT task table.

Revision ID: 0001
Revises: None
"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ppt_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("audience", sa.String(80), nullable=False),
        sa.Column("slide_count", sa.SmallInteger(), nullable=False),
        sa.Column("requirements", sa.String(3000), server_default=sa.text("''"), nullable=False),
        sa.Column("template_id", sa.String(64), server_default=sa.text("'business_blue'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ppt_tasks"),
        sa.CheckConstraint("slide_count BETWEEN 6 AND 20", name="ck_ppt_tasks_slide_count_range"),
        sa.CheckConstraint(
            "status IN ('queued', 'planning', 'rendering', 'checking', 'succeeded', 'failed')",
            name="ck_ppt_tasks_status_allowed",
        ),
        sa.CheckConstraint("char_length(btrim(topic)) > 0", name="ck_ppt_tasks_topic_nonempty"),
        sa.CheckConstraint("char_length(btrim(audience)) > 0", name="ck_ppt_tasks_audience_nonempty"),
        schema="public",
    )
    op.create_index(
        "ix_ppt_tasks_status_created_at", "ppt_tasks",
        ["status", "created_at"], schema="public",
    )


def downgrade() -> None:
    op.drop_index("ix_ppt_tasks_status_created_at", table_name="ppt_tasks", schema="public")
    op.drop_table("ppt_tasks", schema="public")
