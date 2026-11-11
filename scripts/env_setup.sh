#!/bin/bash
# 环境初始化脚本：启动 Redis(6380) + MySQL，建库
set -e

echo "=== 启动 Ubuntu Redis (6380) ==="
redis-cli -p 6380 ping 2>/dev/null || redis-server --daemonize yes --port 6380 --bind 127.0.0.1
sleep 1
redis-cli -p 6380 ping

echo "=== MySQL 状态 ==="
service mysql start 2>/dev/null || true
mysqladmin status | head -1

echo "=== 创建 cpp_game 库 ==="
mysql -e "CREATE DATABASE IF NOT EXISTS cpp_game DEFAULT CHARSET utf8mb4;"
mysql -e "SHOW DATABASES;" | grep cpp_game

echo "=== 环境就绪 ==="
