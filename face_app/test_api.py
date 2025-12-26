#!/usr/bin/env python3
"""
人脸识别 FaceEngine Python 测试脚本
使用 ctypes 调用 libface_engine.so

Usage:
    python test_api.py --image test.jpg

"""

import ctypes
import numpy as np
import argparse
import os
import sys
import time
import cv2
from pathlib import Path
from datetime import datetime

# ========================================
# 配置
# ========================================
LIB_PATH = "./lib/libface_engine.so"  # 动态库路径
RETINAFACE_MODEL = "./models/RetinaFace.rknn"
MOBILEFACENET_MODEL = "./models/mobilefacenet.rknn"
OUTPUT_DIR = "./test_output"  # 输出目录

# ========================================
# 加载动态库
# ========================================
try:
    lib = ctypes.CDLL(LIB_PATH)
    print(f"✓ Successfully loaded library: {LIB_PATH}")
except OSError as e:
    print(f"✗ Error: Failed to load library {LIB_PATH}")
    print(f"  {e}")
    print("\nPlease compile the library first:")
    print("  cd face_detection && mkdir -p build && cd build && cmake .. && make -j4")
    sys.exit(1)

# ========================================
# 定义函数签名
# ========================================

# void* FaceEngine_Create()
lib.FaceEngine_Create.restype = ctypes.c_void_p
lib.FaceEngine_Create.argtypes = []

# int FaceEngine_Init(void* engine, const char* retinaface_model, const char* mobilefacenet_model)
lib.FaceEngine_Init.restype = ctypes.c_int
lib.FaceEngine_Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

# int FaceEngine_ExtractFeature(void* engine, unsigned char* jpeg_data, int data_len, float* feature_512)
lib.FaceEngine_ExtractFeature.restype = ctypes.c_int
lib.FaceEngine_ExtractFeature.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_float),
]

# void FaceEngine_Destroy(void* engine)
lib.FaceEngine_Destroy.restype = None
lib.FaceEngine_Destroy.argtypes = [ctypes.c_void_p]

# float FaceEngine_CosineSimilarity(const float* emb1, const float* emb2)
lib.FaceEngine_CosineSimilarity.restype = ctypes.c_float
lib.FaceEngine_CosineSimilarity.argtypes = [
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
]

# ========================================
# FaceEngine 类封装
# ========================================


