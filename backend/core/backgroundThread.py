import logging
import threading
import time

import cv2
from pyexpat import features

from backend.core import doorController
from backend.core.camera import get_camera
from backend.core.face_engine import get_face_engine
from backend.database import manager
from backend.database.manager import db_manager

'''
    后台线程，用于持续读取摄像头帧处理日常任务
'''
class BackgroundThread(threading.Thread):

    '''
        初始化后台线程
        Args:
            check_interval: 检查间隔时间（秒），默认100ms
            motion_threshold: 移动侦测阈值，默认500
            similarity_threshold: 人脸识别相似度阈值，默认0.5
    '''
    def __init__(self, check_interval=0.1, motion_threshold=500, similarity_threshold=0.5):
        super().__init__(target=self.run)
        super().__init__()
        self.daemon = True  # 设置为守护线程，主程序退出时自动结束
        self.check_interval = check_interval
        self.motion_threshold = motion_threshold
        self.similarity_threshold = similarity_threshold
        self.running = False  # 线程运行状态标志
        self.db_manager = manager.DatabaseManager()
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

            # 移动监测
            if camera.detect_motion(prev_frame, frame, self.motion_threshold):
                logging.info("Move!")
                prev_frame = frame

                # 使用 cv2.imencode 将帧转为 Bytes (模拟图片文件)
                _, img_encoded = cv2.imencode('.jpg', frame)
                img_bytes = img_encoded.tobytes()

                # 调用 face_engine 进行人脸识别获得512维特征向量
                results = face_engine.extract_feature(img_bytes)
                if results is not None:
                    logging.info("识别到人脸")
                else:
                    logging.info("未识别到人脸")

                # 与数据库中的特征向量进行比较，判断是否为已知人脸
                # 从数据库中获取所有人脸特征
                db_results = db_manager.get_face_features()

                # 遍历数据库中的每个人脸特征，计算相似度
                for item in db_results:
                    sim = face_engine.compute_similarity(results, item['feature_vector'])
                    # 若为已知人脸相似度大于0.5，记录日志并且开锁
                    if sim > self.similarity_threshold:
                        logging.info(f"识别到 {item['name']}, 相似度: {sim:.4f}")
                        self.door_lock.open()
                        logging.info("开锁")
                        break

            time.sleep(self.check_interval)