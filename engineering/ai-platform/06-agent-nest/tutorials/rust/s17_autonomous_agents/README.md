# s17: Autonomous Agents — 自己看板，自己认领

在 s16 基础上新增自治机制：**scan_unclaimed_tasks（任务板扫描）+ idle_poll（60s
有界轮询：收件箱优先 → 任务板认领 → 超时关机）+ 身份重注入 + WORK 阶段 10 轮上限**。
队友生命周期从两段（WORK → IDLE 无限等）升级为三段（WORK → IDLE → SHUTDOWN）。
s01–s16 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理/cron/团队/协议 照旧）。

```text
 ┌─────────────────────────────────────────────────┐
 │ WORK（≤10 轮 LLM）                              │
 │  身份重注入 → inbox 分发 → LLM → 工具执行       │
 └───────────────┬─────────────────────────────────┘
                 │ stop_reason != tool_use（或 10 轮用尽）
                 ▼
 ┌─────────────────────────────────────────────────┐
 │ IDLE（12×5s = 60s）                             │
 │  ① inbox 优先                                  │
 │     shutdown_request → 响应 → SHUTDOWN          │
 │     其他消息 → 注入 → 回 WORK                   │
 │  ② 任务板 scan_unclaimed                       │
 │     未认领 → claim(自己) → 回 WORK              │
 │  ③ 60s 无新工作 → SHUTDOWN                     │
 └───────────────┬─────────────────────────────────┘
                 │ shutdown / timeout
                 ▼
 ┌─────────────────────────────────────────────────┐
 │ SHUTDOWN：summary → lead、移除、finished        │
 └─────────────────────────────────────────────────┘
```

## 三阶段生命周期

| 阶段 | 行为 | 退出条件 |
|------|------|---------|
| WORK | 身份重注入 → inbox 分发 → LLM/工具循环 | `stop_reason != tool_use` 或 10 轮上限 |
| IDLE | 每 5s 轮询：收件箱优先、任务板其次 | 有工作回 WORK / shutdown_request 退出 / 60s 超时 |
| SHUTDOWN | 发 summary、移除注册、finished | — |

**核心转变**：队友不再等 Lead 分配——空闲时自己扫描看板、认领未分配任务（依赖已完成的），做完再找下一个。Lead 只需创建任务 + 启动队友。

## 相对 s16 的改动

