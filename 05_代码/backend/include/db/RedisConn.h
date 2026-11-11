// T-12: Redis 连接（thread_local hiredis，端口 6380）
#pragma once
#include <hiredis/hiredis.h>
#include <string>
#include <string_view>
#include <optional>

namespace db {

class RedisConn {
public:
    RedisConn(const char* host, int port);
    ~RedisConn();

    RedisConn(const RedisConn&) = delete;
    RedisConn& operator=(const RedisConn&) = delete;

    bool setEx(const std::string& key, const std::string& val, int ttl_sec);
    std::optional<std::string> get(const std::string& key);
    bool del(const std::string& key);

private:
    redisContext* ctx_ = nullptr;
};

RedisConn& threadLocalRedis();

}  // namespace db
