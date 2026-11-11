// T-07: 异步日志，后台线程批量刷盘
#pragma once
#include "log/LockfreeQueue.h"
#include <string>
#include <thread>
#include <fstream>
#include <atomic>
#include <vector>

namespace log {

struct LogEntry {
    char msg[512];
    size_t len;
};

class AsyncLogger {
public:
    static AsyncLogger& instance();

    // 初始化：指定日志文件，启动后台刷盘线程
    void start(const std::string& path, size_t queue_cap = 1 << 16);
    void stop();

    // 生产者线程调用（非阻塞）：push 一条日志
    void push(const char* msg, size_t len);

private:
    AsyncLogger() = default;
    ~AsyncLogger();
    AsyncLogger(const AsyncLogger&) = delete;
    AsyncLogger& operator=(const AsyncLogger&) = delete;

    void writerLoop();  // 后台线程跑这个

    std::unique_ptr<LockfreeQueue<LogEntry>> queue_;
    std::thread writer_thread_;
    std::atomic<bool> running_{false};
    std::ofstream out_file_;
};

}  // namespace log
