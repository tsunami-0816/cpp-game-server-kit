# 第 5.5 步 独立代码 Review 报告

- **结论：🟢 通过（附条件）** —— stage6 机器闸门 0 ❌，三条主链路（echo 回显 / M4 登录 / M5 建房·广播·重连）复跑可重现；但存在 8 行映射降级、若干 P1 设计偏离与并发/内存隐患，列入第三、五节，需人工确认并在第 6/7 步闭环。本报告不替代第 9 步最终验收。
- **reviewer 上下文**：独立 sub-agent，全新上下文，未参与 5A/5B 任何产品源码、脚本、文档编写；所有结论以本次亲自读码 + WSL 复跑输出为准，不采信实施者自评。
- **审查范围**：
  - 网络库 `include/net/*`、`src/net/*`（FdGuard / Buffer / Channel / EventLoop / TcpServer）
  - 无锁日志 `include/log/*`、`src/log/*`（LockfreeQueue / AsyncLogger / LogMacros）
  - 协议与存储 `include/proto_codec/*`、`include/db/*`、`src/db/*`、`proto/game.proto`、`sql/*`
  - 登录网关 `src/gateway/main_gateway.cpp`
  - 战斗服 `include/battle/*`、`src/battle/*`、`third_party/kcp/*`
  - 压测工具 `src/tools/*`、`scripts/*`、`08_测试/perf/perf_report.md`、`README.md`、`_问题台账.md`
- **审查环境**：WSL2 Ubuntu-22.04；MySQL 3306 active；Redis 6380 PONG；干净重建 `build/` 后复跑。
- **映射表复核**：全表 30 行逐行核实（高风险 P0 任务对应 10 项 + 前 1/3 D-01~D-10 全读源码 + 全部原 ✅ 行回查证据）；**降级 8 行**：D-02、D-03、D-08、D-09、D-12、D-17、D-18、D-20（明细见第一节末表）。

## 前置机器闸门记录（真实输出）

命令（在工作流仓工具目录下，对本项目目录执行）：

```
python3 scripts/design_impl_check.py projects/cpp-game-server-kit --stage 6 --json
```

- **复核前**（实施者自填口径）：`total=30, verified=29, unverified=1, missing=0, cut=0, status=OK`。
- **本次降级后复跑**：

```json
{
  "stage": "6", "status": "OK", "total": 30,
  "verified": 21, "unverified": 9, "missing": 0, "cut": 0,
  "evidence_missing": 0, "invalid_rows": []
}
```

stage6 只阻塞 ❌未实现：**0 ❌，闸门通过**。9 条 ⚠️ 在 stage9/10 会转为阻塞，须在后续步骤补验证或补实现。

---

## 第一层 需求正确性

> 核实方式分两类：**文件:行号** 直接读码；**命令+输出** 本次 WSL 复跑。证据列空话（"编译通过/已验证/就绪"）不作为通过依据。

### 1.1 复跑记录（本次亲自执行）

| 编号 | 命令 | 真实输出摘要 | 结论 |
|---|---|---|---|
| 闸门 | `design_impl_check.py --stage 6 --json` | 30 条 / 21✅ / 9⚠️ / 0❌，status=OK | 通过 |
| D-07/D-23 | `build/bin/bench_queue 1000000` | push=1,000,000，pop=1,000,000，✅ 零丢失；QPS 34,238,987 条/s（本机本次值；原表记 1657 万/s 为当次实测，量级远超 ≥10 万/s 判据） | 通过 |
| D-27 | `bash scripts/check_modern_cpp.sh` | 命中类别 5/5（RAII / 移动语义 / variant·optional / concepts / 协程），exit 0 | 通过 |
| D-06 | `python3 test_echo.py` | 发送 `hello-cpp-game`，收到 `hello-cpp-game`，✅ T-05 冒烟通过，exit 0 | 通过 |
| D-15/D-16/D-28 | `bash scripts/regress_gateway.sh` | EXIT=0；`code=0 msg=ok uid=1`，回包携带 token（前缀 `f8b38c2000fc0d36…`，运行时会话令牌）；`redis-cli -p 6380 get session:1` 有值，`TTL session:1` = 7143（SETEX 7200 生效） | 主链路通过（缺陷见第二、三层） |
| D-17/D-18/D-19/D-20 | `bash scripts/regress_battle.sh` | EXIT=0；`CreateRoomRsp type=2 room_id=1000`；`FrameBroadcast type=6 frame=0 inputs=1 input=42`；`RejoinRoomRsp type=8 code=0 frame_no=1 history=0` | 回包链路通；**重连历史 history=0**，见 D-20 降级 |
| D-25 | 干净重建：`rm -rf build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j$(nproc)` | cmake_exit=0，make_exit=0，无 error；产出 6 个二进制（echo_server / echo_baseline / bench_queue / stress_client / game_gateway / battle_server）；**warning 26 行**（见 1.3） | 编译通过，warning 未清零 |
| D-24 | 哈希复核（PowerShell SHA256） | `sha256("salt1123456")=55baa696…f7388c` 与 `sql/schema.sql:16` 一致；`sha256("salt2123456")=63e48047…3a5e6` 与 `schema.sql:17` 一致；代码拼接顺序 `salt+password`（`main_gateway.cpp:85`）与种子一致 | 通过 |
| Q-002 | `wc -l include/*/*.h src/*/*.cpp`（不含 third_party / pb 生成 / build） | **1748 行**，与台账 Q-002 登记一致 | 台账诚实 |

