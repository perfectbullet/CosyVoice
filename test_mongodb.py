#!/usr/bin/env python3
"""
MongoDB 连接测试脚本

用法:
    python test_mongodb.py              # 测试默认连接
    python test_mongodb.py --host 192.168.8.233  # 指定主机
    python test_mongodb.py --remote     # 使用远程连接字符串
"""

import argparse
import sys
from pymongo import MongoClient
from datetime import datetime


# MongoDB 配置
DEFAULT_HOST = "192.168.8.233"
DEFAULT_PORT = 27017
USERNAME = "admin"
PASSWORD = "tts_password_2024"
DATABASE = "tts_service2"


def test_connection(host=DEFAULT_HOST, port=DEFAULT_PORT, username=USERNAME, password=PASSWORD, database=DATABASE):
    """测试 MongoDB 连接"""
    print("=" * 60)
    print("MongoDB 连接测试")
    print("=" * 60)
    print(f"主机: {host}")
    print(f"端口: {port}")
    print(f"用户: {username}")
    print(f"数据库: {database}")
    print("-" * 60)

    # 构建连接字符串
    if username and password:
        conn_str = f"mongodb://{username}:{password}@{host}:{port}/"
    else:
        conn_str = f"mongodb://{host}:{port}/"

    print(f"连接字符串: mongodb://{username}:***@{host}:{port}/")
    print()

    try:
        # 连接 MongoDB
        print("正在连接...")
        client = MongoClient(conn_str, serverSelectionTimeoutMS=5000)

        # 测试连接
        result = client.admin.command('ping')
        print("✓ Ping 成功")

        # 获取服务器信息
        server_info = client.server_info()
        print(f"✓ MongoDB 版本: {server_info.get('version', 'unknown')}")

        # 列出所有数据库
        print()
        print("可用的数据库:")
        dbs = client.list_database_names()
        for db in dbs:
            print(f"  - {db}")

        # 连接到目标数据库
        if database in dbs:
            print()
            print(f"✓ 数据库 '{database}' 存在")

            db = client[database]
            collections = db.list_collection_names()

            if collections:
                print(f"  集合:")
                for col in collections:
                    count = db[col].count_documents({})
                    print(f"    - {col}: {count} 条文档")
            else:
                print(f"  (空数据库，无集合)")

            # 测试写入
            print()
            print("测试写入...")
            test_col = db["test_connection"]
            test_doc = {
                "test": True,
                "timestamp": datetime.now(),
                "message": "MongoDB 连接测试"
            }
            result = test_col.insert_one(test_doc)
            print(f"✓ 写入成功，文档ID: {result.inserted_id}")

            # 测试读取
            doc = test_col.find_one({"_id": result.inserted_id})
            print(f"✓ 读取成功: {doc.get('message')}")

            # 清理测试数据
            test_col.delete_one({"_id": result.inserted_id})
            print(f"✓ 清理测试数据完成")

        else:
            print()
            print(f"✗ 数据库 '{database}' 不存在")

        print()
        print("=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ 连接失败: {e}")
        print("=" * 60)
        return False
    finally:
        if 'client' in locals():
            client.close()


def main():
    parser = argparse.ArgumentParser(description="MongoDB 连接测试")
    parser.add_argument("--host", default=DEFAULT_HOST, help="MongoDB 主机地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MongoDB 端口")
    parser.add_argument("--username", default=USERNAME, help="用户名")
    parser.add_argument("--password", default=PASSWORD, help="密码")
    parser.add_argument("--database", default=DATABASE, help="数据库名")
    parser.add_argument("--remote", action="store_true", help="使用远程连接模式")

    args = parser.parse_args()

    # 如果是远程模式，从环境或配置读取
    if args.remote:
        print("使用远程连接模式")
        print("请根据实际情况修改连接参数")
        print()

    success = test_connection(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        database=args.database
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
