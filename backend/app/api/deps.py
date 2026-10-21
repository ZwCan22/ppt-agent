from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.security import SESSION_COOKIE_NAME
from app.db.session import get_db
from app.schemas.user import UserPublic
from app.services.auth import (
    InvalidSessionError,
    get_user_by_session,
)


def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserPublic:
    response.headers["Cache-Control"] = "no-store"
    token = request.cookies.get(SESSION_COOKIE_NAME)

    try:
        return get_user_by_session(db, token)
    except InvalidSessionError as exc:
        raise HTTPException(
            status_code=401,
            detail="请先登录或重新登录",
            headers={"Cache-Control": "no-store"},
        ) from exc
