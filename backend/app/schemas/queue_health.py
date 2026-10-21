from typing import Literal

from pydantic import BaseModel, Field


class QueueHealthResponse(BaseModel):
    status: Literal["ok", "warning"]
    queued_task_count: int = Field(ge=0)
    oldest_queued_task_age_seconds: int | None = Field(
        default=None, ge=0,
        description="当前queued任务中最早提交者的年龄；重新排队时包含之前的执行时间",
    )
    warning_after_seconds: int = Field(ge=1)
    message: str
