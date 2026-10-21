import hashlib
import secrets

from pwdlib import PasswordHash

SESSION_COOKIE_NAME = "ppt_agent_session"
_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """注册时：把原始密码转换成密码哈希。"""
    return _password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """登录时：检查输入密码是否匹配数据库中的哈希。"""
    return _password_hasher.verify(password, stored_hash)


def generate_session_token() -> str:
    """生成随机登录凭证。"""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """计算登录凭证的哈希，用于数据库保存和查询。"""
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()