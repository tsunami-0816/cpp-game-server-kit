#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探索演示（给第一次上手的人看的）：
一步步用客户端脚本给服务器发包，每一步先用大白话讲“在干嘛、看什么”，再把回包字段翻译成人话。
不是断言式测试，跑通不通都会打印预期 vs 实际，方便你照着猜下一次会发生什么。

运行前提：服务已拉起（gateway TCP 8001 / battle UDP 8002 / Redis 6380）。
直接跑：PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 explore_demo.py
"""
import socket, struct, time, os, sys, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_pb2

GW_HOST, GW_PORT = "127.0.0.1", 8001
BT_HOST, BT_PORT = "127.0.0.1", 8002

# 错误码人话表
CODE_MSG = {
    0: "成功",
    1001: "用户不存在",
    1002: "密码错误",
    1003: "登录凭证(token)无效/过期/被冒充",
    2001: "房间不存在",
    2002: "房间已满员",
}


def line(c="—"):
    print(c * 64)


def say(text):
    print(f"\n【{text}】")


def login(username, password):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((GW_HOST, GW_PORT))
    req = game_pb2.LoginReq()
    req.username = username
    req.password = password
    s.sendall(struct.pack(">I", len(req.SerializeToString())) + req.SerializeToString())
    header = s.recv(4)
    blen = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < blen:
        buf += s.recv(blen - len(buf))
    rsp = game_pb2.LoginRsp()
    rsp.ParseFromString(buf)
    s.close()
    return rsp


def battle_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    return s


def send_battle(sock, msg_type, pb):
    sock.sendto(bytes([msg_type]) + pb.SerializeToString(), (BT_HOST, BT_PORT))


def udp_expect(sock, expected_type, pb_cls, deadline=3.0):
    end = time.time() + deadline
    while time.time() < end:
        sock.settimeout(2)
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            break
        if len(data) > 0 and data[0] == expected_type:
            msg = pb_cls()
            msg.ParseFromString(data[1:])
            return msg
    return None


def main():
    line("=")
    print("cpp-game-server-kit 探索演示  ·  全程用两个种子账号：user1 / user2，密码都是 123456")
    line("=")

    # ---------- 第 1 步：登录 user1 ----------
    say("第 1 步 · 登录 user1（正向，应该成功）")
    print("动作：把用户名+密码发给网关 8001；服务器查 MySQL 核对密码，通过后发一张“令牌 token”回来。")
    r1 = login("user1", "123456")
    print(f"回包：code={r1.code}（{CODE_MSG.get(r1.code,'未知')}） uid={r1.uid} "
          f"token={r1.token[:16]}…（共 {len(r1.token)} 位） msg={r1.msg}")
    print("人话：code=0 就是登录成功；uid 是账号编号；token 是后面进房间要出示的“门禁牌”。")
    token1, uid1 = r1.token, r1.uid

    # ---------- 第 2 步：登录 user2 ----------
    say("第 2 步 · 登录 user2（正向，应该成功）")
    r2 = login("user2", "123456")
    print(f"回包：code={r2.code}（{CODE_MSG.get(r2.code,'未知')}） uid={r2.uid} "
          f"token={r2.token[:16]}… msg={r2.msg}")
    token2, uid2 = r2.token, r2.uid

    # ---------- 第 3 步：user1 建房 ----------
    say("第 3 步 · user1 创建房间（要出示 token 门禁牌）")
    print("动作：把 token+uid 发给战斗服 8002，请它开一个新房间。")
    s1 = battle_socket()
    cr = game_pb2.CreateRoomReq(); cr.token = token1; cr.uid = uid1
    send_battle(s1, 1, cr)
    rc = udp_expect(s1, 2, game_pb2.CreateRoomRsp)
    room_a = rc.room_id if rc else None
    print(f"回包：code={rc.code if rc else '超时无回包'}（{CODE_MSG.get(rc.code,'超时')}） room_id={room_a} msg={rc.msg if rc else ''}")
    print("人话：code=0 且 room_id≥1000 就是建房成功；这个房号后面进房/重连都要填。")

    # ---------- 第 4 步：user2 进房 ----------
    say("第 4 步 · user2 加入刚才那个房间")
    print("动作：user2 带上自己的 token，报房号加入；回包 members 是当前房内所有人的 uid 列表。")
    s2 = battle_socket()
    j = game_pb2.JoinRoomReq(); j.token = token2; j.room_id = room_a; j.uid = uid2
    send_battle(s2, 3, j)
    rj = udp_expect(s2, 4, game_pb2.JoinRoomRsp)
    print(f"回包：code={rj.code if rj else '超时无回包'}（{CODE_MSG.get(rj.code,'超时')}） "
          f"members={list(rj.members) if rj else '-'} msg={rj.msg if rj else ''}")
    print("人话：members 同时包含 1 和 2，说明两人都在同一间房里。")

    # ---------- 第 5 步：发帧 + 等广播 ----------
    say("第 5 步 · 两人各发一帧操作，等服务器广播")
    print("动作：FrameInput 就是“这一帧我按了什么”（input 是个数字示例）；服务器每 100ms 把房里攒的帧广播给全员。")
    fi1 = game_pb2.FrameInput(); fi1.room_id = room_a; fi1.uid = uid1; fi1.input = 42
    send_battle(s1, 5, fi1)
    fi2 = game_pb2.FrameInput(); fi2.room_id = room_a; fi2.uid = uid2; fi2.input = 7
    send_battle(s2, 5, fi2)
    time.sleep(0.3)
    seg = None
    end = time.time() + 1.5
    while time.time() < end:
        s1.settimeout(0.8)
        try:
            data, _ = s1.recvfrom(2048); seg = data; break
        except socket.timeout:
            break
    print(f"收到 UDP 广播段：{len(seg) if seg else 0} 字节（KCP 封装；裸脚本不解析里面的帧内容，能收到段就说明广播链路通）")

    # ---------- 第 6 步：断线重连 ----------
    say("第 6 步 · 断线后重新回到房间（重连）")
    print("动作：关掉旧连接，拿新连接带着 token 调 Rejoin；回带 frame_no（当前帧号）和 history（还没广播的积压帧）。")
    s1.close()  # 模拟断线
    sr = battle_socket()
    rr = game_pb2.RejoinRoomReq(); rr.token = token1; rr.room_id = room_a; rr.uid = uid1
    send_battle(sr, 7, rr)
    rrsp = udp_expect(sr, 8, game_pb2.RejoinRoomRsp)
    hist = list(rrsp.history) if rrsp else []
    print(f"回包：code={rrsp.code if rrsp else '超时无回包'}（{CODE_MSG.get(rrsp.code,'超时')}） "
          f"frame_no={rrsp.frame_no if rrsp else '-'} 积压帧={len(hist)} 条 msg={rrsp.msg if rrsp else ''}")
    for h in hist[:3]:
        print(f"    积压帧：uid={h.uid} input={h.input}")
    print("人话：code=0 就重连成功；history 是掉线期间攒下、还没来得及广播给你的帧。")
    sr.close(); s2.close()

    line()
    print("接下来是反向用例：故意填错东西，看服务器怎么拒绝。")

    # ---------- 第 7 步：反向用例 ----------
    say("第 7.1 · 密码故意填错（预期 1002）")
    rw = login("user1", "wrongpass")
    print(f"回包：code={rw.code}（{CODE_MSG.get(rw.code,'未知')}） msg={rw.msg}")

    say("第 7.2 · 填一个不存在的账号（预期 1001）")
    rn = login("nobody_xyz", "123456")
    print(f"回包：code={rn.code}（{CODE_MSG.get(rn.code,'未知')}） msg={rn.msg}")

    say("第 7.3 · 伪造一个假 token 去建房（预期 1003）")
    sf = battle_socket()
    fc = game_pb2.CreateRoomReq(); fc.token = "fake-token-not-in-redis"; fc.uid = uid1
    send_battle(sf, 1, fc)
    rf = udp_expect(sf, 2, game_pb2.CreateRoomRsp)
    print(f"回包：code={rf.code if rf else '超时无回包'}（{CODE_MSG.get(rf.code,'超时')}） msg={rf.msg if rf else ''}")
    sf.close()

    say("第 7.4 · 进一个不存在的房号（预期 2001）")
    sj = battle_socket()
    jn = game_pb2.JoinRoomReq(); jn.token = token2; jn.room_id = 999999; jn.uid = uid2
    send_battle(sj, 3, jn)
    rjn = udp_expect(sj, 4, game_pb2.JoinRoomRsp)
    print(f"回包：code={rjn.code if rjn else '超时无回包'}（{CODE_MSG.get(rjn.code,'超时')}） msg={rjn.msg if rjn else ''}")
    sj.close()

    line("=")
    print("演示结束。想自己试：改本文件里 login(...) 的账号/密码、room_id、input 数字，再跑一次看回包变化。")
    print("种子账号只有 user1 / user2（密码 123456）；其余账号都会被 1001 拒绝。")
    line("=")


if __name__ == "__main__":
    main()
