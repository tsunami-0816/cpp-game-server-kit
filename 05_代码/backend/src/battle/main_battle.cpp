// T-17~T-20: battle_server 主程序
// UDP 8002，房间管理 + 100ms 帧广播 + 断线重连
#include "battle/KcpServer.h"
#include "battle/CoroTask.h"
#include "db/RedisConn.h"
#include "game.pb.h"
#include <iostream>
#include <map>
#include <vector>
#include <mutex>
#include <atomic>
#include <algorithm>
#include <thread>
#include <unistd.h>

using namespace battle;

// T-17: 房间
struct Room {
    uint64_t roomId;
    std::vector<KcpSession*> members;
    std::vector<game::FrameInput> history;  // 帧历史（断线重连用，保留最近 100 条）
    int frameNo = 0;
};

static std::map<uint64_t, Room> g_rooms;
static std::mutex g_roomsMutex;
static std::atomic<uint64_t> g_nextRoomId{1000};

// 校验 token：从 Redis 查 session:{uid} 是否等于请求里的 token
// 合法返回 uid（>0），非法返回 0
static uint64_t checkToken(const std::string& token, uint64_t declaredUid) {
    if (token.empty() || declaredUid == 0) return 0;
    auto& redis = db::threadLocalRedis();
    auto val = redis.get("session:" + std::to_string(declaredUid));
    if (!val) return 0;
    return (*val == token) ? declaredUid : 0;
}

// 一轮广播：把所有房间积压的帧 input 推给成员
// 注意：广播走 KCP 可靠传输（sess->send → ikcp_send），回包走 sendRaw 兼容裸 socket 测试客户端
static void broadcastOnce() {
    std::lock_guard<std::mutex> lk(g_roomsMutex);
    for (auto& [rid, room] : g_rooms) {
        if (room.history.empty()) continue;
        game::FrameBroadcast bc;
        bc.set_room_id(rid);
        bc.set_frame_no(room.frameNo++);
        for (auto& inp : room.history) {
            *bc.add_inputs() = inp;
        }
        std::string body = bc.SerializeAsString();
        std::string pkt(1, (char)6);
        pkt += body;
        for (auto* sess : room.members) {
            // 走 KCP ARQ：ikcp_send 负责可靠传输/重传/滑动窗口
            sess->send(pkt.data(), pkt.size());
        }
        // 广播后清空积压，但历史保留供重连拉取（在 FrameInput 入队时按 100 条截断）
        room.history.clear();
    }
}

// T-18/M7: 100ms 帧广播协程 —— co_await 挂起定时，到点恢复跑一轮
static CoroTask broadcastLoop() {
    while (true) {
        co_await sleepMs(100);  // 挂起 100ms，后台线程到点 resume
        broadcastOnce();
    }
}

