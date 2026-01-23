#!/usr/bin/env python3
"""
MongoDB 数据库创建脚本

根据配置创建数据库和初始集合

用法:
    python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr

    # 用户已存在时，强制更新密码
    python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr --force
"""

import argparse
import sys
from pymongo import MongoClient
from datetime import datetime


# 默认配置
DEFAULT_HOST = "192.168.8.233"
DEFAULT_PORT = 27017
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "tts_password_2024"


def create_database_and_user(host, port, admin_username, admin_password, username, password, database, force=False):
    """创建 MongoDB 数据库和用户"""

    # 使用 admin 用户连接
    admin_conn_str = f"mongodb://{admin_username}:{admin_password}@{host}:{port}/"

    print("=" * 60)
    print("MongoDB 数据库创建脚本")
    print("=" * 60)
    print(f"主机: {host}:{port}")
    print(f"管理员: {admin_username}")
    print(f"目标数据库: {database}")
    print(f"用户: {username}")
    print("-" * 60)

    try:
        # 使用 admin 连接 MongoDB
        print("正在连接 MongoDB (使用管理员账号)...")
        client = MongoClient(admin_conn_str, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✓ 连接成功")

        # 获取目标数据库
        db = client[database]

        # 处理用户 - 在 admin 数据库创建用户，授权访问目标数据库
        print()
        print(f"处理用户 '{username}'...")

        admin_db = client['admin']

        # 检查用户是否已存在于 admin 数据库
        try:
            existing_users = admin_db.command("usersInfo", username)['users']
            user_exists = len(existing_users) > 0

            if user_exists:
                if force:
                    # 删除并重建用户
                    admin_db.command("dropUser", username)
                    print(f"  - 删除旧用户 '{username}'")
                    # 在 admin 数据库创建用户，授权访问目标数据库
                    admin_db.command(
                        "createUser",
                        username,
                        pwd=password,
                        roles=[
                            {"role": "readWrite", "db": database},
                            {"role": "dbAdmin", "db": database}
                        ]
                    )
                    print(f"  ✓ 用户 '{username}' 重建成功 (密码已更新)")
                else:
                    print(f"  - 用户 '{username}' 已存在")
                    print(f"  提示: 如需更新密码，请使用 --force 参数")
            else:
                # 在 admin 数据库创建新用户
                admin_db.command(
                    "createUser",
                    username,
                    pwd=password,
                    roles=[
                        {"role": "readWrite", "db": database},
                        {"role": "dbAdmin", "db": database}
                    ]
                )
                print(f"  ✓ 用户 '{username}' 创建成功")
        except Exception as e:
            print(f"  ⚠ 处理用户时出错: {e}")

        # 创建初始集合
        print()
        print("创建初始集合...")

        if "tts_tasks" not in db.list_collection_names():
            db.create_collection("tts_tasks")
            print("  ✓ 创建集合: tts_tasks")
        else:
            print("  - 集合已存在: tts_tasks")

        if "speaker_registrations" not in db.list_collection_names():
            db.create_collection("speaker_registrations")
            print("  ✓ 创建集合: speaker_registrations")
        else:
            print("  - 集合已存在: speaker_registrations")

        # 插入初始化标记
        init_col = db["_init"]
        init_col.delete_many({})
        init_col.insert_one({
            "initialized": True,
            "created_at": datetime.now(),
            "database": database,
            "user": username
        })
        print("  ✓ 写入初始化标记")

        # 验证新用户连接
        print()
        print("验证用户连接...")
        # 使用 authSource=admin 验证
        new_conn_str = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin"
        test_client = MongoClient(new_conn_str, serverSelectionTimeoutMS=5000)
        test_client[database].list_collection_names()
        print("  ✓ 用户连接验证成功")
        test_client.close()

        print()
        print("=" * 60)
        print(f"✓ 数据库 '{database}' 配置完成!")
        print("=" * 60)
        print()
        print("连接信息:")
        print(f"  主机: {host}:{port}")
        print(f"  数据库: {database}")
        print(f"  用户: {username}")
        print()
        print("连接字符串:")
        print(f"  mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin")

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ 操作失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'client' in locals():
            client.close()


def main():
    parser = argparse.ArgumentParser(
        description="MongoDB 数据库创建脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建新用户和数据库
  python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr

  # 用户已存在时，强制更新密码
  python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr --force
        """
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"MongoDB 主机 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"MongoDB 端口 (默认: {DEFAULT_PORT})")
    parser.add_argument("-u", "--username", required=True, help="用户名")
    parser.add_argument("-p", "--password", required=True, help="密码")
    parser.add_argument("-d", "--database", required=True, help="数据库名")
    parser.add_argument("--force", action="store_true", help="用户已存在时，强制更新密码")

    args = parser.parse_args()

    success = create_database_and_user(
        host=args.host,
        port=args.port,
        admin_username=ADMIN_USERNAME,
        admin_password=ADMIN_PASSWORD,
        username=args.username,
        password=args.password,
        database=args.database,
        force=args.force
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
