// T-16: KcpServer —— UDP 8002，管理所有 KcpSession
#pragma once
#include "battle/KcpSession.h"
#include <unordered_map>
#include <map>
#include <mutex>
#include <functional>
#include <thread>
#include <atomic>

namespace battle {

class KcpServer {
public:
    explicit KcpServer(int port);
    ~KcpServer();

    void start();
    void stop();

    int udpFd() const { return udp_fd_; }
    // 注意：返回的 sessions_ 必须在 sessions_mutex_ 保护下访问
    std::map<AddrKey, KcpSession*>& sessions() { return sessions_; }
    std::mutex& sessionsMutex() { return sessions_mutex_; }

    std::function<void(KcpSession*, const char*, int)> onPacket;
    // 会话被超时销毁前回调（持 sessions_mutex_ 调用），业务层应从此会话的所有房间成员表里摘除指针，避免 UAF
    std::function<void(KcpSession*)> onSessionTimeout;

private:
    void recvLoop();
    void tickLoop();

    int udp_fd_ = -1;
    int port_;
    std::map<AddrKey, KcpSession*> sessions_;
    std::mutex sessions_mutex_;  // 保护 sessions_：recvLoop(insert/find) 与 tickLoop(erase/iterate) 跨线程
    uint32_t next_conv_ = 1;
    std::atomic<bool> running_{false};
    std::thread recv_thread_;
    std::thread tick_thread_;
};

}  // namespace battle