### 1.2 逐行核实结论

| 编号 | 核实方式（文件:行号 / 命令+输出） | 结论 |
|---|---|---|
| D-01 | `include/net/FdGuard.h:11` 析构 close；`:16-24` 移动构造/赋值、删除拷贝；`test_echo.py` 复跑通过。RAII 代码存在；但证据列"test_echo 跑通"并未做退出后 fd 泄漏核查（lsof），RAII 释放未被运行证据直接覆盖 | ✅ 保留（建议第 8 步补 fd 泄漏核查证据） |
| D-02 | `include/net/Buffer.h:14-40`：append/take/tryPeekBodyLen 存在；`:33-40` 未做 4MB 上限校验（上限只在 `Codec.h:11,29`）；网关链路实际未使用 Buffer（`main_gateway.cpp:58-66` 直接栈上 `char buf[4096]` read）；粘包/半包无对应用例，`test_echo.py` 仅单包 | **⚠️ 降级**（原 ✅已实现已验证 → ⚠️已实现未验证） |
| D-03 | `include/net/Channel.h:10-13` variant 三态上下文；`:29-31` 三类回调；`src/net/Channel.cpp:5-6` 仅 enable/disableWriting。variant 类型存在，但 TimerCtx/KcpCtx 两条上下文路径无运行验证；原状态写"✅已实现未验证"属口径混用 | **⚠️ 降级并更正状态口径**（→ ⚠️已实现未验证） |
| D-04 | `src/net/EventLoop.cpp:22-38` epoll_wait 循环 + 事件分发；`cpu_sample.txt` 显示 echo_server NLWP=4（1 accept + 3 worker）；`test_echo.py` 复跑通过。worker loop 在 echo 路径上承载事件 | ✅ 保留（备注：网关路径未走 worker，见 D-05/第三层） |
| D-05 | `src/net/TcpServer.cpp:40-42` 建 N 个 loop；`:78` atomic round-robin 选 loop；`:80` 回调传出 loop。轮询选择代码存在；但回调是否把连接挂到 worker loop 由各业务自己决定（网关未挂，见第三层）；设计目录中的独立 `WorkerThreadPool.h` 未单独立文件，线程池内联在 TcpServer | ✅ 保留（结构合并，功能在 echo 路径验证） |
| D-06 | `src/tools/echo_server.cpp:49-64` 读尽循环 + `send(MSG_NOSIGNAL)`；`test_echo.py` 复跑收发一致 | ✅ 通过 |
| D-07 | `include/log/LockfreeQueue.h:14` concepts 约束；`:24-35` tryPush（tail acquire / head release）；`:38-48` tryPop（head acquire / tail release）；`:55-56` 缓存行对齐；`bench_queue 100 万` 复跑零丢失 | ✅ 通过（内存序配对正确；SPSC 单生产者限制见第三层） |
| D-08 | `include/log/AsyncLogger.h`、`src/log/AsyncLogger.cpp:14-60` 实现存在；src 全量 grep **无 LOG_INFO/LOG_ERROR 业务调用**（Q-004 属实）；`AsyncLogger.cpp:38` 队列满静默丢日志；`writerLoop` 停止冲刷逻辑薄弱（`:43,:57`） | **⚠️ 降级**（原 ✅已实现未验证 → ⚠️已实现未验证；台账 Q-004 已登记未接入） |
| D-09 | `include/log/LogMacros.h:32-36` concatAll fold 编译通过；`:21-28` `format()` 定义后**从未被调用**，`{}` 占位符未做替换；宏拼接参数但不解析占位符；未接入业务链路 | **⚠️ 降级**（→ ⚠️已实现未验证） |
| D-10 | `include/proto_codec/Codec.h:14-20` encode 大端；`:24-31` tryDecodeHeader；`test_login.py:25` `struct.pack(">I", …)` 对齐；M4 复跑编解码通。边界：`:29` 超长/空包与解析失败都返回 nullopt，调用方无法区分 4001/4002（见第二层） | ✅ 保留（协议主路径通过；错误分支缺失见第二层） |
| D-11 | `proto/game.proto:5-19` 九则消息与设计 §5.2 一致；二进制实际链接生成 pb（登录/战斗两条链路复跑解析成功） | ✅ 通过 |
| D-12 | `src/db/MysqlConn.cpp:85-88` thread_local 惰性单连接；单链路登录实测 code=0。**设计要素未落地**：无连接池、未按 worker 数预建 N 连接、worker 线程未持有连接；`:33,:45,:72` prepare/exec 失败与查无此户都返回 `nullopt`，调用方无法分流 3001/1001 | **⚠️ 降级**（原 ✅已实现已验证 → ⚠️已实现未验证） |
| D-13 | `src/db/RedisConn.cpp:19-25` setEx、`:27-35` get、`:37-42` del；`:44-47` thread_local 6380；`session:1` 写入复跑确认。封装功能通；但房间/帧历史所需 HSET/HGETALL/LRANGE/RPUSH/LTRIM/INCR 方法均未实现 | ✅ 保留（封装本身验证通过；房间/帧 Redis 缺口计入 D-18/D-20） |
| D-14 | `src/db/MysqlConn.cpp:26-82` 预处理语句防注入；`UserRow` 字段与 `schema.sql:6-9` 对齐；种子哈希复核一致。异常分流缺陷同 D-12 | ✅ 保留（备注 DB 异常被归并为"用户不存在"） |
| D-15 | `src/gateway/main_gateway.cpp:54` 监听 8001；regress_gateway 复跑 `listening on 0.0.0.0:8001`、新连入 fd=10 | ✅ 通过 |
| D-16 | `main_gateway.cpp:78-99` 查用户→比对 hash→写 Redis→回包，M4 复跑 code=0/uid=1/token。缺陷：`:93` setEx 失败未校验仍回 code=0；无 3001 内部错误分支；回调为阻塞 while 循环；粘包/半包未缓冲（见第二、三层） | ✅ 保留（主链路通过；异常分支缺陷列入第二层） |
| D-17 | `include/battle/KcpSession.h`、`src/battle/KcpSession.cpp` API 存在；但业务四个发送点**全部走 `sendRaw` 裸 UDP**（`main_battle.cpp:43,93,112,141`）；`KcpSession::send`（`ikcp_send`，`KcpSession.cpp:56-58`）**无调用方**；收包侧 `ikcp_input` 失败即回落裸回调（`KcpSession.cpp:43-47`）。实测 M5 流量未走 KCP ARQ 可靠传输；`third_party/kcp` 为自研最小兼容实现（既定取舍） | **⚠️ 降级**（原 ✅已实现已验证 → ⚠️已实现未验证） |
| D-18 | `src/battle/main_battle.cpp:17-26` 内存 `map<uint64_t,Room>` + `vector<KcpSession*>`；建房/进房回成员复跑通。**设计要素未落地**：Redis hash `HSET room:{id} uid ready` 未实现（src 无 HSET 调用）；无 2001 房间不存在 / 2002 满员分支（实际回 404，`:102,:128`）；无离线标记、无成员超时清理；重复 Join/Rejoin 会向 members 重复 push 同一指针（`:104,:135`） | **⚠️ 降级**（原 ✅已实现已验证 → ⚠️已实现未验证） |
| D-19 | `main_battle.cpp:50-55` CoroTask broadcastLoop，`co_await sleepMs(100)`；复跑 0.3s 后收到 `FrameBroadcast frame=0 inputs=1`。备注：协程返回值丢弃（`:61`）；每 tick 起一个 detached 线程（`CoroTask.h:28-31`）；`broadcastOnce` 持锁期间逐条 sendRaw（`:30,:42-44`）；history 广播后即清空（`:45`） | ✅ 保留（广播功能实测通过；健壮性问题见第三层） |
| D-20 | `main_battle.cpp:122-142` Rejoin 回包 code=0；**复跑 `history=0`**：history 在 `broadcastOnce` 广播后清空（`:45`），重连时已无历史；未走 Redis LRANGE；无 100 条 LTRIM 上限；原证据"回历史帧"不被本次复跑支持 | **⚠️ 降级**（原 ✅已实现已验证 → ⚠️已实现未验证） |
| D-21 | `src/battle/KcpServer.cpp:11-23` UDP bind 8002；regress_battle 复跑 `KCP/UDP listening on 0.0.0.0:8002` | ✅ 通过 |
| D-22 | `src/tools/stress_client.cpp:59-177` 输出连接数/断开/QPS/平均·最大延迟/RSS；`stress_optimized_ab.txt` 三轮 1000/1000、断开 0、RSS 3.65~3.71MB。备注：M1 完整判据为 5 分钟长稳压测，当前证据为 10 秒/轮；`stress_echo_1000conn.md:28` 已自陈 5 分钟复测留 step8 | ✅ 保留（10 秒口径通过；5 分钟长稳未验证） |
| D-23 | 同 D-07，`bench_queue` 复跑 100 万零丢失 | ✅ 通过 |
| D-24 | `sql/schema.sql:5-11` users DDL 与设计 §4.1 一致；`:15-17` 种子两条；哈希复核一致 | ✅ 通过 |
| D-25 | `scripts/build.sh`；干净重建产出 6 个二进制，make exit 0。备注：26 行 warning 未清零，且 `CMakeLists.txt:9` 未加规范要求的 `-Werror`（见 1.3） | ✅ 保留（构建可用；warning 治理列入 P2） |
| D-26 | `scripts/run_asan.sh`、`run_valgrind.sh` 存在；`asan_report.log` 无 ASan error/leak 行；`valgrind_report.log` `definitely lost: 0 bytes`、`ERROR SUMMARY: 0 errors`。**覆盖范围缺口**：ASan 只编 echo/bench/stress（`run_asan.sh:18`），Valgrind 只跑 echo（`run_valgrind.sh:20`）；设计 M3 口径含登录链路，gateway/battle 均未跑内存检测 | ✅ 保留（脚本与日志真实；覆盖范围缺口列入第三层） |
| D-27 | `check_modern_cpp.sh` 复跑 5/5 命中，行号输出可复现 | ✅ 通过 |
| D-28 | `scripts/test_login.py` + `regress_gateway.sh` 复跑 EXIT=0、code=0、Redis session 落盘 | ✅ 通过 |
| D-29 | `08_测试/perf/perf_report.md:53` 比值 ×1.029（+2.9%），明确未达 1.30；A/B 证据文件数字与报告表一致（baseline 均 79078 / optimized 均 81328）；Q-001 deferred | ⚠️ 保持（台账诚实，未达标已如实标注） |
| D-30 | `README.md:21-74` 五步指南：依赖→schema→.env→build.sh→起服压测，命令与 `scripts/build.sh`、`regress_*.sh` 一致。备注：第 3 步复制 .env，但代码不解析 .env（硬编码），见第二层 | ✅ 保留（步骤可复现；.env 装饰性问题列 P2） |

