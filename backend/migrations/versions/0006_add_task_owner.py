"""Add ownership to PPT tasks."""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ppt_tasks",
        sa.Column(
            "owner_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
        schema="public",
    )

    op.create_foreign_key(
        "fk_ppt_tasks_owner_id_users",
        source_table="ppt_tasks",
        referent_table="users",
        local_cols=["owner_id"],
        remote_cols=["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_ppt_tasks_owner_created_id",
        "ppt_tasks",
        ["owner_id", "created_at", "id"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ppt_tasks_owner_created_id",
        table_name="ppt_tasks",
        schema="public",
    )

    op.drop_constraint(
        "fk_ppt_tasks_owner_id_users",
        "ppt_tasks",
        type_="foreignkey",
        schema="public",
    )

    op.drop_column(
        "ppt_tasks",
        "owner_id",
        schema="public",
    )