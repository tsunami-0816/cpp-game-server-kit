// T-14: game_gateway 登录网关主程序
// 监听 TCP 8001，收 LoginReq → 查 MySQL → 写 Redis session → 回 LoginRsp
#include "net/TcpServer.h"
#include "net/EventLoop.h"
#include "db/MysqlConn.h"
#include "db/RedisConn.h"
#include "proto_codec/Codec.h"
#include "game.pb.h"
#include <openssl/sha.h>
#include <iostream>
#include <string>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <cstring>

using namespace net;

// sha256 转 hex
static std::string sha256Hex(const std::string& input) {
    unsigned char buf[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(input.data()), input.size(), buf);
    static const char* hex = "0123456789abcdef";
    std::string out;
    out.reserve(SHA256_DIGEST_LENGTH * 2);
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        out.push_back(hex[buf[i] >> 4]);
        out.push_back(hex[buf[i] & 0xf]);
    }
    return out;
}

// 生成 32 字节随机 token
static std::string genToken() {
    char buf[32];
    int fd = open("/dev/urandom", O_RDONLY);
    read(fd, buf, 32);
    close(fd);
    static const char* hex = "0123456789abcdef";
    std::string out;
    for (int i = 0; i < 32; ++i) {
        out.push_back(hex[(unsigned char)buf[i] >> 4]);
        out.push_back(hex[(unsigned char)buf[i] & 0xf]);
    }
    return out;
}

int main() {
    // 先初始化 DB 连接（主线程）
    db::threadLocalMysql();
    db::threadLocalRedis();
    std::cout << "[gateway] DB connected" << std::endl;

    TcpServer server(8001, 3);

    server.setConnCallback([](int client_fd, EventLoop* loop) {
        std::cout << "[gateway] new conn fd=" << client_fd << std::endl;
        char buf[4096];
        while (true) {
            ssize_t n = ::read(client_fd, buf, sizeof(buf));
            if (n <= 0) { ::close(client_fd); break; }

            // 解包头
            auto body_len = codec::tryDecodeHeader(buf, n);
            if (!body_len) { ::close(client_fd); break; }
            if (n < 4 + *body_len) { ::close(client_fd); break; }

            // 反序列化 LoginReq
            game::LoginReq req;
            if (!req.ParseFromArray(buf + 4, *body_len)) {
                // 4001 协议解析失败
                ::close(client_fd);
                break;
            }

            // 查 MySQL
            auto& mysql = db::threadLocalMysql();
            auto user = mysql.findUserByUsername(req.username());
            game::LoginRsp rsp;

            if (!user) {
                rsp.set_code(1001);
                rsp.set_msg("user not found");
            } else {
                std::string calc_hash = sha256Hex(user->salt + req.password());
                if (calc_hash != user->password_hash) {
                    rsp.set_code(1002);
                    rsp.set_msg("wrong password");
                } else {
                    // 写 Redis session
                    std::string token = genToken();
                    std::string key = "session:" + std::to_string(user->id);
                    db::threadLocalRedis().setEx(key, token, 7200);
                    rsp.set_code(0);
                    rsp.set_token(token);
                    rsp.set_uid(user->id);
                    rsp.set_msg("ok");
                }
            }

            // 回包
            std::string body = rsp.SerializeAsString();
            std::string packet = codec::encode(body);
            ::write(client_fd, packet.data(), packet.size());
        }
    });

    std::cout << "[gateway] listening on 0.0.0.0:8001" << std::endl;
    server.start();
    return 0;
}
