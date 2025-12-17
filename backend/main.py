from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.backgroundThread import BackgroundThread
from backend.core.camera import get_camera
from backend.core.face_engine import get_face_engine
from backend.routers import auth, face, stream, unlock
from backend.database.manager import db_manager as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 引擎初始化以及摄像头初始化
    print("Application started")
    face_engine = get_face_engine()
    camera = get_camera()
    back = BackgroundThread()
    back.start()
    yield
    # 引擎销毁以及摄像头销毁
    print("Application shutting down")
    back.stop()
    db.close()  # 关闭数据库连接
    del face_engine
    del camera


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(face.router)
app.include_router(stream.router)
app.include_router(unlock.router)
