// T-08: LOG_INFO 宏，用 C++17 fold expression 拼接参数
#pragma once
#include "log/AsyncLogger.h"
#include <sstream>
#include <string>
#include <type_traits>

namespace log_detail {

// 把任意类型转成字符串
template<typename T>
std::string toString(const T& v) {
    if constexpr (std::is_convertible_v<T, const char*>) {
        // 覆盖 const char* / char* / 字符串字面量（const char[N]）
        return std::string(v);
    } else {
        return std::to_string(v);
    }
}

// 把参数按顺序 fold 拼接（LOG_INFO 宏实际调用的版本）
template<typename... Args>
std::string concatAll(const Args&... args) {
    std::ostringstream oss;
    (oss << ... << toString(args));  // fold expression 折叠
    return oss.str();
}

}  // namespace log_detail

#define LOG_INFO(...) \
    do { \
        auto _s = log_detail::concatAll(__VA_ARGS__); \
        ::log::AsyncLogger::instance().push(_s.c_str(), _s.size()); \
    } while(0)
