// 交付阶段（step10）单元探针：对网络/日志基础组件做最小可执行验证，补齐映射表 D-02/D-03/D-08/D-09 证据。
// 不依赖业务链路；断言失败 return 1，全部通过 return 0。
// 用法: ./unit_probe <日志文件路径>
#include "net/Buffer.h"
#include "net/Channel.h"
#include "log/AsyncLogger.h"
#include "log/LogMacros.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static int g_fail = 0;

#define CHECK(cond, msg)                                          \
    do {                                                          \
        if (cond) { std::cout << "  ✅ " << msg << std::endl; }   \
        else { std::cout << "  ❌ " << msg << std::endl; g_fail = 1; } \
    } while (0)

// ---- D-02: Buffer 半包/整包/take ----
static void probeBuffer() {
    std::cout << "[D-02] Buffer 读写缓冲区" << std::endl;

    // 半包：只到 2 字节，不足 4B 包头
    net::Buffer partial;
    partial.append("\x00\x00", 2);
    CHECK(!partial.tryPeekBodyLen().has_value(), "半包（<4B 包头）返回 nullopt");

    // 整包：4B 大端 body len=5 + 5B body（独立实例，避免半包残留污染包头）
    net::Buffer full;
    uint32_t body_len = 5;
    uint32_t be_len = __builtin_bswap32(body_len);
    std::string head(reinterpret_cast<const char*>(&be_len), 4);
    std::string body = "hello";
    full.append(head.data(), 4);
    full.append(body.data(), 5);
    auto len = full.tryPeekBodyLen();
    CHECK(len.has_value() && *len == 5, "整包 peek 出 body 长度=5");
    CHECK(full.readable() == 9, "可读字节=4 包头+5 body=9");

    std::vector<char> taken = full.take(9);
    CHECK(taken.size() == 9, "take(9) 取回整包 9 字节");
    CHECK(full.readable() == 0, "take 后缓冲区清空");
}

// ---- D-03: Channel variant 三态上下文 + 回调分发 ----
static void probeChannel() {
    std::cout << "[D-03] Channel variant 上下文分发" << std::endl;

    // 不传 EventLoop：探针不触发 enableWriting/updateChannel，loop_ 仅保存不解引用
    net::Channel ch(nullptr, 3, net::ClientCtx{10});

    net::ClientCtx capturedClient{};
    ch.setReadCallback([&](const net::ChannelCtx& ctx) {
        capturedClient = std::get<net::ClientCtx>(ctx);
    });
    ch.handleRead();
    CHECK(std::holds_alternative<net::ClientCtx>(ch.context()), "ClientCtx 上下文类型正确");
    CHECK(capturedClient.conn_fd == 10, "读回调收到 ClientCtx.conn_fd=10");

    net::Channel timerCh(nullptr, 4, net::TimerCtx{77});
    int64_t timerId = 0;
    timerCh.setCloseCallback([&](const net::ChannelCtx& ctx) {
        timerId = std::get<net::TimerCtx>(ctx).timer_id;
    });
    timerCh.handleClose();
    CHECK(timerId == 77, "关回调收到 TimerCtx.timer_id=77");

    net::Channel kcpCh(nullptr, 5, net::KcpCtx{2024});
    int conv = 0;
    kcpCh.setWriteCallback([&](const net::ChannelCtx& ctx) {
        conv = std::get<net::KcpCtx>(ctx).kcp_conv;
    });
    kcpCh.handleWrite();
    CHECK(conv == 2024, "写回调收到 KcpCtx.conv=2024");
}

// ---- D-08 / D-09: AsyncLogger 后台刷盘 + LOG_INFO 宏拼接 ----
static void probeLogger(const std::string& logPath) {
    std::cout << "[D-08/D-09] AsyncLogger + LOG_INFO 宏" << std::endl;
    log::AsyncLogger::instance().start(logPath, 1 << 12);

    LOG_INFO("uid=", 1, " name=", "user1", " n=", 42);
    LOG_INFO("second-line");

    log::AsyncLogger::instance().stop();

    std::ifstream ifs(logPath);
    std::ostringstream oss;
    std::string line;
    int lines = 0;
    while (std::getline(ifs, line)) { oss << line << '\n'; ++lines; }
    std::string content = oss.str();

    CHECK(lines == 2, "后台刷盘落盘 2 条日志（push 2 / 落盘 2）");
    CHECK(content.find("uid=1 name=user1 n=42") != std::string::npos,
          "LOG_INFO 多类型参数 fold 拼接落盘正确");
    CHECK(content.find("second-line") != std::string::npos, "第二条日志落盘");
}

int main(int argc, char* argv[]) {
    std::string logPath = "/tmp/unit_probe.log";
    if (argc > 1) logPath = argv[1];

    probeBuffer();
    probeChannel();
    probeLogger(logPath);

    if (g_fail == 0) {
        std::cout << "=== unit_probe 全部通过 ===" << std::endl;
        return 0;
    }
    std::cout << "=== unit_probe 存在失败项 ===" << std::endl;
    return 1;
}
