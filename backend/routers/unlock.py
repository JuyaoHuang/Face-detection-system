import threading
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Header

from backend.core.doorController import get_door_controller
from backend.utils.auth import verify_token, extract_token_from_header

router = APIRouter(
    prefix="/api",
    tags=["unlock"],
    responses={404: {"description": "Not found"}},
)


@router.post("/unlock")
async def unlock(background_tasks: BackgroundTasks, authorization: Optional[str] = Header(None)):
    """管理员远程开门

    Args:
        background_tasks: FastAPI后台任务
        authorization: Authorization Header，格式: "Bearer <token>"

    Returns:
        成功返回 {"status": "success"}，否则返回错误信息

    说明:
        - 验证JWT token后，在后台线程中执行开门操作
        - 立即返回，不阻塞请求（开门操作需要3秒）
    """
    # 从 Header 中提取 token
    token = extract_token_from_header(authorization)
    if not token:
        return {"status": "error", "message": "Missing or invalid authorization header"}

    # 验证 token
    username = verify_token(token)
    if not username:
        return {"status": "error", "message": "Invalid or expired token"}

    # 在后台任务中执行开门操作
    def open_door():
        door_controller = get_door_controller()
        door_controller.open()

    background_tasks.add_task(open_door)

    return {"status": "success", "message": "Door unlock initiated"}
