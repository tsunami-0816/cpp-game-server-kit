#include "battle/KcpSession.h"
#include "battle/KcpServer.h"
#include <sys/socket.h>
#include <arpa/inet.h>
#include <cstring>
#include <unistd.h>
#include <iostream>

namespace battle {

static uint32_t nowMs() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

KcpSession::KcpSession(uint32_t conv, KcpServer* owner, const sockaddr_in& addr)
    : owner_(owner), addr_(addr), last_active_(time(nullptr)) {
    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &addr.sin_addr, ip, sizeof(ip));
    key_.ip = ip;
    key_.port = ntohs(addr.sin_port);

    kcp_ = ikcp_create(conv, this);
    kcp_->user = this;
    ikcp_set_output(kcp_, &KcpSession::udpOutput);
}

KcpSession::~KcpSession() {
    ikcp_release(kcp_);
}

int KcpSession::udpOutput(const char* buf, int len, void* user) {
    KcpSession* self = (KcpSession*)user;
    int fd = self->owner_->udpFd();
    sendto(fd, buf, len, 0, (sockaddr*)&self->addr_, sizeof(self->addr_));
    return len;
}

void KcpSession::onUdpData(const char* data, int len) {
    last_active_ = time(nullptr);
    int ret = ikcp_input(kcp_, data, len);
    if (ret < 0) {
        // 不是 KCP 包（裸 protobuf 测试客户端），直接回调
        if (onMsg) onMsg(this, data, len);
        return;
    }
    // 把解出来的完整包挨个回调
    char buf[2048];
    int n;
    while ((n = ikcp_recv(kcp_, buf, sizeof(buf))) > 0) {
        if (onMsg) onMsg(this, buf, n);
    }
}

int KcpSession::send(const char* data, int len) {
    return ikcp_send(kcp_, data, len);
}

void KcpSession::sendRaw(const char* data, int len) {
    int n = sendto(owner_->udpFd(), data, len, 0, (sockaddr*)&addr_, sizeof(addr_));
    std::cout << "[battle] sendRaw to " << key_.ip << ":" << key_.port << " len=" << len << " ret=" << n << std::endl;
}

void KcpSession::update(uint32_t now_ms) {
    ikcp_update(kcp_, now_ms);
}

}  // namespace battle