### 1.3 编译 warning 明细（干净重建 `/tmp/make_full.log`，共 26 行）

- 9 行 `cc1plus: warning: …/build/game.pb.h: not a directory`：`CMakeLists.txt:28` 把 pb 头文件路径当目录 include，属构建配置瑕疵。
- 7 行 `Clock skew detected`：WSL 跨盘时间戳噪声，非代码问题。
- 约 10 行代码级告警：`LockfreeQueue.h:10` 命名空间 `log` 与内建函数 `log` 冲突；`ikcp.c:106` sign-compare；`echo_baseline.cpp:52` / `main_gateway.cpp:37,104` write·read 返回值未用；`TcpServer.cpp:12` 未使用函数；`main_gateway.cpp:56` 未使用参数 `loop`；`main_gateway.cpp:66` 有符号/无符号比较；`KcpSession.cpp:11` 未使用函数 `nowMs()`。
- 规范 4.1 要求 `-Wall -Wextra -Wpedantic -Werror`，`CMakeLists.txt:9` 实际只有前三组、无 `-Werror`。

### 1.4 降级行汇总（已直接回写映射表状态与证据列）

| 编号 | 原状态 | 新状态 | 降级要点（证据） |
|---|---|---|---|
| D-02 | ✅已实现已验证 | ⚠️已实现未验证 | Buffer 无粘包/半包/超长用例；网关未使用；无 4MB 上限校验（Buffer.h:33-40） |
| D-03 | ✅已实现未验证（口径混用） | ⚠️已实现未验证 | variant 存在；Timer/Kcp 上下文路径无运行验证（Channel.h:10-13） |
| D-08 | ✅已实现未验证 | ⚠️已实现未验证 | 未接入业务链路；队列满静默丢条（AsyncLogger.cpp:38；grep 无 LOG_INFO） |
| D-09 | ✅已实现未验证 | ⚠️已实现未验证 | `{}` 占位符未替换，`format()` 未被调用（LogMacros.h:21-28） |
| D-12 | ✅已实现已验证 | ⚠️已实现未验证 | 无 per-worker 连接池；DB 异常与用户不存在不可分流（MysqlConn.cpp:33,45,72,85-88） |
| D-17 | ✅已实现已验证 | ⚠️已实现未验证 | 业务走 sendRaw 裸 UDP；`ikcp_send` 无调用方；KCP ARQ 未上业务路径（main_battle.cpp:43,93,112,141） |
| D-18 | ✅已实现已验证 | ⚠️已实现未验证 | 房间成员仅内存；无 Redis hash；无 2001/2002 分支；无离线清理（main_battle.cpp:17-26,102,128） |
| D-20 | ✅已实现已验证 | ⚠️已实现未验证 | 复跑 history=0；未走 Redis LRANGE；无 100 条上限（main_battle.cpp:45,122-142） |

