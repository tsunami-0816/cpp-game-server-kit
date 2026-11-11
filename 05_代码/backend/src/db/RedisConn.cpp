#include "db/RedisConn.h"
#include <iostream>

namespace db {

RedisConn::RedisConn(const char* host, int port) {
    ctx_ = redisConnect(host, port);
    if (!ctx_ || ctx_->err) {
        std::string err = ctx_ ? ctx_->errstr : "null ctx";
        if (ctx_) redisFree(ctx_);
        throw std::runtime_error("redis connect failed: " + err);
    }
}

RedisConn::~RedisConn() {
    if (ctx_) redisFree(ctx_);
}

bool RedisConn::setEx(const std::string& key, const std::string& val, int ttl_sec) {
    redisReply* r = (redisReply*)redisCommand(ctx_, "SETEX %s %d %s",
                                               key.c_str(), ttl_sec, val.c_str());
    bool ok = r && r->type == REDIS_REPLY_STATUS;
    if (r) freeReplyObject(r);
    return ok;
}

std::optional<std::string> RedisConn::get(const std::string& key) {
    redisReply* r = (redisReply*)redisCommand(ctx_, "GET %s", key.c_str());
    std::optional<std::string> out;
    if (r && r->type == REDIS_REPLY_STRING) {
        out = std::string(r->str, r->len);
    }
    if (r) freeReplyObject(r);
    return out;
}

bool RedisConn::del(const std::string& key) {
    redisReply* r = (redisReply*)redisCommand(ctx_, "DEL %s", key.c_str());
    bool ok = r && r->integer >= 1;
    if (r) freeReplyObject(r);
    return ok;
}

RedisConn& threadLocalRedis() {
    thread_local RedisConn conn("127.0.0.1", 6380);  // 用 6380（6379 被 Windows Redis 占了）
    return conn;
}

}  // namespace db
