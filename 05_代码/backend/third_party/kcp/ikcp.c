// T-15: 最小化 KCP 兼容实现
#define _POSIX_C_SOURCE 199309L
#include "ikcp.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>

static uint32_t iclock() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

IKCP* ikcp_create(uint32_t conv, void* user) {
    IKCP* k = (IKCP*)calloc(1, sizeof(IKCP));
    k->conv = conv;
    k->user = user;
    k->snd_una = 1;
    k->snd_nxt = 1;
    k->rcv_nxt = 1;
    return k;
}

void ikcp_release(IKCP* kcp) { free(kcp); }

void ikcp_set_output(IKCP* kcp, int (*output)(const char*, int, void*)) {
    kcp->output = output;
}

// 底层发送一个 kcp segment（20B 头 + data）
static int ikcp_output_seg(IKCP* kcp, IKCPSEGMENT* seg) {
    char pkt[KCP_MTU_DEF];
    int off = 0;
    memcpy(pkt + off, &kcp->conv, 4); off += 4;
    memcpy(pkt + off, &seg->cmd, 4); off += 4;
    memcpy(pkt + off, &seg->sn, 4); off += 4;
    memcpy(pkt + off, &seg->ts, 4); off += 4;
    memcpy(pkt + off, seg->data, seg->len); off += seg->len;
    return kcp->output(pkt, off, kcp->user);
}

int ikcp_send(IKCP* kcp, const char* data, int len) {
    if (len <= 0 || len > (int)sizeof(((IKCPSEGMENT*)0)->data)) return -1;
    if (kcp->nsnd_buf >= KCP_WND_SIZE) return -2;  // 发送窗口满

    IKCPSEGMENT* seg = &kcp->snd_buf[kcp->nsnd_buf++];
    memset(seg, 0, sizeof(*seg));
    seg->conv = kcp->conv;
    seg->cmd = KCP_CMD_PUSH;
    seg->sn = kcp->snd_nxt++;
    seg->len = len;
    seg->rto = KCP_RTO_INIT;
    seg->ts = iclock();
    seg->resendts = seg->ts + seg->rto;
    memcpy(seg->data, data, len);

    ikcp_output_seg(kcp, seg);
    return 0;
}

// 收 UDP 包：解析 kcp 头，处理 PUSH/ACK
int ikcp_input(IKCP* kcp, const char* data, int len) {
    if (len < 16) return -1;
    uint32_t conv, cmd, sn, ts;
    memcpy(&conv, data, 4);
    memcpy(&cmd, data+4, 4);
    memcpy(&sn, data+8, 4);
    memcpy(&ts, data+12, 4);
    if (conv != kcp->conv) return -2;

    if (cmd == KCP_CMD_PUSH) {
        // 新数据包，放进接收缓冲
        if (kcp->nrcv_buf >= KCP_WND_SIZE) return -3;
        IKCPSEGMENT* seg = &kcp->rcv_buf[kcp->nrcv_buf++];
        seg->sn = sn;
        seg->len = len - 16;
        memcpy(seg->data, data + 16, seg->len);
        // 回 ACK
        IKCPSEGMENT ack;
        memset(&ack, 0, sizeof(ack));
        ack.cmd = KCP_CMD_ACK;
        ack.sn = sn;
        ikcp_output_seg(kcp, &ack);
    } else if (cmd == KCP_CMD_ACK) {
        // 确认发送窗口里的包
        for (int i = 0; i < kcp->nsnd_buf; ++i) {
            if (kcp->snd_buf[i].sn == sn) {
                // 擦掉这个已确认的包
                for (int j = i; j < kcp->nsnd_buf - 1; ++j)
                    kcp->snd_buf[j] = kcp->snd_buf[j+1];
                kcp->nsnd_buf--;
                kcp->snd_una++;
                break;
            }
        }
    }
    return 0;
}

int ikcp_recv(IKCP* kcp, char* buf, int maxlen) {
    // 按顺序取 rcv_nxt 对应的包
    for (int i = 0; i < kcp->nrcv_buf; ++i) {
        if (kcp->rcv_buf[i].sn == kcp->rcv_nxt) {
            IKCPSEGMENT* seg = &kcp->rcv_buf[i];
            int n = seg->len < (size_t)maxlen ? seg->len : maxlen;
            memcpy(buf, seg->data, n);
            // 擦掉
            for (int j = i; j < kcp->nrcv_buf - 1; ++j)
                kcp->rcv_buf[j] = kcp->rcv_buf[j+1];
            kcp->nrcv_buf--;
            kcp->rcv_nxt++;
            return n;
        }
    }
    return -1;  // 没有按序的包
}

void ikcp_update(IKCP* kcp, uint32_t current_ms) {
    // 超时重传
    for (int i = 0; i < kcp->nsnd_buf; ++i) {
        IKCPSEGMENT* seg = &kcp->snd_buf[i];
        if ((int)current_ms >= seg->resendts) {
            seg->rto = seg->rto * 2;
            if (seg->rto > KCP_RTO_MAX) seg->rto = KCP_RTO_MAX;
            seg->resendts = current_ms + seg->rto;
            seg->ts = current_ms;
            ikcp_output_seg(kcp, seg);
        }
    }
}
