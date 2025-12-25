import logging
import threading
import time
from typing import Optional
from pathlib import Path

from backend.config import DOOR_OPEN_DURATION, LED_SYSFS_PATH


class DoorController:
    """门控制器类（使用LED指示灯代替实际门锁）"""

    def __init__(self, status: bool = False):
        """初始化门控制器"""
        # 添加初始化标志，避免单例模式下重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.status = status  # 当前门状态：False-关闭，True-打开
        self._door_lock = threading.Lock()  # 实例级别的线程锁，用于控制开门操作
        self.led_path = Path(LED_SYSFS_PATH) if LED_SYSFS_PATH else None

        # 检查LED设备是否可用
        if self.led_path and self.led_path.exists():
            logging.info(f"[DoorController] LED device found: {self.led_path}")
            # 初始化时关闭 LED（开发板上电时 LED9 默认会亮）
            self._set_led(0)
            logging.info("[DoorController] LED turned off on initialization")
        elif self.led_path:
            logging.warning(f"[DoorController] LED device not found: {self.led_path}")
            self.led_path = None
        else:
            logging.info("[DoorController] LED control disabled (LED_SYSFS_PATH not configured)")

    def _set_led(self, brightness: int):
        """
        控制LED亮度

        Args:
            brightness: 亮度值 (0-255)，0为关闭，255为最亮
        """
        if not self.led_path:
            logging.debug("[DoorController] LED not configured, simulating LED control")
            return

        try:
            # 限制亮度范围
            brightness = max(0, min(255, brightness))

            # 写入亮度值到sysfs
            with open(self.led_path, 'w') as f:
                f.write(str(brightness))

            logging.info(f"[DoorController] LED brightness set to {brightness}")
        except PermissionError:
            logging.error(f"[DoorController] Permission denied: {self.led_path}. Run with sudo or configure udev rules.")
        except Exception as e:
            logging.error(f"[DoorController] Failed to control LED: {e}")

    def open(self):
        """开门操作（非阻塞）- 使用LED亮起代替实际门锁开启

        如果门已经在开门过程中，则直接返回，不执行重复操作
        """
        # 尝试获取锁，如果已被锁定则直接返回
        if not self._door_lock.acquire(blocking=False):
            logging.info("[DoorController] Door is busy")
            return

        try:
            logging.info("[DoorController] Open the door (LED ON)")
            # 点亮LED（代替实际门锁开启）
            self._set_led(255)
            self.status = True

            # 保持LED亮起指定时间（从配置文件读取）
            time.sleep(DOOR_OPEN_DURATION)

            # 关闭LED（代替实际门锁关闭）
            logging.info("[DoorController] Close the door (LED OFF)")
            self._set_led(0)
            self.status = False

        finally:
            # 确保无论是否发生异常，都能释放锁
            self._door_lock.release()


# ========================================
# 全局单例实例（供 FastAPI 使用）
# ========================================

# 延迟初始化：只在首次调用时创建实例
_door_controller_instance: Optional[DoorController] = None


def get_door_controller() -> DoorController:
    """
    获取全局 DoorController 实例（单例模式）

    供 FastAPI 路由函数调用
    """
    global _door_controller_instance
    if _door_controller_instance is None:
        _door_controller_instance = DoorController()
    return _door_controller_instance


if __name__ == "__main__":
    """单元测试：验证 DoorController 功能"""
    import threading
    import time

    print("=" * 60)
    print("开始测试 DoorController")
    print("=" * 60)

    # 测试1: 单例模式
    print("\n[Test 1] 单例模式测试")
    try:
        door1 = get_door_controller()
        door2 = get_door_controller()
        if door1 is door2:
            print("[PASS] 单例模式正确：door1 is door2")
        else:
            print("[FAIL] 单例模式错误：创建了多个实例")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试2: 初始化状态
    print("\n[Test 2] 初始化状态测试")
    try:
        door = get_door_controller()
        if door.status == False:
            print(f"[PASS] 初始状态正确：status={door.status}")
        else:
            print(f"[FAIL] 初始状态错误：status={door.status}，应该为False")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试3: 单次开门操作
    print("\n[Test 3] 单次开门操作")
    try:
        door = get_door_controller()
        print("开始开门...")
        start_time = time.time()
        door.open()
        elapsed = time.time() - start_time
        print(f"开门完成，耗时: {elapsed:.2f}秒")

        if 3.0 <= elapsed <= 3.5:
            print("[PASS] 开门时间正确（约3秒）")
        else:
            print(f"[WARN] 开门时间异常：{elapsed:.2f}秒")

        if door.status == False:
            print(f"[PASS] 开门后状态正确：status={door.status}")
        else:
            print(f"[FAIL] 开门后状态错误：status={door.status}")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    # 测试4: 并发开门（核心测试）
    print("\n[Test 4] 并发开门测试（防止重复开门）")
    try:
        door = get_door_controller()
        results = []

        def open_door_task(task_id):
            """开门任务"""
            print(f"  线程{task_id}: 尝试开门")
            start = time.time()
            door.open()
            elapsed = time.time() - start
            results.append({"task_id": task_id, "elapsed": elapsed})
            print(f"  线程{task_id}: 完成（耗时: {elapsed:.2f}秒）")

        # 创建3个线程同时开门
        threads = []
        for i in range(3):
            t = threading.Thread(target=open_door_task, args=(i,))
            threads.append(t)

        # 启动所有线程
        print("启动3个并发线程...")
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 分析结果
        print("\n结果分析:")
        long_tasks = [r for r in results if r["elapsed"] >= 3.0]
        short_tasks = [r for r in results if r["elapsed"] < 0.1]

        print(f"  执行完整操作的线程: {len(long_tasks)} 个")
        print(f"  被阻塞返回的线程: {len(short_tasks)} 个")

        if len(long_tasks) == 1 and len(short_tasks) == 2:
            print("[PASS] 并发控制正确：只有1个线程执行了开门，其他2个被阻塞")
        else:
            print("[FAIL] 并发控制异常")

    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    # 测试5: 锁释放测试
    print("\n[Test 5] 锁释放测试")
    try:
        door = get_door_controller()
        # 第一次开门
        door.open()
        time.sleep(0.1)
        # 第二次开门（应该成功，证明锁已释放）
        print("第二次开门...")
        start = time.time()
        door.open()
        elapsed = time.time() - start

        if elapsed >= 3.0:
            print("[PASS] 锁正确释放，第二次开门成功")
        else:
            print("[FAIL] 第二次开门异常")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
