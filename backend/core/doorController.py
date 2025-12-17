import logging
import threading
import time
from typing import Optional


class DoorController:
    '''门控制器类'''

    def __init__(self, status: bool = False):
        '''初始化门控制器'''
        # 添加初始化标志，避免单例模式下重复初始化
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.status = status  # 当前门状态：False-关闭，True-打开
        self._door_lock = threading.Lock()  # 实例级别的线程锁，用于控制开门操作

    def open(self):
        """开门操作（非阻塞）

        如果门已经在开门过程中，则直接返回，不执行重复操作
        """
        # 尝试获取锁，如果已被锁定则直接返回
        if not self._door_lock.acquire(blocking=False):
            logging.info("Door is busy")
            return 

        try:
            logging.info("Open the door")
            # TODO: 调用 GPIO 控制开门的实际硬件操作
            self.status = True

            # 保持门打开3秒
            time.sleep(3)

            # 执行关锁操作
            logging.info("Close the door")
            # TODO: 调用 GPIO 控制关锁的实际硬件操作
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


if __name__ == '__main__':
    """单元测试：验证 DoorController 功能"""
    import threading
    import time

    print("="*60)
    print("开始测试 DoorController")
    print("="*60)

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
            print(f"[PASS] 开门时间正确（约3秒）")
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
            results.append({'task_id': task_id, 'elapsed': elapsed})
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
        long_tasks = [r for r in results if r['elapsed'] >= 3.0]
        short_tasks = [r for r in results if r['elapsed'] < 0.1]

        print(f"  执行完整操作的线程: {len(long_tasks)} 个")
        print(f"  被阻塞返回的线程: {len(short_tasks)} 个")

        if len(long_tasks) == 1 and len(short_tasks) == 2:
            print("[PASS] 并发控制正确：只有1个线程执行了开门，其他2个被阻塞")
        else:
            print(f"[FAIL] 并发控制异常")

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

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
