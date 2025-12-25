#!/usr/bin/env python3
"""
LED 控制测试脚本

测试 DoorController 的 LED 控制功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.doorController import get_door_controller
import time

def main():
    print("=" * 60)
    print("LED 控制测试")
    print("=" * 60)

    # 获取门控制器实例
    door = get_door_controller()

    # 测试1: 检查LED设备
    print("\n[Test 1] LED设备检查")
    if door.led_path:
        print(f"  LED设备路径: {door.led_path}")
        if door.led_path.exists():
            print("  ✓ LED设备存在")
        else:
            print("  ✗ LED设备不存在")
    else:
        print("  ⚠ LED未配置，将使用日志模拟")

    # 测试2: 手动控制LED
    print("\n[Test 2] 手动控制LED")
    print("  [1/4] 点亮LED (255)...")
    door._set_led(255)
    time.sleep(2)

    print("  [2/4] 半亮度 (128)...")
    door._set_led(128)
    time.sleep(2)

    print("  [3/4] 低亮度 (50)...")
    door._set_led(50)
    time.sleep(2)

    print("  [4/4] 关闭LED (0)...")
    door._set_led(0)
    time.sleep(1)

    # 测试3: 模拟开门操作
    print("\n[Test 3] 模拟开门操作（LED亮3秒）")
    print("  调用 door.open()...")
    start = time.time()
    door.open()
    elapsed = time.time() - start
    print(f"  ✓ 开门完成，耗时: {elapsed:.2f}秒")

    # 测试4: 并发测试
    print("\n[Test 4] 并发测试（连续调用2次）")
    print("  第1次开门...")
    import threading

    def open_task(task_id):
        print(f"    线程{task_id}: 开始")
        door.open()
        print(f"    线程{task_id}: 完成")

    t1 = threading.Thread(target=open_task, args=(1,))
    t2 = threading.Thread(target=open_task, args=(2,))

    t1.start()
    time.sleep(0.5)  # 错开启动时间
    t2.start()

    t1.join()
    t2.join()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n提示:")
    print("  - 如果看到 'Permission denied'，请使用 sudo 运行此脚本")
    print("  - 如果LED未配置，将只显示日志模拟输出")
    print("  - 观察开发板上的 'work' LED 是否按预期亮起/熄灭")

if __name__ == "__main__":
    main()
