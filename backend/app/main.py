from contextlib import asynccontextmanager
import logging
from app.api.auth import router as auth_router
from fastapi import FastAPI

from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.ppt import router as ppt_router
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.logging_config import setup_logging
from app.db.engine import engine
from app.middleware.request_logging import register_request_logging


setup_logging("api")
logger = logging.getLogger("ppt_agent.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_started")
    try:
        yield
    finally:
        engine.dispose()
        logger.info("api_stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

register_request_logging(app)
register_error_handlers(app)

app.include_router(health_router, prefix="/api")
app.include_router(ppt_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

if settings.app_env == "development":
    app.include_router(debug_router, prefix="/api")
