// M6 对照基线版 Echo Server：初始未优化实现（单次 read、::write 回显、worker 3）
// 仅用于 perf_report 前后对比，不参与正式交付链路
#include "net/TcpServer.h"
#include "net/EventLoop.h"
#include "net/Channel.h"
#include <iostream>
#include <unordered_map>
#include <mutex>
#include <unistd.h>
#include <cstring>
#include <sys/socket.h>

using namespace net;

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

        // 初始版：回调里单次 read，::write 同步回写
        ch->setReadCallback([client_fd](const ChannelCtx&) {
            char buf[4096];
            ssize_t n = ::read(client_fd, buf, sizeof(buf));
            if (n > 0) {
                ::write(client_fd, buf, n);
            } else if (n == 0) {
                closeConn(client_fd);
            } else if (errno != EAGAIN && errno != EWOULDBLOCK) {
                closeConn(client_fd);
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

    std::cout << "[echo-baseline] listening on 0.0.0.0:" << port << std::endl;
    server.start();
    return 0;
}
