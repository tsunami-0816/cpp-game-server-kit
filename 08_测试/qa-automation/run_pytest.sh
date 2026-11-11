#!/bin/bash
# step8 pytest 统一入口：设置 protobuf 纯 Python 实现后调用 pytest。
# 用法: bash run_pytest.sh [pytest 参数]，例: bash run_pytest.sh -q
cd "$(dirname "$0")"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
exec python3 -m pytest "$@"
