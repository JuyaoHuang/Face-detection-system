"""
数据集检测脚本
检查casia-webface数据集的图片格式是否适合MobileFaceNet输入
"""

import os
import sys
from PIL import Image
from collections import defaultdict
import numpy as np

# 设置标准输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_dataset(label_file, dataset_root, sample_size=100):
    """
    检查数据集图片格式

    Args:
        label_file: 标签文件路径
        dataset_root: 数据集根目录
        sample_size: 采样检查的图片数量（0表示全部检查）
    """
    print("=" * 60)
    print("CASIA-WebFace 数据集格式检查")
    print("=" * 60)

    # 读取标签文件
    print(f"\n正在读取标签文件: {label_file}")
    with open(label_file, 'r') as f:
        lines = f.readlines()

    total_images = len(lines)
    print(f"标签文件中共有 {total_images} 条记录")

    # 采样或全部检查
    if sample_size > 0 and sample_size < total_images:
        import random
        sample_lines = random.sample(lines, sample_size)
        print(f"将随机采样 {sample_size} 张图片进行检查")
    else:
        sample_lines = lines
        print(f"将检查全部 {total_images} 张图片")

    # 统计信息
    size_counter = defaultdict(int)
    format_counter = defaultdict(int)
    valid_images = 0
    invalid_images = []

    print("\n开始检查图片...")
    for i, line in enumerate(sample_lines):
        parts = line.strip().split()
        if len(parts) < 2:
            continue

        img_path = os.path.join(dataset_root, parts[1])

        try:
            with Image.open(img_path) as img:
                # 检查尺寸
                size = img.size
                size_counter[size] += 1

                # 检查格式
                format_counter[img.format] += 1

                valid_images += 1

        except Exception as e:
            invalid_images.append((img_path, str(e)))

        # 进度显示
        if (i + 1) % 1000 == 0:
            print(f"  已检查: {i + 1}/{len(sample_lines)} 张图片...")

    print(f"\n检查完成! 有效图片: {valid_images}/{len(sample_lines)}")

    # 输出统计结果
    print("\n" + "=" * 60)
    print("图片尺寸分布:")
    print("=" * 60)
    sorted_sizes = sorted(size_counter.items(), key=lambda x: x[1], reverse=True)
    for size, count in sorted_sizes[:10]:  # 显示前10种最常见的尺寸
        percentage = (count / valid_images) * 100
        print(f"  {size[0]}x{size[1]}: {count} 张 ({percentage:.2f}%)")

    if len(sorted_sizes) > 10:
        print(f"  ... 还有 {len(sorted_sizes) - 10} 种其他尺寸")

    print("\n" + "=" * 60)
    print("图片格式分布:")
    print("=" * 60)
    for fmt, count in format_counter.items():
        percentage = (count / valid_images) * 100
        print(f"  {fmt}: {count} 张 ({percentage:.2f}%)")

    # MobileFaceNet输入要求检查
    print("\n" + "=" * 60)
    print("MobileFaceNet 输入要求检查:")
    print("=" * 60)
    print(f"  要求输入尺寸: 112x112")

    target_size = (112, 112)
    matching_images = size_counter.get(target_size, 0)
    if matching_images > 0:
        percentage = (matching_images / valid_images) * 100
        print(f"  ✓ 符合尺寸的图片: {matching_images} 张 ({percentage:.2f}%)")
    else:
        print(f"  ✗ 没有图片符合112x112尺寸要求")

    # 给出建议
    print("\n" + "=" * 60)
    print("建议:")
    print("=" * 60)

    if matching_images == valid_images:
        print("  ✓ 所有图片均符合MobileFaceNet输入要求，可以直接使用!")
    elif matching_images > 0:
        print(f"  ⚠ 只有部分图片符合要求，建议对数据集进行预处理")
        print(f"  ⚠ 需要调整 {valid_images - matching_images} 张图片的尺寸")
    else:
        print("  ⚠ 数据集需要预处理，建议:")
        print("      1. 使用MTCNN或其他人脸检测器裁剪人脸区域")
        print("      2. 将所有图片resize到112x112")
        print("      3. 或者使用项目中的data_pipe.py自动处理")

        # 检查是否有预处理好的数据集
        fixed_dataset = os.path.join(os.path.dirname(dataset_root), "casia_webface_fixed_112x112")
        if os.path.exists(fixed_dataset):
            print(f"\n  ℹ 发现已处理的数据集: {fixed_dataset}")
            print(f"     建议使用该数据集进行训练")

    # 显示无效图片
    if invalid_images:
        print("\n" + "=" * 60)
        print("无效图片列表:")
        print("=" * 60)
        for img_path, error in invalid_images[:10]:  # 只显示前10个
            print(f"  {img_path}: {error}")
        if len(invalid_images) > 10:
            print(f"  ... 还有 {len(invalid_images) - 10} 张无效图片")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    # 配置路径
    project_root = os.path.dirname(os.path.abspath(__file__))
    label_file = os.path.join(project_root, "datasets", "casia-webface.txt")
    dataset_root = os.path.join(project_root, "datasets")

    # 检查原始数据集
    print("\n>>> 检查原始数据集: casia-webface")
    check_dataset(label_file, dataset_root, sample_size=0)

    # 检查预处理后的数据集（如果存在）
    fixed_dataset = os.path.join(project_root, "datasets", "casia_webface_fixed_112x112")
    if os.path.exists(fixed_dataset):
        print("\n\n>>> 检查预处理后的数据集: casia_webface_fixed_112x112")
        # 为预处理数据集生成标签路径
        fixed_label = label_file  # 使用相同的标签文件，但路径需要调整

        # 读取并修改标签文件路径
        with open(label_file, 'r') as f:
            lines = f.readlines()

        # 采样检查
        import random
        sample_lines = random.sample(lines, min(1000, len(lines)))

        print(f"检查预处理数据集的 {len(sample_lines)} 个样本...")
        size_counter = defaultdict(int)
        valid = 0

        for line in sample_lines:
            parts = line.strip().split()
            if len(parts) < 2:
                continue

            # 替换路径
            img_path = parts[1].replace("casia-webface", "casia_webface_fixed_112x112")
            img_path = os.path.join(project_root, "datasets", img_path)

            try:
                with Image.open(img_path) as img:
                    size_counter[img.size] += 1
                    valid += 1
            except:
                pass

        print(f"\n预处理数据集统计:")
        for size, count in size_counter.items():
            percentage = (count / valid) * 100 if valid > 0 else 0
            print(f"  {size[0]}x{size[1]}: {count} 张 ({percentage:.2f}%)")

        if (112, 112) in size_counter and size_counter[(112, 112)] == valid:
            print("\n  ✓ 预处理数据集所有图片均为112x112，可以直接用于训练!")
