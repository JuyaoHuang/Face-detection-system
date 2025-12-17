from fastapi import APIRouter

from backend.database.manager import db_manager
from backend.utils.auth import create_access_token
from backend.utils.password import verify_password

router = APIRouter(
    prefix = "/api",
    tags = ["auth"],
    responses = {404: {"description": "Not found"}},
)

@router.post("/login")
async def login(username: str, password: str):
    """管理员登录

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        成功返回 {"status": "success", "token": "<jwt_token>"}
        失败返回 {"status": "error", "message": "Invalid credentials"}
    """
    # 从数据库获取 hash 后的密码
    hashed_password = db_manager.get_administrator(username)
    if hashed_password and verify_password(password, hashed_password):
        # 生成 JWT token
        token = create_access_token(username)
        return {"status": "success", "token": token}
    else:
        return {"status": "error", "message": "Invalid credentials"}

@router.post("/change_login_password")
async def change_password(username: str, old_password: str, new_password: str):
    """修改管理员密码

    Args:
        username: 用户名
        old_password: 旧的明文密码
        new_password: 新的明文密码

    Returns:
        成功返回 {"status": "success"}
        失败返回 {"status": "error", "message": "Invalid credentials"}
    """
    # 从数据库获取 hash 后的密码
    hashed_password = db_manager.get_administrator(username)
    if hashed_password and verify_password(old_password, hashed_password):
        # 旧密码验证通过，更新为新密码（数据库会自动 hash）
        db_manager.update_administrator_password(username, new_password)
        return {"status": "success"}
    else:
        return {"status": "error", "message": "Invalid credentials"}
