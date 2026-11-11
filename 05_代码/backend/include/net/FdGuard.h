// T-01: RAII 封装 int fd，析构自动 close（演示 M7 RAII）
#pragma once
#include <unistd.h>

namespace net {

class FdGuard {
public:
    FdGuard() = default;
    explicit FdGuard(int fd) : fd_(fd) {}
    ~FdGuard() { if (fd_ >= 0) ::close(fd_); }

    // 禁止拷贝，允许移动
    FdGuard(const FdGuard&) = delete;
    FdGuard& operator=(const FdGuard&) = delete;
    FdGuard(FdGuard&& other) noexcept : fd_(other.fd_) { other.fd_ = -1; }
    FdGuard& operator=(FdGuard&& other) noexcept {
        if (this != &other) {
            if (fd_ >= 0) ::close(fd_);
            fd_ = other.fd_;
            other.fd_ = -1;
        }
        return *this;
    }

    int get() const { return fd_; }
    // 放弃所有权（不 close）
    int release() { int f = fd_; fd_ = -1; return f; }

private:
    int fd_ = -1;
};

}  // namespace net
