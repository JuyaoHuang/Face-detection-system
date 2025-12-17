"""JWT 认证工具模块"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

# JWT 配置
SECRET_KEY = "your-secret-key-change-in-production"  # 生产环境应该从环境变量读取
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24  # token 有效期 24 小时


def create_access_token(username: str) -> str:
    """生成 JWT token

    Args:
        username: 管理员用户名

    Returns:
        JWT token 字符串
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": username,  # subject - 用户名
        "exp": expire,    # expiration - 过期时间
        "iat": now  # issued at - 签发时间
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_token(token: str) -> Optional[str]:
    """验证 JWT token

    Args:
        token: JWT token 字符串

    Returns:
        如果验证成功，返回用户名；否则返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except jwt.ExpiredSignatureError:
        # token 已过期
        return None
    except jwt.InvalidTokenError:
        # token 无效
        return None


def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization Header 中提取 token

    Args:
        authorization: Authorization Header 的值，格式: "Bearer <token>"

    Returns:
        提取的 token，如果格式错误返回 None
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]
