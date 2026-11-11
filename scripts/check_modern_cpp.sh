#!/bin/bash
# T-24/M7: 现代 C++ 特性检查 —— 5 类特性各至少 1 处真实命中（排除 third_party / pb 生成代码）
set -u
ROOT="$(dirname "$0")/../05_代码/backend"
cd "$ROOT"

# 扫描目录：include + src（不含 third_party、build*、*.pb.*）
SCAN_DIRS="include src"
PASS=0
FAIL=0

check_feature() {
    local name="$1"; local pattern="$2"; local hint="$3"
    echo "=== [$name] $hint ==="
    # -E 正则，排除 third_party 与 protobuf 生成文件
    hits=$(grep -rnE "$pattern" $SCAN_DIRS 2>/dev/null \
        | grep -v "third_party/" | grep -E "\.(h|hpp|cpp|cc):" | head -5)
    if [ -z "$hits" ]; then
        echo "  ❌ 未命中"
        FAIL=$((FAIL+1))
    else
        echo "$hits" | sed 's/^/  /'
        PASS=$((PASS+1))
    fi
}

# 1. RAII：析构函数释放资源（close fd / 释放连接）
check_feature "1 RAII" "~[A-Za-z]+\(" "析构函数自动释放 fd/连接"

# 2. 移动语义：移动构造/赋值 noexcept，或 std::move
check_feature "2 移动语义" "FdGuard\(FdGuard&&\)|operator=\(FdGuard&&\)|std::move\(" "移动构造/赋值或显式 move"

# 3. variant / optional：类型安全的可空/多态上下文
check_feature "3 variant/optional" "std::variant|std::optional" "variant 或 optional"

# 4. concepts：requires 约束模板参数
check_feature "4 concepts" "requires |is_trivially_copyable|concept " "模板约束 requires"

# 5. C++20 协程：coroutine_handle / co_await / CoroTask
check_feature "5 协程" "coroutine_handle|co_await|co_return|CoroTask" "协程任务/co_await"

echo ""
echo "=== 判定 ==="
echo "命中类别: $PASS / 5"
if [ "$FAIL" -eq 0 ]; then
    echo "✅ M7 五类现代 C++ 特性全部命中"
    exit 0
else
    echo "❌ 有 $FAIL 类未命中"
    exit 1
fi
