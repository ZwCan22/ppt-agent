"""Read-only queue observations; warnings never change task state."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.models.ppt_task import PptTask
from app.schemas.queue_health import QueueHealthResponse


def inspect_queue(connection: Connection, *, warning_seconds: int) -> QueueHealthResponse:
    statement = select(
        func.count(PptTask.id).label("queued_task_count"),
        func.min(PptTask.created_at).label("oldest_created_at"),
        func.now().label("checked_at"),
    ).where(PptTask.status == "queued")
    row = connection.execute(statement).mappings().one()
    count = row["queued_task_count"]
    oldest = row["oldest_created_at"]
    age: int | None = None
    if count and oldest is not None:
        # PostgreSQL timestamps are aware; naive UTC also supports SQLite tests.
        def utc(value: datetime) -> datetime:
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

        age = max(0, int((utc(row["checked_at"]) - utc(oldest)).total_seconds()))
    warning = age is not None and age >= warning_seconds
    if warning:
        message = "存在提交时间较久且仍在排队的任务，请检查处理能力和服务运行情况"
    elif count:
        message = "当前有任务排队，尚未达到提醒阈值"
    else:
        message = "当前没有排队任务"
    return QueueHealthResponse(
        status="warning" if warning else "ok",
        queued_task_count=count,
        oldest_queued_task_age_seconds=age,
        warning_after_seconds=warning_seconds,
        message=message,
    )
