from typing import Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


PptTaskStatus = Literal[
    "queued", "planning", "rendering", "checking", "succeeded", "failed",
]


class PptBrief(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [{
                "topic": "企业知识库如何利用RAG提高问答可靠性",
                "audience": "企业技术负责人和产品经理",
                "slide_count": 8,
                "requirements": "用于10分钟内部分享，语言简洁，不编造统计数据。",
                "template_id": "business_blue",
            }]
        },
    )

    topic: str = Field(
        min_length=1,
        max_length=200,
        description="PPT主题",
    )
    audience: str = Field(
        min_length=1,
        max_length=80,
        description="面向的听众",
    )
    slide_count: int = Field(
        default=8,
        strict=True,
        ge=6,
        le=20,
        description="总页数，包含封面和结束页",
    )
    requirements: str = Field(
        default="",
        max_length=3000,
        description="其他内容与表达要求",
    )
    template_id: Literal["business_blue"] = Field(
        default="business_blue",
        description="模板标识，首版约定使用business_blue",
    )


class PptValidationResponse(BaseModel):
    valid: Literal[True] = True
    brief: PptBrief

class PptTaskCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: PptTaskStatus
    created_at: datetime

class PptTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic: str
    audience: str
    slide_count: int

    status: PptTaskStatus

    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class PptTaskListResponse(BaseModel):
    items: list[PptTaskResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool
