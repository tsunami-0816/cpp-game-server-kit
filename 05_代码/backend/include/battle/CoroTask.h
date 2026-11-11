// T-18/M7: C++20 协程任务 —— 战斗服广播循环用 co_await 定时挂起/恢复
// 说明: g++11 协程为实验实现，需编译选项 -fcoroutines（见 CMakeLists）
#pragma once
#include <coroutine>
#include <chrono>
#include <thread>
#include <functional>

namespace battle {

// 空返回值协程任务：co_return 结束，不产生值
struct CoroTask {
    struct promise_type {
        CoroTask get_return_object() { return {}; }
        std::suspend_never initial_suspend() { return {}; }
        std::suspend_never final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() {}
    };
};

// co_await sleep(ms)：挂起当前协程，后台线程睡眠 ms 后恢复
struct SleepAwaiter {
    int ms;
    bool await_ready() const { return ms <= 0; }

    void await_suspend(std::coroutine_handle<> h) {
        std::thread([h, this]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(ms));
            h.resume();  // 到点恢复协程
        }).detach();
    }

    void await_resume() {}
};

inline SleepAwaiter sleepMs(int ms) { return SleepAwaiter{ms}; }

}  // namespace battle
