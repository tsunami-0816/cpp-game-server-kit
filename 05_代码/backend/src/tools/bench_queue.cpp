// T-22: bench_queue 无锁队列压测
// 用法: ./bench_queue [总条数]
// 单线程 push，另一个线程 pop，统计 QPS 和对账条数
#include "log/LockfreeQueue.h"
#include <iostream>
#include <thread>
#include <atomic>
#include <chrono>
#include <cstdlib>

int main(int argc, char* argv[]) {
    size_t total = 1'000'000;
    if (argc > 1) total = std::stoull(argv[1]);

    log::LockfreeQueue<int> q(1 << 16);  // 65536 容量
    std::atomic<size_t> popped{0};

    // 消费者线程
    std::thread consumer([&]() {
        int x;
        while (popped.load() < total) {
            if (q.tryPop(x)) popped.fetch_add(1);
        }
    });

    // 生产者线程
    auto t0 = std::chrono::steady_clock::now();
    size_t pushed = 0;
    for (size_t i = 0; i < total; ++i) {
        while (!q.tryPush(static_cast<int>(i))) {
            // 队列满，等消费者消费
        }
        pushed++;
    }
    consumer.join();
    auto t1 = std::chrono::steady_clock::now();

    double seconds = std::chrono::duration<double>(t1 - t0).count();
    double qps = total / seconds;

    std::cout << "=== LockfreeQueue 压测结果 ===" << std::endl;
    std::cout << "总条数: " << total << std::endl;
    std::cout << "push: " << pushed << "  pop: " << popped.load() << std::endl;
    std::cout << "耗时: " << seconds << " s" << std::endl;
    std::cout << "QPS: " << (size_t)qps << " 条/s" << std::endl;

    if (pushed == popped.load()) {
        std::cout << "✅ 零丢失" << std::endl;
        return 0;
    } else {
        std::cout << "❌ 丢失 " << (pushed - popped.load()) << " 条" << std::endl;
        return 1;
    }
}