int main() {
    // 初始化 Redis 连接（主线程）
    db::threadLocalRedis();

    KcpServer server(8002);

    // 启动 100ms 广播协程
    broadcastLoop();

    // UAF 防护：会话被超时销毁时，从所有房间的 members 表里摘除该指针
    server.onSessionTimeout = [](KcpSession* dead) {
        std::lock_guard<std::mutex> lk(g_roomsMutex);
        for (auto& [rid, room] : g_rooms) {
            room.members.erase(
                std::remove(room.members.begin(), room.members.end(), dead),
                room.members.end());
        }
    };

    server.onPacket = [&](KcpSession* sess, const char* data, int len) {
        if (len < 1) return;
        uint8_t msgType = data[0];
        const char* pbData = data + 1;
        int pbLen = len - 1;

        game::CreateRoomReq createReq;
        game::JoinRoomReq joinReq;
        game::FrameInput frameIn;
        game::RejoinRoomReq rejoinReq;

        // 回包辅助：类型头 + pb body，走 sendRaw（单包响应，兼容 Python 裸 socket 测试客户端）
        auto sendRsp = [sess](uint8_t type, const google::protobuf::Message& msg) {
            std::string body = msg.SerializeAsString();
            std::string pkt(1, (char)type);
            pkt += body;
            sess->sendRaw(pkt.data(), pkt.size());
        };

        if (msgType == 1 && createReq.ParseFromArray(pbData, pbLen)) {
            // CreateRoom：校验 token
            uint64_t uid = checkToken(createReq.token(), createReq.uid());
            if (uid == 0) {
                game::CreateRoomRsp rsp; rsp.set_code(1003); rsp.set_msg("invalid token");
                sendRsp(2, rsp);
                return;
            }
            sess->uid = uid;

            uint64_t rid = g_nextRoomId++;
            {
                std::lock_guard<std::mutex> lk(g_roomsMutex);
                Room room;
                room.roomId = rid;
                room.members.push_back(sess);
                g_rooms[rid] = std::move(room);
            }
            sess->roomId = rid;

            game::CreateRoomRsp rsp;
            rsp.set_code(0);
            rsp.set_room_id(rid);
            sendRsp(2, rsp);
            std::cerr << "[battle] create room " << rid << " by uid=" << uid << std::endl;

        } else if (msgType == 3 && joinReq.ParseFromArray(pbData, pbLen)) {
            // JoinRoom：校验 token
            uint64_t uid = checkToken(joinReq.token(), joinReq.uid());
            if (uid == 0) {
                game::JoinRoomRsp rsp; rsp.set_code(1003); rsp.set_msg("invalid token");
                sendRsp(4, rsp);
                return;
            }
            sess->uid = uid;

            std::lock_guard<std::mutex> lk(g_roomsMutex);
            auto it = g_rooms.find(joinReq.room_id());
            game::JoinRoomRsp rsp;
            if (it == g_rooms.end()) {
                rsp.set_code(2001);  // 设计错误码：房间不存在（原 404 已修正）
                rsp.set_msg("room not found");
            } else if (it->second.members.size() >= 50) {  // 修复-Q014：满员阈值对齐基线 M5/架构 §5.3 契约 50 人（原硬编码 8）
                rsp.set_code(2002);  // 房间满员
                rsp.set_msg("room full");
            } else {
                it->second.members.push_back(sess);
                sess->roomId = joinReq.room_id();
                rsp.set_code(0);
                for (auto* m : it->second.members) rsp.add_members(m->uid);
            }
            sendRsp(4, rsp);

        } else if (msgType == 5 && frameIn.ParseFromArray(pbData, pbLen)) {
            // FrameInput：存到房间历史（保留最近 100 条）
            std::lock_guard<std::mutex> lk(g_roomsMutex);
            auto it = g_rooms.find(frameIn.room_id());
            if (it != g_rooms.end()) {
                it->second.history.push_back(frameIn);
                if (it->second.history.size() > 100) {
                    it->second.history.erase(it->second.history.begin());
                }
            }

        } else if (msgType == 7 && rejoinReq.ParseFromArray(pbData, pbLen)) {
            // RejoinRoom：校验 token
            uint64_t uid = checkToken(rejoinReq.token(), rejoinReq.uid());
            if (uid == 0) {
                game::RejoinRoomRsp rsp; rsp.set_code(1003); rsp.set_msg("invalid token");
                sendRsp(8, rsp);
                return;
            }
            sess->uid = uid;

            std::lock_guard<std::mutex> lk(g_roomsMutex);
            auto it = g_rooms.find(rejoinReq.room_id());
            game::RejoinRoomRsp rsp;
            if (it == g_rooms.end()) {
                rsp.set_code(2001);
                rsp.set_msg("room not found");
            } else {
                rsp.set_code(0);
                rsp.set_frame_no(it->second.frameNo);
                // 回传未广播的历史帧（最近 100 条截断）
                for (auto& h : it->second.history) {
                    *rsp.add_history() = h;
                }
                it->second.members.push_back(sess);
                sess->roomId = rejoinReq.room_id();
            }
            sendRsp(8, rsp);
            std::cerr << "[battle] rejoin room " << rejoinReq.room_id() << " uid=" << uid << std::endl;
        }
    };

    std::cout << "[battle] KCP/UDP listening on 0.0.0.0:8002" << std::endl;
    server.start();
    // 主线程阻塞，不要 return（return 会析构 server 导致线程 join 死锁）
    while (true) {
        sleep(3600);
    }
    return 0;
}
