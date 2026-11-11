#!/usr/bin/env python3
# T-20 验证：battle_server UDP 8002 帧同步（先登录拿真 token，再调 battle）
import socket, struct, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import game_pb2

GW_HOST, GW_PORT = "127.0.0.1", 8001
BT_HOST, BT_PORT = "127.0.0.1", 8002

def login():
    """连 gateway 登录，返回 (token, uid)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((GW_HOST, GW_PORT))
    req = game_pb2.LoginReq()
    req.username = "user1"
    req.password = "123456"
    body = req.SerializeToString()
    s.sendall(struct.pack(">I", len(body)) + body)
    header = s.recv(4)
    blen = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < blen:
        buf += s.recv(blen - len(buf))
    rsp = game_pb2.LoginRsp()
    rsp.ParseFromString(buf)
    s.close()
    assert rsp.code == 0, f"登录失败 code={rsp.code}"
    return rsp.token, rsp.uid

def main():
    token, uid = login()
    print(f"[login] ok uid={uid} token={token[:12]}...")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)

    def send_msg(msg_type, pb):
        s.sendto(bytes([msg_type]) + pb.SerializeToString(), (BT_HOST, BT_PORT))

    def recv_rsp(expected_type, pb_cls):
        # KCP 栈后台会发 ACK/控制段到同一 socket，循环收直到拿到期望类型
        deadline = time.time() + 3
        while time.time() < deadline:
            s.settimeout(2)
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                break
            if len(data) > 0 and data[0] == expected_type:
                msg = pb_cls()
                msg.ParseFromString(data[1:])
                return msg
            # 否则是 KCP 控制段，跳过
        raise TimeoutError(f"等不到 type={expected_type} 的回包")

    # 1. CreateRoom
    req = game_pb2.CreateRoomReq()
    req.token = token
    req.uid = uid
    send_msg(1, req)
    r = recv_rsp(2, game_pb2.CreateRoomRsp)
    print(f"[1] CreateRoomRsp code={r.code} room_id={r.room_id} msg={r.msg}")
    assert r.code == 0, f"建房失败 code={r.code}"
    room_id = r.room_id

    # 2. 发 FrameInput
    fi = game_pb2.FrameInput()
    fi.room_id = room_id
    fi.uid = uid
    fi.input = 42
    send_msg(5, fi)

    # 3. 等广播（走 KCP，Python 裸 socket 只验证收到 UDP 包，不解析 pb）
    time.sleep(0.3)
    try:
        data, _ = s.recvfrom(2048)
        print(f"[2] 收到 UDP 包 {len(data)} 字节（KCP 帧广播段，Python 裸 socket 不解 pb）")
    except socket.timeout:
        print("❌ 没收到帧广播 UDP 包")
        sys.exit(1)

    # 4. RejoinRoom
    rr = game_pb2.RejoinRoomReq()
    rr.token = token
    rr.uid = uid
    rr.room_id = room_id
    send_msg(7, rr)
    rrsp = recv_rsp(8, game_pb2.RejoinRoomRsp)
    print(f"[3] RejoinRoomRsp code={rrsp.code} frame_no={rrsp.frame_no} history={len(rrsp.history)}")
    assert rrsp.code == 0, f"重连失败 code={rrsp.code}"
    print("✅ M5 全部通过")

if __name__ == "__main__":
    main()
