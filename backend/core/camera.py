import logging
from typing import Optional

import cv2

class Camera:
    camera = None

    '''单例模式'''
    def __new__(cls, index=0):
        if cls.camera is None:
            cls.camera = super().__new__(cls)
        return cls.camera

    '''初始化函数，打开相机'''
    def __init__(self, index=0):
        self.index = index
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open camera{index}")
        # 初始化移动监测所需的变量
        self.first_frame = None
        self.motion_contour_threshold = 500  # 轮廓面积阈值，用于判断是否有显著运动

    '''析构函数，释放相机资源'''
    def __del__(self):
        self.cap.release()
        print(f"Camera{self.index} released")

    '''获取一帧图像'''
    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            logging.error("Failed to read frame from camera")
            return None
        return frame

    '''移动监测'''
    def detect_motion(self, prevFrame, frame, motion_threshold):
        # 转换为灰度图像
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 应用高斯模糊
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        # 初始化第一帧
        if self.first_frame is None:
            self.first_frame = gray

        # 转换前一帧为灰度并模糊（如果不是灰度图像）
        if len(prevFrame.shape) > 2:
            prev_gray = cv2.cvtColor(prevFrame, cv2.COLOR_BGR2GRAY)
            prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
        else:
            prev_gray = prevFrame

        # 计算当前帧与前一帧的差异
        frame_delta = cv2.absdiff(prev_gray, gray)
        thresh = cv2.threshold(frame_delta, motion_threshold, 255, cv2.THRESH_BINARY)[1]

        # 扩展阈值图像，填充空洞
        thresh = cv2.dilate(thresh, None, iterations=2)

        # 查找轮廓
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 如果轮廓面积超过阈值，认为检测到运动
        for contour in contours:
            if cv2.contourArea(contour) > self.motion_contour_threshold:
                return True

        return False



# ========================================
# 全局单例实例（供 FastAPI 使用）
# ========================================

# 延迟初始化：只在首次调用时创建实例
_camera_instance: Optional[Camera] = None


def get_camera() -> Camera:
    """
    获取全局 Camera 实例（单例模式）

    供 FastAPI 路由函数调用
    """
    global _camera_instance
    if _camera_instance is None:
        _camera_instance = Camera()
    return _camera_instance