### 1.5 架构写了、映射表漏登记的条目

- **战斗服 token 鉴权**（架构 §5.4：CreateRoom/JoinRoom/FrameInput/RejoinRoom 必须带 token，先 `GET session:{uid}`，不存在回 1003）：代码未实现，proto 字段 `token` 被解析后从未读取（`main_battle.cpp:69-72` 建对象但无 `.token()` 调用）。映射表无独立行登记。
- **Redis 房间/帧 key**（架构 §4.2：`room:{id}` hash、`room:{id}:frame` list、`room:next_id` INCR）：实现全部落在内存，映射表 D-18/D-20 证据未体现该缺口。
- **错误码 4001/4002**（复审 P2-03 补入设计）：代码无对应回包分支。

---

## 第二层 系统一致性

| 检查项 | 证据（文件:行号） | 结论 |
|---|---|---|
| DB 字段 ↔ 结构体 ↔ 查询列 | `schema.sql:6-9`（id/username/password_hash/salt）↔ `MysqlConn.h:10-15` `UserRow` ↔ `MysqlConn.cpp:29` SELECT 四列 | ✅ 命名/类型一致，无漂移 |
| Proto 消息 ↔ 后端读写字段 | `game.proto:5-19` 九则消息；`main_gateway.cpp:82-97`（code/token/uid/msg）；`main_battle.cpp:86-88,107,131-133`（room_id/members/frame_no/history/inputs） | ✅ 字段名/编号一致 |
| 网关编解码格式（4B 大端包头 + pb body） | 发：`Codec.h:14-20` `htobe32`；收：`Codec.h:24-31` `be32toh`；客户端：`test_login.py:25` `struct.pack(">I", …)` | ✅ 收发两端大端对齐 |
| 战斗服编解码格式（1B 类型头 + pb body） | 服务端：`main_battle.cpp:65-67` 取 `data[0]` 类型、`data+1` body；服务端回包类型 2/4/6/8（`:91,:110,:40,:139`）；对齐客户端 `debug_battle.py:6,10` | ⚠️ 服务端与 debug_battle.py 对齐；**`scripts/test_battle.py:18,31,50` 直接发裸 pb、不带类型头**，两个 Python 客户端契约不一致，该脚本对当前服务端不通 |
| 错误码语义 | 设计 §5.3：0/1001/1002/1003/2001/2002/3001/4001/4002；代码实际：网关 1001（`main_gateway.cpp:82`）、1002（`:87`）、0；战斗服 404（`main_battle.cpp:102,128`） | ❌ 漂移：① 404 不在设计错误码表（应为 2001）；② 1003 token 无效、2002 满员、3001 内部错误、4001 解析失败、4002 超长 **均无分支**；③ 解析失败/超长当前为静默关 fd（`main_gateway.cpp:65,72`），不回错误码包 |
| Redis key 设计 | 架构 §4.2：所有 key 带 `cpp_game:` 前缀；`session:{uid}` / `room:{id}` hash / `room:{id}:frame` list / `room:next_id`；代码：`main_gateway.cpp:92` `session:` 无前缀；战斗服无任何 room/frame key 调用（grep 无 HSET/LRANGE/RPUSH/LTRIM/INCR） | ❌ 前缀缺失；房间/帧/自增房间号三类 key 未落地 Redis |
| 配置一致性 | `.env` / `.env.example.template` 列 MySQL/Redis 主机端口；代码硬编码：`MysqlConn.cpp:86` `127.0.0.1/root/""/cpp_game`、`RedisConn.cpp:45` `127.0.0.1:6380`；无 .env 解析代码 | ⚠️ .env 为装饰性配置，不被程序读取；6380 避让 6379 在 .env/README/代码注释三处口径一致 |
| 密码哈希口径 | 设计 §3.2：sha256(salt+pwd)；代码 `main_gateway.cpp:85` `salt + password`；种子 `schema.sql:14-17` 同口径；哈希复算一致 | ✅ 一致（降级方案 sha256+salt 为基线 §3.2 明示取舍） |
| 资源 RAII 口径 | 规范 4.1：fd/MYSQL*/redisContext*/FILE* 必须析构释放；`FdGuard.h:11`、`MysqlConn.cpp:18-20`、`RedisConn.cpp:15-17`、`AsyncLogger.h:39` 均有析构；战斗服 `KcpSession*`/`EchoConn*` 为裸 new（`KcpServer.cpp:58`、`echo_server.cpp:45-46`），无 RAII 包装 | ⚠️ 数据库/文件句柄 RAII 到位；会话指针裸堆分配，释放路径不完整（见第三层 UAF） |

