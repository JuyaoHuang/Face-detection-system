import logging
from typing import Optional

import cv2

class Camera:
    '''摄像头管理类'''

    def __init__(self, index=0):
        '''初始化函数，打开相机'''
        # 添加初始化标志，避免单例模式下重复初始化
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.index = index
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open camera{index}")
        # 初始化移动监测所需的变量
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
    def detect_motion(self, prevFrame, frame, binary_threshold):
        # 转换为灰度图像
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 应用高斯模糊
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # 转换前一帧为灰度并模糊（如果不是灰度图像）
        if len(prevFrame.shape) > 2:
            prev_gray = cv2.cvtColor(prevFrame, cv2.COLOR_BGR2GRAY)
            prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
        else:
            prev_gray = prevFrame

        # 计算当前帧与前一帧的差异
        frame_delta = cv2.absdiff(prev_gray, gray)
        thresh = cv2.threshold(frame_delta, binary_threshold, 255, cv2.THRESH_BINARY)[1]

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


if __name__ == '__main__':
    """单元测试：验证 Camera 功能"""
    import numpy as np

    print("="*60)
    print("开始测试 Camera")
    print("="*60)

    # 测试1: 单例模式
    print("\n[Test 1] 单例模式测试")
    try:
        cam1 = Camera()
        cam2 = Camera()
        if cam1 is cam2:
            print("[PASS] 单例模式正确：cam1 is cam2")
        else:
            print("[FAIL] 单例模式错误：创建了多个实例")
    except Exception as e:
        print(f"[INFO] 摄像头初始化失败（可能没有摄像头硬件）: {e}")
        print("[SKIP] 跳过后续需要硬件的测试")
        print("\n" + "="*60)
        print("测试完成（部分跳过）")
        print("="*60)
        exit(0)

    # 测试2: 初始化标志
    print("\n[Test 2] 初始化标志测试")
    try:
        cam = Camera()
        if hasattr(cam, '_initialized') and cam._initialized == True:
            print("[PASS] 初始化标志正确设置")
        else:
            print("[FAIL] 初始化标志未设置")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试3: 重复初始化
    print("\n[Test 3] 重复初始化测试（防止重复打开摄像头）")
    try:
        cam = Camera(index=0)
        original_cap = cam.cap
        # 再次调用 __init__（单例模式下会被调用）
        cam.__init__(index=0)
        if cam.cap is original_cap:
            print("[PASS] 重复初始化被正确阻止，摄像头未重新打开")
        else:
            print("[FAIL] 摄像头被重新打开")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试4: 获取帧
    print("\n[Test 4] 获取帧测试")
    try:
        cam = get_camera()
        frame = cam.get_frame()
        if frame is not None:
            print(f"[PASS] 成功获取帧，shape={frame.shape}")
        else:
            print("[FAIL] 获取帧失败")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试5: 运动检测算法（不需要真实运动）
    print("\n[Test 5] 运动检测算法测试")
    try:
        cam = get_camera()

        # 创建两个相同的测试帧（无运动）
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.zeros((480, 640, 3), dtype=np.uint8)

        motion_detected = cam.detect_motion(frame1, frame2, binary_threshold=25)

        if not motion_detected:
            print("[PASS] 相同帧检测无运动：正确")
        else:
            print("[FAIL] 相同帧检测到运动：错误")

        # 创建两个不同的帧（有运动）
        frame3 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame4 = np.ones((480, 640, 3), dtype=np.uint8) * 255

        motion_detected2 = cam.detect_motion(frame3, frame4, binary_threshold=25)

        if motion_detected2:
            print("[PASS] 完全不同的帧检测到运动：正确")
        else:
            print("[FAIL] 完全不同的帧未检测到运动：错误")

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 测试6: 轮廓面积阈值设置
    print("\n[Test 6] 轮廓面积阈值测试")
    try:
        cam = get_camera()
        original_threshold = cam.motion_contour_threshold
        print(f"  默认轮廓面积阈值: {original_threshold}")

        # 修改阈值
        cam.motion_contour_threshold = 1000
        if cam.motion_contour_threshold == 1000:
            print("[PASS] 轮廓面积阈值可以修改")
        else:
            print("[FAIL] 轮廓面积阈值修改失败")

        # 恢复默认值
        cam.motion_contour_threshold = original_threshold
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试7: get_camera() 函数
    print("\n[Test 7] get_camera() 函数测试")
    try:
        cam1 = get_camera()
        cam2 = get_camera()
        if cam1 is cam2:
            print("[PASS] get_camera() 返回同一实例")
        else:
            print("[FAIL] get_camera() 返回不同实例")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n注意：如果没有摄像头硬件，某些测试会失败")
