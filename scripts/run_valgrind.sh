#!/bin/bash
# T-23: Valgrind 内存检测 —— 跑 echo_server 链路，definitely lost = 0 bytes
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT/05_代码/backend"
BUILD_DIR=build

# 确保 Release 产物在
if [ ! -x "$BUILD_DIR/bin/echo_server" ]; then
    echo "先跑 scripts/build.sh 构建 Release 产物"
    exit 1
fi

VG_LOG=/tmp/valgrind_evidence.log
: > "$VG_LOG"

echo "=== Valgrind 启动 echo_server（8011）==="
valgrind --tool=memcheck --leak-check=full --show-leak-kinds=definite \
    --errors-for-leak-kinds=definite --error-exitcode=42 \
    --log-file="$VG_LOG" \
    "$BUILD_DIR/bin/echo_server" 8011 &
VG_PID=$!
sleep 3

python3 - <<'PY' 2>&1
import socket
s = socket.socket()
s.settimeout(3)
s.connect(("127.0.0.1", 8011))
s.sendall(b"hello-valgrind")
print("echo reply:", s.recv(64))
s.close()
PY

sleep 1
kill "$VG_PID" 2>/dev/null
wait "$VG_PID" 2>/dev/null

echo "=== Valgrind 结果判定 ==="
if grep -q "definitely lost: [1-9]" "$VG_LOG"; then
    echo "❌ Valgrind 存在 definitely lost:"
    grep -A3 "definitely lost" "$VG_LOG"
    exit 1
fi
echo "✅ Valgrind definitely lost = 0 bytes（echo 链路）"
grep -E "definitely lost|indirectly lost|ERROR SUMMARY" "$VG_LOG"
cp "$VG_LOG" "$ROOT/06_冒烟/evidence/valgrind_report.log"
