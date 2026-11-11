#include "net/EventLoop.h"
#include "net/Channel.h"
#include "net/FdGuard.h"
#include <iostream>
#include <unistd.h>
#include <cstring>

namespace net {

EventLoop::EventLoop() {
    epfd_ = ::epoll_create1(EPOLL_CLOEXEC);
    if (epfd_ < 0) {
        std::cerr << "epoll_create1 failed: " << std::strerror(errno) << std::endl;
    }
    tid_ = std::this_thread::get_id();
}

EventLoop::~EventLoop() {
    if (epfd_ >= 0) ::close(epfd_);
}

void EventLoop::loop() {
    running_ = true;
    tid_ = std::this_thread::get_id();
    while (running_) {
        int n = ::epoll_wait(epfd_, active_events_.data(), kMaxEvents, kEpollTimeoutMs);
        for (int i = 0; i < n; ++i) {
            auto* ch = static_cast<Channel*>(active_events_[i].data.ptr);
            uint32_t ev = active_events_[i].events;
            if (ev & (EPOLLERR | EPOLLHUP)) {
                ch->handleClose();
            } else {
                if (ev & (EPOLLIN | EPOLLPRI)) ch->handleRead();
                if (ev & EPOLLOUT)             ch->handleWrite();
            }
        }
    }
}

void EventLoop::stop() {
    running_ = false;
}

void EventLoop::updateChannel(Channel* ch) {
    struct epoll_event ev{};
    ev.events = ch->events();
    ev.data.ptr = ch;
    // EPOLL_CTL_ADD 失败说明已经 add 过，改成 MOD
    if (::epoll_ctl(epfd_, EPOLL_CTL_ADD, ch->fd(), &ev) < 0) {
        ::epoll_ctl(epfd_, EPOLL_CTL_MOD, ch->fd(), &ev);
    }
}

void EventLoop::removeChannel(Channel* ch) {
    ::epoll_ctl(epfd_, EPOLL_CTL_DEL, ch->fd(), nullptr);
}

}  // namespace net
