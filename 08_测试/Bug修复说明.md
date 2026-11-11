# Bug 修复说明（step8 第一轮全量测试）

> 本文件只记 step8 实际改了代码的缺陷；问题台账统一在项目根 `_问题台账.md`，回归结论回写台账状态列，不另建 BUGLIST。

## 8-1 Q-014 房间满员阈值 8 → 50（P2，verified）

### 现象

战斗服 `JoinRoom` 满员判定把成员数阈值硬编码为 8，而基线 M5 / 架构 §5.3 契约为 **50 人房间**；2002（room full）分支存在，但阈值与契约不符。2 人联调不受阻，直到 step8 五十人压测前必须对齐。

### 根因

5A 实现时未把基线 M5 的 50 人契约贯彻到满员判定，属上下文遗忘（基线约定未带入实现）。全仓检索确认阈值仅 `main_battle.cpp` 一处，无第二处散落。

### 修改文件与代码片段

`05_代码/backend/src/battle/main_battle.cpp`（JoinRoom 分支，约 152 行）

修改前：

```cpp
} else if (it->second.members.size() >= 8) {
    rsp.set_code(2002);  // 房间满员
    rsp.set_msg("room full");
}
```

修改后：

```cpp
} else if (it->second.members.size() >= 50) {  // 修复-Q014：满员阈值对齐基线 M5/架构 §5.3 契约 50 人（原硬编码 8）
    rsp.set_code(2002);  // 房间满员
    rsp.set_msg("room full");
}
```

### 修改影响分析（R3 不超范围）

- **改动范围**：仅 `JoinRoom` 分支的满员比较常数 `8 → 50`，未改动成员表结构、广播、鉴权、协议码。
- **不受影响的链路**：
  - `CreateRoom`：建房者直接入房，不经过满员校验；
  - `RejoinRoom`：断线重连恢复原会话，不重新做满员判定；
  - `FrameInput` / `broadcastOnce` / `checkToken`：与成员数阈值无关；
  - 网关登录、房间分配、错误码 2001/1003 分支均未触碰。
- **遗留边界**：阈值仍是代码内常量，未抽为配置项；后续迭代可改为可配置房间容量。members 不去重问题见 Q-016（deferred），与本阈值修复相互独立。

### 自测说明

| 自测项 | 命令 / 方式 | 结果 | 证据 |
|---|---|---|---|
| step7 主链路回归 | WSL 内重编 battle 后跑 `scripts/step7_integration.py` | 22/22 通过，主链路未破坏 | `qa-automation/reports/regress_q014.log` |
| 五十人房间进房压测 | `python3 perf_room.py --clients 50 --duration 10` | 建房 code=0，49 个加入者全部进房成功，无 2002 误拒；进房耗时 0.094s | `reports/perf_room.json` |
| 阈值源码走查 | 全仓 grep 满员比较，确认仅 152 行一处 | 无第二处硬编码 8/50 散落 | 源码 `main_battle.cpp:152` |
| 全量 pytest | `bash run_pytest.sh -q` | 49 passed / 2 xfailed / 0 failed，P0 7/7 通过 | `reports/full_run2.log`、`reports/p0_run.log` |

### 台账与日志

- 台账：Q-014 状态 `open → verified`，轮次 R1，归属已注明回归证据。
- 失败日志：按 R10「失败必记录」记入 `_失败日志.md` 第 8 步（类别 AI产出错误，根因上下文遗忘，触发规则 R10）。

---

## 本轮未改代码、记 deferred 的项

以下问题在 step8 测试中确认存在或仍未闭环，按分级规则留到下版本，未在本轮改动服务端代码：

| 台账 ID | 级别 | 简述 | 处置 |
|---|---|---|---|
| Q-001 | P2 | M6 A/B 比值 1.046，未达 ≥1.30 | deferred，后续客户端多线程化 + 异步读写流水线后复测 |
| Q-002 | P2 | M8 自研 1823 行，低于 3000 下限 | deferred，后续补业务代码后 cloc 复核 |
| Q-013 | P2 | 房间/成员/帧历史落内存 map，重启丢失 | deferred，后续评估补 Redis 房间态 |
| Q-016 | P2 | members 不去重，重复 Join/Rejoin 致成员膨胀 | deferred，用例以 xfail 标注 |
| Q-017 | P2 | FrameInput 入口无鉴权/房间归属校验 | deferred，step8.5 安全复核后补 |
| Q-019 | P2 | 登录 20 并发后 TPS 见顶约 530，RT 线性上升 | deferred，后续线程数校准 + DB/Redis 异步化 |
| Q-015 | P3 | `scripts/test_battle.py` 陈旧脚本与现协议不符 | deferred，后续清理或改写 |
| Q-020 | P3 | 广播应用层 P99 当前客户端模型不可测 | deferred，需服务端打点闭环 |
| Q-021 | P3 | L3 直连常驻 MySQL/Redis，未用 Testcontainers | deferred，环境降级，已在报告注明 |
