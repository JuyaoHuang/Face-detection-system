"""密码 Hash 工具模块

使用 bcrypt 进行密码加密和验证
"""

from passlib.context import CryptContext

# 创建密码上下文，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对密码进行 hash 加密

    Args:
        password: 明文密码

    Returns:
        hash 后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否正确

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的 hash 密码

    Returns:
        密码正确返回 True，否则返回 False
    """
    return pwd_context.verify(plain_password, hashed_password)
