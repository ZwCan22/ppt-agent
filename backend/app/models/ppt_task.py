from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PptTask(Base):
    __tablename__ = "ppt_tasks"
    __table_args__ = (
        CheckConstraint(
            "slide_count BETWEEN 6 AND 20",
            name="ck_ppt_tasks_slide_count_range",
        ),
        CheckConstraint(
            "status IN ('queued', 'planning', 'rendering', "
            "'checking', 'succeeded', 'failed')",
            name="ck_ppt_tasks_status_allowed",
        ),
        CheckConstraint(
            "char_length(btrim(topic)) > 0",
            name="ck_ppt_tasks_topic_nonempty",
        ),
        CheckConstraint(
            "char_length(btrim(audience)) > 0",
            name="ck_ppt_tasks_audience_nonempty",
        ),
        Index("ix_ppt_tasks_status_created_at", "status", "created_at"),
        Index(
            "ix_ppt_tasks_owner_created_id",
            "owner_id",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "idempotency_key IS NULL OR owner_id IS NOT NULL",
            name="ck_ppt_tasks_idempotency_requires_owner",
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key",
            name="uq_ppt_tasks_owner_idempotency_key",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4,
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "public.users.id",
            name="fk_ppt_tasks_owner_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    # 同一次创建请求的重试沿用此编号；旧客户端可以不传。
    idempotency_key: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True,
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    audience: Mapped[str] = mapped_column(String(80), nullable=False)
    slide_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    requirements: Mapped[str] = mapped_column(
        String(3000), nullable=False, default="", server_default=text("''"),
    )
    template_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="business_blue",
        server_default=text("'business_blue'"),
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued",
        server_default=text("'queued'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
    outline_json: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True,
    )
    artifact_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
    )
    # 已经领取执行的次数，第一次领取前为 0
    attempt_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # 每次领取时生成一个新的编号
    execution_token: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    # 本次领取凭证的到期时间
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
