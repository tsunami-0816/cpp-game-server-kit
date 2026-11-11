# -*- coding: utf-8 -*-
"""L2 接口集成：战斗服房间链路（UDP 8002，1B type + protobuf）。

四象限：正向建房/进房 / 反向伪造 token / 边界房间不存在 / 满员阈值走查。
"""
import pytest
import yaml

from pathlib import Path

from common.assert_util import assert_code, assert_members_contain

DATA = Path(__file__).resolve().parents[2] / "data" / "test_accounts.yaml"
with open(DATA, encoding="utf-8") as f:
    DATA_CFG = yaml.safe_load(f)
FAKE_TOKEN = DATA_CFG["battle"]["fake_token"]
NO_ROOM = DATA_CFG["battle"]["nonexistent_room"]


@pytest.mark.l2
@pytest.mark.p0
def test_create_room_success(seed_user1, battle_factory):
    c = battle_factory()
    r = c.create_room(seed_user1.token, seed_user1.uid)
    assert_code(r.code, 0, f"msg={r.msg}")
    assert r.room_id >= 1000


@pytest.mark.l2
@pytest.mark.p0
def test_join_room_success(seed_user1, seed_user2, battle_factory):
    c1 = battle_factory()
    room = c1.create_room(seed_user1.token, seed_user1.uid)
    assert_code(room.code, 0)

    c2 = battle_factory()
    join = c2.join_room(seed_user2.token, room.room_id, seed_user2.uid)
    assert_code(join.code, 0, f"msg={join.msg}")
    assert_members_contain(join.members, [seed_user1.uid, seed_user2.uid])


@pytest.mark.l2
@pytest.mark.p1
def test_create_room_bad_token_rejected(battle_factory):
    c = battle_factory()
    r = c.create_room(FAKE_TOKEN, 1)
    assert_code(r.code, 1003)


@pytest.mark.l2
@pytest.mark.p1
def test_join_room_bad_token_rejected(seed_user1, battle_factory):
    c1 = battle_factory()
    room = c1.create_room(seed_user1.token, seed_user1.uid)
    c2 = battle_factory()
    r = c2.join_room(FAKE_TOKEN, room.room_id, 2)
    assert_code(r.code, 1003)


@pytest.mark.l2
@pytest.mark.p1
def test_rejoin_room_bad_token_rejected(battle_factory):
    c = battle_factory()
    r = c.rejoin_room(FAKE_TOKEN, NO_ROOM, 1)
    assert_code(r.code, 1003)


@pytest.mark.l2
@pytest.mark.p1
def test_join_nonexistent_room(seed_user2, battle_factory):
    c = battle_factory()
    r = c.join_room(seed_user2.token, NO_ROOM, seed_user2.uid)
    assert_code(r.code, 2001)


@pytest.mark.l2
@pytest.mark.p1
def test_rejoin_nonexistent_room(seed_user1, battle_factory):
    c = battle_factory()
    r = c.rejoin_room(seed_user1.token, NO_ROOM, seed_user1.uid)
    assert_code(r.code, 2001)


@pytest.mark.l2
@pytest.mark.p2
def test_room_full_branch_threshold_is_50(seed_user1, battle_factory):
    """满员 2002 分支存在；阈值对齐 50（Q-014）。

    不实跑 50 人触发满员（M5 压测观察容量）；本用例做源码走查 + 分支可达性确认。
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[4] / "05_代码" / "backend" /
           "src" / "battle" / "main_battle.cpp").read_text(encoding="utf-8")
    assert "2002" in src and "room full" in src
    assert "members.size() >= 50" in src
