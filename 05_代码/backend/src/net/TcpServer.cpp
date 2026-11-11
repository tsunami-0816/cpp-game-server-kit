#include "net/TcpServer.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <iostream>
#include <cstring>
#include <unistd.h>

namespace net {

static int setNonBlocking(int fd) {
    int flags = ::fcntl(fd, F_GETFL, 0);
    return ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

TcpServer::TcpServer(uint16_t port, int worker_num)
    : port_(port), worker_num_(worker_num) {
    // 创建监听 socket
    int fd = ::socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd < 0) throw std::runtime_error("socket failed");

    int opt = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(port_);

    if (::bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        throw std::runtime_error(std::string("bind failed: ") + std::strerror(errno));
    }
    if (::listen(fd, 128) < 0) {
        throw std::runtime_error("listen failed");
    }
    listen_fd_ = FdGuard(fd);

    // 建 worker EventLoop + 线程
    for (int i = 0; i < worker_num_; ++i) {
        worker_loops_.push_back(std::make_unique<EventLoop>());
    }
}

TcpServer::~TcpServer() {
    for (auto& loop : worker_loops_) loop->stop();
    for (auto& t : worker_threads_) if (t.joinable()) t.join();
}

void TcpServer::start() {
    // 启动 worker 线程
    for (int i = 0; i < worker_num_; ++i) {
        worker_threads_.emplace_back([this, i]() {
            worker_loops_[i]->loop();
        });
    }
    // 主线程跑 accept
    acceptLoop();
}

void TcpServer::acceptLoop() {
    while (true) {
        sockaddr_in cli{};
        socklen_t len = sizeof(cli);
        int cfd = ::accept4(listen_fd_.get(), (sockaddr*)&cli, &len,
                            SOCK_NONBLOCK | SOCK_CLOEXEC);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                // 非阻塞 listen fd，没连接了就睡一下避免 busy loop
                usleep(1000);
                continue;
            }
            std::cerr << "accept error: " << std::strerror(errno) << std::endl;
            break;
        }
        // round-robin 选 worker loop
        int idx = next_round_robin_.fetch_add(1) % worker_num_;
        EventLoop* loop = worker_loops_[idx].get();
        if (onConn_) onConn_(cfd, loop);
    }
}

}  // namespace net
