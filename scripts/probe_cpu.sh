#!/bin/bash
# 压测期间采样 echo_server 各线程 CPU，判断瓶颈在服务端还是客户端
cd "$(dirname "$0")/../05_代码/backend/build/bin"
pkill -9 echo_server 2>/dev/null; fuser -k 8000/tcp 2>/dev/null; sleep 1
setsid bash -c "ulimit -n 65535; exec ./echo_server 8000" > /tmp/echo_cpu.log 2>&1 < /dev/null &
sleep 1

./stress_client -c 1000 -d 12 -p 8000 > /tmp/cpu_stress.log 2>&1 &
SPID=$!
sleep 5

SPID_SRV=$(pgrep -x echo_server | head -1)
{
  echo "=== 服务端进程级 CPU/内存（压测中）pid=$SPID_SRV ==="
  ps -o pid,%cpu,%mem,nlwp,comm -p "$SPID_SRV"
  echo "=== 客户端进程级 CPU/内存 ==="
  ps -o pid,%cpu,%mem,nlwp,comm -C stress_client
  echo "=== 服务端各线程 top ==="
  top -b -n 1 -H -p "$SPID_SRV"
} > /tmp/cpu_sample.log 2>&1

wait "$SPID"
{
  echo "=== 压测结果 ==="
  grep -E "QPS|平均延迟|中途断开" /tmp/cpu_stress.log
  echo "=== 服务端采样 ==="
  cat /tmp/cpu_sample.log
} > /tmp/cpu_report.log 2>&1

pkill -9 echo_server 2>/dev/null
echo "done"
