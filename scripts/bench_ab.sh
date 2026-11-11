#!/bin/bash
# M6: A/B 压测对比 —— echo_baseline（初始版） vs echo_server（优化版），各跑 N 轮，结果落 evidence
set -u
BIN="$(dirname "$0")/../05_代码/backend/build/bin"
EV="$(dirname "$0")/../08_测试/perf/evidence"
CONN=${1:-1000}; DUR=${2:-10}; ROUNDS=${3:-3}

run_one() {
    local exe=$1; local tag=$2; local out=$3
    pkill -9 echo_baseline 2>/dev/null; pkill -9 echo_server 2>/dev/null
    fuser -k 8000/tcp 2>/dev/null; sleep 1
    setsid bash -c "ulimit -n 65535; exec '$BIN/$exe' 8000" > /tmp/ab_srv.log 2>&1 < /dev/null &
    sleep 1
    : > "$out"
    for i in $(seq 1 "$ROUNDS"); do
        echo "----- $tag round $i -----" >> "$out"
        "$BIN/stress_client" -c "$CONN" -d "$DUR" -p 8000 >> "$out" 2>&1
    done
    pkill -9 "$exe" 2>/dev/null
}

run_one echo_baseline "baseline" "$EV/stress_baseline_ab.txt"
run_one echo_server  "optimized" "$EV/stress_optimized_ab.txt"

echo "=== BASELINE ==="
grep -E "QPS|平均延迟|中途断开" "$EV/stress_baseline_ab.txt"
echo "=== OPTIMIZED ==="
grep -E "QPS|平均延迟|中途断开" "$EV/stress_optimized_ab.txt"
