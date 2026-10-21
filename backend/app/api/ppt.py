from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.ppt_task import PptTask
from app.schemas.errors import ErrorResponse
from app.schemas.ppt import (
    PptBrief,
    PptTaskCreated,
    PptTaskListResponse,
    PptTaskResponse,
    PptValidationResponse,
)
from app.schemas.user import UserPublic
from app.services.task_creation import SubmissionConflictError, create_task

PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

router = APIRouter(prefix="/ppt", tags=["PPT需求"])


@router.post(
    "/validate",
    response_model=PptValidationResponse,
    summary="校验PPT生成需求",
    description="检查并整理需求，返回通过校验的需求对象。",
    responses={
        422: {"model": ErrorResponse, "description": "请求参数不符合要求"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
def validate_ppt_brief(brief: PptBrief) -> PptValidationResponse:
    return PptValidationResponse(brief=brief)

@router.post(
    "/tasks",
    response_model=PptTaskCreated,
    status_code=201,
    summary="创建PPT生成任务",
    description=(
        "可通过Idempotency-Key请求头传入UUID提交编号。"
        "同一用户使用同一编号与相同需求重试时返回原任务及当前状态；"
        "同一编号搭配不同需求返回409。不传编号时每次创建新任务。"
    ),
    responses={
        200: {"model": PptTaskCreated, "description": "返回已有任务，没有重复创建"},
        401: {"model": ErrorResponse, "description": "未登录或登录已过期"},
        409: {"model": ErrorResponse, "description": "提交编号已用于不同需求"},
        422: {"model": ErrorResponse, "description": "需求或提交编号格式不正确"},
    },
)
def create_ppt_task(
    brief: PptBrief,
    response: Response,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: UUID | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="本次提交的UUID；网络重试沿用原编号，新的制作意图使用新编号",
    ),
) -> PptTaskCreated:
    try:
        result, created = create_task(
            db, brief, owner_id=current_user.id, idempotency_key=idempotency_key,
        )
    except SubmissionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="这个提交编号已用于其他需求，请为新的制作请求使用新编号",
            headers={"Cache-Control": "no-store"},
        ) from exc

    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/tasks",
    response_model=PptTaskListResponse,
    summary="查询PPT任务历史",
    description="仅返回当前用户的任务，按创建时间和任务编号倒序排列。",
    responses={
        401: {"model": ErrorResponse, "description": "未登录或登录已过期"},
        422: {"model": ErrorResponse, "description": "分页参数不符合要求"},
    },
)
def list_ppt_tasks(
    limit: int = Query(default=20, ge=1, le=100, description="每页任务数"),
    offset: int = Query(default=0, ge=0, description="跳过的任务数"),
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PptTaskListResponse:
    statement = (
        select(PptTask)
        .where(PptTask.owner_id == current_user.id)
        .order_by(PptTask.created_at.desc(), PptTask.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    tasks = db.scalars(statement).all()

    return PptTaskListResponse(
        items=[PptTaskResponse.model_validate(task) for task in tasks[:limit]],
        limit=limit,
        offset=offset,
        has_more=len(tasks) > limit,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=PptTaskResponse,
    summary="查询PPT任务",
    responses={
        401: {"model": ErrorResponse, "description": "未登录或登录已过期"},
        404: {"model": ErrorResponse, "description": "任务不存在或不属于当前用户"},
    },
)
def get_ppt_task(
    task_id: UUID,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PptTask:
    task = db.scalar(
        select(PptTask).where(
            PptTask.id == task_id,
            PptTask.owner_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get(
    "/tasks/{task_id}/download",
    response_class=FileResponse,
    summary="下载已完成的PPT",
    responses={
        200: {
            "content": {
                PPTX_MEDIA_TYPE: {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        },
        401: {"model": ErrorResponse, "description": "未登录或登录已过期"},
        404: {"model": ErrorResponse, "description": "任务或文件不存在"},
        409: {"model": ErrorResponse, "description": "任务尚未完成"},
    },
)
def download_ppt(
    task_id: UUID,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    task = db.scalar(
        select(PptTask).where(
            PptTask.id == task_id,
            PptTask.owner_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "succeeded" or not task.artifact_path:
        raise HTTPException(status_code=409, detail="PPT尚未制作完成")

    storage_dir = settings.storage_dir.resolve()
    file_path = (storage_dir / task.artifact_path).resolve()

    if not file_path.is_relative_to(storage_dir):
        raise HTTPException(status_code=500, detail="文件暂时无法下载")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="PPT文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type=PPTX_MEDIA_TYPE,
        filename=f"ppt-{task_id}.pptx",
        headers={"Cache-Control": "no-store"},
    )
