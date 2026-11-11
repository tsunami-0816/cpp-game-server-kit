#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M3 内存检测业务探针：分别打 ASan/Valgrind 版 gateway 与 battle 的关键路径。

用法:
    python3 memcheck_probe.py --target gateway
    python3 memcheck_probe.py --target battle
探针只验证链路跑通并触发被测代码路径；内存问题由 ASan/Valgrind 在服务端日志判定。
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.gateway_client import GatewayClient  # noqa: E402
from common.battle_client import BattleClient  # noqa: E402


def probe_gateway():
    gw = GatewayClient()
    r1 = gw.login("user1", "123456")
    print(f"[gateway] user1 login code={r1.code} uid={r1.uid}")
    assert r1.code == 0
    r2 = gw.login("user1", "wrongpass")
    print(f"[gateway] wrong password code={r2.code}")
    assert r2.code == 1002
    r3 = gw.login("nobody_xyz", "123456")
    print(f"[gateway] unknown user code={r3.code}")
    assert r3.code == 1001


def probe_battle():
    gw = GatewayClient()
    u1 = gw.login("user1", "123456")
    u2 = gw.login("user2", "123456")
    assert u1.code == 0 and u2.code == 0

    c1 = BattleClient()
    room = c1.create_room(u1.token, u1.uid)
    print(f"[battle] create room code={room.code} room_id={room.room_id}")
    assert room.code == 0

    c2 = BattleClient()
    join = c2.join_room(u2.token, room.room_id, u2.uid)
    print(f"[battle] join code={join.code} members={join.members}")
    assert join.code == 0

    c1.send_frame(room.room_id, u1.uid, 42)
    c2.send_frame(room.room_id, u2.uid, 7)
    time.sleep(0.25)
    seg = c1.recv_segment(timeout=1.0)
    print(f"[battle] broadcast segment={len(seg) if seg else 0} bytes")

    c1.close()
    c3 = BattleClient()
    rejoin = c3.rejoin_room(u1.token, room.room_id, u1.uid)
    print(f"[battle] rejoin code={rejoin.code} frame_no={rejoin.frame_no}")
    assert rejoin.code == 0
    c2.close(); c3.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["gateway", "battle"], required=True)
    args = ap.parse_args()
    if args.target == "gateway":
        probe_gateway()
    else:
        probe_battle()
    print(f"[probe] {args.target} path done")


if __name__ == "__main__":
    main()
