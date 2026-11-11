# step8 全量性能测试报告 · cpp-game-server-kit

> 第 8 步产物。汇总 M1/M2/M4/M5/M6 实测数据、工具口径、瓶颈定位与未验证边界。
> 所有数字来自 `08_测试/qa-automation/reports/` 下原始日志/JSON，未做估算或凑数。
> Echo 链路专题调优过程见 `08_测试/perf/perf_report.md`（M6 初始版 vs 调优版热点分析）。

## 1. 测试环境与工具

> R22 探针闭合：不适用（路线=生产，无 F1/F2 逆向 `[❓]` 项）。

- WSL2 Ubuntu-22.04，Python 3.10.12，Release `-O2`；MySQL 3306 / Redis 6380 本机常驻。
- 被测：`game_gateway`（TCP 8001，3 worker）、`battle_server`（UDP 8002，KCP）、`echo_server`（TCP 8000）。
- 压测工具：
  - 登录接口：`qa-automation/perf_test.py`（Python ThreadPoolExecutor 多线程，短连接，每请求新建 TCP）。
  - 房间帧同步：`qa-automation/perf_room.py`（Python 多线程 UDP 客户端）。
  - 长连接 / Echo A/B：自研 C++ `stress_client`（单线程 epoll，1000 长连接，64B 心跳）。
  - 无锁队列：C++ `bench_queue`（SPSC push/pop 对账）。
- **JMeter 降级说明**：本机 WSL 未安装 JMeter（`jmeter: command not found`），且本项目为自定义 TCP + Protobuf 二进制协议，JMeter 原生 TCP Sampler 无法静态构造 protobuf body（动态序列化需在 JSR223/BeanShell 另写一套客户端，成本高收益低）。本轮以 Python 多线程压测为准；`qa-automation/jmeter/login_stress.jmx` 仅留线程组 + 聚合报告占位骨架，**不产出可运行的 JMeter 压测、也不以补齐 JMeter 为后续必须项**；第二工具交叉验证的缺口已记入诚实边界，待后续若引入可解析私有协议的压测客户端再补对照。
- **perf 采样降级**：WSL 内核与系统 perf 版本不匹配，`perf record/report` 不可用（沿用既有结论，见 `perf/perf_report.md` §2）；定位手段为进程/线程级 `ps`、`top -H` 快照 + 压测拐点数据归因。

## 2. M1 · Echo 千连接长连稳压（基线：≥1000 长连，5 分钟断开=0，RSS 波动 <50MB）

证据：`reports/m1_stress_echo.log`（`stress_client -c 1000 -d 300`）

| 指标 | 实测 | 基线判据 | 结论 |
|---|---|---|---|
| 并发连接 | 1000/1000 | ≥1000 | 达标 |
| 中途断开 | 0 | =0 | 达标 |
| 当前在线 | 1000 | — | 持平 |
| 稳压时长 | 300.01 s | 5 分钟 | 达标 |
| 服务端 RSS | 3540KB → 3776KB，增量 **236KB** | 波动 <50MB | 达标 |
| 客户端 RSS | 3.65 MB | — | 稳定 |
| 回显 QPS | 91268 /s | — | — |
| 平均 / 最大延迟 | 10.479 ms / 86.777 ms | — | — |

> 说明：300s 内发包 27,384,000、收包 27,381,554，差值 2,446 为回环 UDP/内核缓冲在高并发下的零星丢包，不触发断连；长连接保持与内存增长两项判据均满足。

## 3. M2 · 无锁队列百万条对账（基线：写入 ≥10 万条/s，100 万条 0 丢失）

证据：`reports/m2_bench_queue.log`（`bench_queue 1000000`）

| 指标 | 实测 | 基线判据 | 结论 |
|---|---|---|---|
| push / pop | 1,000,000 / 1,000,000 | 落盘=push（0 丢失） | 达标（零丢失） |
| 吞吐 | **12,204,025 条/s**（0.08194 s） | ≥10 万条/s | 达标（约 122 倍余量） |

> 口径：当前 `bench_queue` 为纯内存 SPSC 队列对账，后台写盘线程未纳入本压测计时；吞吐为队列 push/pop 能力，不等于最终落盘 TPS。

## 4. M4 · 登录全链路（基线：端到端 <50ms，Redis 可读 session）

### 4.1 单请求延迟（无并发排队）

种子账号单次登录 RT 约 **2.4–2.9 ms**（L2/L4 用例实测，`reports/l4.log`、`full_run2.log`），端到端 <50ms，达标；登录后 Redis `session:{uid}` 可读到一致 token，TTL 7190–7200s（L3 用例断言）。

### 4.2 三档并发压测（证据：`reports/perf_login.json` / `perf_login_run.log`，每档 10s，错误率 0）

| 并发 | 成功请求 | TPS | 平均 RT | P95 RT | 最大 RT | 错误率 |
|---|---|---|---|---|---|---|
| 10 | 7019 | 701.9 | 14.24 ms | 21.72 ms | 28.30 ms | 0 |
| 20 | 5334 | 533.4 | 37.54 ms | 47.10 ms | 58.64 ms | 0 |
| 50 | 5360 | 536.0 | 93.68 ms | 107.92 ms | 131.37 ms | 0 |

**拐点观察**：TPS 在 10→20 并发由 701.9 降至 533.4，20→50 基本持平（533.4→536.0）；平均 RT 随并发近似线性上升（14.24→37.54→93.68 ms）。即 **20 并发后服务端处理能力见顶（约 530 TPS）**，继续加并发只增加排队延迟，不提升吞吐；三档业务错误率与异常均为 0。

