from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.errors import ErrorResponse
from app.schemas.user import UserLogin, UserPublic, UserRegister
from app.core.config import settings
from app.core.security import SESSION_COOKIE_NAME
from app.services.auth import login_user, logout_user
from app.services.users import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
    register_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["用户认证"],
)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=201,
    summary="注册用户",
    responses={
        409: {
            "model": ErrorResponse,
            "description": "用户名已被使用",
        },
        422: {
            "model": ErrorResponse,
            "description": "请求参数不符合要求",
        },
    },
)
def register_user_endpoint(
    data: UserRegister,
    db: Session = Depends(get_db),
) -> UserPublic:
    try:
        return register_user(db, data)
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="用户名已被使用",
        ) from exc

@router.post(
    "/login",
    response_model=UserPublic,
    summary="用户登录",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "用户名或密码错误",
        },
        422: {
            "model": ErrorResponse,
            "description": "请求参数不符合要求",
        },
    },
)
def login_user_endpoint(
    data: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
) -> UserPublic:
    try:
        user, token, expires_at = login_user(db, data)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        ) from exc

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.auth_session_ttl_seconds,
        expires=expires_at,
        path="/api",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
    )

    response.headers["Cache-Control"] = "no-store"

    return user


@router.get(
    "/me",
    response_model=UserPublic,
    summary="查询当前登录用户",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "未登录或登录已过期",
        },
    },
)
def get_me(
    response: Response,
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    response.headers["Cache-Control"] = "no-store"
    return current_user


@router.post(
    "/logout",
    status_code=204,
    response_class=Response,
    summary="退出当前登录",
)
def logout_user_endpoint(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)

    # 先撤销数据库中的登录会话。
    logout_user(db, token)

    # 再通知浏览器清除登录 Cookie。
    response = Response(status_code=204)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/api",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"

    return response
