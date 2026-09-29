# s14: Cron Scheduler — 按时间表生产工作

在 s13 基础上新增定时调度：独立调度任务按 cron 表达式把触发入队，
主循环两条路径消费（**回合内注入** + **空闲唤醒 select!**）。
s01–s13 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理照旧）。

```text
  cron_scheduler_loop (tokio task, 1s)
                  │  cron_matches + 分钟去重
                  ▼
  ┌──────────────────────────────┐
  │ CRON_QUEUE                   │
  │  scheduler -> main           │  ← 调度任务写,主循环消费
  └───────────────┬──────────────┘
                  │ tx.send(()) 唤醒空闲主循环
                  ▼
  ┌──────────────────────────────┐
  │ agent_loop loop-top consume  │
  │  [Scheduled] {prompt} inject │  ← 注入为 user 消息(路径A)
  │  -> streaming LLM -> tools   │
  └───────────────┬──────────────┘
                  │
                  ▼
  ┌──────────────────────────────┐
  │ .scheduled_tasks.json        │
  │  durable across restarts     │  ← 跨重启恢复任务定义
  └──────────────────────────────┘
```

## 四层模型

1. **Scheduler**：`cron_scheduler_loop`（tokio 任务，1s 轮询），匹配则入队；
2. **Queue**：`CRON_QUEUE`，调度任务写、主循环消费，解耦生产与执行；
3. **交付**：两条路径——路径 A：agent_loop 循环顶部消费（长回合中到期的任务
   在下一轮迭代注入，不等回合结束）；路径 B：main 的 `tokio::select!` 定时分支
   （空闲时被 `tx.send(())` 唤醒，自动跑一轮）；
4. **Consumer**：注入 `[Scheduled] {prompt}` 为 user 消息，走完整管线。

## CronJob 与 cron 表达式

```text
CronJob { id: cron_{:06}, cron: "0 9 * * *", prompt, recurring, durable }

  分钟  小时  日  月  星期
    *    *   *   *   *      每分钟
    0    9   *   *   *      每天早上 9:00
   */5    *   *   *   *      每 5 分钟
    0    9   *   *  1-5     工作日早上 9:00（cron 周日=0）
```

支持 `*` / `*/N` / `N` / `N-M` / `N,M,...`。标准语义：分钟/小时/月必须全匹配，
**DOM/DOW 同时约束时任一匹配即可（OR）**——`0 9 13 * 5` 在 13 号或周五触发。

## 相对 s13 的改动

| s13 | s14 |
|-----|-----|
| 触发方式：用户手动 | 调度任务自动入队 + 空闲自动交付 |
| 无时间概念 | `chrono::Local` 本地时间；五字段 cron 匹配 |
| 状态无持久化需求 | `.scheduled_tasks.json`（durable 数组，跨重启恢复） |
| REPL 顺序读 stdin | `tokio::select!`：stdin 分支 + 定时分支（空闲唤醒） |
| 14 个工具 | 17 个（+ schedule_cron / list_crons / cancel_cron） |
| 依赖无 chrono / libc | `chrono = "0.4"`（本地时间）、`libc = "0.2"`（Gate 3 直读 fd 0） |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s14_cron_scheduler
```

试试这些 prompt：

1. `用 schedule_cron 注册一个每 2 分钟执行的任务，提示词是"运行 date 命令并汇报"`
2. `列出现在所有的定时任务`
3. `注册一个 1 分钟后的一次性提醒(recurring=false)，内容是"检查构建状态"`
4. `取消刚才的周期性任务并确认`

**无人值守验证**：注册每 2 分钟任务后**不输入任何内容**，等调度任务触发 →
`[cron fire]` → `[queue processor] delivering scheduled work` → 模型自动执行。

可选环境变量同 s13：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG` /
`FALLBACK_MODEL_ID` / `STREAM_THINKING`；另加 `CONTEXT_LIMIT`（L4 摘要阈值，字符，
默认 300_000 ≈ 10 万 token，面向 deepseek-v4-flash 的 1M 上下文；128K 网关勿超 ~350K）。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **调度与执行解耦** | 调度任务只判时间入队，agent_loop 只消费注入，通过 `CRON_QUEUE` 连接 |
| **判火纯函数** | `fire_due_jobs` 时间字段注入（minute/hour/day/month/weekday/marker），去重/跨天/一次性全部可单测，不用真 sleep |
| **分钟去重带日期** | marker `"YYYY-MM-DD HH:MM"`：同分钟不重复触发，日级任务跨天不跳过 |
| **一次性任务自删** | `recurring=false` 触发后从注册表移除，durable 则同步落盘 |
| **双重校验** | 注册时 `validate_cron` 拒绝非法表达式；启动加载时跳过坏任务——坏数据不拖垮调度 |
| **匹配静默 false** | `cron_matches` 对畸形表达式返回 false 不 panic（替代 Python 的 try/except） |
| **压缩阈值按模型调** | L4 摘要阈值 50K→300K 字符（≈10 万 token：deepseek-v4-flash 是 V4 家族 1M 上下文，同时兼容 128K 网关），`CONTEXT_LIMIT` 环境变量可覆盖；L1 消息数 50→120、L2 保留结果 3→8、L3 落盘 30K→100K/预算 200K→500K——大窗口下压得晚、压得少（实测"压缩频繁"源于 50K 阈值过保守） |
| **空闲唤醒 select!** | 单一 turn-runner（main），无需 agent_lock；`Some(())` 模式让通道关闭时分支自动停用；调度只在**空→非空转变**时发一次唤醒信号，主循环定时分支**排空积压信号**——回合中途触发不会造成提示符刷屏（实测教训） |
| **bash stdin = EOF** | run_bash 显式 `Stdio::piped()` 并立即关闭写端（对齐 Python 的 `capture_output=True`）——读 stdin 的命令（`cat`/`read`/交互程序）立即收到 EOF,不会挂起 agent 等终端输入（实测：定时轮里 bash 卡住,按 Enter 才继续） |
| **Gate 3 直读 fd 0** | 用户确认改用 `libc::read` 直读 fd 0（`RawStdin`）,绕开 `std::io::stdin` 的全局互斥锁——REPL 的 tokio stdin 后台读线程持锁阻塞等输入时,`io::stdin().lock()` 会卡死（实测：定时轮里任何工具都要按 Enter 才能过 PreToolUse） |
| **发送前配对清理** | `sanitize_tool_pairs`：LLM 调用前丢弃找不到配对 tool_use 的孤儿 tool_result——压缩管线按"单对配对"假设工作,cron 注入的纯文本 user 消息制造了新边界,auto compact 尾部保留后实测 API 400 `unexpected tool_use_id found in tool_result`（2026-08 修复）；只清理发送副本,不污染历史 |
| **回合内注入** | agent_loop 循环顶部消费：长回合进行中的触发在下一轮迭代注入，不等回合结束 |
| **MAX_JOBS=50** | 防模型刷任务（CC 行为，前向扩展）；超限报错 |
| **local 时区** | 所有时间按本地时区解释（同 Python/CC） |

