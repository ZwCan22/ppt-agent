from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class UserRegister(BaseModel):
    """注册接口接收的数据。"""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9_]+$",
        description="用户名，只能包含小写英文字母、数字和下划线",
    )

    password: SecretStr = Field(
        min_length=12,
        max_length=128,
        description="密码，长度为12至128个字符",
    )


class UserPublic(BaseModel):
    """接口允许返回的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    created_at: datetime

class UserLogin(BaseModel):
    """登录时提交的数据。"""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9_]+$",
    )

    password: SecretStr = Field(
        min_length=1,
        max_length=128,
    )