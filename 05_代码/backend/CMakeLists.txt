cmake_minimum_required(VERSION 3.16)
project(cpp_game_server_kit C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 编译选项
add_compile_options(-Wall -Wextra -Wpedantic -O2)

# 输出目录：build/bin/
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# 找依赖
find_package(Protobuf REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

# hiredis / mysqlclient 是 C 库，手动找
find_library(HIREDIS_LIB hiredis REQUIRED)
find_library(MYSQL_LIB mysqlclient REQUIRED)

# third_party/kcp（暂时空，T-15 再加）
# add_subdirectory(third_party/kcp)

# proto 生成（T-10）
protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS proto/game.proto)
include_directories(${PROTO_HDRS})

# ============ 网络库 + 日志库（静态库，被所有可执行文件链接） ============
add_library(net STATIC
    src/net/FdGuard.cpp
    src/net/Buffer.cpp
    src/net/EventLoop.cpp
    src/net/Channel.cpp
    src/net/TcpServer.cpp
)
target_include_directories(net PUBLIC include)
target_link_libraries(net PUBLIC Threads::Threads)

add_library(log STATIC
    src/log/AsyncLogger.cpp
)
target_include_directories(log PUBLIC include)
target_link_libraries(log PUBLIC Threads::Threads)

add_library(db STATIC
    src/db/MysqlConn.cpp
    src/db/RedisConn.cpp
)
target_include_directories(db PUBLIC include)
target_link_libraries(db PUBLIC ${MYSQL_LIB} ${HIREDIS_LIB})

# T-15: kcp 静态库
add_library(kcp STATIC third_party/kcp/ikcp.c)
set_target_properties(kcp PROPERTIES LINKER_LANGUAGE C)
target_include_directories(kcp PUBLIC third_party/kcp)

# ============ Echo Server（T-05） ============
add_executable(echo_server src/tools/echo_server.cpp)
target_link_libraries(echo_server PRIVATE net log)

# ============ Echo Baseline（M6 对照基线版，单次 read/write） ============
add_executable(echo_baseline src/tools/echo_baseline.cpp)
target_link_libraries(echo_baseline PRIVATE net log)

# ============ bench_queue（T-22 无锁队列压测） ============
add_executable(bench_queue src/tools/bench_queue.cpp)
target_link_libraries(bench_queue PRIVATE log)

# ============ unit_probe（step10 交付阶段组件探针：Buffer/Channel/AsyncLogger/LOG_INFO） ============
add_executable(unit_probe src/tools/unit_probe.cpp)
target_link_libraries(unit_probe PRIVATE net log)

# ============ stress_client（T-21 长连接压测） ============
add_executable(stress_client src/tools/stress_client.cpp)
target_link_libraries(stress_client PRIVATE net log)

# ============ game_gateway（T-14 登录网关） ============
add_executable(game_gateway ${PROTO_SRCS} src/gateway/main_gateway.cpp)
target_link_libraries(game_gateway PRIVATE net log db protobuf::libprotobuf OpenSSL::Crypto)
target_include_directories(game_gateway PRIVATE ${CMAKE_CURRENT_BINARY_DIR})

# ============ battle_server（T-20 KCP 战斗服） ============
add_executable(battle_server ${PROTO_SRCS} src/battle/KcpSession.cpp src/battle/KcpServer.cpp src/battle/main_battle.cpp)
target_link_libraries(battle_server PRIVATE net log db kcp protobuf::libprotobuf)
target_include_directories(battle_server PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_compile_options(battle_server PRIVATE -fcoroutines)  # g++11 协程实验开关

# ============ 后续可执行文件占位（开发时逐步打开） ============
# add_executable(bench_queue src/tools/bench_queue.cpp)
# target_link_libraries(bench_queue PRIVATE net log)
