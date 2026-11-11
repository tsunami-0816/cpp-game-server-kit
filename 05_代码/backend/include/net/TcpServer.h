// T-04: TcpServer + WorkerThreadPool，one-loop-per-thread
#pragma once
#include "net/EventLoop.h"
#include "net/Channel.h"
#include "net/FdGuard.h"
#include <vector>
#include <thread>
#include <atomic>
#include <functional>
#include <memory>
#include <unordered_map>

namespace net {

class TcpServer {
public:
    // 新连接回调：参数是 (client_fd, 该连接所属的 EventLoop)
    using ConnCallback = std::function<void(int client_fd, EventLoop* loop)>;

    TcpServer(uint16_t port, int worker_num = 3);
    ~TcpServer();

    void start();   // 启动主循环（阻塞）
    void setConnCallback(ConnCallback cb) { onConn_ = std::move(cb); }

private:
    void acceptLoop();   // 主线程跑这个
    void newConnection(int client_fd);

    uint16_t port_;
    int worker_num_;
    FdGuard listen_fd_;
    std::vector<std::unique_ptr<EventLoop>> worker_loops_;
    std::vector<std::thread> worker_threads_;
    std::atomic<int> next_round_robin_{0};
    std::unique_ptr<Channel> accept_channel_;
    ConnCallback onConn_;
};

}  // namespace net
