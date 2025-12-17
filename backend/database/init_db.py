"""数据库初始化脚本

删除旧数据库，创建新数据库，并初始化默认管理员账户
"""

import os
import sys

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from backend.database.manager import init_database


def main():
    print("=" * 60)
    print("数据库初始化")
    print("=" * 60)

    # 数据库文件路径（在 backend/database/ 目录下）
    db_path = os.path.join(current_dir, 'database.db')

    # 检查并删除旧数据库
    if os.path.exists(db_path):
        print(f"\n警告：发现旧的数据库文件: {db_path}")
        print("该文件将被删除...")
        os.remove(db_path)
        print("[OK] 旧数据库已删除")

    print("\n正在创建新数据库...")

    # 初始化数据库
    # db_manager 在 import 时已创建，表结构已自动创建
    # 现在创建默认管理员
    init_database()

    print("\n[OK] 数据库初始化完成！")
    print(f"[OK] 数据库文件位置: {db_path}")
    print("\n" + "=" * 60)
    print("默认管理员账户信息：")
    print("  用户名: admin")
    print("  密码: 123456")
    print("  注意：密码已使用 bcrypt 加密存储")
    print("=" * 60)


if __name__ == '__main__':
    main()
