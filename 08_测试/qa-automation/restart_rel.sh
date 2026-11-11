#!/bin/bash
# 仅重启 Release game_gateway / battle_server，不触碰 echo_server（避免打断 M1 长连压测）。
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REL="$ROOT/05_代码/backend/build/bin"
RPT="$ROOT/08_测试/qa-automation/reports"
pkill -9 game_gateway 2>/dev/null || true
pkill -9 battle_server 2>/dev/null || true
fuser -k 8001/tcp 2>/dev/null || true
fuser -k 8002/udp 2>/dev/null || true
sleep 1.5
setsid bash -c "exec '$REL/game_gateway' 8001" > "$RPT/gw.log" 2>&1 < /dev/null &
setsid bash -c "exec '$REL/battle_server' 8002" > "$RPT/bt.log" 2>&1 < /dev/null &
sleep 2.5
pgrep -af game_gateway
pgrep -af battle_server
