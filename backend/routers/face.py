from fastapi import APIRouter, UploadFile, File
import cv2

from backend.core.camera import get_camera
from backend.core.face_engine import get_face_engine
from backend.database.manager import db_manager

router = APIRouter(
    prefix = "/api/face",
    tags = ["face"],
    responses = {404: {"description": "Not found"}},
)

@router.post("/capture")
async def capture_face(username: str):
    camera = get_camera()
    face_engine = get_face_engine()
    frame = camera.get_frame()
    if frame is None:
        return {"status": "error", "message": "Failed to capture frame"}

    # 将帧编码为 JPEG 字节流（extract_feature 要求输入 bytes）
    _, img_encoded = cv2.imencode('.jpg', frame)
    img_bytes = img_encoded.tobytes()

    # 录入人脸
    faces = face_engine.extract_feature(img_bytes)
    if not faces:
        return {"status": "error", "message": "No face detected"}
    # 保存人脸特征向量
    if not db_manager.add_face_feature(username, faces):
        return {"status": "error", "message": "Failed to save face feature"}

    return {"status": "success"}

@router.get("/list")
async def getList():
    name_list = db_manager.get_face_name_list()
    return name_list

@router.post("/recognize")
async def recognize_face(file: UploadFile = File(...)):
    """远程人脸识别测试

    Args:
        file: 上传的图片文件

    Returns:
        识别结果，包含匹配的人名和相似度，或未识别到人脸/未匹配的错误信息

    说明:
        - 用于管理员测试系统准确度，或远程验证照片
        - 不会触发开门操作
    """
    face_engine = get_face_engine()

    # 读取上传的图片文件内容
    img_bytes = await file.read()

    # 提取人脸特征
    features = face_engine.extract_feature(img_bytes)
    if not features:
        return {"status": "error", "message": "No face detected"}

    # 从数据库获取所有已注册的人脸特征
    db_results = db_manager.get_face_features()
    if not db_results:
        return {"status": "error", "message": "No registered faces in database"}

    # 遍历数据库中的人脸特征，计算相似度
    best_match = None
    best_similarity = 0.0

    for item in db_results:
        similarity = face_engine.compute_similarity(features, item['feature_vector'])
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = item['name']

    # 返回识别结果（不设阈值，返回最佳匹配）
    return {
        "status": "success",
        "name": best_match,
        "similarity": round(best_similarity, 4)
    }

@router.delete("/reset")
async def delete_all_faces():
    if not db_manager.delete_all_face_names():
        return {"status": "error", "message": "Failed to delete all face names"}
    return {"status": "success"}

@router.delete("/{name}")
async def delete_face(name: str):
    if not db_manager.delete_face_name(name):
        return {"status": "error", "message": "Failed to delete face name"}
    return {"status": "success"}
