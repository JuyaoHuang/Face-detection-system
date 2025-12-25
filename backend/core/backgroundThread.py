import logging
import threading
import time

import cv2

from backend.core import doorController
from backend.core.camera import get_camera
from backend.core.face_engine import get_face_engine
from backend.database.manager import db_manager
from backend.config import (
    CHECK_INTERVAL,
    BINARY_THRESHOLD,
    CONTOUR_THRESHOLD,
    SIMILARITY_THRESHOLD,
)

"""
    后台线程，用于持续读取摄像头帧处理日常任务
"""


class BackgroundThread(threading.Thread):
    """
    初始化后台线程
    Args:
        check_interval: 检查间隔时间（秒），默认从配置文件读取
        binary_threshold: 二值化阈值，用于帧差检测，默认从配置文件读取
        contour_threshold: 轮廓面积阈值，过滤小运动，默认从配置文件读取
        similarity_threshold: 人脸识别相似度阈值，默认从配置文件读取
    """

    def __init__(
        self,
        check_interval=None,
        binary_threshold=None,
        contour_threshold=None,
        similarity_threshold=None,
    ):
        super().__init__(target=self.run)
        self.daemon = True  # 设置为守护线程，主程序退出时自动结束

        # 使用配置文件中的值作为默认值
        self.check_interval = (
            check_interval if check_interval is not None else CHECK_INTERVAL
        )
        self.binary_threshold = (
            binary_threshold if binary_threshold is not None else BINARY_THRESHOLD
        )
        self.contour_threshold = (
            contour_threshold if contour_threshold is not None else CONTOUR_THRESHOLD
        )
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else SIMILARITY_THRESHOLD
        )

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
                _, img_encoded = cv2.imencode(".jpg", frame)
                img_bytes = img_encoded.tobytes()

                # 调用 face_engine 进行人脸识别获得512维特征向量
                results = face_engine.extract_feature(img_bytes)

                if results is not None:
                    # 识别到人脸，进行特征比对
                    logging.info("识别到人脸，开始特征比对")

                    # 从数据库中获取所有人脸特征
                    db_results = db_manager.get_face_features()
                    logging.info(f"数据库中有 {len(db_results)} 个已录入人脸")

                    # 如果数据库为空
                    if len(db_results) == 0:
                        logging.warning("数据库中没有已录入的人脸，无法比对")
                    else:
                        # 遍历数据库中的每个人脸特征，计算相似度
                        max_sim = 0.0
                        matched_name = None

                        for item in db_results:
                            sim = face_engine.compute_similarity(
                                results, item["feature_vector"]
                            )
                            logging.info(f"与 {item['name']} 的相似度: {sim:.4f}")

                            # 记录最高相似度
                            if sim > max_sim:
                                max_sim = sim
                                matched_name = item['name']

                            # 若为已知人脸相似度大于阈值，记录日志并且开锁
                            if sim > self.similarity_threshold:
                                print(f"✓ 识别成功: {item['name']}, 相似度: {sim:.4f} (阈值: {self.similarity_threshold})")
                                self.door_lock.open()
                                logging.info("开锁")
                                break
                        else:
                            # 所有比对都失败
                            logging.warning(f"✗ 识别失败: 最高相似度 {max_sim:.4f} ({matched_name}), 未达到阈值 {self.similarity_threshold}")
                else:
                    # 未识别到人脸
                    logging.info("未识别到人脸")

            # 更新前一帧（无论是否检测到运动）
            prev_frame = frame
            time.sleep(self.check_interval)
