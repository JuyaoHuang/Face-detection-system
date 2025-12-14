"""
将ONNX模型转换为RKNN模型（用于RK3568开发板）
适用于rknn-toolkit2 v2.3.2

环境要求：
- Python 3.8
- rknn-toolkit2==2.3.2
- 运行环境：Linux (VMware虚拟机)
"""

import os
import sys
from pathlib import Path
import argparse
import numpy as np
import cv2
from rknn.api import RKNN


def load_calibration_data(dataset_path, label_file, max_images=50):
    """
    加载量化校准数据集，并保存为txt格式供RKNN使用

    Args:
        dataset_path: 数据集根目录 (datasets/int_data)
        label_file: 标签文件 (int_data_labels.txt)
        max_images: 最多使用多少张图片进行校准（默认50张）

    Returns:
        dataset_txt_path: 校准数据集路径列表文件（.txt）
    """
    print(f"\n{'='*60}")
    print("准备量化校准数据集")
    print(f"{'='*60}")

    dataset_path = Path(dataset_path)
    label_file = Path(label_file)

    if not label_file.exists():
        print(f"错误: 标签文件不存在 {label_file}")
        print(f"请先运行以下命令创建标签文件：")
        print(f'  grep -E "casia-webface/000696|casia-webface/000697" datasets/int_data/casia-webface.txt > datasets/int_data/int_data_labels.txt')
        return None

    print(f"数据集路径: {dataset_path}")
    print(f"标签文件: {label_file}")

    # 读取标签文件
    with open(label_file, 'r') as f:
        lines = f.readlines()

    total_images = len(lines)
    print(f"标签文件中共有 {total_images} 张图片")

    # 限制校准图片数量
    if max_images > 0 and max_images < total_images:
        lines = lines[:max_images]
        print(f"使用前 {max_images} 张图片进行校准")
    else:
        print(f"使用全部 {total_images} 张图片进行校准")

    # 收集有效图片路径
    valid_image_paths = []

    for i, line in enumerate(lines):
        parts = line.strip().split()
        if len(parts) < 2:
            continue

        # 路径格式：casia-webface/000696/00063125.jpg
        # 需要替换为：datasets/int_data/000696/00063125.jpg
        img_relative_path = parts[1]
        img_path = str(dataset_path / img_relative_path.replace('casia-webface/', ''))

        # 检查图片是否存在
        if not os.path.exists(img_path):
            print(f"警告: 图片不存在 {img_path}")
            continue

        try:
            # 验证图片可读取
            img = cv2.imread(img_path)
            if img is None:
                print(f"警告: 无法读取图像 {img_path}")
                continue

            # 检查尺寸
            if img.shape[0] != 112 or img.shape[1] != 112:
                print(f"警告: 图像尺寸不是112x112: {img.shape}, 路径: {img_path}")
                continue

            # 添加到有效列表（使用绝对路径）
            abs_path = os.path.abspath(img_path)
            valid_image_paths.append(abs_path)

            if (i + 1) % 50 == 0:
                print(f"  已验证: {i + 1}/{len(lines)} 张图片...")

        except Exception as e:
            print(f"警告: 验证图像失败 {img_path}: {e}")
            continue

    if len(valid_image_paths) == 0:
        print("错误: 没有找到有效的校准图片!")
        return None

    print(f"\n找到 {len(valid_image_paths)} 张有效校准图片")

    # 保存为txt文件（RKNN需要）
    dataset_txt_path = 'calibration_dataset.txt'
    with open(dataset_txt_path, 'w') as f:
        for img_path in valid_image_paths:
            f.write(img_path + '\n')

    print(f"校准数据集列表已保存到: {dataset_txt_path}")

    return dataset_txt_path


