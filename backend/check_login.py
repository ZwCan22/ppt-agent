from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.engine import engine
from app.schemas.user import UserLogin
from app.services.users import (
    InvalidCredentialsError,
    authenticate_user,
)


def main() -> None:
    username = input("请输入用户名：")
    password = getpass("请输入密码（输入时不显示）：")

    try:
        data = UserLogin(
            username=username,
            password=password,
        )
    except ValidationError:
        print("输入格式不符合要求")
        return

    with Session(engine) as db:
        try:
            user = authenticate_user(db, data)
        except InvalidCredentialsError:
            print("验证失败：用户名或密码错误")
            return

        print("身份验证通过，用户名：", user.username)


if __name__ == "__main__":
    main()