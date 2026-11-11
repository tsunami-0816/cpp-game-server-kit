#include "battle/KcpServer.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <iostream>
#include <cstring>
#include <vector>

namespace battle {

KcpServer::KcpServer(int port) : port_(port) {
    udp_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (udp_fd_ < 0) throw std::runtime_error("udp socket failed");

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(port_);
    if (bind(udp_fd_, (sockaddr*)&addr, sizeof(addr)) < 0) {
        close(udp_fd_);
        throw std::runtime_error("udp bind 8002 failed: " + std::string(strerror(errno)));
    }
}

KcpServer::~KcpServer() { stop(); }

void KcpServer::start() {
    running_ = true;
    recv_thread_ = std::thread(&KcpServer::recvLoop, this);
    tick_thread_ = std::thread(&KcpServer::tickLoop, this);
}

void KcpServer::stop() {
    running_ = false;
    if (recv_thread_.joinable()) recv_thread_.join();
    if (tick_thread_.joinable()) tick_thread_.join();
    close(udp_fd_);
}

void KcpServer::recvLoop() {
    char buf[2048];
    while (running_) {
        sockaddr_in cli{};
        socklen_t cli_len = sizeof(cli);
        ssize_t n = recvfrom(udp_fd_, buf, sizeof(buf), 0, (sockaddr*)&cli, &cli_len);
        if (n <= 0) continue;

        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &cli.sin_addr, ip, sizeof(ip));
        AddrKey key{ip, ntohs(cli.sin_port)};

        KcpSession* sess = nullptr;
        {
            std::lock_guard<std::mutex> lk(sessions_mutex_);
            auto it = sessions_.find(key);
            if (it == sessions_.end()) {
                // 新连接：建 KCP 会话
                sess = new KcpSession(next_conv_++, this, cli);
                sess->onMsg = [this](KcpSession* s, const char* data, int len) {
                    if (onPacket) onPacket(s, data, len);
                };
                sessions_[key] = sess;
            } else {
                sess = it->second;
            }
        }
        // 喂 UDP 数据给 KCP（不持锁，避免 onMsg 回调里再抢 g_roomsMutex 时死锁）
        sess->onUdpData(buf, n);
    }
}

void KcpServer::tickLoop() {
    while (running_) {
        timespec ts{0, 10 * 1000 * 1000};  // 10ms
        nanosleep(&ts, nullptr);
        uint32_t now = [](){ timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec*1000 + t.tv_nsec/1000000; }();

        // 每轮 tick：先 update 所有会话，再清理超时
        std::vector<std::pair<AddrKey, KcpSession*>> timed_out;
        {
            std::lock_guard<std::mutex> lk(sessions_mutex_);
            for (auto& [key, sess] : sessions_) {
                sess->update(now);
                if (time(nullptr) - sess->lastActive() > 60) {
                    timed_out.emplace_back(key, sess);
                }
            }
            for (auto& [key, sess] : timed_out) {
                sessions_.erase(key);
            }
        }
        // 锁外通知业务层摘除悬空指针 + 释放会话
        for (auto& [key, sess] : timed_out) {
            std::cout << "[battle] timeout " << key.ip << ":" << key.port << std::endl;
            if (onSessionTimeout) onSessionTimeout(sess);
            delete sess;
        }
    }
}

}  // namespace battle
