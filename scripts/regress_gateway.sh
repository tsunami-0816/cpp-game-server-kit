#!/bin/bash
# step5A 收尾回归：起 MySQL/Redis，起 game_gateway，跑 test_login.py，留存日志
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN="$ROOT/05_代码/backend/build/bin"
SCR="$ROOT/scripts"

service mysql start >/dev/null 2>&1
redis-cli -p 6380 ping >/dev/null 2>&1 || setsid redis-server --port 6380 --bind 127.0.0.1 --daemonize yes >/tmp/redis.log 2>&1 </dev/null
sleep 1.5

pkill -9 game_gateway 2>/dev/null; fuser -k 8001/tcp 2>/dev/null; sleep 1
setsid bash -c "exec '$BIN/game_gateway' 8001" > /tmp/gw.log 2>&1 < /dev/null &
sleep 2

cd "$SCR"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 test_login.py > /tmp/login_reg.log 2>&1
echo "EXIT=$?"
echo "=== login ==="
cat /tmp/login_reg.log
echo "=== gateway log ==="
cat /tmp/gw.log
pkill -9 game_gateway 2>/dev/null
