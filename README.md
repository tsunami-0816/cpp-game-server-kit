# cpp-game-server-kit

[![CI](https://github.com/tsunami-0816/cpp-game-server-kit/actions/workflows/test.yml/badge.svg)](https://github.com/tsunami-0816/cpp-game-server-kit/actions/workflows/test.yml)

现代 C++ 游戏服务器基础设施套件：手写 epoll Reactor 网络库 + 无锁日志队列 + Protobuf 登录网关 + KCP 帧同步战斗服。纯后端，无前端、无 HTTP。

## 测试与 CI

- 框架：pytest 四层（L1 单元 / L2 接口 / L3 中间件 / L4 端到端），用例与脚本在 `08_测试/qa-automation/`。
- 本机全量：`cd 08_测试/qa-automation && bash run_pytest.sh -q`（本轮 49 passed / 2 xfailed / 0 failed）。
- P0 冒烟：`python3 p0_runner.py`（7 条主链路用例，台账 `p0_cases.json`）。
- CI（`.github/workflows/test.yml`）：GitHub Actions 无 MySQL/Redis 中间件且不编译 C++，仅跑 `pytest --collect-only` 做用例收集性校验保绿；集成/E2E 全量用例在本机 WSL2 执行。
- 测试产物：`08_测试/全量测试用例清单.md`、`08_测试/基线指标验证表.md`、`08_测试/perf-report.md`、Allure 报告 `08_测试/qa-automation/reports/html/`。

## 技术栈

- C++20（g++ 11.4，协程实验性 `-fcoroutines`）、CMake 3.22
- Protobuf 3.12、hiredis 0.14、MySQL client 8.0、OpenSSL 3.0
- 自研最小 kcp 兼容实现（`third_party/kcp/`）

## 端口

| 服务 | 协议 | 端口 |
|---|---|---|
| echo_server | TCP | 8000 |
| game_gateway | TCP | 8001 |
| battle_server | KCP/UDP | 8002 |
| MySQL | TCP | 3306 |
| Redis | TCP | 6380（避让被占用的 6379） |

## 五步跑起来（Ubuntu 22.04 / WSL2）

### 1. 安装依赖

```bash
sudo apt-get update
sudo apt-get install -y g++ cmake protobuf-compiler libprotobuf-dev \
  libhiredis-dev libmysqlclient-dev libssl-dev mysql-server redis-server
```

### 2. 初始化数据库

```bash
sudo service mysql start
mysql -uroot < 05_代码/backend/sql/schema.sql
mysql -uroot < 05_代码/backend/sql/fix_hash.sql
```

种子账号：`user1` / `user2`，密码均为 `123456`。

### 3. 配置环境

```bash
cp 05_代码/backend/.env.example.template 05_代码/backend/.env
# 按需核对 MySQL/Redis host:port（开发库 root 空密码、Redis 无密码）
```

### 4. 编译

```bash
bash scripts/build.sh
# 产物在 05_代码/backend/build/bin/：
#   echo_server / game_gateway / battle_server / stress_client / bench_queue / echo_baseline
```

### 5. 起服务并压测

```bash
# 起 Redis（6380）
redis-server --port 6380 --bind 127.0.0.1 --daemonize yes

# 终端 A：回显压测服务端
ulimit -n 65535 && ./05_代码/backend/build/bin/echo_server 8000

# 终端 B：1000 连接压测
ulimit -n 65535 && ./05_代码/backend/build/bin/stress_client -c 1000 -d 10 -p 8000
```

登录链路与战斗服回归：

```bash
bash scripts/regress_gateway.sh   # 起 MySQL/Redis + 网关，跑 test_login.py（user1/123456 → code=0 回 token）
bash scripts/regress_battle.sh    # 起战斗服，跑 debug_battle.py（建房→帧输入→广播→重连拉历史）
```

## 目录导航

| 路径 | 内容 |
|---|---|
| `01_项目基线说明书.md` | M1~M8 量化指标与范围边界 |
| `02_架构设计/` | 二轮架构设计（D-01~D-30） |
| `04_任务拆解与开发规范.md` | T-01~T-25 任务与风险级别 |
| `05_代码/backend/` | 后端源码 + `后端开发实现文档.md` |
| `05.5_代码Review/` | 独立代码 Review 报告 |
| `08_测试/perf/` | Echo 链路专题压测与热点分析 |
| `08_测试/perf-report.md` | step8 全量性能汇总（M1/M2/M4/M5/M6 实测 + 瓶颈分析） |
| `08_测试/基线指标验证表.md` | M1–M8 逐条实测归属与达标判定 |
| `08_测试/全量测试用例清单.md` | 51 条用例分层/优先级/类型/结果 |
| `08_测试/qa-automation/` | pytest 四层框架、压测脚本、Allure 报告 |
| `_设计实施映射表.md` | 设计→实施逐条映射与佐证 |
| `_问题台账.md` | 遗留问题与技术债 |

## 已知限制

- M6 性能 A/B 复测比值 1.046（+4.6%），未达 ≥1.30；详见 `08_测试/perf-report.md` §6。
- M8 自研代码 1935 行（wc -l，含注释/空行与压测工具，step10 补 unit_probe 后复测），低于 3000 行下限，列为技术债。
- M5 广播应用层 P99 延迟在裸 UDP 客户端模型下不可测，标为未验证边界。
- WSL 内核与系统 perf 版本不匹配，未出 perf 火焰图，以线程级 CPU 采样替代。
- 日志模块已实现，尚未接入网关/战斗服业务链路。
- 战斗服为最小化自研 kcp 兼容实现，非 skywind3000 原版。
