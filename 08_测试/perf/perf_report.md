# M6 性能调优报告（Echo Server 链路）

## 1. 测试环境
- WSL2 Ubuntu-22.04，g++ 11.4.0，Release `-O2`，12th Gen i5-12500H（16 核），7.8GB 内存
- 被测：自研 echo_server（手写 epoll Reactor，3 worker 线程）
- 压测：自研 stress_client（单线程 epoll，1000 长连接，64B 定长心跳，回环 127.0.0.1:8000）
- 口径：每轮 10 秒，各版本跑 3 轮取平均；`ulimit -n 65535`

## 2. 工具与方法说明
- **perf top/record 在本环境不可用**：WSL 内核 `6.18.33.2-microsoft` 与系统 perf（5.15 配套）版本不匹配，`perf --version` 报 `perf not found for kernel`，无法生成 perf 采样与火焰图。
- 替代定位手段：`ps -o %cpu,%mem,nlwp` 进程级采样 + `top -b -n 1 -H` 线程级采样，在压测第 5 秒快照（证据 `evidence/cpu_sample.txt`）。
- A/B 对照：同一压测模型下分别跑初始版 `echo_baseline` 与优化版 `echo_server`，各 3 轮，避免跨版本系统负载漂移。

## 3. 热点定位（CPU 采样，压测中快照）

| 进程 | 线程数 NLWP | 进程 CPU% | 说明 |
|---|---|---|---|
| echo_server（服务端） | 4（1 accept + 3 worker） | 16.6% | 各 worker 线程 6.2%~18.8%，均未打满 |
| stress_client（客户端） | 1（单线程） | 36.0% | 单核未打满，仍在 epoll_wait 等回显 |
| 整机 | — | idle 89.7%，load avg 0.83 | 系统资源大量空闲 |

**定位结论**：服务端与客户端 CPU 均未打满，整机近 90% 空闲，瓶颈**不在用户态热点函数**，而在：
1. 回环 TCP 的 RTT 与 epoll 唤醒粒度（小包 64B，每包 read+write 两次系统调用，延迟主导吞吐）；
2. 服务端回调内同步 read/write 的 Reactor 模型，worker 未做完整异步读写流水线；
3. 压测客户端单线程串行 write 1000 个 fd，发包节奏受限。

echo 回显路径本身不构造 `std::string`/`std::vector`，基线说明书列举的 string_view、vector 预分配、move 等优化手段在该路径上无可作用的分配热点——这是本项目 echo 链路与典型业务网关路径的客观差异。

## 4. A/B 前后对比（1000 连接 × 10 秒 × 3 轮）

### 初始版 echo_baseline（单次 read、`::write` 回写）

| 轮次 | QPS（回显/s） | 平均延迟 ms | 最大延迟 ms | 断开 | 客户端 RSS MB |
|---|---|---|---|---|---|
| 1 | 79859 | 12.070 | 15.764 | 0 | 3.71 |
| 2 | 79169 | 12.179 | 16.845 | 0 | 3.66 |
| 3 | 78205 | 12.330 | 17.291 | 0 | 3.65 |
| **平均** | **79078** | **12.193** | 16.60 | **0** | 3.67 |

### 优化版 echo_server（read 循环读尽 + send MSG_NOSIGNAL + 回调 const& 传参）

| 轮次 | QPS（回显/s） | 平均延迟 ms | 最大延迟 ms | 断开 | 客户端 RSS MB |
|---|---|---|---|---|---|
| 1 | 81785 | 11.791 | 16.517 | 0 | 3.65 |
| 2 | 80022 | 12.049 | 16.288 | 0 | 3.71 |
| 3 | 82177 | 11.766 | 15.459 | 0 | 3.66 |
| **平均** | **81328** | **11.869** | 16.09 | **0** | 3.67 |

### 对比判定

| 指标 | 初始版 | 优化版 | 变化 |
|---|---|---|---|
| 平均 QPS | 79078 | 81328 | **×1.029（+2.9%）** |
| 平均延迟 ms | 12.193 | 11.869 | -2.7% |
| 断开数 | 0 | 0 | 持平 |
| RSS MB | 3.67 | 3.67 | 持平 |

## 5. 已实施的优化
1. **回调上下文 `const ChannelCtx&` 传参**：`Channel` 三个回调由按值传 `std::variant` 改为 const 引用，消除每次读事件的 variant 拷贝（`include/net/Channel.h`）。
2. **read 循环读尽内核缓冲**：读回调改为循环 `read` 直到 `EAGAIN/EWOULDBLOCK`，减少同一次 epoll 唤醒内遗留数据触发的二次 EPOLLIN。
3. **回写 `send(..., MSG_NOSIGNAL)`**：替代 `::write`，对端已关闭时不触发 SIGPIPE，避免服务端被信号杀掉。
4. **worker 线程数校准**：实测 8 worker 因过度线程调度反而降速，回退到 3 worker（与 CPU 采样结论一致：服务端本就不饱和）。

## 6. M6 达成判定
- **判据**：调优后 QPS / 初始 QPS ≥ **1.30**。
- **实测**：比值 **1.029（+2.9%）**，**未达到 1.30 目标**。
- **归因**：
  - echo 回显路径无用户态内存/字符串分配热点，微优化（拷贝消除、循环读尽）收益为个位数百分比；
  - 瓶颈是回环 RTT、epoll 唤醒粒度与同步 read/write 模型，属于架构层面限制，非局部代码微调可突破；
  - 压测客户端单线程，尚未解除其发包侧瓶颈，服务端吞吐未被打满，无法在当前模型下体现服务端侧的上限收益。
- **诚实说明**：本报告未虚构 perf 截图与提升比例；1.30 目标在当前 MVP 架构与单线程压测模型下客观未达成，列为技术债，见第 7 节。

## 7. 后续优化路线（step8 全量测试 / 迭代）
1. **压测客户端多线程化**：连接分片到 N 个发包线程，各自独立 epoll，atomic 汇总指标，先解除客户端瓶颈，使服务端成为被测对象后再复测服务端上限。
2. **服务端异步读写流水线**：连接写缓冲 + EPOLLOUT 关注，回调内只入队，由 loop 批量 flush；替代当前回调内同步 send。
3. **accept 线程 epoll 化**：listen fd 挂主 loop epoll，替换 `usleep(1000)` 轮询，消除 accept 路径 busy/休眠抖动。
4. **序列化路径优化（网关/战斗服）**：LoginRsp/FrameBroadcast 的 `std::string`/repeated 字段做 `Reserve` 预分配、`string_view` 传参、`std::move` 转移所有权——该路径才是 string/vector 优化的落点，echo 路径不适用。
5. 具备原生 Linux 内核的环境补跑 `perf record/report`，出真实热点函数栈与火焰图。

## 8. 证据文件清单（`08_测试/perf/evidence/`）
- `stress_baseline_ab.txt`：初始版 3 轮原始压测输出
- `stress_optimized_ab.txt`：优化版 3 轮原始压测输出
- `cpu_sample.txt`：压测中 ps/top -H 线程级 CPU 采样快照
- `cpu_stress.txt`：采样轮次压测结果（66283 QPS / 14.56ms）
- `stress_echo_1000conn.md`：1000 连接初步长连接验证记录（M1）

## 9. 复现命令
```bash
# A/B 对比（1000 连接，10s，各 3 轮）
bash scripts/bench_ab.sh 1000 10 3
# 单版压测
bash scripts/bench_stress.sh 1000 10 3 /tmp/bench.log
# CPU 采样
bash scripts/probe_cpu.sh
```