---

## 第三层 回归（并发 / 事务 / 幂等 / 接口签名 / 回归用例）

| 受影响模块 | 验证方式 | 结论 |
|---|---|---|
| 登录幂等性 | 读码 `main_gateway.cpp:91-97`：重复登录 `SETEX session:{uid}` 覆盖 token，旧 token 自然失效；无旧连接主动踢下线逻辑（设计 04 §2"重复登录旧连接踢下线"未实现） | ⚠️ session 覆盖幂等可用；旧连接剔除缺失，P2 |
| thread_local DB/Redis 连接竞态 | 读码：网关回调由 accept 主线程同步调用（`TcpServer.cpp:80` → `main_gateway.cpp:56`），回调内 `threadLocalMysql/Redis`（`main_gateway.cpp:77,93`）都在主线程创建使用；worker EventLoop 上未挂任何连接 | ⚠️ 当前未暴露多线程竞态，但 per-worker thread_local 模型未被真正验证；一旦后续把连接处理搬上 worker 线程，需复核 thread_local 惰性初始化时机 |
| 无锁队列内存序 | `LockfreeQueue.h:24-48`：生产者 tail-acquire/head-release，消费者 head-acquire/tail-release，SPSC 配对；100 万条复跑零丢失 | ✅ 单生产者单消费者下正确。**隐患**：SPSC 仅允许一个生产者；AsyncLogger 若被多个 worker 线程并发 push，队列协议被破坏。当前日志未接入业务，隐患未激活，接入前须改 MPSC 或加生产者锁 |
| 异步广播失败兜底 | `main_battle.cpp:42-44` 成员 `sendRaw` 返回值未检；发送失败不重试、不摘除成员；离线成员仍留在 members 列表 | ⚠️ 无失败兜底，P1/P2 |
| 战斗服 sessions_ 表并发 | `KcpServer.cpp:54-62` recvLoop 线程 find/insert；`KcpServer.cpp:79-87` tickLoop 线程遍历/erase；`sessions_` 无互斥锁（对比 `g_roomsMutex` 只保护房间表） | ❌ `std::map` 跨线程数据竞争，P1；高并发下可能迭代器失效/崩溃 |
| 会话超时删除悬空指针（UAF） | `KcpServer.cpp:84-85` `delete sess; sessions_.erase(key)`；该指针仍在 `Room.members`（`main_battle.cpp:19,104,135`）；下一轮 `broadcastOnce` `sendRaw`（`:43`）访问已释放内存 | ❌ 内存安全隐患，P1；当前 60 秒超时 + 短测试流程未触发，且 battle_server 未跑 ASan/Valgrind，未被既有检测覆盖 |
| 接口签名变更调用方同步 | `MysqlConn`/`RedisConn`/`KcpSession` 均单调用方，头文件与实现签名一致；`KcpSession::send`（ikcp_send）无调用方，属死代码；`KcpSession::nowMs()` 未被使用（编译告警） | ✅ 无签名漏改；死代码建议 step8 清理 |
| 协议层公共组件复用 | 网关走 `Codec.h`；战斗服 1B 类型头在 `main_battle.cpp` 内联硬编码（`:40,:91,:110,:139`），未抽公共编解码组件；两套 framing 约定分散在服务端与两个 Python 客户端 | ⚠️ 可维护性风险，P2 |
| 回归用例覆盖 | Glob 全项目 **无 `p0_cases.json`**；现有 `test_echo.py` / `test_login.py` / `debug_battle.py` 均为单 happy-path；无并发压测异常分支、无 1001/1002/DB 宕机/Redis 宕机/房间不存在/重复登录/断线 3 秒重连的断言用例 | ❌ **尚无回归用例，风险带入第 7 步**；本报告不虚构任何未执行的测试结果 |
| 内存安全检测覆盖 | `run_asan.sh:18` 只 make echo_server/bench_queue/stress_client；`run_valgrind.sh:20` 只跑 echo_server；gateway、battle_server 未纳入 ASan/Valgrind | ⚠️ M3 设计口径含登录链路；战斗服 UAF/竞态恰好在未检测覆盖范围内，建议 step8 补测 |