## 结构

```
s14_cron_scheduler/
├── Cargo.toml          # s13 依赖全集 + chrono
├── README.md
└── src/
    └── main.rs         # 6633 行：s13 全套 + cron 调度（~949 行新增）
```

## 测试

```bash
cargo test -p s14_cron_scheduler -- --test-threads=1
```

174 个单元测试（157 从 s13 携入 + 17 新增），覆盖：
- cron 字段匹配：`*` / `*/N` / `N` / `N-M` / `N,M` / 非法静默 false
- `cron_matches`：标准语义 + **DOM/DOW OR 语义矩阵**（周五/13 号/周五 13 号）+ 周日=0
- `validate_cron` 全错误路径（字段数/越界/step≤0/range 反序/非数字，文案对齐 Python）
- `fire_due_jobs` 时间序列：同分钟去重、下一分钟再触发、跨天不跳过、
  一次性移除 + durable 上报
- schedule/cancel/list 往返；`MAX_JOBS` 上限
- durable 持久化：落盘数组 JSON → 重建加载 → 取消同步移除；坏任务跳过
- execute_sync 新分发分支
- `sanitize_tool_pairs`：孤儿 tool_result 丢弃、user 消息纯文本兜底、
  混合 user 块（文本+tool_result）原样保留

## 与 Python 版对比

对照 `../../python/s14_cron_scheduler/code.py`。CronJob 字段、五字段匹配语义
（含 DOM/DOW OR）、校验文案、durable 数组 JSON、输出标记
（`[cron register/fire/cancel/inject cron]`、`loaded N durable job(s)`）逐字对齐。
差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | s13 简化栈（11 工具，无错误恢复/记忆/技能） | s13 全量保留（17 工具 + 全部机制） |
| 调度线程 | `threading.Thread` + `time.sleep(1)`（首轮先睡） | tokio 任务 + `interval(1s)`（首 tick 立即） |
| 队列处理器 | 独立线程 + 非阻塞 `agent_lock` | **`tokio::select!` 合入主循环**（单一 turn-runner，无需锁） |
| 单 job 容错 | 调度线程 per-job try/except | 注册/加载双重校验 + 匹配静默 false（更防御） |
| 作业数上限 | 无 | `MAX_JOBS = 50`（CC 行为，前向扩展） |
| 慢词启发式 | 朴素子串匹配 | 词边界匹配（s13 已修） |
| 消息配对防线 | 无（回合间不注入纯文本 user 消息） | `sanitize_tool_pairs` 发送前配对清理——本实现独有：cron 的 `[Scheduled]` 注入 + auto compact 尾部保留会打破 tool_use/tool_result 配对（实测 API 400），清理只作用于发送副本（Python 版无此问题，故无对应逻辑） |

## 已知行为（TEST.md 注意事项同步）

- **重启后"当前分钟即触发"**：`LAST_FIRED` 是内存态，重启后为空；若重启时刻
  命中某任务分钟，启动后第一 tick 即触发一次（Python 同行为）；
- **进程关闭调度即停**：daemon 语义由 runtime 退出承担；durable 只保任务定义
  跨重启，不保"进程关闭时照常触发"（需要系统 crontab）；
- **用户输入在定时轮期间排队**：单一 turn-runner，回合结束才处理（与 Python
  的 agent_lock 阻塞语义一致）；
- **压缩频繁非 bug**：L4 阈值原 50K 字符（≈12–15K token）对 1M 窗口过于保守，
  已调至 300K 默认 + `CONTEXT_LIMIT` 可覆盖；前三层（落盘/裁中段/占位）0 API，
  频繁触发属正常；
- **cron 测试并行竞态**：cron 单测共享 `CRON_JOBS`/`CRON_QUEUE`/`LAST_FIRED` 静态，
  并行时 `cron_reset_state` 互相清状态导致偶发失败，`--test-threads=1` 稳定
  （与 s07 `SKILL_REGISTRY` 竞态同类）。

## 后续章节

| 章节 | 主题 | 在 s14 基础上增加 |
|------|------|--------------------|
| s15 | Agent Teams | 队友线程来认领 .tasks/ 里的任务（文件收件箱 + 并行队友） |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
