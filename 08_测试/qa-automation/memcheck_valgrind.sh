#!/bin/bash
# M3（Q-011）：Valgrind 覆盖 game_gateway / battle_server，definitely lost 判定。
# 复用 Release 二进制；端口 8001/8002 写死，先停 Release，Valgrind 起服务跑探针，最后恢复 Release。
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REL="$ROOT/05_代码/backend/build/bin"
QA="$ROOT/08_测试/qa-automation"
RPT="$QA/reports"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
mkdir -p "$RPT"

VG="valgrind --tool=memcheck --leak-check=full --show-leak-kinds=definite \
  --errors-for-leak-kinds=definite --track-origins=no --fair-sched=yes"

cleanup_port() {
  pkill -9 game_gateway 2>/dev/null || true
  pkill -9 battle_server 2>/dev/null || true
  fuser -k 8001/tcp 2>/dev/null || true
  fuser -k 8002/udp 2>/dev/null || true
  sleep 1.5
}

cleanup_port

# ---- Valgrind gateway ----
$VG --log-file="$RPT/vg_gateway.log" "$REL/game_gateway" 8001 &
VG_GW=$!
sleep 5
python3 "$QA/memcheck_probe.py" --target gateway > "$RPT/vg_gateway_probe.log" 2>&1
GW_PROBE=$?
kill "$VG_GW" 2>/dev/null || true; wait "$VG_GW" 2>/dev/null || true
sleep 1

# ---- Valgrind gateway + battle ----
$VG --log-file="$RPT/vg_gateway_b.log" "$REL/game_gateway" 8001 &
VG_GW2=$!
$VG --log-file="$RPT/vg_battle.log" "$REL/battle_server" 8002 &
VG_BT=$!
sleep 5
python3 "$QA/memcheck_probe.py" --target battle > "$RPT/vg_battle_probe.log" 2>&1
BT_PROBE=$?
kill "$VG_GW2" "$VG_BT" 2>/dev/null || true
wait "$VG_GW2" "$VG_BT" 2>/dev/null || true
sleep 1

# ---- 判定 ----
{
  echo "gateway probe exit=$GW_PROBE ; battle probe exit=$BT_PROBE"
  echo "=== definitely lost / ERROR SUMMARY ==="
  for f in vg_gateway.log vg_gateway_b.log vg_battle.log; do
    echo "--- $f ---"
    grep -E "definitely lost|indirectly lost|ERROR SUMMARY|Invalid|uninitialised" "$RPT/$f" 2>/dev/null || echo "(无匹配)"
  done
} | tee "$RPT/vg_summary.txt"

# ---- 恢复 Release ----
setsid bash -c "exec '$REL/game_gateway' 8001" > "$RPT/gw.log" 2>&1 < /dev/null &
setsid bash -c "exec '$REL/battle_server' 8002" > "$RPT/bt.log" 2>&1 < /dev/null &
sleep 2.5
echo "Release gateway/battle 已恢复" | tee -a "$RPT/vg_summary.txt"

[ "$GW_PROBE" -eq 0 ] && [ "$BT_PROBE" -eq 0 ]