---

## 高风险变更确认（命中时）

> 对应 `04_任务拆解与开发规范.md` 风险级别=高 的任务：T-03/T-04/T-06/T-07/T-11/T-12/T-14/T-15/T-16/T-18。**逐项标注是否需人工确认**；本表不自动放行。

| 模块（任务） | 改动 | 影响链路 | 回滚方式 | 是否需人工确认 |
|---|---|---|---|---|
| Channel + EventLoop（T-03，D-03/D-04） | epoll 事件分发、variant 三态上下文、EPOLLIN/OUT/ERR/HUP 回调 | 所有 TCP 服务（echo/gateway/battle 网络层） | 还原 `include/net/Channel.h`、`include/net/EventLoop.h`、`src/net/EventLoop.cpp`、`src/net/Channel.cpp` | **是**：Timer/Kcp 上下文未实测；`Channel.cpp:5-6` EPOLLOUT 位硬编码 `0x04` 未用宏；跨线程 `epoll_ctl` 见 T-04 |
| TcpServer + WorkerThreadPool（T-04，D-05） | 监听 socket/bind/listen、accept round-robin、worker 线程组 | echo_server / game_gateway 接入层 | 还原 `include/net/TcpServer.h`、`src/net/TcpServer.cpp` | **是**：① 连接是否挂到 worker loop 由业务回调自行决定，网关未挂；② accept 主线程 `usleep(1000)` 轮询（`TcpServer.cpp:71`）而非 listen fd 挂 epoll；③ 回调在主线程发起 `epoll_ctl`，与 worker loop 并发访问 Channel 状态 |
| SPSC LockfreeQueue（T-06，D-07） | 环形队列 + atomic memory_order + 缓存行对齐 + concepts 约束 | 日志链路、bench_queue 压测 | 还原 `include/log/LockfreeQueue.h` | 否（本次复跑 100 万零丢失，内存序配对正确）；**附带条件**：接入多生产者前必须复核队列模型 |
| AsyncLogger 后台刷盘（T-07，D-08） | 后台线程批量 pop 写文件、队列满丢弃、stop 汇合 | 全链路日志（当前未接入业务） | 还原 `include/log/AsyncLogger.h`、`src/log/AsyncLogger.cpp` | **是**：未接入 gateway/battle（Q-004）；队列满静默丢日志；writerLoop 停止冲刷与退出条件薄弱（`AsyncLogger.cpp:43,57`） |
| MySQL thread_local（T-11，D-12/D-14） | libmysqlclient RAII 封装、预处理查询、thread_local 连接 | M4 登录查用户 | 还原 `include/db/MysqlConn.h`、`src/db/MysqlConn.cpp`、`sql/schema.sql`、`sql/fix_hash.sql` | **是**：无连接池/预建 N 连接；DB 异常与用户不分流；`ping()` 未被调用；连接断开重连策略缺失 |
| Redis thread_local（T-12，D-13） | hiredis RAII 封装、setEx/get/del、thread_local 连接 | M4 session 写入 | 还原 `include/db/RedisConn.h`、`src/db/RedisConn.cpp` | **是**：setEx 失败未向上汇报；房间/帧 Redis 方法未实现；线程搬迁后 thread_local 时机待复核 |
| gateway + LoginHandler（T-14，D-15/D-16/D-28） | 8001 监听、sha256(salt+pwd)、session 写入、LoginRsp 回包 | M4 登录全链路 | 还原 `src/gateway/main_gateway.cpp` | **是**：① 阻塞 while 回调跑在 accept 主线程，多连接串行；② 无 3001/1003/4001/4002 分支；③ read/write 返回值未校验（`main_gateway.cpp:37,104`）；④ 半包/粘包无缓冲；⑤ token 生成 `read()` 返回值未检（`:37`） |
| kcp 入仓（T-15，D-17 底层） | `third_party/kcp/ikcp.c/.h` 自研最小兼容实现（conv/cmd/sn/ts、PUSH/ACK、超时重传） | 战斗服传输层 | 还原 `third_party/kcp/` 与 `CMakeLists.txt:55-57` kcp 库目标 | **是**：既定取舍为非 skywind3000 原版；窗口滑动/拥塞控制/序号回绕为简化实现；`ikcp.c:106` 有 sign-compare 告警 |
| KcpSession 封装（T-16，D-17） | 会话表、ikcp_input/recv/send/update、UDP 输出回调 | 战斗服收发包 | 还原 `include/battle/KcpSession.h`、`src/battle/KcpSession.cpp`、`include/battle/KcpServer.h`、`src/battle/KcpServer.cpp` | **是**：业务实际走 sendRaw 裸 UDP；会话表跨线程无锁；超时删除遗留悬空指针（见第三层） |
| 100ms 广播协程（T-18，D-19） | CoroTask promise_type、`co_await sleepMs`、detached 线程定时恢复、broadcastOnce 遍历成员打包 | M5 帧同步广播 | 还原 `include/battle/CoroTask.h`、`main_battle.cpp:29-55` 广播段 | **是**：协程返回值丢弃、无取消路径；每 tick detached 线程；广播持锁发送；history 广播后清空导致重连拿不到历史 |

