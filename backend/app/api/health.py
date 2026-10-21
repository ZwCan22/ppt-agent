import logging

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.engine import engine
from app.core.worker_health import (
    HEARTBEAT_TIMEOUT_SECONDS, get_worker_status, heartbeat_directory,
)
from app.schemas.errors import ErrorResponse
from app.schemas.queue_health import QueueHealthResponse
from app.services.queue_monitor import inspect_queue


router = APIRouter(tags=["系统"])
logger = logging.getLogger("ppt_agent.database")


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ppt-agent-backend",
        "environment": settings.app_env,
    }


@router.get(
    "/health/db",
    summary="检查数据库连接",
    responses={
        503: {"model": ErrorResponse, "description": "数据库暂时不可用"},
    },
)
def database_health_check(request: Request) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            result = connection.execute(text(
                "SELECT current_database() AS database_name, "
                "current_user AS user_name"
            )).mappings().one()
    except SQLAlchemyError as exc:
        request_id = getattr(request.state, "request_id", "unknown")
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        logger.warning(
            "database_check_failed request_id=%s error_type=%s sqlstate=%s",
            request_id,
            type(exc).__name__,
            sqlstate,
        )
        raise HTTPException(
            status_code=503,
            detail="数据库暂时不可用",
        ) from exc

    return {
        "status": "ok",
        "database": result["database_name"],
        "user": result["user_name"],
    }


@router.get(
    "/health/worker",
    summary="检查Worker存活心跳（不代表模型服务可用）",
    responses={503: {"model": ErrorResponse, "description": "未检测到有效Worker心跳"}},
)
def worker_health_check(request: Request, response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        status = get_worker_status(heartbeat_directory())
    except OSError as exc:
        logger.warning(
            "worker_health_read_failed request_id=%s error_type=%s",
            getattr(request.state, "request_id", "unknown"), type(exc).__name__,
        )
        raise HTTPException(
            status_code=503, detail="Worker心跳暂时无法读取",
            headers={"Cache-Control": "no-store"},
        ) from exc
    if status.active_workers == 0:
        raise HTTPException(
            status_code=503,
            detail="未检测到有效Worker心跳，Worker可能未启动或心跳已过期",
            headers={"Cache-Control": "no-store"},
        )
    return {
        "status": "ok",
        "active_workers": status.active_workers,
        "latest_heartbeat_age_seconds": status.latest_heartbeat_age_seconds,
        "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
    }


@router.get(
    "/health/queue",
    response_model=QueueHealthResponse,
    summary="只读检查任务排队数量和提交时长",
    description="超出提醒阈值时返回HTTP 200和warning，不修改任务状态。",
    responses={503: {"model": ErrorResponse, "description": "队列检查暂不可用"}},
)
def queue_health_check(request: Request, response: Response) -> QueueHealthResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        with engine.connect() as connection:
            return inspect_queue(connection, warning_seconds=settings.queue_warning_seconds)
    except SQLAlchemyError as exc:
        logger.warning(
            "queue_health_check_failed request_id=%s error_type=%s",
            getattr(request.state, "request_id", "unknown"), type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="队列检查暂不可用，请检查数据库连接",
            headers={"Cache-Control": "no-store"},
        ) from exc
