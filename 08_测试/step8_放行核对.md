# step8 放行核对记录 · cpp-game-server-kit

> 对照 `prompts/step08_全量测试.md` §放行清单逐项核对。机器判据以 `qa-automation/reports/` 原始日志为准；本记录只做结论归集，不替代台账与基线表。
> 核对时间：2026-11-11；全量复跑结果 **49 passed / 2 xfailed / 0 failed**（`reports/full_run_final.log`），P0 **7/7**（`reports/p0_run_rerun.txt`）。

## 一、放行清单逐项

| # | 放行项 | 结论 | 证据 / 说明 |
|---|---|---|---|
| 1 | pytest 四层框架搭好，一键跑通 0 failed | ✅ | L1 24 / L2 20 / L3 6 / L4 1，共 51 条；`reports/full_run_final.log` 49 passed / 2 xfailed / 0 failed；入口 `bash run_pytest.sh -q` |
| 2 | 每个核心接口有正向+反向+边界+越权用例 | ✅ | 登录：成功/用户不存在/密码错/空用户名/空密码/注入探测；房间：建房/进房/伪造 token 建房·进房·重连/不存在房间；越权：他人 token 冒充 uid、重复登录覆盖旧 token。见 `全量测试用例清单.md` L2 表 |
| 3 | 台账「来源阶段=8」的 P0/P1 全部 verified，无 open/fixed 残留 | ✅ | 门禁 `LEDGER_OPEN` 通过；本轮来源=8 新增 Q-019(P2)、Q-020(P3)、Q-021(P3) 均 deferred，无 P0/P1 open/fixed |
| 4 | 每条 P1 改 verified 前已记失败日志（R10） | ✅ | 本轮无 P1 修复；Q-014(P2) 已按 R10 记入 `_失败日志.md`。历史 5.5 轮 4 条 P1 verified 未记日志，门禁 `LOG_GAP_WARNING` 缺口 2 条（仅警告、不阻塞，留 step10 复盘归因） |
| 5 | 轮次日志记录本轮 open P0/P1 数且单调下降；P2/P3 标 deferred | ✅ | 台账轮次日志「8 / R1」：0 open P0/P1；Q-016/Q-017/Q-019 等 P2、Q-015/020/021 等 P3 均 deferred |
| 6 | 已知 Bug 用 xfail 标记，修复后自动转 PASS | ✅ | Q-016（members 不去重）、Q-017（FrameInput 无鉴权）`@pytest.mark.xfail(strict=False)`，对应 L2-19/L2-20 |
| 7 | 性能测试完成：Python + JMeter 双工具数据表 + 瓶颈分析 + 调优建议 | ⚠️ 部分（协议不匹配，不硬套） | Python 多线程压测三档（10/20/50）数据齐全（`perf_login.json`）；**JMeter 本机未安装**（`jmeter: command not found`），且自定义 TCP+Protobuf 二进制协议无法用原生 TCP Sampler 静态构造 body，按协议选型以 Python 压测为准，不把补齐 JMeter 列为必须项；`jmeter/login_stress.jmx` 仅占位骨架，第二工具交叉验证缺口记入诚实边界。降级原因见 `perf-report.md` §1。瓶颈定位 §7.1、候选改进 §7.2 齐全 |
| 8 | Allure 报告能生成，截图交付 | ✅ | `reports/allure-results/` 用例结果；`reports/html/` 静态报告 85 个文件，`index.html` 入口在位 |
| 9 | GitHub Actions CI 配好，README 有绿 badge | ⚠️ 部分 | `.github/workflows/test.yml` 落地：push/PR main → Python 3.10 → 装依赖 → `pytest --collect-only`（CI 无中间件，仅收集性校验保绿）；本地复跑 51 collected exit 0（`reports/ci_collect.txt`）。**远程 badge 待 step10.5 独立建仓后回填 OWNER/REPO**：当前项目目录挂靠工作流仓、无独立远程项目仓，README badge 以注释占位，不虚构 URL |
| 10 | 基线指标验证表已产出，每个量化指标有验证归属 | ✅ | `基线指标验证表.md` M1–M8 逐条：验证方式 + 证据文件 + 结论；M5 广播 P99 标未验证边界，M6/M8 如实标未达标技术债，无「预计达标」 |
| 11 | R22 探针测试闭合（仅翻新线）；生产线写「不适用」 | ✅ | 路线=生产，无 F1/F2 逆向 `[❓]` 项；已在 `全量测试用例清单.md` 头部与 `perf-report.md` §1 标注「R22 探针闭合：不适用」 |
| 12 | P2/P3 与未覆盖场景登记，移交第 10 步下版本规划 | ✅ | 台账 deferred 归档视图 11 条；未覆盖边界见清单第六节（广播 P99、满员 2002 实跑、L3 Testcontainers 降级、两条 xfail 缺陷） |

## 二、完成门禁红灯分类（`reports/gate_check_step8b.txt`）

> 门禁脚本 `workflow_completion_check.py` 在 step10.0 才强制全绿；本轮 step8 提前跑一次，红灯按性质分类如下，不把后续步骤/不适用项当成 step8 缺陷。

| 类别 | 门禁项 | 处置 |
|---|---|---|
| 后续步骤预期缺失 | 8.5 安全扫描报告、9 验收报告、10 交付复盘/交付包 | 属后续步骤，step8 不补；到对应步骤落盘 |
| 本项目不适用 | step5B 前端精修记录、R23 前端 UI 质量报告、taste 审美报告、`openapi.json` | 纯后端无前端；协议为 TCP+Protobuf 非 HTTP/JSON，6.5 以 proto 契约对账替代 OpenAPI |
| 词表误判（诚实结论被 forbid 命中） | 5.5 Review 报告「未达标」、7.5 重置记录「未重置」、基线表「未达标/TODO」 | 基线表 M6/M8 的「未达标（技术债）」是 R14 要求的如实归属，M7 行「无 TODO 占位」是引用基线口径；不能为过词表改成达标，维持原文 |
| 历史遗留 | 映射表 9 条 ⚠️已实现未验证；失败日志缺口 2 条（P1 verified 4 vs 日志 2） | 映射表 ⚠️ 对应 Q-013 等 deferred 项；日志缺口为 5.5 轮未走 R10，仅警告不阻塞，step10 复盘归因 |
| 看板一致性粗判 | 脚本扫到「进行中/未开始/当前卡点」关键词 | 关键词粗判，后续步骤状态本就为「未开始」；step10.0 交付前看板闭环时复核 |

## 三、step8 结论

- 台账收敛：0 open/fixed P0/P1；全量 pytest 0 failed；基线 M1–M8 均有验证归属；P0 主链路 7/7 通过。
- 两项 ⚠️ 边界已如实记录：JMeter 未装（骨架可复跑）、远程 CI badge 待独立建仓回填。
- **放行进入 step8.5 安全扫描**；step8.5 为强制卡点，P0/P1 安全项未清零前不进 step9。
