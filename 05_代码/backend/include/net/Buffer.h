// T-02: 读写缓冲区，TryReadMessage 返回 std::optional（演示 M7 optional）
#pragma once
#include <vector>
#include <cstddef>
#include <optional>
#include <cstring>
#include <cstdint>

namespace net {

class Buffer {
public:
    // 追加读到的 n 字节到缓冲区末尾
    void append(const char* data, size_t n) {
        buf_.insert(buf_.end(), data, data + n);
    }

    // 可读字节数
    size_t readable() const { return buf_.size(); }

    //  peek 前 n 字节（不移除）
    const char* peek() const { return buf_.data(); }

    // 取回前 n 字节并从缓冲区移除
    std::vector<char> take(size_t n) {
        std::vector<char> out(buf_.begin(), buf_.begin() + n);
        buf_.erase(buf_.begin(), buf_.begin() + n);
        return out;
    }

    // 假设协议是 4 字节大端包头 + body。
    // 如果缓冲区里已经有完整一个包，返回 body 长度；否则返回 nullopt。
    std::optional<size_t> tryPeekBodyLen() const {
        if (readable() < 4) return std::nullopt;
        uint32_t len = 0;
        std::memcpy(&len, buf_.data(), 4);
        len = be32toh(len);  // 大端转主机序
        if (readable() < 4 + len) return std::nullopt;
        return static_cast<size_t>(len);
    }

private:
    std::vector<char> buf_;
};

}  // namespace net
