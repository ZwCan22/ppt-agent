from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["系统"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ppt-agent-backend",
        "environment": settings.app_env,
    }