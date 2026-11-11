# -*- coding: utf-8 -*-
"""protobuf 兼容加载。

scripts/game_pb2.py 由 protoc 3.12 旧风格生成，与 protobuf 7.x C++ 运行时不兼容；
测试客户端只做小包序列化，统一切到纯 Python 解析实现（基线/报告已注明该取舍）。
必须在 import game_pb2 之前设置环境变量。
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

_QA_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _QA_DIR.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import game_pb2  # noqa: E402

pb2 = game_pb2

# 消息类型头（与 main_gateway.cpp / main_battle.cpp 保持一致）
MSG = {
    "CreateRoomReq": 1, "CreateRoomRsp": 2,
    "JoinRoomReq": 3, "JoinRoomRsp": 4,
    "FrameInput": 5, "FrameBroadcast": 6,
    "RejoinRoomReq": 7, "RejoinRoomRsp": 8,
}
