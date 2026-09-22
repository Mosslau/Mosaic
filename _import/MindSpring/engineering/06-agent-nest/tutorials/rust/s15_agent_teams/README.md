# s15: Agent Teams — 一个搞不定，组队来

在 s14 基础上新增团队机制：**MessageBus 文件收件箱 + 队友 tokio 任务 + Lead 收件箱唤醒**。
s01–s14 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理/cron 照旧）。

```text
  teammate task (tokio, 独立 messages + 4 工具, 上限 10 轮)
        │  BUS.send(name, "lead", summary, "result")
        ▼
  ┌──────────────────────────────┐
  │ .mailboxes/{agent}.jsonl     │  ← 文件收件箱（append 一行 JSON = 发消息）
  └───────────────┬──────────────┘
                  │ bus_peek("lead") || has_pending_background()
                  │ inbox_poller (tokio task, 1s) → wake 通道
                  ▼
  ┌──────────────────────────────┐
  │ main select! 第三路          │
  │  [Inbox] 注入 history        │  ← Lead 看到队友消息并反应
  │  -> run_turn(None)           │
  └──────────────────────────────┘
```

## 四层模型

1. **MessageBus**：`bus_send`（append 一行 JSON）/ `bus_read_inbox`（读全文 + 删文件，
   消费式）/ `bus_peek`（非破坏探测）。每个 Agent 一个 `.mailboxes/{agent}.jsonl`；
2. **Teammate**：`run_spawn_teammate` 起 tokio 任务，独立 system prompt / messages /
   4 个简化工具（bash/read/write/send_message），上限 10 轮，每轮开头读自己收件箱；
3. **Wake**：`inbox_poller`（1s 轮询）在 `bus_peek("lead") || has_pending_background()`
   时发唤醒信号，main 的 `tokio::select!` 第三路消费；
4. **Inject**：唤醒轮把 `[Inbox]\nFrom {from}: ...` 与后台通知合流注入 history，
   走完整管线（run_turn(None)，与 cron 空闲唤醒同构）。

## 相对 s14 的改动

| s14 | s15 |
|-----|-----|
| Agent 数量：1 | 1 Lead + N 队友任务（并行） |
| 通信：无 | MessageBus + `.mailboxes/*.jsonl` |
| REPL select! 两路（stdin / cron） | 三路（+ inbox 唤醒） |
| 17 个工具 | 20 个（+ spawn_teammate / send_message / check_inbox） |
| 无队友概念 | 队友：独立 prompt / messages / 4 工具 / 10 轮上限 / 完成自动汇报 |
| 队友执行无先例 | 队友工具不走权限 hook（Gate3 需 stdin 交互；真实 CC 用权限冒泡，s16） |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s15_agent_teams
```

试试这些 prompt：

1. `Spawn alice as a backend developer. Ask her to create a file called schema.sql with a users table.`
2. `Check your inbox for alice's result.`
3. `Send a message to alice: please verify the schema.`
4. `Spawn bob as a tester. Ask him to check if schema.sql exists and list its contents.`

**无人值守验证**：spawn 队友后**不输入任何内容**，等队友干完 → `[teammate] alice finished` →
`[wake: 1 inbox + 0 background -> new turn]` → Lead 自动跑一轮 → `[all teammates done]`。