---

## 误报与已确认不修（写清为什么不算问题）

| 事项 | 核查结论 | 为什么不算新缺陷 / 不修依据 |
|---|---|---|
| Q-001：M6 A/B 比值 1.03（+2.9%）未达 ≥1.30 | `perf_report.md:53` 如实记录 1.029；`stress_baseline_ab.txt` / `stress_optimized_ab.txt` 三轮数字与报告表一致；未虚构 perf 截图 | 台账 deferred，归因分析在报告 §6/§7；按既定流程留 step8 客户端多线程化 + 异步读写流水线后复测，不在 5.5 打回 |
| Q-002：自研 1748 行，低于 3000~5000 | 本次 `wc -l` 复核 = 1748，与台账登记一致 | 口径诚实；留 step8 补单测/健壮性代码后复核，不属于代码造假 |
| Q-003：WSL 内核与 perf 版本不匹配，无火焰图 | `perf_report.md:10` 如实说明；`cpu_sample.txt` 线程级采样快照存在 | 环境限制，替代手段已落地；原生 Linux 补跑列入后续路线 |
| Q-004：AsyncLogger/LOG_INFO 未接入业务链路 | src 全量 grep 无 LOG_INFO/LOG_ERROR 调用；网关/战斗服日志走 std::cerr/std::cout | 台账已登记 deferred（D-08/D-09 本次同步降级为 ⚠️）；不在 5.5 强制接入 |
| 自研最小 kcp 兼容实现 | `third_party/kcp/ikcp.c` 约 130 行，API 对齐 ikcp 命名；README"已知限制"已声明非原版 | 基线 §3.2 / 复审取舍既定；按简化实现评审，不按原版 kcp 的 ARQ 完整性要求打回；但业务未走 KCP 路径的事实已在 D-17 降级标注 |
| Redis 端口 6380 避让 6379 | `.env:17`、`RedisConn.cpp:45` 注释、README:19 三处一致；6380 PONG 实测通 | 环境适配（6379 被 Windows 本机 Redis 占用），非配置漂移 |
| `echo_baseline` 单次 write 未检返回值告警 | 仅用于 M6 A/B 对照（`echo_baseline.cpp:52`），不参与交付链路 | 对照基线刻意保留初始版形态；告警治理随 step8 编译规范统一处理 |
| Valgrind `possibly lost: 864 bytes / 3 blocks`、`still reachable 114,024 bytes` | `valgrind_report.log:22-23`；进程被 SIGTERM 终止（`:8`），线程栈/静态对象未释放属正常 | M3 判据口径为 `definitely lost = 0`（基线 §2 M3），当前 0；possibly lost/reachable 不阻塞 |
| 前端 / HTTP / JWT / Docker | 项目纯 C++ 后端；`.env:27-30` JWT 占位；无前端目录代码 | 基线 §3.3 明确排除；05_代码/frontend 仅目录说明，不按缺失打回 |

---

## 附：本次 Review 未覆盖 / 留待后续步骤

1. 第 8 步全量压测（M1 五分钟长稳、M5 50 人房间 P99/CPU）、ASan/Valgrind 对 gateway/battle 的覆盖、TSan 线程竞争检测——当前无对应用例与环境产物。
2. 第 6.5 步 .proto 契约校验（`06.5_契约/` 目录尚未产出）。
3. 第 8.5 步安全扫描（密码哈希强度、SQL 注入、Redis 未授权、密钥泄露）——本报告仅做代码级初查，未替代强制卡点扫描。
4. 未修改任何产品源码、脚本、文档；唯一写操作：8 行映射表状态/证据列降级（见 1.4）。
