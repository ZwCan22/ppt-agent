from app.core.security import hash_password, verify_password


def main() -> None:
    # 这里只使用练习密码，不要填写真实账号密码。
    sample_password = "Learning-Only-123"
    stored_hash = hash_password(sample_password)

    print(
        "正确密码验证结果：",
        verify_password(sample_password, stored_hash),
    )
    print(
        "错误密码验证结果：",
        verify_password("wrong-password", stored_hash),
    )


if __name__ == "__main__":
    main()