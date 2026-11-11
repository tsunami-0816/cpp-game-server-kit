// T-05: Echo Server —— 异步非阻塞版，连接挂到 worker EventLoop 上（M1 压测基础）
// 用法: ./echo_server [port]
#include "net/TcpServer.h"
#include "net/EventLoop.h"
#include "net/Channel.h"
#include "net/FdGuard.h"
#include <iostream>
#include <unordered_map>
#include <mutex>
#include <unistd.h>
#include <cstring>
#include <sys/socket.h>

using namespace net;

// 每个连接一个 Channel，堆上持有；关闭时从 loop 摘除并释放
struct EchoConn {
    EventLoop*  loop = nullptr;
    Channel*    channel = nullptr;
};

static std::unordered_map<int, EchoConn*> g_conns;
static std::mutex g_connMutex;

static void closeConn(int client_fd) {
    std::lock_guard<std::mutex> lk(g_connMutex);
    auto it = g_conns.find(client_fd);
    if (it == g_conns.end()) return;
    EchoConn* conn = it->second;
    if (conn->loop) conn->loop->removeChannel(conn->channel);
    delete conn->channel;
    delete conn;
    g_conns.erase(it);
    ::close(client_fd);
}

int main(int argc, char* argv[]) {
    uint16_t port = 8000;
    if (argc > 1) port = static_cast<uint16_t>(std::stoi(argv[1]));

    TcpServer server(port, 3);

    server.setConnCallback([](int client_fd, EventLoop* loop) {
        auto* ch = new Channel(loop, client_fd, ClientCtx{client_fd});
        auto* conn = new EchoConn();
        conn->loop = loop;
        conn->channel = ch;

        ch->setReadCallback([client_fd](const ChannelCtx&) {
            char buf[4096];
            while (true) {
                ssize_t n = ::read(client_fd, buf, sizeof(buf));
                if (n > 0) {
                    // MSG_NOSIGNAL: 对端已关时不触发 SIGPIPE；非阻塞下小包一次写完
                    ::send(client_fd, buf, n, MSG_NOSIGNAL);
                } else if (n == 0) {
                    closeConn(client_fd);
                    return;
                } else {
                    if (errno != EAGAIN && errno != EWOULDBLOCK) closeConn(client_fd);
                    return;
                }
            }
        });

        ch->setCloseCallback([client_fd](const ChannelCtx&) {
            closeConn(client_fd);
        });

        ch->setEvents(EPOLLIN);
        loop->updateChannel(ch);

        std::lock_guard<std::mutex> lk(g_connMutex);
        g_conns[client_fd] = conn;
    });

    std::cout << "[echo] server listening on 0.0.0.0:" << port << std::endl;
    server.start();
    return 0;
}
