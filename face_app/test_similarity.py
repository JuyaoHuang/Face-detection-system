#!/usr/bin/env python3
"""
批量人脸相似度测试脚本
用于测试同一人的多张照片之间的相似度

Usage:
    python test_similarity.py --images imgs/1.jpg imgs/2.jpg imgs/3.jpg
    或
    python test_similarity.py --dir imgs/ --pattern "*.jpg"
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
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns

# 导入 test_api.py 中的配置和库加载
from test_api import lib, FaceEngine, LIB_PATH, RETINAFACE_MODEL, MOBILEFACENET_MODEL

# ========================================
# 配置
# ========================================
OUTPUT_DIR = "./similarity_test_output"  # 输出目录


def print_header(text):
    """打印标题"""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print('=' * 70)


def extract_all_features(engine, image_paths):
    """
    批量提取特征向量

    Args:
        engine: FaceEngine 实例
        image_paths: 图片路径列表

    Returns:
        dict: {image_path: (feature, timing_stats)}
    """
    print_header("步骤 1: 提取特征向量")

    results = {}
    all_timings = []

    for i, image_path in enumerate(image_paths, 1):
        print(f"\n[{i}/{len(image_paths)}] Processing: {image_path}")

        feature, timing = engine.extract_feature(
            image_path,
            save_output=False  # 暂不保存单张结果
        )

        if feature is not None:
            results[image_path] = (feature, timing)
            all_timings.append(sum(timing.values()) * 1000)
            print(f"  ✓ Success")
        else:
            print(f"  ✗ Failed to extract feature")
            results[image_path] = (None, None)

    # 统计信息
    if all_timings:
        print(f"\n📊 Extraction Statistics:")
        print(f"  Success rate:  {len(all_timings)}/{len(image_paths)}")
        print(f"  Avg time:      {np.mean(all_timings):.2f} ms")
        print(f"  Min time:      {np.min(all_timings):.2f} ms")
        print(f"  Max time:      {np.max(all_timings):.2f} ms")

    return results


def compute_similarity_matrix(engine, results):
    """
    计算相似度矩阵

    Args:
        engine: FaceEngine 实例
        results: extract_all_features 返回的结果

    Returns:
        tuple: (similarity_matrix, image_names, comparison_times)
    """
    print_header("步骤 2: 计算相似度矩阵")

    # 过滤出成功提取特征的图片
    valid_results = {k: v for k, v in results.items() if v[0] is not None}
    image_paths = list(valid_results.keys())
    n = len(image_paths)

    if n < 2:
        print("✗ Error: Need at least 2 valid images for comparison")
        return None, None, None

    # 初始化相似度矩阵
    similarity_matrix = np.zeros((n, n))
    comparison_times = []

    print(f"\nComputing {n}x{n} similarity matrix...")

    # 计算两两相似度
    for i in range(n):
        for j in range(n):
            if i == j:
                similarity_matrix[i][j] = 1.0  # 自己和自己相似度为1
            elif i < j:  # 只计算上三角
                feature_i = valid_results[image_paths[i]][0]
                feature_j = valid_results[image_paths[j]][0]

                similarity, comp_time = engine.compare_faces(feature_i, feature_j)
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity  # 对称矩阵

                comparison_times.append(comp_time)

                print(f"  {Path(image_paths[i]).name} vs {Path(image_paths[j]).name}: "
                      f"{similarity:.4f} ({comp_time:.4f} ms)")

    # 提取图片名称
    image_names = [Path(p).name for p in image_paths]

    print(f"\n📊 Comparison Statistics:")
    print(f"  Total comparisons: {len(comparison_times)}")
    print(f"  Avg time:          {np.mean(comparison_times):.4f} ms")

    return similarity_matrix, image_names, comparison_times


def visualize_similarity_matrix(similarity_matrix, image_names, output_dir):
    """
    可视化相似度矩阵（热力图）

    Args:
        similarity_matrix: n×n 相似度矩阵
        image_names: 图片名称列表
        output_dir: 输出目录
    """
    print_header("步骤 3: 生成可视化结果")

    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 绘制热力图
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        similarity_matrix,
        annot=True,  # 显示数值
        fmt='.4f',  # 格式化为4位小数
        cmap='RdYlGn',  # 红-黄-绿配色（低-中-高）
        xticklabels=image_names,
        yticklabels=image_names,
        vmin=0,
        vmax=1,
        cbar_kws={'label': 'Cosine Similarity'}
    )
    plt.title('Face Similarity Matrix', fontsize=16, fontweight='bold')
    plt.xlabel('Image', fontsize=12)
    plt.ylabel('Image', fontsize=12)
    plt.tight_layout()

    # 保存热力图
    heatmap_path = Path(output_dir) / f"similarity_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(heatmap_path, dpi=150)
    plt.close()

    print(f"  ✓ Heatmap saved: {heatmap_path}")

    return heatmap_path


def generate_report(similarity_matrix, image_names, results, comparison_times, output_dir, threshold=0.5):
    """
    生成详细的测试报告

    Args:
        similarity_matrix: 相似度矩阵
        image_names: 图片名称列表
        results: 特征提取结果
        comparison_times: 比对耗时列表
        output_dir: 输出目录
        threshold: 相似度阈值
    """
    print_header("步骤 4: 生成测试报告")

    # 创建报告文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = Path(output_dir) / f"similarity_report_{timestamp}.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        # 标题
        f.write("=" * 70 + "\n")
        f.write("           Face Similarity Test Report\n")
        f.write("=" * 70 + "\n")
        f.write(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Threshold: {threshold}\n")
        f.write("\n")

        # 1. 测试图片列表
        f.write("-" * 70 + "\n")
        f.write("1. Test Images\n")
        f.write("-" * 70 + "\n")
        valid_results = {k: v for k, v in results.items() if v[0] is not None}
        for i, (path, (feature, timing)) in enumerate(valid_results.items(), 1):
            f.write(f"[{i}] {path}\n")
            f.write(f"    Feature Norm: {np.linalg.norm(feature):.4f}\n")
            f.write(f"    Extraction Time: {sum(timing.values())*1000:.2f} ms\n")
        f.write("\n")

        # 2. 相似度矩阵
        f.write("-" * 70 + "\n")
        f.write("2. Similarity Matrix\n")
        f.write("-" * 70 + "\n")
        f.write("     ")
        for name in image_names:
            f.write(f"{name:>12} ")
        f.write("\n")

        for i, name in enumerate(image_names):
            f.write(f"{name:<12} ")
            for j in range(len(image_names)):
                f.write(f"{similarity_matrix[i][j]:>12.4f} ")
            f.write("\n")
        f.write("\n")

        # 3. 详细对比结果
        f.write("-" * 70 + "\n")
        f.write("3. Pairwise Comparison Details\n")
        f.write("-" * 70 + "\n")
        n = len(image_names)
        pair_index = 0
        for i in range(n):
            for j in range(i + 1, n):
                similarity = similarity_matrix[i][j]
                comp_time = comparison_times[pair_index]
                pair_index += 1

                match = "✓ MATCH" if similarity >= threshold else "✗ NO MATCH"
                f.write(f"{image_names[i]} vs {image_names[j]}:\n")
                f.write(f"  Similarity: {similarity:.4f}\n")
                f.write(f"  Time:       {comp_time:.4f} ms\n")
                f.write(f"  Result:     {match}\n")
                f.write("\n")

        # 4. 统计分析
        f.write("-" * 70 + "\n")
        f.write("4. Statistical Analysis\n")
        f.write("-" * 70 + "\n")

        # 提取非对角线元素（实际比对结果）
        n = similarity_matrix.shape[0]
        similarities = []
        for i in range(n):
            for j in range(i + 1, n):
                similarities.append(similarity_matrix[i][j])

        f.write(f"Total Comparisons: {len(similarities)}\n")
        f.write(f"Similarity Statistics:\n")
        f.write(f"  Mean:   {np.mean(similarities):.4f}\n")
        f.write(f"  Median: {np.median(similarities):.4f}\n")
        f.write(f"  Std:    {np.std(similarities):.4f}\n")
        f.write(f"  Min:    {np.min(similarities):.4f}\n")
        f.write(f"  Max:    {np.max(similarities):.4f}\n")
        f.write("\n")

        # 基于阈值的判断
        matches = sum(1 for s in similarities if s >= threshold)
        f.write(f"Threshold Analysis (threshold={threshold}):\n")
        f.write(f"  Matches:     {matches}/{len(similarities)} ({matches/len(similarities)*100:.1f}%)\n")
        f.write(f"  No Matches:  {len(similarities)-matches}/{len(similarities)} ({(len(similarities)-matches)/len(similarities)*100:.1f}%)\n")
        f.write("\n")

        # 5. 性能数据
        f.write("-" * 70 + "\n")
        f.write("5. Performance Metrics\n")
        f.write("-" * 70 + "\n")

        extraction_times = [sum(v[1].values())*1000 for v in valid_results.values()]
        f.write(f"Feature Extraction:\n")
        f.write(f"  Avg Time: {np.mean(extraction_times):.2f} ms\n")
        f.write(f"  Min Time: {np.min(extraction_times):.2f} ms\n")
        f.write(f"  Max Time: {np.max(extraction_times):.2f} ms\n")
        f.write("\n")

        f.write(f"Similarity Comparison:\n")
        f.write(f"  Avg Time: {np.mean(comparison_times):.4f} ms\n")
        f.write(f"  Min Time: {np.min(comparison_times):.4f} ms\n")
        f.write(f"  Max Time: {np.max(comparison_times):.4f} ms\n")
        f.write("\n")

        # 6. 结论
        f.write("-" * 70 + "\n")
        f.write("6. Conclusions\n")
        f.write("-" * 70 + "\n")

        if len(similarities) > 0:
            avg_sim = np.mean(similarities)
            if avg_sim >= 0.7:
                f.write("✓ EXCELLENT: All images show very high similarity.\n")
                f.write("  This indicates they are very likely the same person.\n")
            elif avg_sim >= 0.6:
                f.write("✓ GOOD: Images show high similarity.\n")
                f.write("  They are likely the same person.\n")
            elif avg_sim >= 0.5:
                f.write("⚠ MODERATE: Images show moderate similarity.\n")
                f.write("  May need manual review or better quality images.\n")
            else:
                f.write("✗ LOW: Images show low similarity.\n")
                f.write("  They may not be the same person, or image quality is poor.\n")
        f.write("\n")

        f.write("=" * 70 + "\n")
        f.write("End of Report\n")
        f.write("=" * 70 + "\n")

    print(f"  ✓ Report saved: {report_path}")

    # 同时打印到屏幕
    print(f"\n📊 Quick Summary:")
    print(f"  Images tested:     {len(image_names)}")
    print(f"  Total comparisons: {len(similarities)}")
    print(f"  Avg similarity:    {np.mean(similarities):.4f}")
    print(f"  Matches (≥{threshold}):   {matches}/{len(similarities)}")

    return report_path


def save_annotated_images(results, output_dir):
    """
    保存带注释的图片

    Args:
        results: 特征提取结果
        output_dir: 输出目录
    """
    print_header("步骤 5: 保存带注释的图片")

    annotated_dir = Path(output_dir) / "annotated_images"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    for image_path, (feature, timing) in results.items():
        if feature is None:
            continue

        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            print(f"  ✗ Cannot read: {image_path}")
            continue

        h, w = img.shape[:2]

        # 添加半透明背景
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (w - 10, 150), (0, 0, 0), -1)
        img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)

        # 添加文本信息
        font = cv2.FONT_HERSHEY_SIMPLEX
        y_offset = 35

        cv2.putText(img, Path(image_path).name, (20, y_offset),
                    font, 0.7, (255, 255, 255), 2)
        y_offset += 30

        cv2.putText(img, f"Feature Dim: 512", (20, y_offset),
                    font, 0.5, (0, 255, 0), 1)
        y_offset += 25

        cv2.putText(img, f"Norm: {np.linalg.norm(feature):.4f}", (20, y_offset),
                    font, 0.5, (0, 255, 0), 1)
        y_offset += 25

        total_time = sum(timing.values())
        cv2.putText(img, f"Time: {total_time*1000:.2f} ms", (20, y_offset),
                    font, 0.5, (0, 255, 255), 1)

        # 保存
        output_path = annotated_dir / Path(image_path).name
        cv2.imwrite(str(output_path), img)
        print(f"  ✓ Saved: {output_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Batch Face Similarity Test Script")
    parser.add_argument(
        "--images",
        type=str,
        nargs='+',
        default=None,
        help="List of image paths"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="imgs",
        help="Directory containing images (default: imgs)"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="[1-3].jpg",
        help="Filename pattern (default: [1-3].jpg)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Similarity threshold (default: 0.5)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_DIR,
        help="Output directory"
    )
    parser.add_argument(
        "--retinaface",
        type=str,
        default=RETINAFACE_MODEL,
        help="RetinaFace model path"
    )
    parser.add_argument(
        "--mobilefacenet",
        type=str,
        default=MOBILEFACENET_MODEL,
        help="MobileFaceNet model path"
    )

    args = parser.parse_args()

    print_header("Face Similarity Batch Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {args.output}")
    print(f"Threshold: {args.threshold}")

    # 获取图片列表
    if args.images:
        image_paths = args.images
    else:
        # 从目录读取
        image_dir = Path(args.dir)
        if not image_dir.exists():
            print(f"✗ Error: Directory not found: {image_dir}")
            return

        import glob
        pattern_path = str(image_dir / args.pattern)
        image_paths = glob.glob(pattern_path)

        if not image_paths:
            print(f"✗ Error: No images found matching pattern: {pattern_path}")
            return

    image_paths.sort()
    print(f"\nFound {len(image_paths)} images:")
    for i, path in enumerate(image_paths, 1):
        print(f"  [{i}] {path}")

    if len(image_paths) < 2:
        print("\n✗ Error: Need at least 2 images for comparison")
        return

    # 检查模型文件
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

    # 步骤 1: 提取所有特征
    results = extract_all_features(engine, image_paths)

    # 步骤 2: 计算相似度矩阵
    similarity_matrix, image_names, comparison_times = compute_similarity_matrix(engine, results)

    if similarity_matrix is None:
        print("\n✗ Test failed: Not enough valid images")
        return

    # 步骤 3: 可视化相似度矩阵
    heatmap_path = visualize_similarity_matrix(similarity_matrix, image_names, args.output)

    # 步骤 4: 生成详细报告
    report_path = generate_report(
        similarity_matrix,
        image_names,
        results,
        comparison_times,
        args.output,
        args.threshold
    )

    # 步骤 5: 保存带注释的图片
    save_annotated_images(results, args.output)

    # 完成
    print_header("Test Completed Successfully")
    print(f"\n📁 Output files:")
    print(f"  - Heatmap:  {heatmap_path}")
    print(f"  - Report:   {report_path}")
    print(f"  - Annotated images: {args.output}/annotated_images/")
    print(f"\n✓ All done!\n")


if __name__ == "__main__":
    main()
