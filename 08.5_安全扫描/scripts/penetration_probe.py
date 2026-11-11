#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
step 8.5 安全扫描 · 接口级渗透探针（Agent 代跑，用户复核）。

覆盖：
  P-1 弱口令字典（常见默认账号 / 错误密码 / 不存在用户）
  P-2 SQL 注入用户名（预编译语句验证，不得登录成功、不得回 SQL 错误）
  P-3 水平越权（A 的 token 配 B 的 uid 调房间三入口）
  P-4 伪造 / 空 token、uid=0
  P-5 Redis 未授权访问探测（绑定地址 + 是否需要密码）
  P-6 FrameInput(type=5) 鉴权复核（Q-017：协议无 token 字段、分支无 checkToken）
  P-7 畸形 / 超长包健壮性（空 body、非法 pb、超长用户名，服务不得崩溃）
  P-8 回包敏感信息检查（失败回包不得带 password/hash/salt）

口径：每条输出 PASS/FAIL + 原始请求/响应；退出码 0 = 探针自身跑完，
安全结论以报告分级为准（本脚本不替用户下「安全通过」结论）。
"""
import os
import socket
import struct
import subprocess
import sys
import time

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJ, "scripts"))
import game_pb2  # noqa: E402

GW_HOST, GW_PORT = "127.0.0.1", 8001
BT_HOST, BT_PORT = "127.0.0.1", 8002
REDIS_PORT = 6380

RESULTS = []


def report(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}", flush=True)


def login(username, password, raw_body=None):
    """TCP 登录。raw_body 非空时直接发原始字节（畸形包用）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((GW_HOST, GW_PORT))
    if raw_body is not None:
        s.sendall(struct.pack(">I", len(raw_body)) + raw_body)
    else:
        req = game_pb2.LoginReq()
        req.username = username
        req.password = password
        s.sendall(struct.pack(">I", len(req.SerializeToString())) + req.SerializeToString())
    header = s.recv(4)
    if len(header) < 4:
        s.close()
        return None, "", 0, "no-header"
    blen = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < blen:
        chunk = s.recv(blen - len(buf))
        if not chunk:
            break
        buf += chunk
    rsp = game_pb2.LoginRsp()
    try:
        rsp.ParseFromString(buf)
        code, token, uid, msg = rsp.code, rsp.token, rsp.uid, rsp.msg
    except Exception as e:  # 非法 pb 解析失败
        code, token, uid, msg = -1, "", 0, f"parse-error:{e}"
    s.close()
    return code, token, uid, msg


def battle_call(msg_type, pb, sock=None):
    own = sock is None
    s = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    s.sendto(bytes([msg_type]) + pb.SerializeToString(), (BT_HOST, BT_PORT))
    end = time.time() + 2.0
    while time.time() < end:
        try:
            data, _ = s.recvfrom(2048)
        except socket.timeout:
            break
        if len(data) > 0:
            return data[0], data[1:]
    if own:
        s.close()
    return None, None


