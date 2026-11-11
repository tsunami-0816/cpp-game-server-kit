// T-11: MySQL 连接（thread_local，每 worker 一个）
#pragma once
#include <mysql/mysql.h>
#include <string>
#include <string_view>
#include <optional>

namespace db {

struct UserRow {
    uint64_t id;
    std::string username;
    std::string password_hash;
    std::string salt;
};

class MysqlConn {
public:
    MysqlConn(const char* host, const char* user, const char* pass, const char* db);
    ~MysqlConn();

    MysqlConn(const MysqlConn&) = delete;
    MysqlConn& operator=(const MysqlConn&) = delete;

    // 按用户名查用户，找不到返回 nullopt
    std::optional<UserRow> findUserByUsername(const std::string& username);

    bool ping();

private:
    MYSQL* conn_ = nullptr;
};

// 每线程一个连接（thread_local）
MysqlConn& threadLocalMysql();

}  // namespace db