def convert_onnx_to_rknn(onnx_path, rknn_path, dataset_path, label_file,
                         do_quantization=True, max_calib_images=50):
    """
    将ONNX模型转换为RKNN模型

    Args:
        onnx_path: 输入ONNX模型路径
        rknn_path: 输出RKNN模型路径
        dataset_path: 校准数据集路径
        label_file: 校准数据集标签文件
        do_quantization: 是否进行INT8量化
        max_calib_images: 最多使用多少张图片进行校准
    """
    print(f"\n{'='*60}")
    print("ONNX → RKNN 模型转换工具")
    print(f"{'='*60}")
    print(f"输入模型: {onnx_path}")
    print(f"输出模型: {rknn_path}")
    print(f"目标平台: RK3568")
    print(f"RKNN-Toolkit2 版本: 2.3.2")
    print(f"量化策略: {'INT8量化' if do_quantization else '不量化'}")
    print(f"{'='*60}\n")

    # 初始化变量
    dataset_txt_path = None

    # 创建RKNN对象
    rknn = RKNN(verbose=True)

    # 1. 配置模型
    print("步骤 1/5: 配置RKNN模型参数...")

    # rknn-toolkit2 v2.3.2 使用新的量化类型命名
    # w8a8: 权重8位 + 激活8位 (INT8量化)
    # w8a16: 权重8位 + 激活16位 (混合精度)
    if do_quantization:
        ret = rknn.config(
            target_platform='rk3568',          # 目标平台：RK3568
            quantized_dtype='w8a8',            # INT8量化：权重8位 + 激活8位
            optimization_level=3,              # 优化级别 (0-3)
            output_optimize=True,              # 输出优化（布尔值）
            # 预处理配置：匹配MobileFaceNet的输入要求
            # 输入：RGB图像，[0-255]
            # 归一化：(pixel/255 - 0.5) / 0.5 = (pixel - 127.5) / 127.5
            mean_values=[[127.5, 127.5, 127.5]],  # 均值
            std_values=[[127.5, 127.5, 127.5]],   # 标准差
        )
    else:
        # 不量化时不指定 quantized_dtype
        ret = rknn.config(
            target_platform='rk3568',
            optimization_level=3,
            output_optimize=True,
            mean_values=[[127.5, 127.5, 127.5]],
            std_values=[[127.5, 127.5, 127.5]],
        )

    if ret != 0:
        print('配置RKNN失败!')
        return False
    print('✓ RKNN配置成功')

    # 2. 加载ONNX模型
    print("\n步骤 2/5: 加载ONNX模型...")
    # 指定输入形状（RKNN不支持动态batch_size）
    ret = rknn.load_onnx(
        model=onnx_path,
        inputs=['input'],                    # 输入名称
        input_size_list=[[1, 3, 112, 112]]  # 固定batch_size=1
    )
    if ret != 0:
        print('加载ONNX模型失败!')
        return False
    print('✓ ONNX模型加载成功')

    # 3. 构建模型（包含量化）
    print("\n步骤 3/5: 构建RKNN模型...")

    if do_quantization:
        # 准备量化校准数据集
        print("\n准备量化校准数据集...")
        dataset_txt_path = load_calibration_data(
            dataset_path,
            label_file,
            max_images=max_calib_images
        )

        if dataset_txt_path is None:
            print("错误: 无法准备校准数据集!")
            return False

        print(f"\n开始量化（校准数据集: {dataset_txt_path}）...")
        print("这可能需要几分钟时间，请耐心等待...")

        # 构建模型并量化（传递txt文件路径）
        ret = rknn.build(
            do_quantization=True,
            dataset=dataset_txt_path  # 传递txt文件路径
        )
    else:
        # 不量化
        ret = rknn.build(do_quantization=False)

    if ret != 0:
        print('构建RKNN模型失败!')
        return False
    print('✓ RKNN模型构建成功')

    # 4. 导出RKNN模型
    print(f"\n步骤 4/5: 导出RKNN模型到 {rknn_path}...")
    ret = rknn.export_rknn(rknn_path)
    if ret != 0:
        print('导出RKNN模型失败!')
        return False
    print('✓ RKNN模型导出成功')

    # 5. 精度分析（可选）
    print("\n步骤 5/5: 进行精度分析...")
    try:
        # 尝试初始化运行时（仅在RK3568设备上有效）
        if do_quantization and dataset_txt_path:
            # 读取几张图片进行测试
            with open(dataset_txt_path, 'r') as f:
                test_image_paths = [line.strip() for line in f.readlines()[:5]]

            print("  初始化运行时...")
            ret = rknn.init_runtime()
            if ret == 0:
                print("  运行推理测试...")
                for i, img_path in enumerate(test_image_paths):
                    # 读取图片
                    img = cv2.imread(img_path)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    # 扩展维度到 (1, 112, 112, 3) - 添加 batch 维度
                    img = np.expand_dims(img, axis=0)

                    # 推理（指定数据格式为 NHWC）
                    outputs = rknn.inference(inputs=[img], data_format='nhwc')
                    if outputs:
                        output_shape = outputs[0].shape
                        output_range = [outputs[0].min(), outputs[0].max()]
                        print(f"  测试图片 {i+1}: 输出形状={output_shape}, 范围=[{output_range[0]:.4f}, {output_range[1]:.4f}]")
                print("✓ 推理测试成功")
            else:
                print("⚠ 初始化运行时失败（这在非RK3568设备上是正常的）")
        else:
            print("⚠ 跳过精度分析（未使用量化）")
    except Exception as e:
        print(f"⚠ 精度分析跳过: {e}")

    # 释放资源
    rknn.release()

    # 输出模型信息
    rknn_file = Path(rknn_path)
    if rknn_file.exists():
        file_size_mb = rknn_file.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print("转换完成!")
        print(f"{'='*60}")
        print(f"RKNN模型路径: {rknn_path}")
        print(f"模型大小: {file_size_mb:.2f} MB")
        print(f"\n下一步：将模型部署到RK3568开发板")
        print(f"{'='*60}\n")
        return True
    else:
        print("\n错误: RKNN模型文件未生成")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='将MobileFaceNet ONNX模型转换为RKNN格式（RK3568）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本用法（INT8量化）
  python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn

  # 指定校准数据集
  python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn -d datasets/int_data -l datasets/int_data/int_data_labels.txt

  # 不进行量化（使用FP16）
  python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn --no-quantization

