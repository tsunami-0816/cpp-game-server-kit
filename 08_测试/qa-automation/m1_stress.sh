#!/bin/bash
# M1：echo_server 1000 长连接稳压测（基线：5 分钟断开=0，RSS 波动 <50MB）。
# 用法: bash m1_stress.sh [连接数 1000] [秒数 300]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN="$ROOT/05_代码/backend/build/bin"
RPT="$ROOT/08_测试/qa-automation/reports"
CONN=${1:-1000}
DUR=${2:-300}
OUT="$RPT/m1_stress_echo.log"

pkill -9 echo_server 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

setsid bash -c "ulimit -n 65535; exec '$BIN/echo_server' 8000" > /tmp/m1_echo_srv.log 2>&1 < /dev/null &
sleep 1
SRV_PID=$(pgrep -x echo_server | head -1)

rss_kb() {
  local pid=$1
  [ -n "$pid" ] && awk '/VmRSS:/{print $2}' /proc/"$pid"/status 2>/dev/null
}

RSS_BEFORE=$(rss_kb "$SRV_PID")
echo "server pid=$SRV_PID RSS_before=${RSS_BEFORE}KB" > "$OUT"

ulimit -n 65535
"$BIN/stress_client" -c "$CONN" -d "$DUR" -p 8000 >> "$OUT" 2>&1

RSS_AFTER=$(rss_kb "$SRV_PID")
echo "server RSS_after=${RSS_AFTER}KB" >> "$OUT"
echo "server RSS_delta=$(( ${RSS_AFTER:-0} - ${RSS_BEFORE:-0} ))KB" >> "$OUT"

pkill -9 echo_server 2>/dev/null || true
echo "=== M1 结束 ===" >> "$OUT"