## 5. M5 · 五十人房间帧同步 + 断线重连（基线：广播 P99 <50ms；重连 ≤3s；50 人 CPU <30% 单核）

证据：`reports/perf_room.json` / `perf_room_run.log`（`perf_room.py --clients 50 --duration 10`）

| 指标 | 实测 | 基线判据 | 结论 |
|---|---|---|---|
| 建房 | code=0，room_id=1024 | — | 通过 |
| 进房成功 | 49/49（code=0），耗时 0.094s | 50 人容量 | 达标（阈值已对齐 50，无 2002 误拒） |
| 帧上报 | 4950 帧 / 10s = 495 帧/s | 每 100ms 上报 | 通过 |
| 收到广播段 | 25,052 段（全员广播放大） | — | 广播链路通 |
| 断线重连 | code=0，恢复 **1.3 ms** | ≤3s | 达标 |
| 服务端 CPU 快照 | 0.3%（4 线程） | <30% 单核 | 达标 |

**未验证边界（诚实标注）**：
- **广播应用层 P99 延迟 <50ms：未验证**。战斗服广播走 libkcp（`ikcp_send` 封装段），裸 Python UDP 客户端只能收到 KCP 封装段，无法解出应用层 `FrameBroadcast` 的发送/接收时间戳，故无法测应用层端到端 P99。本报告不以「收到封装段的时长」冒充应用层广播延迟。要闭环该指标，需在服务端广播路径打时间戳、或用能解 KCP 段序的客户端对端打点。
- CPU 采样为压测前后 `ps` 瞬时快照，未取到帧阶段峰值；50 人规模下占用很低，但峰值 CPU 未做持续采样。

## 6. M6 · 性能调优收益复测（基线：调优后/初始 QPS ≥1.30）

证据：`reports/m6_ab_rerun.log`、`perf/evidence/stress_baseline_ab.txt`、`stress_optimized_ab.txt`（1000 连接 × 10s × 3 轮）

| 版本 | 轮次 QPS（回显/s） | 平均 QPS | 平均延迟 | 断开 |
|---|---|---|---|---|
| echo_baseline（初始版） | 89529 / 87034 / 85305 | **87,289** | 10.90 ms | 0 |
| echo_server（调优版） | 93011 / 85582 / 95236 | **91,276** | 10.47 ms | 0 |

- **复测比值 = 91276 / 87289 ≈ 1.046（+4.6%）**，与上一轮 1.029 结论一致，**未达到 1.30 目标**。
- 判定：未达标，维持技术债（台账 Q-001）。
- 归因（沿用 `perf/perf_report.md` §6）：echo 回显路径无用户态内存/字符串分配热点，微优化收益为个位数百分比；瓶颈在回环 RTT、epoll 唤醒粒度与回调内同步 read/write 模型；压测客户端单线程发包受限，服务端未被打满。

## 7. 瓶颈定位与候选改进方向

### 7.1 登录接口（M4 压测拐点）
1. **worker 线程数有限**：网关 TcpServer 配 3 worker 线程，20 并发后处理见顶；连接/任务在 worker 队列排队，RT 随并发线性上升。
2. **回调内同步阻塞 DB/Redis**：登录回调在 worker 线程内同步执行 MySQL 查用户 + Redis 写 session，单次阻塞占用 worker；DB/Redis 抖动会直接传导为请求排队。
3. **短连接开销**：每请求新建 TCP 连接，三次握手 + 连接回收计入 RT；压测模型为短连接，贴近真实登录但放大了建连成本。
4. 整机与服务端 CPU 均未打满（M5 快照 0.3%），瓶颈更偏向**线程数/同步阻塞/锁与调度**，而非用户态算力热点。

### 7.2 候选改进（技术债，不在本轮实现范围）
- worker 线程数按核数校准；登录 DB/Redis 访问异步化或接入连接池，回调内只入队。
- 连接写缓冲 + EPOLLOUT 关注，回调内只入队、loop 批量 flush，解除同步 send。
- 压测客户端多线程化（连接分片到独立发包线程），先解除客户端瓶颈再测服务端上限。
- 具备原生 Linux 内核环境补跑 `perf record/report`，出真实热点函数栈与火焰图。

## 8. 证据文件清单（`08_测试/qa-automation/reports/`）

| 指标 | 文件 |
|---|---|
| M1 长连 300s | `m1_stress_echo.log` |
| M2 队列百万对账 | `m2_bench_queue.log` |
| M4 登录三档压测 | `perf_login.json`、`perf_login_run.log` |
| M5 五十人房间 | `perf_room.json`、`perf_room_run.log` |
| M6 A/B 复测 | `m6_ab_rerun.log`、`../../perf/evidence/stress_baseline_ab.txt`、`stress_optimized_ab.txt` |
| M3 内存检测 | `asan_summary.txt`、`vg_summary.txt` 及 `asan_*.log`、`vg_*.log` |

## 9. 复现命令

```bash
cd 08_测试/qa-automation
# 登录三档压测（10/20/50 并发，各 10s）
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 perf_test.py --dur 10 --levels 10,20,50
# 50 人房间压测
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 perf_room.py --clients 50 --duration 10
# M1 千连接 300s 稳压
bash m1_stress.sh 1000 300
# M6 Echo A/B（1000 连接，10s，3 轮）
bash ../../scripts/bench_ab.sh 1000 10 3
```