可选环境变量同 s14：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG` /
`FALLBACK_MODEL_ID` / `STREAM_THINKING` / `CONTEXT_LIMIT`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **文件收件箱** | 消息 = 一行 JSON（from/to/content/type/ts），跨线程/跨进程可见、可审计；教学版无锁（read+unlink 竞态可接受，真实 CC 用 proper-lockfile） |
| **消费式读取** | `bus_read_inbox` 读全文 + 删文件：同一消息只被消费一次；`bus_peek` 非破坏，轮询不丢消息 |
| **队友独立上下文** | 独立 system prompt + messages（窗口 20 条，对齐 Python `[-20:]`），与 s06 子代理同源；区别：队友存活多轮、可收消息、完成向 Lead 汇报 |
| **10 轮上限** | `MAX_TEAMMATE_ROUNDS` 防死循环（教学版；真实 CC 用 idle loop + shutdown_request，s16 引入协议） |
| **复用 call_llm** | 队友 LLM 调用继承 s11 错误恢复（退避/重试/错误分类）——Python 版是裸调用 + 静默 break，Rust 更防御（错误打印一行后退出） |
| **队友不走权限 hook** | Gate 3 需 stdin 交互，后台队友任务不可行；对齐 Python 教学版（真实 CC 用权限冒泡，s16 引入） |
| **agent 名校验** | 黑名单思路：拒绝 `/ \ . :` 空格与控制字符（`../` 无法穿越），中文等 Unicode 名允许（队友名常为中文）；≤64 字节——Python 教学版 `to="../x"` 可路径穿越写任意文件（Rust 前向修复） |
| **唤醒条件共享** | `bus_peek("lead") || has_pending_background()`：队友消息与后台任务完成共用一条唤醒通道 |
| **积压排空** | 唤醒分支排空积压信号（s14 cron 同款防御）：回合中途的多次唤醒合并为一次注入，提示符不刷屏 |
| **配对防线延续** | s14 的 `sanitize_tool_pairs` 覆盖新注入形态：`[Inbox]` 纯文本 user 消息夹在 tool_use/tool_result 之间不误伤合法配对（有回归测试） |
| **完成宣告** | `announce_teammates_done`：曾有队友 + 现在全空 + 收件箱/后台排空 → `[all teammates done]` 只打一次 |

## 结构

```
s15_agent_teams/
├── Cargo.toml          # s14 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 7439 行：s14 全套 + Agent Teams（~800 行新增）
```

## 测试

```bash
cargo test -p s15_agent_teams -- --test-threads=1
```

197 个单元测试（174 从 s14 携入 + 23 新增），覆盖：
- MessageBus：send→read 往返（五字段 + ts）、消费式读取、`peek` 非破坏、
  空收件箱、非法 JSONL 行跳过
- agent 名校验：`../` / `a.b` / `a:b` / 空名 / 超长 / 含空格被拒；ASCII 与**中文名**（小红）放行
- 中文往返：中文队友名 + 中文消息内容五字段完整（回归：截断为字符级，不切坏 UTF-8）
- check_inbox：空文案 `(inbox empty)`、`[from] content[:200]` 格式化与截断、消费语义
- send_message：`Sent to {to}` + 实际送达
- `format_inbox_block`：`[Inbox]\nFrom {from}: ...` 注入格式（对齐 Python）
- 队友：system prompt 组装、4 工具集、重名拒绝、非法名拒绝、
  `SpawnTeammateInput` serde 缺字段校验
- `all_tools` 恰 20 个且含 3 个团队工具
- `sanitize_tool_pairs` s15 回归：inbox 纯文本注入不破坏配对、文本+结果合流保留
- 唤醒条件端到端：后台任务完成 → `has_pending_background` → collect 复位

## 与 Python 版对比

对照 `../../python/s15_agent_teams/code.py`。MessageBus 语义（五字段/append/消费式/peek）、
队友上限 10 轮与窗口 20 条、输出文案（`Teammate 'x' already exists` / `Sent to {to}` /
`(inbox empty)` / `[teammate] x spawned/finished` / `[bus]` / `[wake: N inbox + M background
-> new turn]` / `[all teammates done]`）逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | s14 简化栈（14 工具，无错误恢复/记忆/技能/压缩/hook） | s14 全量保留（20 工具 + 全部机制） |
| 队友线程 | `threading.Thread` + 裸 `client.messages.create`（异常静默 break） | `tokio::task::spawn` + 复用 `call_llm`（错误恢复/退避继承；错误打印一行后 break，更可观测） |
| 事件循环 | `input_reader` + `inbox_poller` 双线程事件队列 | `tokio::select!` 三路（stdin / cron / wake），无需 input_reader 线程 |
| 邮箱路径安全 | `to` 直接拼文件名（`../x` 可穿越） | agent 名白名单校验（前向修复） |
| 队友权限 | 无闸门 | 无权限 hook（对齐 Python；真实 CC 用权限冒泡，s16） |
| 消息配对防线 | 无（回合间不注入纯文本 user 消息） | `sanitize_tool_pairs` 覆盖 inbox 注入形态（s14 已有机制 + s15 回归测试） |
| 队友工具执行 | 4 handler dict，串行 | `execute_sync` + `spawn_blocking`（并行/超时继承） |
| 队友执行可见性 | 无工具输出预览 | `[teammate:{name}]` 灰字预览（90，stderr）——可观测性增强；队友标记统一走 stderr（对齐 [HOOK] 惯例），不插入 Lead 流式回复中间（实测交错教训），`2>log.txt` 可单独收集诊断 |
| 工具描述措辞 | spawn_teammate "background thread" | "background task"（tokio 语义更准确） |
| 单元测试 | 无 | 23 个新增（MessageBus/队友/工具/唤醒/中文往返 + 回归） |

## 已知行为（TEST.md 注意事项同步）

- **收件箱残留**：`.mailboxes/` 是运行时产物（已入 .gitignore），进程退出即残留——
  下次启动 Lead 会读到上次的消息（教学版不清理，Python 同）；
- **队友 10 轮即止**：不是 idle loop——队友跑完上限就结束并汇报，不会一直待命
  （真实 CC 的 idle loop + shutdown_request 协议是 s16 的内容）；
- **唤醒是合并的**：回合中途到达的多个唤醒信号被排空合并为一次注入
  （`[wake: N inbox + M background -> new turn]` 一次打印）；
- **队友标记走 stderr**：`[teammate]`/`[teammate:{name}]`/`[bus]` 打印到 stderr（对齐 [HOOK] 惯例）——队友线程与 Lead 流式输出共用 stdout 会互相插入（实测交错教训），改后 `1>reply.txt` 可拿到干净的模型回复、`2>log.txt` 收集诊断；
- **队友 LLM 错误不重试到天荒地老**：call_llm 内部退避重试照常，但队友本身的
  一次失败（如上下文超限）就打印错误并退出（对齐 Python 的 break 语义）；
- **并行测试竞态**：`ACTIVE_TEAMMATES` 静态与 cron 静态同类，
  `--test-threads=1` 稳定（与 s07 `SKILL_REGISTRY` 竞态同类）。

## 后续章节

| 章节 | 主题 | 在 s15 基础上增加 |
|------|------|--------------------|
| s16 | Team Protocols | 关机握手（shutdown_request/approved）、消息类型约定 |
| s17 | Autonomous Agents | 队友 idle loop 自主认领任务 |
| s18 | Worktree Isolation | 每任务独立 git worktree |
| s19 | MCP Plugin | 外部工具接入同一工具池 |
| s20 | Comprehensive | 完整集成示例 |
