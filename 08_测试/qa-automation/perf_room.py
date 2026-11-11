#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M5 战斗服 50 人房间压测（Python 多线程 UDP 客户端）。

覆盖：建房 → N 人进房成功率 → 帧上报吞吐 → 断线重连恢复耗时 → 服务端 CPU 采样。
边界（诚实记录）：广播走 KCP(ikcp_send)，裸 Python UDP 客户端只见 KCP 封装段，
无法解出应用层 FrameBroadcast 时间戳，故「广播 P99 < 50ms」在本客户端模型下不可测，
报告中标为未验证项，不以收到段时长冒充应用层广播延迟。

用法:
    python3 perf_room.py [--clients 50] [--duration 10]
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.proto_util import pb2, MSG  # noqa: E402
from common.config_util import CONFIG  # noqa: E402
from common.gateway_client import GatewayClient  # noqa: E402

QA_ROOT = Path(__file__).resolve().parent
REPORT = QA_ROOT / "reports" / "perf_room.json"
BT = CONFIG["battle"]


class RoomClient:
    def __init__(self, idx, token, uid):
        self.idx = idx
        self.token = token
        self.uid = uid
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)
        self.room_id = 0
        self.frames_sent = 0
        self.segments_recv = 0

    def _send(self, mtype, pb):
        self.sock.sendto(bytes([mtype]) + pb.SerializeToString(), (BT["host"], BT["port"]))

    def _recv(self, expect_type, pb_cls, deadline=3.0):
        end = time.time() + deadline
        while time.time() < end:
            self.sock.settimeout(max(0.1, end - time.time()))
            try:
                data, _ = self.sock.recvfrom(2048)
            except socket.timeout:
                return None
            if data and data[0] == expect_type:
                msg = pb_cls()
                msg.ParseFromString(data[1:])
                return msg
        return None

    def create_room(self):
        req = pb2.CreateRoomReq(); req.token = self.token; req.uid = self.uid
        self._send(MSG["CreateRoomReq"], req)
        rsp = self._recv(MSG["CreateRoomRsp"], pb2.CreateRoomRsp)
        if rsp and rsp.code == 0:
            self.room_id = rsp.room_id
        return rsp.code if rsp else -1

    def join(self):
        req = pb2.JoinRoomReq(); req.token = self.token
        req.room_id = self.room_id; req.uid = self.uid
        self._send(MSG["JoinRoomReq"], req)
        rsp = self._recv(MSG["JoinRoomRsp"], pb2.JoinRoomRsp)
        return rsp.code if rsp else -1

    def rejoin(self):
        req = pb2.RejoinRoomReq(); req.token = self.token
        req.room_id = self.room_id; req.uid = self.uid
        t0 = time.time()
        self._send(MSG["RejoinRoomReq"], req)
        rsp = self._recv(MSG["RejoinRoomRsp"], pb2.RejoinRoomRsp)
        rt = (time.time() - t0) * 1000
        return (rsp.code if rsp else -1), rt

    def send_frame(self, inp):
        f = pb2.FrameInput(); f.room_id = self.room_id
        f.uid = self.uid; f.input = inp
        self._send(MSG["FrameInput"], f)
        self.frames_sent += 1

    def close(self):
        self.sock.close()


def battle_cpu() -> str:
    p = subprocess.run(["ps", "-C", "battle_server", "-o", "%cpu=,nlwp="],
                       capture_output=True, text=True, timeout=5)
    return p.stdout.strip() or "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=50)
    ap.add_argument("--duration", type=float, default=10.0)
    args = ap.parse_args()

    gw = GatewayClient()
    u1 = gw.login("user1", "123456")
    u2 = gw.login("user2", "123456")
    assert u1.code == 0 and u2.code == 0, f"压测前置登录失败: {u1.code}/{u2.code}"
    tokens = [(u1.token, u1.uid), (u2.token, u2.uid)]

    clients = [RoomClient(i, tokens[i % 2][0], tokens[i % 2][1]) for i in range(args.clients)]

    # 1. 建房
    host = clients[0]
    create_code = host.create_room()
    room_id = host.room_id
    for c in clients:  # 回填房间号给所有客户端
        c.room_id = room_id
    print(f"建房 code={create_code} room_id={room_id}")

    # 2. 其余客户端进房（并发）
    join_codes = {}
    join_lock = threading.Lock()

    def join_worker(c):
        code = c.join()
        with join_lock:
            join_codes[c.idx] = code

    threads = [threading.Thread(target=join_worker, args=(c,)) for c in clients[1:]]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    join_elapsed = time.time() - t0

    code_dist = {}
    for code in join_codes.values():
        code_dist[str(code)] = code_dist.get(str(code), 0) + 1

    # 3. 帧上报阶段：每 100ms 一帧，持续 duration；后台收广播段
    stop_at = time.time() + args.duration
    recv_stop = threading.Event()

    def recv_worker(c):
        while not recv_stop.is_set():
            c.sock.settimeout(0.2)
            try:
                data, _ = c.sock.recvfrom(2048)
                if data:
                    c.segments_recv += 1
            except socket.timeout:
                pass

    recv_threads = [threading.Thread(target=recv_worker, args=(c,), daemon=True) for c in clients]
    for t in recv_threads:
        t.start()

    cpu_before = battle_cpu()
    frame_lock = threading.Lock()

    def frame_worker(c):
        n = 0
        while time.time() < stop_at:
            c.send_frame(n)
            n += 1
            time.sleep(0.1)

    frame_threads = [threading.Thread(target=frame_worker, args=(c,)) for c in clients]
    for t in frame_threads:
        t.start()
    for t in frame_threads:
        t.join()
    time.sleep(0.3)
    cpu_after = battle_cpu()
    recv_stop.set()
    for t in recv_threads:
        t.join(timeout=1.0)

    total_frames = sum(c.frames_sent for c in clients)
    total_segments = sum(c.segments_recv for c in clients)

    # 4. 断线重连：取一个客户端 close 后 rejoin，测恢复耗时
    victim = clients[-1]
    victim.close()
    time.sleep(0.2)
    victim.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    victim.sock.settimeout(2.0)
    rejoin_code, rejoin_rt = victim.rejoin()

    result = {
        "clients": args.clients,
        "frame_phase_s": args.duration,
        "create_room_code": create_code,
        "room_id": room_id,
        "join": {
            "elapsed_s": round(join_elapsed, 3),
            "code_distribution": code_dist,
            "success": sum(1 for v in join_codes.values() if v == 0),
            "failed": sum(1 for v in join_codes.values() if v != 0),
        },
        "frames": {
            "total_sent": total_frames,
            "segments_received": total_segments,
            "frame_send_rate_per_s": round(total_frames / args.duration, 1),
        },
        "reconnect": {"code": rejoin_code, "recovery_ms": round(rejoin_rt, 1)},
        "cpu": {"before": cpu_before, "during/after": cpu_after},
        "boundary": "广播应用层 P99 延迟：裸 UDP 客户端只见 KCP 封装段，无法解出应用层帧时间戳，未验证。",
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for c in clients:
        c.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n报告已保存: {REPORT}")


if __name__ == "__main__":
    main()
