from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import cv2
import logging
import asyncio

from backend.config import DEV_MODE

# 根据 DEV_MODE 动态导入
if DEV_MODE:
    from backend.core.mock import get_mock_camera as get_camera
else:
    from backend.core.camera import get_camera

router = APIRouter(
    prefix="/api",
    tags=["stream"],
    responses={404: {"description": "Not found"}},
)


@router.get("/video_stream")
async def stream(request: Request):
    """
    实时视频流接口 (MJPEG)

    修复说明：
    - 添加客户端断开检测，当用户离开页面时自动停止流
    - 避免摄像头资源一直被占用
    """
    camera = get_camera()

    async def generate_frames():
        try:
            while True:
                # 检测客户端是否断开连接
                if await request.is_disconnected():
                    logging.info("[VideoStream] Client disconnected, stopping stream")
                    break

                # 1. 从相机获取原始帧 (cv::Mat 格式)
                frame = camera.get_frame()
                if frame is None:
                    await asyncio.sleep(0.01)  # 避免空帧时占用过多 CPU
                    continue

                # 2. 将帧编码为 JPG 格式
                ret, buffer = cv2.imencode(".jpg", frame)
                if not ret:
                    continue

                # 3. 将 JPG 转换为字节流
                frame_bytes = buffer.tobytes()

                # 4. 构建 HTTP multipart/x-mixed-replace 响应
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )

                # 短暂休眠，避免占用过多 CPU（控制帧率）
                await asyncio.sleep(0.033)  # 约 30 FPS

        except Exception as e:
            logging.error(f"[VideoStream] Error in generate_frames: {e}")
        finally:
            logging.info("[VideoStream] Stream stopped, camera resource released")

    # 返回流式响应
    return StreamingResponse(
        generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )
