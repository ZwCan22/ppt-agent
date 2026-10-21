from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_session_token,
    hash_session_token,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.user import UserLogin, UserPublic
from app.services.users import authenticate_user


def login_user(
    db: Session,
    data: UserLogin,
) -> tuple[UserPublic, str, datetime]:
    try:
        # 1. 验证账号密码，取得用户信息。
        user = authenticate_user(db, data)

        # 2. 为本次登录生成新的随机凭证。
        token = generate_session_token()

        # 3. 计算本次登录的失效时间。
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.auth_session_ttl_seconds
        )

        # 4. 创建登录记录，数据库只保存凭证哈希。
        login_session = UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )

        db.add(login_session)

        # 5. 正式保存登录记录。
        db.commit()

    except Exception:
        db.rollback()
        raise

    return user, token, expires_at


class InvalidSessionError(Exception):
    """登录凭证无效或已经过期。"""


def get_user_by_session(
    db: Session,
    token: str | None,
) -> UserPublic:
    # 缺少凭证或凭证过长，直接拒绝。
    if not token or len(token) > 128:
        raise InvalidSessionError("登录状态无效")

    token_hash = hash_session_token(token)

    # 同时查询会话及其所属用户。
    user = db.scalar(
        select(User)
        .join(
            UserSession,
            UserSession.user_id == User.id,
        )
        .where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > func.now(),
            User.is_active.is_(True),
        )
    )

    if user is None:
        raise InvalidSessionError("登录状态无效")

    return UserPublic.model_validate(user)


def logout_user(
    db: Session,
    token: str | None,
) -> None:
    # 没有有效格式的凭证，也允许完成退出操作。
    if not token or len(token) > 128:
        return

    token_hash = hash_session_token(token)

    try:
        db.execute(
            delete(UserSession).where(
                UserSession.token_hash == token_hash
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
