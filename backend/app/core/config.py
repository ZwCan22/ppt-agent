from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = Field(default="PPT智能体业务后端", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"

    db_host: str = Field(default="127.0.0.1", min_length=1)
    db_port: int = Field(default=15432, ge=1, le=65535)
    db_name: str = Field(default="ppt_agent", min_length=1)
    db_user: str = Field(default="ppt_app", min_length=1)
    db_password: SecretStr = Field(min_length=1)
    dify_base_url: AnyHttpUrl = Field(default="http://localhost/v1")
    dify_api_key: SecretStr = Field(min_length=1)
    dify_timeout_seconds: int = Field(default=180, ge=1, le=600)
    storage_dir: Path = Field(default=BACKEND_DIR / "storage")

    log_dir: Path = Field(default=BACKEND_DIR / "logs")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    log_backup_count: int = Field(default=3, ge=1, le=20)

    queue_warning_seconds: int = Field(default=180, ge=1, le=86400)

    auth_session_ttl_seconds: int = Field(
        default=8 * 60 * 60,
        ge=300,
        le=7 * 24 * 60 * 60,
    )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="PPT_",
        extra="forbid",
        hide_input_in_errors=True,
    )


settings = Settings()
