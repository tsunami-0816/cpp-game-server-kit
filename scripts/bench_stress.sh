#!/bin/bash
# T-21/T-25: 长连接压测 —— 起 echo_server，跑 N 轮 stress_client，QPS/延迟落盘
# 用法: bench_stress.sh <连接数> <秒数> <轮次> <输出日志>
set -u
cd "$(dirname "$0")/../05_代码/backend/build/bin"

CONN=${1:-1000}
DUR=${2:-10}
ROUNDS=${3:-3}
OUT=${4:-/tmp/bench_stress.log}

pkill -9 echo_server 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
sleep 1

setsid bash -c "ulimit -n 65535; exec ./echo_server 8000" > /tmp/echo_bench.log 2>&1 < /dev/null &
sleep 1

: > "$OUT"
for i in $(seq 1 "$ROUNDS"); do
    echo "----- round $i -----" >> "$OUT"
    ./stress_client -c "$CONN" -d "$DUR" -p 8000 >> "$OUT" 2>&1
done

echo "=== 汇总 QPS / 平均延迟 / 断开 ==="
grep -E "QPS|平均延迟|中途断开" "$OUT"
pkill -9 echo_server 2>/dev/null
