#!/bin/bash
# M3（Q-011）：ASan 覆盖 game_gateway / battle_server。
# 端口 8001/8002 写死，先停 Release，起 ASan 二进制跑业务探针，采集 stderr，最后恢复 Release。
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REL="$ROOT/05_代码/backend/build/bin"
ASAN="$ROOT/05_代码/backend/build-asan/bin"
QA="$ROOT/08_测试/qa-automation"
RPT="$QA/reports"
export ASAN_OPTIONS="detect_leaks=1:symbolize=1:abort_on_error=0"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

mkdir -p "$RPT"

cleanup_port() {
  pkill -9 game_gateway 2>/dev/null || true
  pkill -9 battle_server 2>/dev/null || true
  fuser -k 8001/tcp 2>/dev/null || true
  fuser -k 8002/udp 2>/dev/null || true
  sleep 1
}

cleanup_port

# ---- ASan gateway ----
setsid bash -c "exec '$ASAN/game_gateway' 8001" > "$RPT/asan_gateway.log" 2>&1 < /dev/null &
sleep 2
python3 "$QA/memcheck_probe.py" --target gateway > "$RPT/asan_gateway_probe.log" 2>&1
GW_PROBE=$?
pkill -TERM game_gateway 2>/dev/null || true
sleep 1
pkill -9 game_gateway 2>/dev/null || true

# ---- ASan battle（同时起 ASan gateway 供探针登录拿 token）----
setsid bash -c "exec '$ASAN/game_gateway' 8001" > "$RPT/asan_gateway_b.log" 2>&1 < /dev/null &
setsid bash -c "exec '$ASAN/battle_server' 8002" > "$RPT/asan_battle.log" 2>&1 < /dev/null &
sleep 2
python3 "$QA/memcheck_probe.py" --target battle > "$RPT/asan_battle_probe.log" 2>&1
BT_PROBE=$?
pkill -TERM battle_server game_gateway 2>/dev/null || true
sleep 1
pkill -9 battle_server game_gateway 2>/dev/null || true

# ---- 汇总 ----
echo "gateway probe exit=$GW_PROBE ; battle probe exit=$BT_PROBE" | tee "$RPT/asan_summary.txt"
echo "=== ASan 错误扫描（AddressSanitizer / ERROR / leak）===" | tee -a "$RPT/asan_summary.txt"
grep -E "AddressSanitizer|ERROR|DEADLY|leak|LeakSanitizer|SEGV|heap-buffer|stack-buffer|use-after" \
  "$RPT/asan_gateway.log" "$RPT/asan_battle.log" 2>/dev/null | tee -a "$RPT/asan_summary.txt" || true
echo "=== 扫描结束（无输出即未检出 ASan 错误）===" | tee -a "$RPT/asan_summary.txt"

# ---- 恢复 Release ----
setsid bash -c "exec '$REL/game_gateway' 8001" > "$RPT/gw.log" 2>&1 < /dev/null &
setsid bash -c "exec '$REL/battle_server' 8002" > "$RPT/bt.log" 2>&1 < /dev/null &
sleep 2.5
echo "Release gateway/battle 已恢复" | tee -a "$RPT/asan_summary.txt"

[ "$GW_PROBE" -eq 0 ] && [ "$BT_PROBE" -eq 0 ]
