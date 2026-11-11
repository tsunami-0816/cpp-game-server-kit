// T-09: Protobuf 编解码 —— 4 字节大端包头 + pb body
#pragma once
#include <cstdint>
#include <cstddef>
#include <optional>
#include <string>

namespace codec {

constexpr size_t kHeaderLen = 4;
constexpr size_t kMaxBodyLen = 4 * 1024 * 1024;  // 4MB

// 把 protobuf 序列化成 4B包头+body 的格式
inline std::string encode(const std::string& body) {
    uint32_t len = htobe32(static_cast<uint32_t>(body.size()));
    std::string out;
    out.append(reinterpret_cast<const char*>(&len), 4);
    out.append(body);
    return out;
}

// 从 buf 的前 n 字节里尝试解出一个完整包的 body 长度；不够返回 nullopt
// out_len 是 body 长度，调用方要再收 out_len 字节才是完整包
inline std::optional<size_t> tryDecodeHeader(const char* buf, size_t n) {
    if (n < kHeaderLen) return std::nullopt;
    uint32_t len;
    __builtin_memcpy(&len, buf, 4);
    len = be32toh(len);
    if (len == 0 || len > kMaxBodyLen) return std::nullopt;  // 非法包
    return static_cast<size_t>(len);
}

}  // namespace codec
