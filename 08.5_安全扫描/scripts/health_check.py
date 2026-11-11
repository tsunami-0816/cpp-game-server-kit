#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8.5 交接前正向探活：user1 登录 + Redis 残留核对。"""
import os
import socket
import struct
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import game_pb2  # noqa: E402

s = socket.socket()
s.settimeout(3)
s.connect(("127.0.0.1", 8001))
r = game_pb2.LoginReq()
r.username = "user1"
r.password = "123456"
s.sendall(struct.pack(">I", len(r.SerializeToString())) + r.SerializeToString())
h = s.recv(4)
bl = struct.unpack(">I", h)[0]
b = b""
while len(b) < bl:
    b += s.recv(bl - len(b))
rsp = game_pb2.LoginRsp()
rsp.ParseFromString(b)
print(f"login code={rsp.code} uid={rsp.uid} token_len={len(rsp.token)}")
s.close()

keys = subprocess.run(["redis-cli", "-p", "6380", "keys", "*"],
                      capture_output=True, text=True).stdout.strip()
print(f"redis keys: {keys or '(empty)'}")
