// T-04: EventLoop 单线程 epoll_wait 循环
#pragma once
#include <vector>
#include <memory>
#include <atomic>
#include <thread>
#include <sys/epoll.h>

namespace net {

class Channel;

constexpr int kMaxEvents = 1024;
constexpr int kEpollTimeoutMs = 1000;

class EventLoop {
public:
    EventLoop();
    ~EventLoop();

    void loop();                       // 跑 epoll_wait 循环（在自己线程里）
    void stop();                       // 唤醒退出
    void updateChannel(Channel* ch);   // 增/改 epoll 事件
    void removeChannel(Channel* ch);  // 从 epoll 摘除

    std::thread::id threadId() const { return tid_; }

private:
    int epfd_ = -1;
    std::atomic<bool> running_{false};
    std::thread::id tid_;
    std::vector<struct epoll_event> active_events_{kMaxEvents};
};

}  // namespace net
