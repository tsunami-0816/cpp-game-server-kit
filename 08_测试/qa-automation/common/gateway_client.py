# -*- coding: utf-8 -*-
"""网关 TCP 客户端：4B 大端长度头 + protobuf body（对齐 Codec.h / main_gateway.cpp）。"""
import socket
import struct
import time
from dataclasses import dataclass

from .proto_util import pb2
from .config_util import CONFIG


@dataclass
class LoginResult:
    code: int
    token: str
    uid: int
    msg: str
    rt_ms: float


class GatewayClient:
    def __init__(self, host: str = None, port: int = None):
        cfg = CONFIG["gateway"]
        self.host = host or cfg["host"]
        self.port = port or cfg["port"]

    def login(self, username: str, password: str, timeout: float = 3.0) -> LoginResult:
        req = pb2.LoginReq()
        req.username = username
        req.password = password
        body = req.SerializeToString()

        t0 = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((self.host, self.port))
            s.sendall(struct.pack(">I", len(body)) + body)
            header = s.recv(4)
            if len(header) < 4:
                return LoginResult(-1, "", 0, "header truncated", (time.time() - t0) * 1000)
            blen = struct.unpack(">I", header)[0]
            buf = b""
            while len(buf) < blen:
                chunk = s.recv(blen - len(buf))
                if not chunk:
                    break
                buf += chunk
            rsp = pb2.LoginRsp()
            rsp.ParseFromString(buf)
            return LoginResult(rsp.code, rsp.token, rsp.uid, rsp.msg,
                               (time.time() - t0) * 1000)
        finally:
            s.close()
