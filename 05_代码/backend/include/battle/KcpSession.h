// T-16: KcpSession —— 一个 UDP 对端 = 一条 KCP 会话
#pragma once
#include "ikcp.h"
#include <string>
#include <netinet/in.h>
#include <functional>
#include <time.h>

namespace battle {

class KcpServer;  // 前置声明

struct AddrKey {
    std::string ip;
    int port;
    bool operator<(const AddrKey& o) const {
        return ip < o.ip || (ip == o.ip && port < o.port);
    }
};

class KcpSession {
public:
    KcpSession(uint32_t conv, KcpServer* owner, const sockaddr_in& addr);
    ~KcpSession();

    // 收到 UDP 包喂进来
    void onUdpData(const char* data, int len);

    // 应用层要发数据
    int send(const char* data, int len);
    // 裸 sendto（不走 KCP 封装，测试客户端用）
    void sendRaw(const char* data, int len);

    // 每 10ms 调一次
    void update(uint32_t now_ms);

    const AddrKey& key() const { return key_; }
    time_t lastActive() const { return last_active_; }

    // 应用层消息回调（收到完整包时调）
    std::function<void(KcpSession*, const char*, int)> onMsg;

    uint64_t uid = 0;  // 登录后绑定
    uint64_t roomId = 0;

private:
    static int udpOutput(const char* buf, int len, void* user);

    IKCP* kcp_;
    KcpServer* owner_;
    sockaddr_in addr_;
    AddrKey key_;
    time_t last_active_;
};

}  // namespace battle
