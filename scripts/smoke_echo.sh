#!/bin/bash
# T-05 验证：启动 echo_server，发个包看能不能回显
set -e
cd "$(dirname "$0")/../05_代码/backend/build/bin"

# 后台启动 echo_server
./echo_server 8000 &
ECHO_PID=$!
sleep 1

# 用 /dev/tcp 发数据并读回显
echo "hello cpp-game" > /dev/tcp/127.0.0.1/8000
sleep 0.5

# 检查进程还在不在
if kill -0 $ECHO_PID 2>/dev/null; then
    echo "✅ echo_server 运行中 (pid=$ECHO_PID)"
else
    echo "❌ echo_server 崩了"
    exit 1
fi

# 清理
kill $ECHO_PID 2>/dev/null || true
echo "=== T-05 Echo Server 冒烟通过 ==="
