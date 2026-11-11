#!/bin/bash
# step5A 收尾回归：起 gateway + battle_server，跑 debug_battle.py（先登录再调战斗服）
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN="$ROOT/05_代码/backend/build/bin"
SCR="$ROOT/scripts"

# 清场
pkill -9 game_gateway 2>/dev/null; pkill -9 battle_server 2>/dev/null
fuser -k 8001/tcp 2>/dev/null; fuser -k 8002/udp 2>/dev/null
sleep 1

# 起 gateway（登录网关）
setsid bash -c "exec '$BIN/game_gateway'" > /tmp/gw.log 2>&1 < /dev/null &
sleep 1.5

# 起 battle_server（战斗服）
setsid bash -c "exec '$BIN/battle_server' 8002" > /tmp/bt.log 2>&1 < /dev/null &
sleep 1.5

cd "$SCR"
echo "=== login + battle client ==="
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 debug_battle.py
echo "EXIT=$?"
echo "=== gateway log ==="
cat /tmp/gw.log
echo "=== battle log ==="
cat /tmp/bt.log

# 清场
pkill -9 game_gateway 2>/dev/null
pkill -9 battle_server 2>/dev/null
