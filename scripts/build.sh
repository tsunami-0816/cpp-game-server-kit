#!/bin/bash
# T-25: 一键编译脚本
set -e
cd "$(dirname "$0")/../05_代码/backend"
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -20
make -j$(nproc) 2>&1 | tail -30
echo "=== 编译产物 ==="
ls -lh bin/
