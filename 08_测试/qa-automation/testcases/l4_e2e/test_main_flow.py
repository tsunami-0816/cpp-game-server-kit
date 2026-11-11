# -*- coding: utf-8 -*-
"""L4 端到端：登录 → 建房 → 双人进房 → 发帧 → 广播段到达 → 断线重连拉房间态。

P0 主路径，覆盖 MVP 一句话链路（基线 §1）。
"""
import time

import pytest

from common.assert_util import assert_code, assert_members_contain


@pytest.mark.l4
@pytest.mark.p0
def test_main_flow_login_room_frame_rejoin(seed_user1, seed_user2, battle_factory):
    # 1. user1 建房
    c1 = battle_factory()
    room = c1.create_room(seed_user1.token, seed_user1.uid)
    assert_code(room.code, 0, f"建房失败 msg={room.msg}")
    assert room.room_id >= 1000

    # 2. user2 进房，成员列表双方在册
    c2 = battle_factory()
    join = c2.join_room(seed_user2.token, room.room_id, seed_user2.uid)
    assert_code(join.code, 0, f"进房失败 msg={join.msg}")
    assert_members_contain(join.members, [seed_user1.uid, seed_user2.uid])

    # 3. 双方上报操作输入
    c1.send_frame(room.room_id, seed_user1.uid, 42)
    c2.send_frame(room.room_id, seed_user2.uid, 7)

    # 4. 等待至少一个 100ms 广播 tick，成员收到 KCP 封装段
    time.sleep(0.25)
    seg1 = c1.recv_segment(timeout=1.5)
    assert seg1 is not None and len(seg1) > 0, "成员未收到广播段"

    # 5. user1 断线后用新 socket 重连，拉房间态
    c1.close()
    c3 = battle_factory()
    rejoin = c3.rejoin_room(seed_user1.token, room.room_id, seed_user1.uid)
    assert_code(rejoin.code, 0, f"重连失败 msg={rejoin.msg}")
    assert rejoin.frame_no >= 0

    # 6. 重连后上报一帧触发下一轮广播，验证新会话在成员表内能收到后续广播段
    #    （服务端仅在 history 非空时广播，无新帧不下行——既定帧同步语义）
    c3.send_frame(room.room_id, seed_user1.uid, 99)
    time.sleep(0.2)
    seg2 = c3.recv_segment(timeout=1.5)
    assert seg2 is not None and len(seg2) > 0, "重连后未再收到广播段"
