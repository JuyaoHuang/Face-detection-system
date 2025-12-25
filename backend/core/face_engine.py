"""
FaceEngine Python Wrapper for FastAPI Backend
封装 libface_engine.so，提供 Python 友好的接口
"""

import ctypes
import numpy as np
from pathlib import Path
from typing import Optional, List


class FaceEngine:
    """
    人脸识别引擎包裹类（单例模式）

    负责加载 C++ .so 库，管理内存指针，提供 Python 友好的接口
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """单例模式：确保全局只有一个引擎实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化人脸识别引擎"""
        if self._initialized:
            return

        # ========================================
        # 1. 动态库加载与路径管理
        # ========================================

        # 获取 backend 目录的绝对路径
        backend_dir = Path(__file__).parent.parent.resolve()
        project_root = backend_dir.parent

        # 构建路径
        lib_path = project_root / "face_detection" / "build" / "libface_engine.so"
        retinaface_model = (
            project_root / "face_detection" / "models" / "RetinaFace.rknn"
        )
        mobilefacenet_model = (
            project_root / "face_detection" / "models" / "mobilefacenet.rknn"
        )

        # 检查文件是否存在
        if not lib_path.exists():
            raise FileNotFoundError(f"Library not found: {lib_path}")
        if not retinaface_model.exists():
            raise FileNotFoundError(f"Model not found: {retinaface_model}")
        if not mobilefacenet_model.exists():
            raise FileNotFoundError(f"Model not found: {mobilefacenet_model}")

        # 加载动态库
        try:
            self.lib = ctypes.CDLL(str(lib_path))
            print(f"[FaceEngine] Successfully loaded library: {lib_path}")
        except OSError as e:
            raise RuntimeError(f"Failed to load library {lib_path}: {e}")

        # ========================================
        # 2. C 函数的参数类型定义
        # ========================================

        # void* FaceEngine_Create()
        self.lib.FaceEngine_Create.restype = ctypes.c_void_p
        self.lib.FaceEngine_Create.argtypes = []

        # int FaceEngine_Init(void* engine, const char* retinaface_model, const char* mobilefacenet_model)
        self.lib.FaceEngine_Init.restype = ctypes.c_int
        self.lib.FaceEngine_Init.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]

        # int FaceEngine_ExtractFeature(void* engine, unsigned char* jpeg_data, int data_len, float* feature_512)
        self.lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
        self.lib.FaceEngine_ExtractFeature.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float),
        ]

        # void FaceEngine_Destroy(void* engine)
        self.lib.FaceEngine_Destroy.restype = None
        self.lib.FaceEngine_Destroy.argtypes = [ctypes.c_void_p]

        # float FaceEngine_CosineSimilarity(const float* emb1, const float* emb2)
        self.lib.FaceEngine_CosineSimilarity.restype = ctypes.c_float
        self.lib.FaceEngine_CosineSimilarity.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
        ]

        # ========================================
        # 3. 初始化方法
        # ========================================

        # 创建引擎实例
        self.engine_ptr = self.lib.FaceEngine_Create()
        if not self.engine_ptr:
            raise RuntimeError("Failed to create FaceEngine instance")

        # 初始化模型（传入模型路径）
        print("[FaceEngine] Initializing models...")
        print(f"  RetinaFace: {retinaface_model}")
        print(f"  MobileFaceNet: {mobilefacenet_model}")

        ret = self.lib.FaceEngine_Init(
            self.engine_ptr,
            str(retinaface_model).encode("utf-8"),
            str(mobilefacenet_model).encode("utf-8"),
        )

        if ret != 0:
            self.lib.FaceEngine_Destroy(self.engine_ptr)
            raise RuntimeError(f"Failed to initialize FaceEngine (ret={ret})")

        print("[FaceEngine] Initialized successfully")
        self._initialized = True

    # ========================================
    # 4. 核心功能方法
    # ========================================

    def extract_feature(self, image_bytes: bytes) -> Optional[List[float]]:
        """
        提取人脸特征向量（FastAPI 接口）

        Args:
            image_bytes: 图片的二进制数据（JPEG/PNG格式）

        Returns:
            List[float]: 512维特征向量（成功）
            None: 未检测到人脸或处理失败
        """
        if not image_bytes:
            print("[FaceEngine] Error: Empty image data")
            return None

        # 转换为 ctypes 数组
        jpeg_array = np.frombuffer(image_bytes, dtype=np.uint8)
        jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

        # 准备输出缓冲区（512维浮点数组）
        feature_512 = np.zeros(512, dtype=np.float32)
        feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 调用 C++ 函数
        ret = self.lib.FaceEngine_ExtractFeature(
            self.engine_ptr, jpeg_ptr, len(image_bytes), feature_ptr
        )

        # 处理返回值
        if ret == 0:
            # 成功：转换为 Python List
            print("[FaceEngine] Feature extracted successfully")
            return feature_512.tolist()
        elif ret == -1:
            # 未检测到人脸
            print("[FaceEngine] No face detected in the image")
            return None
        else:
            # 其他错误
            print(f"[FaceEngine] Feature extraction failed (ret={ret})")
            return None

    def compute_similarity(self, feature1: List[float], feature2: List[float]) -> float:
        """
        计算两个特征向量的余弦相似度

        Args:
            feature1: 512维特征向量1
            feature2: 512维特征向量2

        Returns:
            float: 余弦相似度 [0, 1]
        """
        # 修复：正确处理 None 和空数组（兼容 list 和 numpy 数组）
        if feature1 is None or feature2 is None:
            return 0.0

        # 检查数组长度
        try:
            if len(feature1) == 0 or len(feature2) == 0:
                return 0.0
        except TypeError:
            # 如果无法获取长度，返回 0
            return 0.0

        if len(feature1) != 512 or len(feature2) != 512:
            print("[FaceEngine] Error: Feature vectors must be 512-dimensional")
            return 0.0

        # 转换为 numpy 数组
        arr1 = np.array(feature1, dtype=np.float32)
        arr2 = np.array(feature2, dtype=np.float32)

        # 转换为 ctypes 指针
        ptr1 = arr1.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr2 = arr2.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 调用 C++ 函数
        similarity = self.lib.FaceEngine_CosineSimilarity(ptr1, ptr2)
        return float(similarity)

    # ========================================
    # 5. 资源释放方法
    # ========================================

    def __del__(self):
        """释放资源（防止内存泄漏）"""
        if hasattr(self, "engine_ptr") and self.engine_ptr:
            self.lib.FaceEngine_Destroy(self.engine_ptr)
            print("[FaceEngine] Engine destroyed")


# ========================================
# 全局单例实例（供 FastAPI 使用）
# ========================================

# 延迟初始化：只在首次调用时创建实例
_face_engine_instance: Optional[FaceEngine] = None


def get_face_engine() -> FaceEngine:
    """
    获取全局 FaceEngine 实例（单例模式）

    供 FastAPI 路由函数调用
    """
    global _face_engine_instance
    if _face_engine_instance is None:
        _face_engine_instance = FaceEngine()
    return _face_engine_instance
