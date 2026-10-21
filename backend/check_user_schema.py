from pydantic import ValidationError

from app.schemas.user import UserRegister


def main() -> None:
    user = UserRegister(
        username="student_01",
        password="Learning-Only-123",
    )

    print("合法用户名：", user.username)
    print("密码显示：", user.password)

    try:
        UserRegister(
            username="ab",
            password="Learning-Only-123",
        )
    except ValidationError:
        print("过短的用户名已被拒绝")

    try:
        UserRegister(
            username="student_01",
            password="123",
        )
    except ValidationError:
        print("过短的密码已被拒绝")


if __name__ == "__main__":
    main()