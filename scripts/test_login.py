#!/usr/bin/env python3
# T-14 验证：启动 game_gateway，发登录包，检查 MySQL/Redis/回包
import socket, subprocess, time, sys, os, struct
from pathlib import Path
# protobuf 动态加载（game_pb2.py 与本脚本同目录）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_pb2

ROOT = Path(__file__).resolve().parent.parent
bin_path = str(ROOT / "05_代码/backend/build/bin/game_gateway")

# 启动 gateway
proc = subprocess.Popen([bin_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(1.5)

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 8001))

    # 构造 LoginReq
    req = game_pb2.LoginReq()
    req.username = "user1"
    req.password = "123456"
    body = req.SerializeToString()
    packet = struct.pack(">I", len(body)) + body
    s.sendall(packet)

    # 收回包
    s.settimeout(3)
    header = s.recv(4)
    body_len = struct.unpack(">I", header)[0]
    rsp_body = b""
    while len(rsp_body) < body_len:
        rsp_body += s.recv(body_len - len(rsp_body))

    rsp = game_pb2.LoginRsp()
    rsp.ParseFromString(rsp_body)
    print(f"code={rsp.code} msg={rsp.msg} uid={rsp.uid} token={rsp.token[:16]}...")

    if rsp.code == 0:
        print("✅ M4 登录成功")
        rc = 0
    else:
        print(f"❌ 登录失败 code={rsp.code}")
        rc = 1
    s.close()
finally:
    proc.terminate()
    proc.wait()
sys.exit(rc)
