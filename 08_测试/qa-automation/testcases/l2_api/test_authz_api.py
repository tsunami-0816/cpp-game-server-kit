# -*- coding: utf-8 -*-
"""L2 鉴权与越权：token/uid 匹配、重复登录覆盖、已知缺陷 xfail（Q-016/Q-017）。"""
from pathlib import Path

import pytest

from common.assert_util import assert_code
from api import auth_api, battle_api

SRC_BATTLE = (Path(__file__).resolve().parents[4] / "05_代码" / "backend" /
              "src" / "battle" / "main_battle.cpp")


@pytest.mark.l2
@pytest.mark.p1
def test_token_uid_mismatch_rejected(battle_factory):
    """user2 的 token 冒充 uid=1 建房：checkToken 查 session:1 不匹配 → 1003。"""
    u2 = auth_api.login("user2", "123456")
    c = battle_factory()
    r = c.create_room(u2.token, 1)  # token 属于 uid2，却声明 uid1
    assert_code(r.code, 1003)


@pytest.mark.l2
@pytest.mark.p1
def test_relogin_overrides_old_token(battle_factory):
    first = auth_api.login("user1", "123456")
    second = auth_api.login("user1", "123456")

    old = battle_factory()
    r_old = old.create_room(first.token, first.uid)
    assert_code(r_old.code, 1003)  # 旧 token 已被覆盖，失效

    new = battle_factory()
    r_new = new.create_room(second.token, second.uid)
    assert_code(r_new.code, 0)


@pytest.mark.l2
@pytest.mark.p2
@pytest.mark.xfail(reason="Q-016：members 按 uid 不去重，重复 Join 重复追加（P2 deferred）",
                   strict=False)
def test_members_dedup_by_uid(seed_user1, battle_factory):
    """同一 uid 重复进房，成员表应去重为 1 条；当前实现 push_back 不去重（已知缺陷）。"""
    c1 = battle_factory()
    room = c1.create_room(seed_user1.token, seed_user1.uid)
    c2 = battle_factory()
    join = c2.join_room(seed_user1.token, room.room_id, seed_user1.uid)
    assert join.members.count(seed_user1.uid) == 1


@pytest.mark.l2
@pytest.mark.p2
@pytest.mark.xfail(reason="Q-017：FrameInput 入口无 token 校验/房间归属校验（P2 deferred，step8.5 复核）",
                   strict=False)
def test_frame_input_requires_auth(seed_user1, battle_factory):
    """无登录态 socket 向存在房间发帧，应被鉴权/归属校验拒绝；当前静默接受（已知缺陷）。"""
    c1 = battle_factory()
    room = c1.create_room(seed_user1.token, seed_user1.uid)

    intruder = battle_factory()
    intruder.send_frame(room.room_id, 99999, 1)  # 无 token、冒充 uid
    seg = intruder.recv_segment(timeout=0.6)
    # 期望：服务端回错误码（1003/归属拒绝）；当前无任何拒绝响应
    assert seg is not None and seg[0] in (2, 4, 8), "FrameInput 未做鉴权/归属校验"