class FaceEngine:
    def __init__(self, retinaface_model, mobilefacenet_model):
        """初始化人脸识别引擎"""
        self.engine = None
        self.retinaface_model = retinaface_model
        self.mobilefacenet_model = mobilefacenet_model

        # 创建引擎实例
        self.engine = lib.FaceEngine_Create()
        if not self.engine:
            raise RuntimeError("Failed to create FaceEngine instance")

        # 初始化模型
        print("Initializing FaceEngine...")
        print(f"  RetinaFace model: {retinaface_model}")
        print(f"  MobileFaceNet model: {mobilefacenet_model}")

        ret = lib.FaceEngine_Init(
            self.engine,
            retinaface_model.encode("utf-8"),
            mobilefacenet_model.encode("utf-8"),
        )

        if ret != 0:
            lib.FaceEngine_Destroy(self.engine)
            raise RuntimeError(f"Failed to initialize FaceEngine (ret={ret})")

        print("✓ FaceEngine initialized successfully")

    def extract_feature(self, image_path, save_output=True, output_dir=OUTPUT_DIR):
        """
        提取人脸特征向量

        Args:
            image_path: 图片文件路径（JPEG格式）
            save_output: 是否保存中间结果图片
            output_dir: 输出目录

        Returns:
            tuple: (特征向量, 时间统计字典)，失败返回 (None, None)
        """
        # 创建输出目录
        if save_output:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        if not os.path.exists(image_path):
            print(f"✗ Error: Image file not found: {image_path}")
            return None, None

        # 时间统计
        timing_stats = {}

        # 1. 读取 JPEG 文件
        t_start = time.time()
        with open(image_path, "rb") as f:
            jpeg_data = f.read()
        timing_stats["load_image"] = time.time() - t_start

        # 2. 转换为 ctypes 数组
        t_start = time.time()
        jpeg_array = np.frombuffer(jpeg_data, dtype=np.uint8)
        jpeg_ptr = jpeg_array.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
        timing_stats["prepare_data"] = time.time() - t_start

        # 3. 准备输出缓冲区
        feature_512 = np.zeros(512, dtype=np.float32)
        feature_ptr = feature_512.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # 4. 调用 C++ 函数提取特征
        print(f"\nExtracting feature from: {image_path}")
        t_start = time.time()
        ret = lib.FaceEngine_ExtractFeature(
            self.engine, jpeg_ptr, len(jpeg_data), feature_ptr
        )
        timing_stats["feature_extraction"] = time.time() - t_start

        if ret == 0:
            print("✓ Feature extracted successfully")
            print(f"  Feature shape: {feature_512.shape}")
            print(f"  Feature norm: {np.linalg.norm(feature_512):.4f}")
            print(
                f"  Feature range: [{feature_512.min():.4f}, {feature_512.max():.4f}]"
            )

            # 保存中间结果图片
            if save_output:
                t_start = time.time()
                self._save_result_image(
                    image_path, feature_512, timing_stats, output_dir
                )
                timing_stats["save_image"] = time.time() - t_start

            # 打印时间统计
            print(f"\n⏱️  Time Statistics:")
            print(f"  Load image:          {timing_stats['load_image'] * 1000:.2f} ms")
            print(
                f"  Prepare data:        {timing_stats['prepare_data'] * 1000:.2f} ms"
            )
            print(
                f"  Feature extraction:  {timing_stats['feature_extraction'] * 1000:.2f} ms"
            )
            if save_output:
                print(
                    f"  Save result image:   {timing_stats['save_image'] * 1000:.2f} ms"
                )
            total_time = sum(timing_stats.values())
            print(f"  Total:               {total_time * 1000:.2f} ms")

            return feature_512, timing_stats
        elif ret == -1:
            print("✗ Error: No face detected in the image")
            return None, None
        else:
            print(f"✗ Error: Feature extraction failed (ret={ret})")
            return None, None

    def _save_result_image(self, image_path, feature, timing_stats, output_dir):
        """
        保存带有特征信息的结果图片

        Args:
            image_path: 原始图片路径
            feature: 提取的特征向量
            timing_stats: 时间统计字典
            output_dir: 输出目录
        """
        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            print(f"✗ Warning: Cannot read image for saving: {image_path}")
            return

        # 在图片上添加信息
        h, w = img.shape[:2]

        # 添加半透明背景
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (w - 10, 180), (0, 0, 0), -1)
        img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)

        # 添加文本信息
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        color = (0, 255, 0)  # 绿色

        y_offset = 35
        line_height = 25

        # 标题
        cv2.putText(
            img,
            "Face Feature Extraction Result",
            (20, y_offset),
            font,
            0.7,
            (255, 255, 255),
            thickness,
        )
        y_offset += line_height + 5

        # 特征信息
        cv2.putText(
            img,
            f"Feature Dim: 512",
            (20, y_offset),
            font,
            font_scale,
            color,
            thickness - 1,
        )
        y_offset += line_height

        cv2.putText(
            img,
            f"Feature Norm: {np.linalg.norm(feature):.4f}",
            (20, y_offset),
            font,
            font_scale,
            color,
            thickness - 1,
        )
        y_offset += line_height

        # 时间信息
        total_time = sum(timing_stats.values())
        cv2.putText(
            img,
            f"Total Time: {total_time * 1000:.2f} ms",
            (20, y_offset),
            font,
            font_scale,
            (0, 255, 255),
            thickness - 1,
        )
        y_offset += line_height

        cv2.putText(
            img,
            f"Extraction: {timing_stats['feature_extraction'] * 1000:.2f} ms",
            (20, y_offset),
            font,
            font_scale,
            (0, 255, 255),
            thickness - 1,
        )

        # 生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = Path(image_path).stem
        output_path = Path(output_dir) / f"{basename}_result_{timestamp}.jpg"

        # 保存图片
        cv2.imwrite(str(output_path), img)
        print(f"  Saved result image: {output_path}")

    def compare_faces(self, feature1, feature2):
        """
        比较两个人脸特征向量的相似度

        Args:
            feature1: 512维特征向量1
            feature2: 512维特征向量2

        Returns:
            tuple: (相似度, 计算时间(ms))
        """
        if feature1 is None or feature2 is None:
            return 0.0, 0.0

        ptr1 = feature1.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr2 = feature2.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        t_start = time.time()
        similarity = lib.FaceEngine_CosineSimilarity(ptr1, ptr2)
        compute_time = (time.time() - t_start) * 1000  # 转换为毫秒

        return float(similarity), compute_time

    def __del__(self):
        """释放资源"""
        if self.engine:
            lib.FaceEngine_Destroy(self.engine)
            print("\n✓ FaceEngine destroyed")


