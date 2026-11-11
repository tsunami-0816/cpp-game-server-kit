#include "log/AsyncLogger.h"
#include <iostream>
#include <cstring>

namespace log {

AsyncLogger& AsyncLogger::instance() {
    static AsyncLogger inst;
    return inst;
}

AsyncLogger::~AsyncLogger() { stop(); }

void AsyncLogger::start(const std::string& path, size_t queue_cap) {
    out_file_.open(path, std::ios::app);
    if (!out_file_.is_open()) {
        std::cerr << "[logger] open " << path << " failed, fallback to stdout" << std::endl;
    }
    queue_ = std::make_unique<LockfreeQueue<LogEntry>>(queue_cap);
    running_ = true;
    writer_thread_ = std::thread(&AsyncLogger::writerLoop, this);
}

void AsyncLogger::stop() {
    if (!running_.exchange(false)) return;
    if (writer_thread_.joinable()) writer_thread_.join();
    if (out_file_.is_open()) out_file_.close();
}

void AsyncLogger::push(const char* msg, size_t len) {
    if (!running_ || !queue_) return;
    LogEntry entry{};
    size_t copy_len = len < sizeof(entry.msg) - 1 ? len : sizeof(entry.msg) - 1;
    std::memcpy(entry.msg, msg, copy_len);
    entry.msg[copy_len] = '\0';
    entry.len = copy_len;
    // 队列满了就丢日志（日志不能阻塞业务线程）
    queue_->tryPush(entry);
}

void AsyncLogger::writerLoop() {
    LogEntry entry;
    while (running_ || queue_) {
        bool got = false;
        // 批量取，一次循环多刷几条
        for (int i = 0; i < 64; ++i) {
            if (!queue_->tryPop(entry)) break;
            got = true;
            if (out_file_.is_open()) {
                out_file_.write(entry.msg, entry.len);
                out_file_.put('\n');
            } else {
                std::cout.write(entry.msg, entry.len) << std::endl;
            }
        }
        if (got && out_file_.is_open()) out_file_.flush();
        if (!running_ && !queue_->tryPop(entry)) break;  // 停了且队列空了
        std::this_thread::sleep_for(std::chrono::microseconds(500));
    }
}

}  // namespace log
