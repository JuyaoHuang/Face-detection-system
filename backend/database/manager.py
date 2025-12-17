import sqlite3
import numpy as np
import os
from typing import Optional, Dict, List, Union

from backend.utils.password import hash_password


class DatabaseManager:
    """数据库管理器类，负责处理所有数据库操作"""

    def __init__(self, db_path: str = None):
        """初始化数据库连接

        Args:
            db_path: 数据库文件路径。如果为 None，则使用默认路径 backend/database/database.db
        """
        if db_path is None:
            # 默认路径：backend/database/database.db
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'database.db')

        # 添加 check_same_thread=False 以支持多线程访问
        # 后台线程和FastAPI请求会并发访问数据库
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """创建管理员表和人脸特征表"""
        # 1. 管理员信息表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS administrators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        # 2. 人脸特征向量表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS face_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                feature_vector BLOB NOT NULL  -- 存储512维特征向量的二进制数据
            )
        ''')

        self.conn.commit()

    def add_administrator(self, username: str, password: str) -> int:
        """添加管理员

        Args:
            username: 用户名
            password: 明文密码（将自动 hash）

        Returns:
            新增记录的 ID
        """
        # 对密码进行 hash
        hashed_password = hash_password(password)
        self.cursor.execute('''
            INSERT INTO administrators (username, password)
            VALUES (?, ?)
        ''', (username, hashed_password))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_administrator(self, username: str) -> str:
        """通过用户名获取管理员信息"""
        self.cursor.execute('''
            SELECT id, username, password
            FROM administrators
            WHERE username = ?
        ''', (username,))
        row = self.cursor.fetchone()
        if row:
            return row[2]
        return ""

    def update_administrator_password(self, username: str, new_password: str) -> bool:
        """更新管理员密码

        Args:
            username: 用户名
            new_password: 新的明文密码（将自动 hash）

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            # 对新密码进行 hash
            hashed_password = hash_password(new_password)
            self.cursor.execute('''
                UPDATE administrators
                SET password = ?
                WHERE username = ?
            ''', (hashed_password, username))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新管理员密码失败: {e}")
            return False


    def get_face_name_list(self) -> List[str]:
        """获取所有用户名列表"""
        self.cursor.execute('''
            SELECT name FROM face_features
        ''')
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def delete_face_name(self, name: str) -> bool:
        """删除指定用户名的人脸特征向量"""
        try:
            self.cursor.execute('''
                DELETE FROM face_features
                WHERE name = ?
            ''', (name,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"删除人脸特征向量失败: {e}")
            return False

    def delete_all_face_names(self) -> bool:
        """删除所有用户名的人脸特征向量"""
        try:
            self.cursor.execute('''
                DELETE FROM face_features
            ''')
            self.conn.commit()
            return True  # 操作成功即返回True，即使删除了0行
        except Exception as e:
            print(f"删除所有人脸特征向量失败: {e}")
            return False



    def add_face_feature(self, name: str, feature_vector: Union[List[float], np.ndarray]) -> bool:
        """添加人脸特征向量

        Args:
            name: 用户名
            feature_vector: 512维特征向量，可以是List[float]或np.ndarray

        Returns:
            bool: 添加成功返回True，失败返回False
        """
        # 统一转换为numpy数组
        if isinstance(feature_vector, list):
            feature_vector = np.array(feature_vector, dtype=np.float32)
        elif not isinstance(feature_vector, np.ndarray):
            print(f"添加人脸特征向量失败: 不支持的类型 {type(feature_vector)}")
            return False

        # 将numpy数组转换为二进制数据
        feature_blob = feature_vector.tobytes()

        try:
            self.cursor.execute('''
                INSERT INTO face_features (name, feature_vector)
                VALUES (?, ?)
            ''', (name, feature_blob))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"添加人脸特征向量失败: {e}")
            return False

    def get_face_features(self) -> List[Dict]:
        """获取所有人脸特征向量"""
        self.cursor.execute('''
            SELECT id, name, feature_vector
            FROM face_features
        ''')
        rows = self.cursor.fetchall()
        features = []
        for row in rows:
            # 将二进制数据转换回numpy数组
            feature_vector = np.frombuffer(row[2], dtype=np.float32)
            features.append({
                'id': row[0],
                'name': row[1],
                'feature_vector': feature_vector
            })
        return features

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


# 创建全局数据库管理器实例
db_manager = DatabaseManager()


def init_database():
    """初始化数据库，创建默认管理员"""
    # 检查是否已有管理员
    admin = db_manager.get_administrator('admin')
    if not admin:
        default_password = '123456'
        db_manager.add_administrator(
            username='admin',
            password=default_password,
        )
        print("默认管理员已创建：用户名=admin, 密码=123456")


if __name__ == '__main__':
    """单元测试：验证 SQL 参数传递和类型转换"""
    import os

    # 使用临时数据库进行测试
    test_db_path = 'test_db.db'

    # 清理旧的测试数据库
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    print("="*50)
    print("开始测试 DatabaseManager")
    print("="*50)

    # 创建测试数据库实例
    test_db = DatabaseManager(db_path=test_db_path)

    # 测试1: 添加管理员
    print("\n[测试1] 添加管理员")
    try:
        test_db.add_administrator('testuser', 'testpass')
        print("添加管理员成功")
    except Exception as e:
        print(f"添加管理员失败: {type(e).__name__}: {e}")

    # 测试2: 获取管理员 (验证 SQL 参数传递问题)
    print("\n[测试2] 获取管理员 (当前实现)")
    try:
        password = test_db.get_administrator('testuser')
        print(f"获取管理员成功: password={password}")
    except Exception as e:
        print(f"获取管理员失败: {type(e).__name__}: {e}")
        print(f"   原因: execute() 第二个参数应该是元组 (username,) 而不是字符串 username")

    # 测试3: 添加人脸特征 - 使用 List (模拟 FaceEngine 返回值)
    print("\n[测试3] 添加人脸特征 - 使用 List[float]")
    try:
        feature_list = [0.1] * 512  # 模拟 FaceEngine 返回的 List[float]
        result = test_db.add_face_feature('张三', feature_list)
        print(f"添加人脸特征成功: {result}")
    except Exception as e:
        print(f"添加人脸特征失败: {type(e).__name__}: {e}")
        print(f"   原因: List 没有 tobytes() 方法，需要先转换为 numpy 数组")

    # 测试4: 添加人脸特征 - 使用 numpy 数组
    print("\n[测试4] 添加人脸特征 - 使用 numpy.ndarray")
    try:
        feature_array = np.array([0.2] * 512, dtype=np.float32)
        result = test_db.add_face_feature('李四', feature_array)
        print(f"添加人脸特征成功: {result}")
    except Exception as e:
        print(f"添加人脸特征失败: {type(e).__name__}: {e}")

    # 测试5: 获取人脸名称列表
    print("\n[测试5] 获取人脸名称列表")
    try:
        names = test_db.get_face_name_list()
        print(f"获取列表成功: {names}")
    except Exception as e:
        print(f"获取列表失败: {type(e).__name__}: {e}")

    # 测试6: 删除指定人脸 (验证 SQL 参数传递问题)
    print("\n[测试6] 删除指定人脸")
    try:
        result = test_db.delete_face_name('李四')
        print(f"删除成功: {result}")
    except Exception as e:
        print(f"删除失败: {type(e).__name__}: {e}")
        print(f"   原因: execute() 第二个参数应该是元组 (name,) 而不是字符串 name")

    # 测试7: 删除所有人脸
    print("\n[测试7] 删除所有人脸")
    try:
        result = test_db.delete_all_face_names()
        print(f"删除所有成功: {result}")
    except Exception as e:
        print(f"删除所有失败: {type(e).__name__}: {e}")

    # 测试8: 删除空表 (验证返回值逻辑)
    print("\n[测试8] 删除空表 (验证返回值逻辑)")
    try:
        result = test_db.delete_all_face_names()
        print(f"删除空表返回: {result}")
        print(f"   说明: 当前实现返回 False (表示空表), 但语义上应该返回 True (操作成功)")
    except Exception as e:
        print(f"删除空表失败: {type(e).__name__}: {e}")

    # 清理
    test_db.close()
    os.remove(test_db_path)

    print("\n" + "="*50)
    print("测试完成")
    print("="*50)
