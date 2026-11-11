// T-15: 最小化 KCP 兼容实现（对齐 skywind3000/kcp 核心 API）
#pragma once
#include <stdint.h>
#include <stddef.h>

#define KCP_RTO_INIT   200
#define KCP_RTO_MIN    100
#define KCP_RTO_MAX    5000
#define KCP_WND_SIZE   128
#define KCP_MTU_DEF    1400
#define KCP_CMD_ACK    2
#define KCP_CMD_PUSH   1

typedef struct IKCPSEGMENT {
    uint32_t conv;
    uint32_t cmd;
    uint32_t sn;
    uint32_t ts;
    int       resendts;
    int       rto;
    size_t    len;
    char      data[KCP_MTU_DEF - 20];
} IKCPSEGMENT;

typedef struct IKCP {
    uint32_t conv;
    uint32_t snd_una;
    uint32_t snd_nxt;
    uint32_t rcv_nxt;
    int      nrcv_buf;
    int      nsnd_buf;

    IKCPSEGMENT snd_buf[KCP_WND_SIZE];
    IKCPSEGMENT rcv_buf[KCP_WND_SIZE];

    int (*output)(const char* buf, int len, void* user);
    void* user;
} IKCP;

#ifdef __cplusplus
extern "C" {
#endif

IKCP* ikcp_create(uint32_t conv, void* user);
void  ikcp_release(IKCP* kcp);
void  ikcp_set_output(IKCP* kcp, int (*output)(const char*, int, void*));
int   ikcp_send(IKCP* kcp, const char* data, int len);
int   ikcp_recv(IKCP* kcp, char* buf, int maxlen);
int   ikcp_input(IKCP* kcp, const char* data, int len);
void  ikcp_update(IKCP* kcp, uint32_t current_ms);

#ifdef __cplusplus
}
#endif
