#!/bin/bash
# 探索演示一键入口：先确保中间件/服务在线，再跑大白话演示脚本；结束后保留服务在线供继续试。
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> 1/2 拉起 MySQL / Redis(6380) / gateway 8001 / battle 8002 ..."
cd "$ROOT/08_测试/qa-automation"
bash services.sh start >/tmp/explore_services.log 2>&1
sleep 1.5

echo "==> 2/2 运行探索演示 ..."
cd "$ROOT/scripts"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 explore_demo.py