注意事项：
  1. 需要在Linux环境下运行（VMware虚拟机）
  2. 需要安装 rknn-toolkit2==2.3.2
  3. 校准数据集应为112x112的人脸图片（RGB格式）
  4. 量化会导致1-3%的精度损失，但显著提升NPU性能
        """
    )

    parser.add_argument('-i', '--input', type=str, required=True,
                        help='输入ONNX模型路径')
    parser.add_argument('-o', '--output', type=str, required=True,
                        help='输出RKNN模型路径')
    parser.add_argument('-d', '--dataset', type=str,
                        default='datasets/int_data',
                        help='校准数据集路径（默认: datasets/int_data）')
    parser.add_argument('-l', '--labels', type=str,
                        default='datasets/int_data/int_data_labels.txt',
                        help='校准数据集标签文件（默认: datasets/int_data/int_data_labels.txt）')
    parser.add_argument('--max-calib-images', type=int, default=50,
                        help='量化校准使用的最大图片数（默认: 50）')
    parser.add_argument('--no-quantization', action='store_true',
                        help='不进行INT8量化（使用FP16）')

    args = parser.parse_args()

    # 检查输入文件
    if not os.path.exists(args.input):
        print(f"错误: 输入ONNX模型不存在: {args.input}")
        sys.exit(1)

    # 执行转换
    success = convert_onnx_to_rknn(
        onnx_path=args.input,
        rknn_path=args.output,
        dataset_path=args.dataset,
        label_file=args.labels,
        do_quantization=not args.no_quantization,
        max_calib_images=args.max_calib_images
    )

    if success:
        print("\n✓ 转换成功!")
        sys.exit(0)
    else:
        print("\n✗ 转换失败!")
        sys.exit(1)


if __name__ == '__main__':
    main()

    # 示例用法：
    # python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn
