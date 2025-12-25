#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OV5695 摄像头测试脚本

功能：
1. 检测摄像头设备是否存在
2. 测试多种打开方式（OpenCV、GStreamer）
3. 捕获测试图像并保存
4. 验证图像质量和格式
5. 生成详细测试报告

使用方法：
    python test_camera.py
    或
    python test_camera.py --index 0 --width 640 --height 480
"""

import os
import sys
import cv2
import argparse
import datetime
from pathlib import Path

# 添加 backend 到路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def print_section(title):
    """打印章节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name, success, message=""):
    """打印测试结果"""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"[{status}] {test_name}")
    if message:
        print(f"      {message}")


def check_video_devices():
    """检查可用的 video 设备"""
    print_section("1. 检查 Video 设备")

    devices = []

    # Linux 系统
    if sys.platform.startswith("linux"):
        video_devices = list(Path("/dev").glob("video*"))
        video_devices.sort()

        if not video_devices:
            print_result("Video 设备检测", False, "未找到任何 /dev/video* 设备")
            return devices

        print(f"找到 {len(video_devices)} 个 video 设备：")
        for device in video_devices:
            device_path = str(device)

            # 跳过符号链接和非数字设备（如 video-camera0）
            device_name = device.name.replace("video", "")
            if not device_name.isdigit():
                print(f"  {device_path}: 跳过（符号链接或非标准设备）")
                continue

            device_index = int(device_name)

            # 尝试获取设备信息
            try:
                # 使用 v4l2-ctl 获取设备信息（如果可用）
                import subprocess

                result = subprocess.run(
                    ["v4l2-ctl", "-d", device_path, "--info"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    # 提取设备名称
                    for line in result.stdout.split("\n"):
                        if "Card type" in line or "Driver name" in line:
                            print(f"  {device_path}: {line.strip()}")
                else:
                    print(f"  {device_path}: (无法获取详细信息)")
                devices.append(device_index)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                print(f"  {device_path}: 存在")
                devices.append(device_index)

    # Windows 系统
    elif sys.platform == "win32":
        print("Windows 系统：尝试枚举摄像头索引...")
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"  索引 {i}: 可用")
                devices.append(i)
                cap.release()
            else:
                break

    if devices:
        print_result("Video 设备检测", True, f"找到 {len(devices)} 个设备")
    else:
        print_result("Video 设备检测", False, "未找到可用设备")

    return devices


def test_opencv_capture(index, width, height, output_dir):
    """测试 OpenCV 标准模式捕获"""
    print_section(f"2. 测试 OpenCV 模式 (索引 {index})")

    try:
        # 打开摄像头
        print(f"正在打开摄像头 (索引 {index})...")
        cap = cv2.VideoCapture(index)

        if not cap.isOpened():
            print_result("OpenCV 打开摄像头", False, "无法打开摄像头")
            return False

        print_result("OpenCV 打开摄像头", True)

        # 设置分辨率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # 获取实际分辨率
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        print(f"请求分辨率: {width}x{height}")
        print(f"实际分辨率: {actual_width}x{actual_height}")
        print(f"帧率: {fps:.1f} FPS")

        # 预热摄像头（跳过前几帧）
        print("预热摄像头...")
        for _ in range(5):
            cap.read()

        # 捕获图像
        print("捕获测试图像...")
        ret, frame = cap.read()

        if not ret or frame is None:
            print_result("捕获图像", False, "无法读取帧")
            cap.release()
            return False

        print_result("捕获图像", True, f"图像尺寸: {frame.shape[1]}x{frame.shape[0]}")

        # 验证图像质量
        mean_brightness = frame.mean()
        print(f"图像平均亮度: {mean_brightness:.2f}")

        if mean_brightness < 10:
            print_result("图像质量检查", False, "图像过暗，可能是摄像头故障")
        elif mean_brightness > 245:
            print_result("图像质量检查", False, "图像过亮，可能是曝光问题")
        else:
            print_result("图像质量检查", True, "亮度正常")

        # 保存图像
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"opencv_test_{timestamp}_{actual_width}x{actual_height}.jpg"
        filepath = output_dir / filename

        cv2.imwrite(str(filepath), frame)
        print_result("保存图像", True, f"文件: {filename}")

        # 释放摄像头
        cap.release()

        return True

    except Exception as e:
        print_result("OpenCV 测试", False, f"异常: {e}")
        return False


def test_gstreamer_capture(index, width, height, output_dir):
    """测试 GStreamer 硬件加速模式"""
    print_section(f"3. 测试 GStreamer 模式 (索引 {index})")

    # GStreamer 管道
    gst_pipeline = (
        f"rkisp device=/dev/video{index} io-mode=1 ! "
        f"video/x-raw,format=NV12,width={width},height={height},framerate=30/1 ! "
        f"videoconvert ! "
        f"video/x-raw,format=BGR ! appsink"
    )

    print("GStreamer 管道:")
    print(f"  {gst_pipeline}")

    try:
        # 打开摄像头
        print("正在打开摄像头 (GStreamer)...")
        cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

        if not cap.isOpened():
            print_result(
                "GStreamer 打开摄像头",
                False,
                "无法打开（可能系统不支持 GStreamer 或 rkisp）",
            )
            return False

        print_result("GStreamer 打开摄像头", True)

        # 预热
        print("预热摄像头...")
        for _ in range(10):
            cap.read()

        # 捕获图像
        print("捕获测试图像...")
        ret, frame = cap.read()

        if not ret or frame is None:
            print_result("捕获图像", False, "无法读取帧")
            cap.release()
            return False

        print_result("捕获图像", True, f"图像尺寸: {frame.shape[1]}x{frame.shape[0]}")

        # 保存图像
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gstreamer_test_{timestamp}_{width}x{height}.jpg"
        filepath = output_dir / filename

        cv2.imwrite(str(filepath), frame)
        print_result("保存图像", True, f"文件: {filename}")

        # 释放摄像头
        cap.release()

        return True

    except Exception as e:
        print_result("GStreamer 测试", False, f"异常: {e}")
        return False


def test_continuous_capture(index, width, height, output_dir, duration=5):
    """测试连续捕获（性能测试）"""
    print_section(f"4. 性能测试 - 连续捕获 {duration} 秒")

    try:
        cap = cv2.VideoCapture(index)

        if not cap.isOpened():
            print_result("性能测试", False, "无法打开摄像头")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # 预热
        for _ in range(5):
            cap.read()

        # 连续捕获
        print(f"连续捕获 {duration} 秒...")
        import time

        start_time = time.time()
        frame_count = 0

        while time.time() - start_time < duration:
            ret, frame = cap.read()
            if ret:
                frame_count += 1

        elapsed = time.time() - start_time
        fps = frame_count / elapsed

        print(f"捕获帧数: {frame_count}")
        print(f"实际 FPS: {fps:.2f}")

        if fps < 10:
            print_result("性能测试", False, f"FPS 过低 ({fps:.2f})")
        elif fps < 20:
            print_result("性能测试", True, f"FPS 正常 ({fps:.2f})，但有优化空间")
        else:
            print_result("性能测试", True, f"FPS 良好 ({fps:.2f})")

        # 保存最后一帧
        if frame is not None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"continuous_test_{timestamp}_{width}x{height}.jpg"
            filepath = output_dir / filename
            cv2.imwrite(str(filepath), frame)
            print(f"保存最后一帧: {filename}")

        cap.release()
        return True

    except Exception as e:
        print_result("性能测试", False, f"异常: {e}")
        return False


def main():
    """主函数"""
    # 参数解析
    parser = argparse.ArgumentParser(description="OV5695 摄像头测试脚本")
    parser.add_argument(
        "--index", type=int, default=None, help="摄像头索引 (默认: 自动检测)"
    )
    parser.add_argument("--width", type=int, default=640, help="图像宽度 (默认: 640)")
    parser.add_argument("--height", type=int, default=480, help="图像高度 (默认: 480)")
    parser.add_argument(
        "--output", type=str, default=None, help="输出目录 (默认: ./camera_test_output)"
    )
    parser.add_argument(
        "--skip-gstreamer", action="store_true", help="跳过 GStreamer 测试"
    )
    parser.add_argument("--skip-performance", action="store_true", help="跳过性能测试")

    args = parser.parse_args()

    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = PROJECT_ROOT / "camera_test_output"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 打印测试配置
    print_section("OV5695 摄像头测试")
    print(f"测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标分辨率: {args.width}x{args.height}")
    print(f"输出目录: {output_dir}")

    # 1. 检查设备
    devices = check_video_devices()

    if not devices:
        print("\n" + "=" * 60)
        print("✗ 测试失败：未找到摄像头设备")
        print("=" * 60)
        return 1

    # 确定测试索引
    if args.index is not None:
        test_index = args.index
    else:
        # 使用第一个可用设备
        test_index = devices[0]
        print(f"\n自动选择设备索引: {test_index}")

    # 2. OpenCV 测试
    opencv_success = test_opencv_capture(
        test_index, args.width, args.height, output_dir
    )

    # 3. GStreamer 测试（可选）
    gstreamer_success = False
    if not args.skip_gstreamer and sys.platform.startswith("linux"):
        gstreamer_success = test_gstreamer_capture(
            test_index, args.width, args.height, output_dir
        )
    else:
        print_section("3. GStreamer 测试")
        print("跳过 GStreamer 测试")

    # 4. 性能测试（可选）
    performance_success = False
    if not args.skip_performance:
        performance_success = test_continuous_capture(
            test_index, args.width, args.height, output_dir
        )
    else:
        print_section("4. 性能测试")
        print("跳过性能测试")

    # 测试总结
    print_section("测试总结")
    print(f"Video 设备检测:   {'✓' if devices else '✗'}")
    print(f"OpenCV 模式:      {'✓' if opencv_success else '✗'}")
    print(
        f"GStreamer 模式:   {'✓' if gstreamer_success else '⊘' if args.skip_gstreamer else '✗'}"
    )
    print(
        f"性能测试:         {'✓' if performance_success else '⊘' if args.skip_performance else '✗'}"
    )

    # 查看保存的图像
    saved_images = list(output_dir.glob("*.jpg"))
    print(f"\n保存的测试图像 ({len(saved_images)} 张):")
    for img in sorted(saved_images):
        file_size = img.stat().st_size / 1024  # KB
        print(f"  {img.name} ({file_size:.1f} KB)")

    # 建议
    print_section("建议")
    if opencv_success:
        print("✓ OpenCV 模式工作正常，建议使用此模式")
        print("  配置: CAMERA_MODE = 'opencv' 或 'auto'")

    if gstreamer_success:
        print("✓ GStreamer 模式工作正常，性能更好（推荐）")
        print("  配置: CAMERA_MODE = 'gstreamer'")

    if not opencv_success and not gstreamer_success:
        print("✗ 摄像头测试失败，请检查：")
        print("  1. 摄像头是否正确连接到 CSI 接口")
        print("  2. 驱动程序是否正确加载")
        print("  3. 设备文件权限是否正确")
        print("  4. 运行 'ls -l /dev/video*' 查看设备")

    print("\n" + "=" * 60)

    return 0 if opencv_success else 1


if __name__ == "__main__":
    sys.exit(main())
    # 功能特性
    #
    # 1. ✅ 自动检测 video 设备 - 扫描 /dev/video* 设备
    # 2. ✅ OpenCV 模式测试 - 标准 V4L2 捕获
    # 3. ✅ GStreamer 模式测试 - RK3568 硬件加速（rkisp）
    # 4. ✅ 性能测试 - 连续捕获 5 秒测量实际 FPS
    # 5. ✅ 图像质量检查 - 验证亮度、尺寸
    # 6. ✅ 标准化命名 - opencv_test_20231219_143025_640x480.jpg
    # 7. ✅ 详细测试报告 - 清晰的成功/失败状态
    #
    # 使用方法
    #
    # 在 RK3568 上运行（推荐）
    #
    # # 1. 上传脚本到开发板
    # scp backend/scripts/test_camera.py root@<RK3568_IP>:/tmp/
    #
    # # 2. SSH 连接并运行
    # ssh root@<RK3568_IP>
    # cd /tmp
    # python3 test_camera.py
    #
    # 在 PC 上运行（开发模式）
    #
    # # 进入项目目录
    # cd backend
    #
    # # 基础测试（自动检测摄像头）
    # python scripts/test_camera.py
    #
    # # 指定摄像头索引和分辨率
    # python scripts/test_camera.py --index 0 --width 1280 --height 720
    #
    # # 跳过 GStreamer 测试（PC 上不支持）
    # python scripts/test_camera.py --skip-gstreamer
    #
    # # 完整命令示例
    # python scripts/test_camera.py \
    #     --index 0 \
    #     --width 640 \
    #     --height 480 \
    #     --output /tmp/camera_test \
    #     --skip-gstreamer
    #
    # 命令行参数
    #
    # | 参数               | 说明                | 默认值               |
    # |--------------------|---------------------|----------------------|
    # | --index            | 摄像头索引          | 自动检测             |
    # | --width            | 图像宽度            | 640                  |
    # | --height           | 图像高度            | 480                  |
    # | --output           | 输出目录            | ./camera_test_output |
    # | --skip-gstreamer   | 跳过 GStreamer 测试 | False                |
    # | --skip-performance | 跳过性能测试        | False                |
    #
    # 输出示例
    #
    # ============================================================
    #   OV5695 摄像头测试
    # ============================================================
    # 测试时间: 2025-12-19 14:30:25
    # 目标分辨率: 640x480
    # 输出目录: camera_test_output
    #
    # ============================================================
    #   1. 检查 Video 设备
    # ============================================================
    # 找到 3 个 video 设备：
    #   /dev/video0: Card type: rkisp
    #   /dev/video1: Card type: ov5695
    #   /dev/video11: 存在
    # [✓ PASS] Video 设备检测
    #       找到 3 个设备
    #
    # ============================================================
    #   2. 测试 OpenCV 模式 (索引 0)
    # ============================================================
    # 正在打开摄像头 (索引 0)...
    # [✓ PASS] OpenCV 打开摄像头
    # 请求分辨率: 640x480
    # 实际分辨率: 640x480
    # 帧率: 30.0 FPS
    # 预热摄像头...
    # 捕获测试图像...
    # [✓ PASS] 捕获图像
    #       图像尺寸: 640x480
    # 图像平均亮度: 128.45
    # [✓ PASS] 图像质量检查
    #       亮度正常
    # [✓ PASS] 保存图像
    #       文件: opencv_test_20251219_143025_640x480.jpg
    #
    # ============================================================
    #   测试总结
    # ============================================================
    # Video 设备检测:   ✓
    # OpenCV 模式:      ✓
    # GStreamer 模式:   ✓
    # 性能测试:         ✓
    #
    # 保存的测试图像 (3 张):
    #   continuous_test_20251219_143032_640x480.jpg (45.2 KB)
    #   gstreamer_test_20251219_143028_640x480.jpg (42.8 KB)
    #   opencv_test_20251219_143025_640x480.jpg (43.5 KB)
    #
    # ============================================================
    #   建议
    # ============================================================
    # ✓ GStreamer 模式工作正常，性能更好（推荐）
    #   配置: CAMERA_MODE = 'gstreamer'
    #
    # 图像命名格式
    #
    # 脚本生成的图像命名格式：
    # <模式>_test_<日期>_<时间>_<宽>x<高>.jpg
    #
    # 示例：
    # opencv_test_20251219_143025_640x480.jpg
    # gstreamer_test_20251219_143028_640x480.jpg
    # continuous_test_20251219_143032_1280x720.jpg
    #
    # 故障排查
    #
    # 问题 1: 未找到 video 设备
    # # 检查设备
    # ls -l /dev/video*
    #
    # # 检查内核模块
    # lsmod | grep ov5695
    # lsmod | grep rkisp
    #
    # # 重新加载驱动
    # sudo modprobe ov5695
    #
    # 问题 2: OpenCV 无法打开摄像头
    # # 检查权限
    # sudo chmod 666 /dev/video*
    #
    # # 或添加用户到 video 组
    # sudo usermod -a -G video $USER
    #
    # 问题 3: GStreamer 测试失败
    # # 安装 GStreamer 插件
    # sudo apt-get install gstreamer1.0-plugins-bad gstreamer1.0-rockchip
    #
    # # 检查 rkisp 是否可用
    # gst-inspect-1.0 rkisp
    #
    # 下一步
    #
    # 运行测试后，请告诉我：
    # 1. 哪个模式测试成功（OpenCV / GStreamer）
    # 2. 实际 FPS 是多少
    # 3. 图像质量如何（亮度、清晰度）
    #
    # 我会根据测试结果优化 backend/config.py 中的摄像头配置！