# ========================================
# 主函数
# ========================================


def main():
    parser = argparse.ArgumentParser(description="FaceEngine Python Test Script")
    parser.add_argument(
        "--image", type=str, required=True, help="Input image path (JPEG)"
    )
    parser.add_argument(
        "--image2",
        type=str,
        default=None,
        help="Second image for comparison (optional)",
    )
    parser.add_argument(
        "--retinaface", type=str, default=RETINAFACE_MODEL, help="RetinaFace model path"
    )
    parser.add_argument(
        "--mobilefacenet",
        type=str,
        default=MOBILEFACENET_MODEL,
        help="MobileFaceNet model path",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_DIR,
        help="Output directory for result images",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Disable saving result images",
    )

    args = parser.parse_args()

    # 检查模型文件是否存在
    if not os.path.exists(args.retinaface):
        print(f"✗ Error: RetinaFace model not found: {args.retinaface}")
        return

    if not os.path.exists(args.mobilefacenet):
        print(f"✗ Error: MobileFaceNet model not found: {args.mobilefacenet}")
        return

    # 创建 FaceEngine 实例
    try:
        engine = FaceEngine(args.retinaface, args.mobilefacenet)
    except RuntimeError as e:
        print(f"✗ {e}")
        return

    save_output = not args.no_save

    # 提取第一张图片的特征
    feature1, timing1 = engine.extract_feature(args.image, save_output, args.output)
    if feature1 is None:
        return

    # 如果提供了第二张图片，进行比对
    if args.image2:
        feature2, timing2 = engine.extract_feature(
            args.image2, save_output, args.output
        )
        if feature2 is not None:
            similarity, compare_time = engine.compare_faces(feature1, feature2)

            print(f"\n{'=' * 50}")
            print("Face Comparison Result:")
            print(f"  Image 1: {args.image}")
            print(f"  Image 2: {args.image2}")
            print(f"  Cosine Similarity: {similarity:.4f}")
            print(f"  Comparison Time: {compare_time:.4f} ms")
            print(
                f"  Judgment: {'Same person ✓' if similarity > 0.5 else 'Different person ✗'}"
            )
            print("  (Threshold: 0.5 for strict, 0.3 for general)")
            print(f"{'=' * 50}")

            # 总体性能统计
            if timing1 and timing2:
                print(f"\n📊 Overall Performance Statistics:")
                total_time1 = sum(timing1.values()) * 1000
                total_time2 = sum(timing2.values()) * 1000
                print(f"  Image 1 total time: {total_time1:.2f} ms")
                print(f"  Image 2 total time: {total_time2:.2f} ms")
                print(f"  Comparison time:    {compare_time:.4f} ms")
                print(
                    f"  Grand total:        {total_time1 + total_time2 + compare_time:.2f} ms"
                )
    else:
        # 只提取特征，打印前10个值作为示例
        print("\nFeature vector (first 10 values):")
        print(f"  {feature1[:10]}")

    if save_output:
        print(f"\n💾 Result images saved to: {args.output}/")

    print("\n✓ Test completed successfully!")


if __name__ == "__main__":
    main()
