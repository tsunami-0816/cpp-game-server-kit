// T-03: Channel 事件分发，回调上下文用 std::variant（演示 M7 variant 类型安全）
#pragma once
#include <functional>
#include <variant>
#include <cstdint>

namespace net {

// 三种上下文：客户端连接 / 定时器 / KCP 会话（T-17 再加）
struct ClientCtx { int conn_fd; };
struct TimerCtx  { int64_t timer_id; };
struct KcpCtx    { int kcp_conv; };
using ChannelCtx = std::variant<ClientCtx, TimerCtx, KcpCtx>;

class EventLoop;  // 前向声明

class Channel {
public:
    using ReadCallback  = std::function<void(const ChannelCtx&)>;
    using WriteCallback = std::function<void(const ChannelCtx&)>;
    using CloseCallback = std::function<void(const ChannelCtx&)>;

    Channel(EventLoop* loop, int fd, ChannelCtx ctx)
        : loop_(loop), fd_(fd), ctx_(std::move(ctx)) {}

    int fd() const { return fd_; }
    ChannelCtx& context() { return ctx_; }

    void setReadCallback(ReadCallback cb)  { onRead_  = std::move(cb); }
    void setWriteCallback(WriteCallback cb){ onWrite_ = std::move(cb); }
    void setCloseCallback(CloseCallback cb){ onClose_ = std::move(cb); }

    void handleRead()  { if (onRead_)  onRead_(ctx_); }
    void handleWrite() { if (onWrite_) onWrite_(ctx_); }
    void handleClose() { if (onClose_) onClose_(ctx_); }

    // 关注/取消关注 EPOLLOUT
    void enableWriting();
    void disableWriting();
    int  events() const { return events_; }
    void setEvents(int ev) { events_ = ev; }

private:
    EventLoop* loop_;
    int fd_;
    ChannelCtx ctx_;
    int events_ = 0;
    ReadCallback  onRead_;
    WriteCallback onWrite_;
    CloseCallback onClose_;
};

}  // namespace net
