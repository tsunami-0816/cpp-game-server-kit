// T-06: SPSC 无锁环形队列（演示 M7 concepts + memory_order）
// 单生产者单消费者：生产者线程 push，消费者线程 pop，无线程安全问题（不需要锁）
#pragma once
#include <atomic>
#include <cstddef>
#include <cassert>
#include <concepts>
#include <vector>

namespace log {

// M7 concepts 约束：队列元素必须是 trivially copyable（memcpy 安全）
template<typename T>
requires std::is_trivially_copyable_v<T>
class LockfreeQueue {
public:
    explicit LockfreeQueue(size_t capacity)
        : cap_(capacity), slots_(capacity) {
        head_.store(0, std::memory_order_relaxed);
        tail_.store(0, std::memory_order_relaxed);
    }

    // 生产者调用：尝试 push 一条，队列满返回 false
    bool tryPush(const T& item) {
        size_t head = head_.load(std::memory_order_relaxed);
        size_t next_head = (head + 1) % cap_;
        // 读 tail 用 acquire，和消费者的 release 配对
        size_t tail = tail_.load(std::memory_order_acquire);
        if (next_head == tail) return false;  // 队列满

        slots_[head] = item;
        // release：确保上面的写在 head 推进之前对消费者可见
        head_.store(next_head, std::memory_order_release);
        return true;
    }

    // 消费者调用：尝试 pop 一条，队列空返回 false
    bool tryPop(T& out) {
        size_t tail = tail_.load(std::memory_order_relaxed);
        // 读 head 用 acquire，和生产者的 release 配对
        size_t head = head_.load(std::memory_order_acquire);
        if (tail == head) return false;  // 队列空

        out = slots_[tail];
        // release：确保上面的读在 tail 推进之前完成
        tail_.store((tail + 1) % cap_, std::memory_order_release);
        return true;
    }

    size_t capacity() const { return cap_; }

private:
    size_t cap_;
    std::vector<T> slots_;
    alignas(64) std::atomic<size_t> head_{0};  // 写索引（生产者独占）
    alignas(64) std::atomic<size_t> tail_{0};  // 读索引（消费者独占）
    // alignas(64) 避免伪共享（false sharing）：head 和 tail 落在不同缓存行
};

}  // namespace log
