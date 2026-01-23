# MongoDB 管理脚本使用说明

## 1. 创建数据库和用户

创建新数据库和用户（推荐）：

```bash
python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr
```

用户已存在时，强制更新密码：

```bash
python create_mongodb_database.py --username=zenking --password=funasr2026 --database=funasr --force
```

### 参数说明

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--username` | `-u` | 是 | 要创建的用户名 |
| `--password` | `-p` | 是 | 用户密码 |
| `--database` | `-d` | 是 | 数据库名 |
| `--host` | | 否 | MongoDB 主机 (默认: 192.168.8.233) |
| `--port` | | 否 | MongoDB 端口 (默认: 27017) |
| `--force` | | 否 | 用户已存在时强制更新密码 |

## 2. 测试连接

```bash
# 测试默认连接
python test_mongodb.py

# 测试指定主机
python test_mongodb.py --host 192.168.8.233

# 完整参数
python test_mongodb.py --host 192.168.8.233 --port 27017 --username zenking --password funasr2026 --database funasr
```

### 测试脚本功能

- Ping MongoDB 服务器
- 显示服务器版本
- 列出所有数据库
- 显示目标数据库的集合和文档数量
- 测试写入/读取操作
- 验证连接成功

## 3. 连接字符串

创建成功后，使用以下连接字符串：

```
mongodb://用户名:密码@主机:端口/数据库名?authSource=admin
```

示例：
```
mongodb://zenking:funasr2026@192.168.8.233:27017/funasr?authSource=admin
```

## 4. 常见问题

### 认证失败

- 确保 `authSource=admin` 参数存在
- 用户已存在时使用 `--force` 更新密码

### 无法连接

- 检查 MongoDB 服务是否运行：`docker-compose ps mongodb`
- 检查端口是否开放：`telnet 192.168.8.233 27017`
