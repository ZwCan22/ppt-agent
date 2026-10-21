from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserLogin, UserPublic, UserRegister


class UsernameAlreadyExistsError(Exception):
    """用户名已经被使用。"""


def register_user(
    db: Session,
    data: UserRegister,
) -> UserPublic:
    # 1. 查询用户名是否已被使用。
    existing_user_id = db.scalar(
        select(User.id).where(User.username == data.username)
    )

    if existing_user_id is not None:
        raise UsernameAlreadyExistsError("用户名已被使用")

    # 2. 创建用户对象，密码先进行哈希处理。
    user = User(
        username=data.username,
        password_hash=hash_password(
            data.password.get_secret_value()
        ),
    )

    try:
        # 3. 将用户写入当前事务。
        db.add(user)
        db.flush()

        # 4. 准备允许返回给前端的信息。
        result = UserPublic.model_validate(user)

        # 5. 提交事务，正式保存。
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        # 处理两个请求同时注册相同用户名的情况。
        sqlstate = getattr(exc.orig, "sqlstate", None)
        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(
            diagnostic, "constraint_name", None
        )

        if (
            sqlstate == "23505"
            and constraint_name == "uq_users_username"
        ):
            raise UsernameAlreadyExistsError(
                "用户名已被使用"
            ) from exc

        raise

    except Exception:
        db.rollback()
        raise

    return result

# 用户不存在时，也执行一次密码验证。
_DUMMY_PASSWORD_HASH = hash_password(
    "Dummy-Password-For-Timing-Only"
)


class InvalidCredentialsError(Exception):
    """账号或密码未通过验证。"""


def authenticate_user(
    db: Session,
    data: UserLogin,
) -> UserPublic:
    # 1. 根据用户名查询用户。
    user = db.scalar(
        select(User).where(User.username == data.username)
    )

    # 2. 选择本次验证使用的哈希。
    stored_hash = (
        user.password_hash
        if user is not None
        else _DUMMY_PASSWORD_HASH
    )

    # 3. 验证输入密码。
    password_matches = verify_password(
        data.password.get_secret_value(),
        stored_hash,
    )

    # 4. 用户必须存在、密码正确，并且账号处于启用状态。
    if (
        user is None
        or not password_matches
        or not user.is_active
    ):
        raise InvalidCredentialsError("用户名或密码错误")

    return UserPublic.model_validate(user)