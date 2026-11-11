// T-21: stress_client 自研 TCP 压测客户端（M1 长连接 / M6 QPS 验证）
// 用法: ./stress_client -c 1000 -d 5 [-h 127.0.0.1] [-p 8000]
// 模型: 单线程 epoll 管理 N 个连接，周期性发心跳收回显，统计连接数/断开数/QPS/延迟/RSS
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/epoll.h>
#include <unistd.h>
#include <fcntl.h>
#include <iostream>
#include <vector>
#include <string>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <atomic>
#include <algorithm>
#include <fstream>

struct ConnState {
    int  fd = -1;
    bool online = false;
    uint64_t seq = 0;
    std::chrono::steady_clock::time_point send_ts;
    char last_msg[64] = {};
};

static const int kMsgLen = 64;
static std::atomic<long long> g_sent{0};
static std::atomic<long long> g_recv{0};
static std::atomic<long long> g_dropped{0};
static std::atomic<long long> g_latency_us{0};
static long long g_max_latency_us = 0;

static int setNonBlocking(int fd) {
    int flags = ::fcntl(fd, F_GETFL, 0);
    return ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static long long readRssKb() {
    std::ifstream f("/proc/self/status");
    std::string line;
    while (std::getline(f, line)) {
        if (line.compare(0, 6, "VmRSS:") == 0) {
            long long kb = 0;
            std::sscanf(line.c_str(), "VmRSS: %lld", &kb);
            return kb;
        }
    }
    return 0;
}

static void makeHeartbeat(ConnState& c) {
    std::snprintf(c.last_msg, sizeof(c.last_msg), "stress-%d-%lu", c.fd, c.seq++);
    size_t len = std::strlen(c.last_msg);
    std::memset(c.last_msg + len, 0, kMsgLen - len);  // 定长补齐
}

int main(int argc, char* argv[]) {
    int conn_num = 1000;
    int duration_s = 5;
    std::string host = "127.0.0.1";
    int port = 8000;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-c" && i+1 < argc) conn_num = std::stoi(argv[++i]);
        else if (a == "-d" && i+1 < argc) duration_s = std::stoi(argv[++i]);
        else if (a == "-h" && i+1 < argc) host = argv[++i];
        else if (a == "-p" && i+1 < argc) port = std::stoi(argv[++i]);
    }

    std::cout << "[stress] target=" << host << ":" << port
              << " conn=" << conn_num << " duration=" << duration_s << "s" << std::endl;

    // 1. 批量建连（阻塞 connect，本地很快）
    std::vector<ConnState> conns(conn_num);
    int epfd = ::epoll_create1(EPOLL_CLOEXEC);
    int connected = 0;

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    ::inet_pton(AF_INET, host.c_str(), &addr.sin_addr);

    for (int i = 0; i < conn_num; ++i) {
        int fd = ::socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) continue;
        if (::connect(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
            ::close(fd);
            continue;
        }
        setNonBlocking(fd);
        ConnState& c = conns[i];
        c.fd = fd;
        c.online = true;
        ++connected;

        epoll_event ev{};
        ev.events = EPOLLIN;
        ev.data.ptr = &c;
        ::epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &ev);
    }
    std::cout << "[stress] connected=" << connected << "/" << conn_num << std::endl;

    if (connected == 0) {
        std::cerr << "[stress] 没有成功连接，退出" << std::endl;
        return 1;
    }

    // 2. 压测循环：定时轮次发心跳，epoll 收回显
    auto t_start = std::chrono::steady_clock::now();
    const std::chrono::milliseconds kTick{100};  // 每 100ms 一轮
    std::vector<epoll_event> events(connected + 16);

    while (true) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - t_start).count();
        if (elapsed >= duration_s) break;

        // 一轮：给每个在线连接发心跳
        for (auto& c : conns) {
            if (!c.online) continue;
            makeHeartbeat(c);
            c.send_ts = now;
            ssize_t w = ::write(c.fd, c.last_msg, kMsgLen);
            if (w == kMsgLen) g_sent.fetch_add(1);
        }

        // 等读事件（最多等一个 tick）
        int n = ::epoll_wait(epfd, events.data(), events.size(), kTick.count());
        for (int i = 0; i < n; ++i) {
            ConnState* c = static_cast<ConnState*>(events[i].data.ptr);
            char buf[kMsgLen];
            ssize_t r = ::read(c->fd, buf, sizeof(buf));
            if (r <= 0) {
                c->online = false;
                g_dropped.fetch_add(1);
                ::close(c->fd);
                continue;
            }
            g_recv.fetch_add(1);
            auto lat = std::chrono::duration_cast<std::chrono::microseconds>(
                std::chrono::steady_clock::now() - c->send_ts).count();
            g_latency_us.fetch_add(lat);
            g_max_latency_us = std::max<long long>(g_max_latency_us, lat);
        }
    }

    // 3. 汇总输出
    auto t_end = std::chrono::steady_clock::now();
    double secs = std::chrono::duration<double>(t_end - t_start).count();
    long long online = 0;
    for (auto& c : conns) if (c.online) ++online;

    double qps = g_recv.load() / secs;
    double avg_lat = g_recv.load() ? g_latency_us.load() / g_recv.load() / 1000.0 : 0.0;
    long long rss_kb = readRssKb();

    std::cout << "=== stress_client 压测结果 ===" << std::endl;
    std::cout << "成功连接: " << connected << std::endl;
    std::cout << "中途断开: " << g_dropped.load() << std::endl;
    std::cout << "当前在线: " << online << std::endl;
    std::cout << "发包总数: " << g_sent.load() << std::endl;
    std::cout << "收包总数: " << g_recv.load() << std::endl;
    std::cout << "耗时: " << secs << " s" << std::endl;
    std::cout << "QPS: " << (long long)qps << " 回显/s" << std::endl;
    std::cout << "平均延迟: " << avg_lat << " ms" << std::endl;
    std::cout << "最大延迟: " << g_max_latency_us / 1000.0 << " ms" << std::endl;
    std::cout << "客户端 RSS: " << rss_kb / 1024.0 << " MB" << std::endl;

    for (auto& c : conns) if (c.online) ::close(c.fd);
    ::close(epfd);

    // M1 判据：断开数 = 0
    return g_dropped.load() == 0 ? 0 : 2;
}
