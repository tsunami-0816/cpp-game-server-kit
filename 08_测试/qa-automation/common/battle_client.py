# -*- coding: utf-8 -*-
"""战斗服 UDP 客户端：1B type 头 + protobuf body（对齐 main_battle.cpp 消息编号）。"""
import socket
import time
from dataclasses import dataclass

from .proto_util import pb2, MSG
from .config_util import CONFIG


@dataclass
class RoomResult:
    code: int
    room_id: int
    msg: str


@dataclass
class JoinResult:
    code: int
    members: list
    msg: str


@dataclass
class RejoinResult:
    code: int
    frame_no: int
    history: list
    msg: str


class BattleClient:
    def __init__(self, host: str = None, port: int = None):
        cfg = CONFIG["battle"]
        self.host = host or cfg["host"]
        self.port = port or cfg["port"]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)

    def _send(self, msg_type: int, pb) -> None:
        self.sock.sendto(bytes([msg_type]) + pb.SerializeToString(),
                         (self.host, self.port))

    def _recv(self, expect_type: int, pb_cls, deadline: float = 3.0):
        end = time.time() + deadline
        while time.time() < end:
            self.sock.settimeout(max(0.1, end - time.time()))
            try:
                data, _ = self.sock.recvfrom(2048)
            except socket.timeout:
                break
            if data and data[0] == expect_type:
                msg = pb_cls()
                msg.ParseFromString(data[1:])
                return msg
        return None

    def create_room(self, token: str, uid: int, deadline: float = 3.0) -> RoomResult:
        req = pb2.CreateRoomReq()
        req.token = token
        req.uid = uid
        self._send(MSG["CreateRoomReq"], req)
        rsp = self._recv(MSG["CreateRoomRsp"], pb2.CreateRoomRsp, deadline)
        if rsp is None:
            return RoomResult(-1, 0, "timeout")
        return RoomResult(rsp.code, rsp.room_id, rsp.msg)

    def join_room(self, token: str, room_id: int, uid: int,
                  deadline: float = 3.0) -> JoinResult:
        req = pb2.JoinRoomReq()
        req.token = token
        req.room_id = room_id
        req.uid = uid
        self._send(MSG["JoinRoomReq"], req)
        rsp = self._recv(MSG["JoinRoomRsp"], pb2.JoinRoomRsp, deadline)
        if rsp is None:
            return JoinResult(-1, [], "timeout")
        return JoinResult(rsp.code, list(rsp.members), rsp.msg)

    def rejoin_room(self, token: str, room_id: int, uid: int,
                    deadline: float = 3.0) -> RejoinResult:
        req = pb2.RejoinRoomReq()
        req.token = token
        req.room_id = room_id
        req.uid = uid
        self._send(MSG["RejoinRoomReq"], req)
        rsp = self._recv(MSG["RejoinRoomRsp"], pb2.RejoinRoomRsp, deadline)
        if rsp is None:
            return RejoinResult(-1, -1, [], "timeout")
        return RejoinResult(rsp.code, rsp.frame_no, list(rsp.history), rsp.msg)

    def send_frame(self, room_id: int, uid: int, inp: int) -> None:
        frame = pb2.FrameInput()
        frame.room_id = room_id
        frame.uid = uid
        frame.input = inp
        self._send(MSG["FrameInput"], frame)

    def recv_segment(self, timeout: float = 1.5):
        """收一段原始 UDP 数据（KCP 封装段，裸客户端不强解 FrameBroadcast）。"""
        end = time.time() + timeout
        while time.time() < end:
            self.sock.settimeout(max(0.1, end - time.time()))
            try:
                data, _ = self.sock.recvfrom(2048)
                return data
            except socket.timeout:
                break
        return None

    def close(self) -> None:
        self.sock.close()
