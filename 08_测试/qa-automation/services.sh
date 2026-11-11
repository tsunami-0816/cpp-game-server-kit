#!/bin/bash
# step8 服务编排：start / stop / restart / status
# 被测：game_gateway(TCP 8001) battle_server(UDP 8002)；中间件 MySQL 3306 / Redis 6380 为本机常驻。
# 日志落 qa-automation/reports/。用法: bash services.sh [start|stop|restart|status]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIN="$ROOT/05_代码/backend/build/bin"
RPT="$ROOT/08_测试/qa-automation/reports"
mkdir -p "$RPT"

ensure_middleware() {
  service mysql start >/dev/null 2>&1 || true
  redis-cli -p 6380 ping >/dev/null 2>&1 \
    || setsid redis-server --port 6380 --bind 127.0.0.1 --daemonize yes >/tmp/redis_step8.log 2>&1 </dev/null
  sleep 1
}

stop_services() {
  pkill -9 game_gateway 2>/dev/null || true
  pkill -9 battle_server 2>/dev/null || true
  pkill -9 echo_server 2>/dev/null || true
  fuser -k 8001/tcp 2>/dev/null || true
  fuser -k 8002/udp 2>/dev/null || true
  fuser -k 8000/tcp 2>/dev/null || true
  sleep 1
}

start_services() {
  ensure_middleware
  stop_services
  setsid bash -c "exec '$BIN/game_gateway' 8001" > "$RPT/gw.log" 2>&1 < /dev/null &
  setsid bash -c "exec '$BIN/battle_server' 8002" > "$RPT/bt.log" 2>&1 < /dev/null &
  sleep 2.5
}

status_services() {
  echo "== TCP =="; ss -ltnp 2>/dev/null | grep -E '8001|3306' || true
  echo "== UDP =="; ss -lunp 2>/dev/null | grep 8002 || true
  echo "== redis =="; redis-cli -p 6380 ping 2>&1
  echo "== mysql =="; mysql -uroot -N -e "SELECT COUNT(*) AS users FROM cpp_game.users;" 2>&1
}

case "${1:-status}" in
  start)   start_services; status_services ;;
  stop)    stop_services; echo "stopped" ;;
  restart) start_services; status_services ;;
  status)  status_services ;;
  *) echo "usage: $0 [start|stop|restart|status]"; exit 1 ;;
esac