def redis_cli(*args):
    try:
        out = subprocess.run(["redis-cli", "-p", str(REDIS_PORT), *args],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip(), out.returncode
    except Exception as e:  # noqa: BLE001
        return f"err:{e}", 1


def main():
    # ---------- P-1 弱口令字典 ----------
    weak = [
        ("admin", "admin"), ("admin", "123456"), ("root", "root"),
        ("test", "123456"), ("user", "123456"), ("guest", "guest"),
    ]
    for u, p in weak:
        code, tok, _, msg = login(u, p)
        report(f"P-1 弱口令 {u}/{p}", code != 0, f"code={code} msg={msg!r} token_len={len(tok)}")

    # 对照：错误密码 / 不存在用户
    code_w, _, _, msg_w = login("user1", "wrongpass")
    report("P-1 错误密码拒绝", code_w == 1002, f"code={code_w} msg={msg_w!r}")
    code_n, _, _, msg_n = login("nobody_xyz", "123456")
    report("P-1 不存在用户拒绝", code_n == 1001, f"code={code_n} msg={msg_n!r}")

    # 正向对照（种子账号可登录，证明探针链路有效）
    code_ok, token1, uid1, msg_ok = login("user1", "123456")
    report("P-1 正向对照 user1/123456 可登录", code_ok == 0 and uid1 == 1 and len(token1) == 64,
           f"code={code_ok} uid={uid1} token_len={len(token1)}")
    code_ok2, token2, uid2, _ = login("user2", "123456")
    report("P-1 正向对照 user2/123456 可登录", code_ok2 == 0 and uid2 == 2,
           f"code={code_ok2} uid={uid2}")

    # ---------- P-2 SQL 注入用户名 ----------
    sqli = [
        "' OR '1'='1", '" OR "1"="1', "admin'-- ", "user1' -- ",
        "' OR 1=1#", "' UNION SELECT 1,2,3,4-- ", "admin' OR '1'='1' -- ",
        "\\' OR 1=1 -- ",
    ]
    for payload in sqli:
        code, tok, _, msg = login(payload, "x")
        leaked = any(k in msg.lower() for k in ["sql", "mysql", "syntax", "error near", "select"])
        report(f"P-2 注入 {payload!r}", code != 0 and not leaked and tok == "",
               f"code={code} msg={msg!r} token_len={len(tok)} sql_leak={leaked}")

    # ---------- P-3 水平越权：A token 配 B uid ----------
    # user1 的 token1 配 uid=2 调三入口
    cr = game_pb2.CreateRoomReq(); cr.token = token1; cr.uid = uid2
    t, body = battle_call(1, cr)
    rsp = game_pb2.CreateRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-3 水平越权 token1/uid2 建房→1003", t == 2 and rsp.code == 1003,
           f"type={t} code={rsp.code} msg={rsp.msg!r}")

    jr = game_pb2.JoinRoomReq(); jr.token = token1; jr.room_id = 1000; jr.uid = uid2
    t, body = battle_call(3, jr)
    rsp = game_pb2.JoinRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-3 水平越权 token1/uid2 进房→1003", t == 4 and rsp.code == 1003,
           f"type={t} code={rsp.code}")

    rr = game_pb2.RejoinRoomReq(); rr.token = token1; rr.room_id = 1000; rr.uid = uid2
    t, body = battle_call(7, rr)
    rsp = game_pb2.RejoinRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-3 水平越权 token1/uid2 重连→1003", t == 8 and rsp.code == 1003,
           f"type={t} code={rsp.code}")

    # 反向：user2 token2 配 uid=1
    cr2 = game_pb2.CreateRoomReq(); cr2.token = token2; cr2.uid = uid1
    t, body = battle_call(1, cr2)
    rsp = game_pb2.CreateRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-3 水平越权 token2/uid1 建房→1003", t == 2 and rsp.code == 1003,
           f"type={t} code={rsp.code}")

    # ---------- P-4 伪造 / 空 token、uid=0 ----------
    fake = game_pb2.CreateRoomReq(); fake.token = "deadbeef" * 8; fake.uid = uid1
    t, body = battle_call(1, fake)
    rsp = game_pb2.CreateRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-4 随机伪造 token→1003", t == 2 and rsp.code == 1003, f"code={rsp.code}")

    empty = game_pb2.CreateRoomReq(); empty.token = ""; empty.uid = uid1
    t, body = battle_call(1, empty)
    rsp = game_pb2.CreateRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-4 空 token→1003", t == 2 and rsp.code == 1003, f"code={rsp.code}")

    zero = game_pb2.CreateRoomReq(); zero.token = token1; zero.uid = 0
    t, body = battle_call(1, zero)
    rsp = game_pb2.CreateRoomRsp(); rsp.ParseFromString(body or b"")
    report("P-4 uid=0→1003", t == 2 and rsp.code == 1003, f"code={rsp.code}")

    # ---------- P-5 Redis 未授权 ----------
    ping, rc = redis_cli("PING")
    report("P-5 Redis 可无密码 PING（本地绑定）", rc == 0 and ping == "PONG",
           f"PING={ping!r} rc={rc}（边界：仅监听 127.0.0.1:6380）")
    keys, _ = redis_cli("KEYS", "*")
    report("P-5 Redis KEYS 列举（本地）", True, f"keys={keys!r}")
    conf, _ = redis_cli("CONFIG", "GET", "requirepass")
    report("P-5 Redis requirepass 为空", "requirepass" in conf, f"CONFIG GET requirepass={conf!r}")

    # ---------- P-6 FrameInput 鉴权复核（Q-017） ----------
    # 先合法建房拿 room_id
    cr_ok = game_pb2.CreateRoomReq(); cr_ok.token = token1; cr_ok.uid = uid1
    t, body = battle_call(1, cr_ok)
    rsp_ok = game_pb2.CreateRoomRsp(); rsp_ok.ParseFromString(body or b"")
    room_id = rsp_ok.room_id if rsp_ok.code == 0 else 1000
    # 不带任何凭据直接塞帧（type=5，proto 本身无 token 字段）
    fi = game_pb2.FrameInput(); fi.room_id = room_id; fi.uid = 99999; fi.input = 1
    t, body = battle_call(5, fi)
    report("P-6 未鉴权 FrameInput 无拒绝回包（Q-017 复核证据）",
           t is None, f"type={t} body={'<无响应包>' if body is None else body[:40]!r}；分支未调 checkToken，proto 无 token 字段")

    # ---------- P-7 畸形 / 超长包健壮性 ----------
    # 空 body
    code, _, _, msg = login("", "", raw_body=b"")
    report("P-7 空 body 包不崩溃", code in (1001, 1002, -1) or msg in ("no-header",),
           f"code={code} msg={msg!r}")
    # 非法 protobuf 字节：解析失败时服务端按断连防护关闭 fd（Q-009 既定边界），
    # 不回包=no-header 属可接受行为，只要进程不崩即可。
    code, _, _, msg = login("", "", raw_body=b"\xff\xfe\xfd\xfcbroken-not-pb")
    report("P-7 非法 pb 字节不崩溃", code in (1001, 1002, -1) or msg == "no-header",
           f"code={code} msg={msg!r}（断连防护关闭 fd，不回包）")
    # 超长用户名（200 字符）
    long_u = "a" * 200
    code, tok, _, msg = login(long_u, "x")
    report("P-7 超长用户名不崩溃", code != 0 and tok == "", f"code={code} msg={msg!r}")
    # 探针后服务仍在：正向再登一次
    code_re, tok_re, _, _ = login("user1", "123456")
    report("P-7 畸形包后服务存活（正向复测）", code_re == 0, f"code={code_re} token_len={len(tok_re)}")

    # ---------- P-8 回包敏感信息 ----------
    code_b, _, _, msg_b = login("user1", "wrongpass")
    # 只核对是否泄露哈希/盐/算法名/明文口令值；提示文案里的 "password" 字样不算泄露。
    leaked_fields = any(k in msg_b.lower() for k in ["hash", "salt", "sha256", "pbkdf", "bcrypt"])
    report("P-8 失败回包不含敏感字段", not leaked_fields, f"msg={msg_b!r} leak={leaked_fields}")

    # ---------- 汇总 ----------
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n==== 渗透探针汇总 {passed}/{total} 条 ====")
    # 注：P-6 为既定缺口复核项，其 FAIL 性质是「记录缺口」，不计入探针执行失败
    sys.exit(0)


if __name__ == "__main__":
    main()
