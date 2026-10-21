from logging.config import dictConfig
from typing import Literal

from app.core.config import BACKEND_DIR, settings


def setup_logging(component: Literal["api", "worker"] = "api") -> None:
    """Write application logs to the console and the component's rotating file."""
    if component not in ("api", "worker"):
        raise ValueError("日志组件必须为 api 或 worker")

    log_dir = settings.log_dir
    if not log_dir.is_absolute():
        log_dir = BACKEND_DIR / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s %(levelname)s "
                    "pid=%(process)d %(name)s %(message)s"
                ),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filename": str(log_dir / f"{component}.log"),
                "maxBytes": settings.log_max_bytes,
                "backupCount": settings.log_backup_count,
                "encoding": "utf-8",
                "errors": "backslashreplace",
            },
        },
        "loggers": {
            "ppt_agent": {
                "handlers": ["console", "file"],
                "level": settings.log_level,
                "propagate": False,
            },
        },
    })
