import logging
import threading
import time

import cv2

from backend.core import doorController
from backend.core.camera import get_camera
from backend.core.face_engine import get_face_engine
from backend.database.manager import db_manager

'''
    后台线程，用于持续读取摄像头帧处理日常任务
'''
class BackgroundThread(threading.Thread):

    '''
        初始化后台线程
        Args:
            check_interval: 检查间隔时间（秒），默认100ms
            binary_threshold: 二值化阈值，用于帧差检测，默认25（取值范围0-255）
            contour_threshold: 轮廓面积阈值，过滤小运动，默认500（像素面积）
            similarity_threshold: 人脸识别相似度阈值，默认0.5
    '''
    def __init__(self, check_interval=0.1, binary_threshold=25, contour_threshold=500, similarity_threshold=0.5):
        super().__init__(target=self.run)   
        self.daemon = True  # 设置为守护线程，主程序退出时自动结束
        self.check_interval = check_interval
        self.binary_threshold = binary_threshold        # 二值化阈值（用于 detect_motion）
        self.contour_threshold = contour_threshold      # 轮廓面积阈值
        self.similarity_threshold = similarity_threshold
        self.running = False  # 线程运行状态标志
        # 使用全局 db_manager 实例，避免创建多个数据库连接
        self.door_lock = doorController.get_door_controller()

    def start(self):
        """启动线程"""
        self.running = True
        super().start()
        logging.info("BackgroundThread started")

    def stop(self):
        """停止线程"""
        self.running = False
        logging.info("BackgroundThread stopping...")

    def run(self):
        camera = get_camera()
        face_engine = get_face_engine()

        # 设置 Camera 的轮廓面积阈值
        camera.motion_contour_threshold = self.contour_threshold

        prev_frame = None
        while self.running:
            # 读取一帧图像
            frame = camera.get_frame()
            if frame is None:
                time.sleep(self.check_interval)
                continue

            # 移动监测
            if prev_frame is None:
                prev_frame = frame
                time.sleep(self.check_interval)
                continue

            # 移动监测（使用二值化阈值）
            if camera.detect_motion(prev_frame, frame, self.binary_threshold):
                logging.info("Move!")

                # 使用 cv2.imencode 将帧转为 Bytes (模拟图片文件)
                _, img_encoded = cv2.imencode('.jpg', frame)
                img_bytes = img_encoded.tobytes()

                # 调用 face_engine 进行人脸识别获得512维特征向量
                results = face_engine.extract_feature(img_bytes)

                if results is not None:
                    # 识别到人脸，进行特征比对
                    logging.info("识别到人脸")

                    # 从数据库中获取所有人脸特征
                    db_results = db_manager.get_face_features()

                    # 遍历数据库中的每个人脸特征，计算相似度
                    for item in db_results:
                        sim = face_engine.compute_similarity(results, item['feature_vector'])
                        # 若为已知人脸相似度大于阈值，记录日志并且开锁
                        if sim > self.similarity_threshold:
                            logging.info(f"识别到 {item['name']}, 相似度: {sim:.4f}")
                            self.door_lock.open()
                            logging.info("开锁")
                            break
                else:
                    # 未识别到人脸
                    logging.info("未识别到人脸")

            # 更新前一帧（无论是否检测到运动）
            prev_frame = frame
            time.sleep(self.check_interval)