| s16 | s17 |
|-----|-----|
| IDLE 无限等待（1s 轮询 inbox） | **IDLE 60s 有界**（5s 轮询 inbox + 任务板，超时自动关机） |
| 任务分配：Lead 手动 assign | **队友自动认领**（scan_unclaimed_tasks：pending + 无 owner + 依赖完成） |
| WORK 无轮数上限 | **WORK ≤10 轮**（防无限干活） |
| 队友工具 5 个 | **8 个**（+ list_tasks / claim_task / complete_task） |
| claim_task 无 owner 检查 | **owner 检查**（`Task {id} already owned by {owner}`，防并发抢单后写覆盖） |
| 身份仅 system prompt | **身份重注入**（messages ≤3 时注入 `<identity>`，压缩/重置后恢复） |
| spawn 返回 | + `(autonomous)` 后缀；工具描述 "Spawn an autonomous teammate agent." |
| system prompt | + `You can list and claim tasks from the board.` |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s17_autonomous_agents
```

**核心验证**：`Create 3 tasks on the board, then spawn alice and bob. Watch them auto-claim and work.`

预期观察：
- 两个队友进入 IDLE → `[idle] alice auto-claimed: ...`（绿）——自动认领不同任务
- 并行完成 → `[complete] ... ✓` → 各自找下一个任务
- 有 blockedBy 依赖的任务在前置完成后被认领
- 全部做完 → 60s 后 `[idle] alice timeout (60s)`（红）→ `[teammate] alice finished`（自动关机）
- IDLE 阶段 `request_shutdown` → `[protocol] alice approved shutdown in idle`（紫，立即响应）

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **收件箱优先** | idle 每次先查 inbox（shutdown_request 立即响应退出，不等下一轮 WORK），再扫任务板——协议消息不被饿死（对齐 Python） |
| **任务板三条件** | `scan_unclaimed_tasks`：pending + 无 owner + `can_start`（所有 blockedBy 已完成）——有依赖不代表不能做，只有被未完成任务阻塞才不能 |
| **claim 失败不注入** | 自动认领检查返回值：`Claimed` 才注入 `<auto-claimed>` 回 WORK；失败黄字提示后继续轮询（防"抢单失败还假装在工作"） |
| **60s 有界 idle** | 12×5s 轮询（对齐 Python IDLE_TIMEOUT）；超时自动 SHUTDOWN——队友不会无限驻留 |
| **WORK 10 轮上限** | 防队友在单个 WORK 阶段无限干活（对齐 Python range(10)） |
| **身份重注入** | messages ≤3 时头部插入 `<identity>`——压缩/重置后恢复身份认知（对齐 Python len 检测） |
| **owner=队友名** | 队友 claim 传自己的名字（对齐 Python `claim_task(id, name)`），任务归属可追溯 |
| **可测性** | `idle_poll_once` 单次检查抽出（inbox → 任务板 → None），同步纯函数可单测；60s 超时逻辑靠常量 + 单次函数守护 |
| **owner 检查顺序** | status → owner → deps（对齐 Python 顺序：已认领任务报 status 错，owner 错仅对"手工置 owner 的 pending 任务"生效） |

## 结构

```
s17_autonomous_agents/
├── Cargo.toml          # s16 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 8758 行：s16 全套 + Autonomous Agents（~270 行净增）
```

## 测试

```bash
cargo test -p s17_autonomous_agents -- --test-threads=1
```

234 个单元测试（223 从 s16 携入 + 11 新增），覆盖：
- `scan_unclaimed_tasks`：无任务空 / pending+无 owner 命中 / 已认领排除 /
  依赖阻塞排除（前置完成前只暴露前置，完成后暴露下游）
- `idle_poll_once`：shutdown_request → Shutdown + 响应落盘（in idle）/ 普通消息 →
  Work + `<inbox>` 注入 / 任务板认领 → Work + `<auto-claimed>` 注入（owner=队友名）/
  claim 失败 → None 继续 / 都空 → None
- `claim_task` owner 检查：已认领报 status 错（对齐 Python 顺序）/ 手工 owner+pending
  任务报 `already owned by`
- 身份重注入：len≤3 注入 `<identity>`（含 name/role）/ len>3 跳过
- 常量：`WORK_MAX_ROUNDS=10` / `IDLE_POLL_INTERVAL_SECS=5` / `IDLE_TIMEOUT_SECS=60`
- 工具集恰 8 个、system prompt 含 board 提示

## 与 Python 版对比

对照 `../../python/s17_autonomous_agents/code.py`。三阶段生命周期、idle_poll 的
"inbox 优先 → 任务板其次 → 超时关机"语义、`[idle]` 系列文案与颜色、`<auto-claimed>`/
`<identity>` 注入格式、`(autonomous)` 后缀、`already owned by` 文案——逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | 14 工具简化栈 | s16 全量保留（23 工具 + 全部机制） |
| idle 等待 | `time.sleep(5)` 同步阻塞 | `tokio::time::sleep` 异步（不阻塞 runtime） |
| 任务板并发 | 无锁（owner 检查兜底） | 同（owner 检查在 s17 副本补上，s12 冻结不动） |
| 队友任务工具执行 | 8 handler dict（list_tasks 简版格式） | `execute_sync` 复用（list/complete 主循环版格式）+ claim_task owner 特判 |
| **system prompt（前移）** | 无 complete 指示（实测队友只报 Done 不更新任务板） | + `When you finish a task, use complete_task to mark it completed.`——实测闭环改进 |
| 单元测试 | 无 | 11 个新增（scan/idle_poll_once/身份注入/owner/常量） |

## 已知行为（TEST.md 注意事项同步）

- **任务认领无文件锁**：教学版"读-改-写"非原子，多队友并发抢同一任务靠 owner
  检查兜底（对齐 Python 注释；真实 CC 用 proper-lockfile 任务锁）；
- **IDLE 阶段 plan_approval_response 原样注入**：不调 handle_inbox_message
  （对齐 Python：idle 只特判 shutdown_request，其余消息整体注入让模型自行理解）；
- **60s 超时自动关机**：无任务即退出，不再无限驻留（s16 行为改变，Python 同）；
- **WORK 10 轮上限**：单个 WORK 阶段 LLM 最多 10 轮（Python 同）；LLM 错误直接
  break 当前 WORK（走 IDLE → 可能超时退出）；
- **身份重注入首轮必触发**：刚 spawn 时 messages 仅 1 条 → 第一轮 WORK 前注入
  `<identity>`（对齐 Python）；
- **`[idle]`/`[protocol]` 标记走 stderr**（对齐 s15/s16 惯例）；
- **队友任务工具打印走 stderr**：`claim_task`/`complete_task` 的 `[claim]`/
  `[complete]`/`[unblocked]` 标记在 s17 副本改为 eprintln（s12 冻结代码原为
  stdout）——s15"后台线程 stdout 打印插入 Lead 流式回复"的教训应用到队友
  新触达的 s12 函数（队友自动认领/完成任务必走这两条链）；
- **并行测试竞态**：任务板走文件系统（cwd 注入，天然并行安全）；`PENDING_REQUESTS`
  沿用 s16 唯一 id 模式；仅 s14 cron 继承竞态按 `--test-threads=1` 约定。
- **队友不调 complete_task（实测现象，Rust 已前移缓解）**：Python 版 system
  prompt 未指示完成时 complete_task——实测两个队友都只报 `(result) Done.` 就
  超时退出，任务板残留 in_progress；**Rust 前移**：prompt 加 `When you finish
  a task, use complete_task to mark it completed.`（实测闭环改进，Python 无）。
  残余场景（模型忽略指示）：Lead 可手动补 complete_task，或 `rm .tasks/` 重置；
- **队友可能虚报完成（实测现象，模型行为）**：bob 认领"health check"后未实现
  就报 Done——教学版无完成校验（真实 CC 靠人工 review 验收）；Lead 实测中
  自己验证并补全了缺失实现（救火行为）；
- **双提示符（实测现象，教学版可接受）**：select! 多路事件循环每次迭代顶部
  打印提示符，cron/wake 空信号迭代会多打一个 `s17 >> `（s14 同款现象，
  其"排空积压信号"修复只解决刷屏不解决空迭代提示符）；无功能影响；

## 后续章节

| 章节 | 主题 | 在 s17 基础上增加 |
|------|------|--------------------|
| s18 | Worktree Isolation | 每任务独立 git worktree，互不干扰 |
| s19 | MCP Plugin | 外部工具接入同一工具池 |
| s20 | Comprehensive | 完整集成示例 |
