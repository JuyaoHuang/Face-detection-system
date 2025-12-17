from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cv2

from backend.core.camera import get_camera

router = APIRouter(
    prefix="/api",
    tags=["stream"],
    responses={404: {"description": "Not found"}},
)


@router.get("/video_stream")
async def stream():
    camera = get_camera()

    def generate_frames():
        while True:
            # 1. 从相机获取原始帧 (cv::Mat 格式)
            frame = camera.get_frame()
            if frame is None:
                continue

            # 2. 将帧编码为 JPG 格式
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            # 3. 将 JPG 转换为字节流
            frame_bytes = buffer.tobytes()

            # 4. 构建 HTTP multipart/x-mixed-replace 响应
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    # 返回流式响应
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )