#include "db/MysqlConn.h"
#include <mysql/mysql.h>
#include <iostream>
#include <cstring>

namespace db {

MysqlConn::MysqlConn(const char* host, const char* user, const char* pass, const char* db) {
    conn_ = mysql_init(nullptr);
    if (!conn_) throw std::runtime_error("mysql_init failed");
    if (!mysql_real_connect(conn_, host, user, pass, db, 3306, nullptr, 0)) {
        std::string err = mysql_error(conn_);
        mysql_close(conn_);
        throw std::runtime_error("mysql connect failed: " + err);
    }
}

MysqlConn::~MysqlConn() {
    if (conn_) mysql_close(conn_);
}

bool MysqlConn::ping() {
    return mysql_ping(conn_) == 0;
}

std::optional<UserRow> MysqlConn::findUserByUsername(const std::string& username) {
    // 预处理语句防 SQL 注入
    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    std::string sql = "SELECT id, username, password_hash, salt FROM users WHERE username=?";
    if (mysql_stmt_prepare(stmt, sql.c_str(), sql.size())) {
        std::cerr << "stmt prepare: " << mysql_stmt_error(stmt) << std::endl;
        mysql_stmt_close(stmt);
        return std::nullopt;
    }

    MYSQL_BIND param = {};
    param.buffer_type = MYSQL_TYPE_STRING;
    param.buffer = (void*)username.c_str();
    param.buffer_length = username.size();
    mysql_stmt_bind_param(stmt, &param);

    if (mysql_stmt_execute(stmt)) {
        std::cerr << "stmt exec: " << mysql_stmt_error(stmt) << std::endl;
        mysql_stmt_close(stmt);
        return std::nullopt;
    }

    UserRow row{};
    uint64_t id;
    char user[65] = {};
    char hash[129] = {};
    char salt[33] = {};
    unsigned long user_len = 65, hash_len = 129, salt_len = 33;

    MYSQL_BIND result[4] = {};
    result[0].buffer_type = MYSQL_TYPE_LONGLONG;
    result[0].buffer = &id;
    result[1].buffer_type = MYSQL_TYPE_STRING;
    result[1].buffer = user;
    result[1].buffer_length = 65;
    result[1].length = &user_len;
    result[2].buffer_type = MYSQL_TYPE_STRING;
    result[2].buffer = hash;
    result[2].buffer_length = 129;
    result[2].length = &hash_len;
    result[3].buffer_type = MYSQL_TYPE_STRING;
    result[3].buffer = salt;
    result[3].buffer_length = 33;
    result[3].length = &salt_len;
    mysql_stmt_bind_result(stmt, result);

    std::optional<UserRow> out;
    if (mysql_stmt_fetch(stmt) == 0) {
        row.id = id;
        row.username = std::string(user, user_len);
        row.password_hash = std::string(hash, hash_len);
        row.salt = std::string(salt, salt_len);
        out = row;
    }
    mysql_stmt_close(stmt);
    return out;
}

// thread_local 每线程一个连接
MysqlConn& threadLocalMysql() {
    thread_local MysqlConn conn("127.0.0.1", "root", "", "cpp_game");
    return conn;
}

}  // namespace db
