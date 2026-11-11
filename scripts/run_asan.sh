#!/bin/bash
# T-23: ASan 内存检测 —— 单独 build-asan 目录加 -fsanitize=address，跑冒烟用例，零 error 零 leak
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT/05_代码/backend"

BUILD_DIR=build-asan
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "=== [1/3] CMake 配置（ASan + Debug -g）==="
cmake .. -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_FLAGS="-fsanitize=address -g -O1 -fno-omit-frame-pointer" \
    -DCMAKE_C_FLAGS="-fsanitize=address -g -O1" \
    -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" 2>&1 | tail -5

echo "=== [2/3] 编译 echo_server / bench_queue / stress_client ==="
make -j"$(nproc)" echo_server bench_queue stress_client 2>&1 | tail -10

echo "=== [3/3] 跑冒烟用例 ==="
ASAN_LOG=/tmp/asan_evidence.log
: > "$ASAN_LOG"

# 3.1 bench_queue 压 10 万条，检查队列无泄漏/越界
echo "--- bench_queue ---"
./bin/bench_queue 100000 2>&1 | tee -a "$ASAN_LOG"

# 3.2 echo_server 起服务，发一条回显，再关闭
echo "--- echo_server ---"
./bin/echo_server 8010 > /tmp/asan_echo.log 2>&1 &
ECHO_PID=$!
sleep 1
python3 - <<'PY' 2>&1 | tee -a "$ASAN_LOG"
import socket
s = socket.socket()
s.settimeout(3)
s.connect(("127.0.0.1", 8010))
s.sendall(b"hello-asan")
print("echo reply:", s.recv(64))
s.close()
PY
kill "$ECHO_PID" 2>/dev/null
wait "$ECHO_PID" 2>/dev/null
cat /tmp/asan_echo.log >> "$ASAN_LOG"

# 判定：ASan 报错关键字
echo "=== ASan 结果判定 ==="
if grep -E "ERROR: AddressSanitizer|SEGV|heap-buffer-overflow|stack-buffer-overflow|leak" "$ASAN_LOG"; then
    echo "❌ ASan 发现问题，见上方日志"
    exit 1
fi
echo "✅ ASan 零 error 零 leak（bench_queue + echo 冒烟）"
cp "$ASAN_LOG" "$ROOT/06_冒烟/evidence/asan_report.log"
