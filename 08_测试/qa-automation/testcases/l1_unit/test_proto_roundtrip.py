# -*- coding: utf-8 -*-
"""L1 单元：protobuf 消息序列化→反序列化字段往返一致（不碰网络/DB）。"""
import pytest

from common.proto_util import pb2


@pytest.mark.l1
def test_login_req_roundtrip():
    req = pb2.LoginReq()
    req.username = "user1"
    req.password = "123456"
    again = pb2.LoginReq()
    again.ParseFromString(req.SerializeToString())
    assert again.username == "user1"
    assert again.password == "123456"


@pytest.mark.l1
def test_login_rsp_roundtrip():
    rsp = pb2.LoginRsp()
    rsp.code = 0
    rsp.token = "ab" * 32
    rsp.uid = 1
    rsp.msg = "ok"
    again = pb2.LoginRsp()
    again.ParseFromString(rsp.SerializeToString())
    assert again.code == 0
    assert again.uid == 1
    assert again.token == "ab" * 32
    assert again.msg == "ok"


@pytest.mark.l1
def test_join_room_rsp_repeated_members():
    rsp = pb2.JoinRoomRsp()
    rsp.code = 0
    rsp.members.extend([1, 2])
    again = pb2.JoinRoomRsp()
    again.ParseFromString(rsp.SerializeToString())
    assert list(again.members) == [1, 2]


@pytest.mark.l1
def test_frame_input_roundtrip():
    frame = pb2.FrameInput()
    frame.room_id = 1000
    frame.uid = 1
    frame.input = 42
    again = pb2.FrameInput()
    again.ParseFromString(frame.SerializeToString())
    assert again.room_id == 1000
    assert again.uid == 1
    assert again.input == 42


@pytest.mark.l1
def test_rejoin_rsp_history_repeated():
    rsp = pb2.RejoinRoomRsp()
    rsp.code = 0
    rsp.frame_no = 3
    f = rsp.history.add()
    f.room_id = 1000
    f.uid = 1
    f.input = 7
    again = pb2.RejoinRoomRsp()
    again.ParseFromString(rsp.SerializeToString())
    assert again.frame_no == 3
    assert len(again.history) == 1
    assert again.history[0].input == 7
