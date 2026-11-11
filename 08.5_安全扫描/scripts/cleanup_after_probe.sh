#!/bin/bash
# step 8.5 探针后干净交接：清 Redis session/room 残留 -> 重启 gateway/battle 清内存房间态 -> 回读验证。
# 不 TRUNCATE users（探针未写 MySQL）；证据落 08.5_安全扫描/evidence/cleanup.log。
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN="$ROOT/05_代码/backend/build/bin"
EVD="$ROOT/08.5_安全扫描/evidence"
mkdir -p "$EVD"

{
  echo "=== 清理前 Redis 键 ==="
  redis-cli -p 6380 keys '*'

  SESS=$(redis-cli -p 6380 keys 'session:*')
  ROOM=$(redis-cli -p 6380 keys 'room:*')
  [ -n "$SESS" ] && redis-cli -p 6380 del $SESS
  [ -n "$ROOM" ] && redis-cli -p 6380 del $ROOM

  echo "=== 清理后 Redis 键 ==="
  redis-cli -p 6380 keys '*'

  echo "=== 重启服务清内存态 ==="
  pkill -9 game_gateway 2>/dev/null
  pkill -9 battle_server 2>/dev/null
  sleep 1
  setsid bash -c "exec '$BIN/game_gateway' 8001"  > "$EVD/gw85.log" 2>&1 </dev/null &
  setsid bash -c "exec '$BIN/battle_server' 8002"  > "$EVD/bt85.log" 2>&1 </dev/null &
  sleep 2.5

  echo "=== 端口复核 ==="
  ss -tlnp 2>/dev/null | grep ':8001' || echo "!! 8001 未监听"
  ss -ulnp 2>/dev/null | grep ':8002' || echo "!! 8002 未监听"

  echo "=== users 种子复核（应 id=1/2） ==="
  mysql -uroot --default-character-set=utf8mb4 cpp_game -N -e \
    "SELECT id,username FROM users ORDER BY id;"
} 2>&1 | tee "$EVD/cleanup.log"
