# learn-claude-code in Rust

用 Rust 重写 s01 ~ s20 的练习工作区。每章一个独立的 binary crate，
与根目录对应的 Python 章节一一对应，对照 `../python/sXX_*/code.py` 实现。

## 运行某一章

```bash
cargo run -p s01_agent_loop
```

## 调试开关

s01 起内置了环境变量调试开关，打开后打印每次 API 调用的原始请求/响应
（pretty-print，走 stderr，不干扰正常输出）：

```bash
S01_DEBUG=1 cargo run -p s01_agent_loop
```

观察 messages 如何逐轮膨胀、tool_use/tool_result 如何配对，都靠它。

## 测试

- **端到端手工测试手册**：[TEST.md](./TEST.md) —— 按机制递进的测试路径
  （T1–T17 覆盖 s01–s20），测试最新累积章即回归全部机制——s20 完结后
  本文档与 TEST.md 同步收尾
- **自动化回归**：`cargo test --workspace`（当前 2775 个测试全绿，含 `example` 五子棋 crate 的 24 个）

## 进度

- [x] s01_agent_loop (705行, 10测试) — while 循环 + bash 工具（含 thinking/signature 保留、HTTP 超时）
- [x] s02_tool_use (1003行, 19测试) — 5 个工具 + match 查表分发 + safe_path 路径沙箱 + Deserialize 强类型参数校验
- [x] s03_permission (1263行, 37测试) — 三道权限闸门（Gate1硬拒/Gate2规则匹配/Gate3用户确认），`&mut impl BufRead` 依赖注入可单测
- [x] s04_hooks (1714行, 60测试) — Hook 系统（4 事件类型 + 5 内置 Hook）+ 权限 hook 化 + 短路语义
- [x] s05_todo_write (1907行, 66测试) — 规划工具 + nag 提醒 + `CURRENT_TODOS: Mutex<Vec<TodoItem>>`
- [x] s06_subagent (2254行, 77测试) — task 工具 + spawn_subagent 上下文隔离 + extract_text 文本提取
- [x] s07_skill_loading (2584行, 86测试) — load_skill 工具 + YAML frontmatter 解析 + 动态 system prompt
- [x] s08_context_compact (3096行, 100测试) — 四层压缩管线 + compact 工具 + reactive 应急（压缩保留尾部 5 条）
- [x] s09_memory (3538行, 108测试) — 文件持久记忆 + 索引注入 + LLM 提取（信号词门控 + 去重 + 合并节流）
- [x] s10_system_prompt (3663行, 112测试) — 动态 system prompt 组装（5 段式，含 skills）+ 缓存
- [x] s11_error_recovery (4270行, 131测试) — 错误分类恢复：截断升 token/续写、超限 reactive compact、429/529 指数退避 + fallback 模型
- [x] s12_task_system (4823行, 145测试) — .tasks/ 持久任务图 + blockedBy 依赖 + 5 任务工具（认领/完成/解禁）
- [x] s13_background_tasks (5684行, 157测试) — 后台任务（run_in_background + 通知注入）+ 流式 SSE 输出 + 并行工具执行（tokio 首章）
- [x] s14_cron_scheduler (6633行, 174测试) — 定时调度：cron 五字段匹配 + durable 持久化 + 空闲自动交付（select! 唤醒）
- [x] s15_agent_teams (7439行, 197测试) — 团队：MessageBus 文件收件箱 + 队友 tokio 任务 + Lead 唤醒注入（select! 第三路）
- [x] s16_team_protocols (8477行, 223测试) — 协议：ProtocolState 状态机 + request_id 握手 + 计划审批 + 队友 idle loop
- [x] s17_autonomous_agents (8758行, 234测试) — 自治：任务板扫描 + 自动认领 + 60s 有界 idle + 身份重注入
- [x] s18_worktree_isolation (9388行, 250测试) — worktree：git 目录隔离 + 任务绑定 + 队友 cwd 切换 + 变更保护
- [x] s19_mcp_plugin (10345行, 280测试) — MCP：动态工具池 + .mcp.json 配置 + 外部工具即插即用
- [x] s20_comprehensive (10470行, 285测试) — 综合：全机制归位 + MCP 权限拦截 + Current time —— 完结

## 环境变量

沿用根目录 `.env`（见 `../.env.example`）：

- `ANTHROPIC_API_KEY` 或 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
- `MODEL_ID`
- `FALLBACK_MODEL_ID`（s11 起可选：连续 529 过载时切换的备用模型）
- `STREAM_THINKING`（s13 起可选：=1 时思考过程灰色流式打到 stderr，默认不显示）

## 已有依赖

s01 起共用：`reqwest`(blocking+rustls) / `serde` / `serde_json` / `dotenvy` / `wait-timeout`。
s02 起加 `glob`；s07 起加 `serde_yaml`（skill frontmatter 完整解析）；s11 起加 `rand`（指数退避的随机抖动）；
s13 起加 `tokio`（async 运行时：SSE 流式 / 并行工具 / 后台任务）；s14 起加 `chrono`（本地时间与日历字段，cron 匹配用）。

后续章节按需加：

```toml
[dependencies]
reqwest = { version = "0.12", features = ["json"] }  # 调 Anthropic API
tokio = { version = "1", features = ["full"] }       # 异步 / 后台任务 / cron
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"    # s09 memory frontmatter
dotenvy = "0.15"      # 读根目录 .env
anyhow = "1"
```

也可以抽一个共享 crate（比如 `harness/`）放 LLM client、消息类型，
在成员里用 `harness = { path = "../harness" }` 引用——但教程的精神是
每章自包含，先复制粘贴，痛感够了再抽。

## 章节对照

| crate | 章节 | 主题 |
|---|---|---|
| s01_agent_loop | s01 | while 循环 + bash 工具 |
| s02_tool_use | s02 | dispatch map 工具分发 |
| s03_permission | s03 | 执行前三道权限闸门 |
| s04_hooks | s04 | pre/post hook 挂载点 |
| s05_todo_write | s05 | 计划工具 + reminder |
| s06_subagent | s06 | 独立 messages 的子 Agent |
| s07_skill_loading | s07 | 按需加载 skill |
| s08_context_compact | s08 | 四层压缩管线 |
| s09_memory | s09 | .memory/ 持久记忆 |
| s10_system_prompt | s10 | 运行时组装 prompt |
| s11_error_recovery | s11 | 错误分类恢复 |
| s12_task_system | s12 | .tasks/ 持久任务图 |
| s13_background_tasks | s13 | 异步与并发：后台任务 + 流式输出 + 并行工具执行 |
| s14_cron_scheduler | s14 | 定时调度线程 |
| s15_agent_teams | s15 | 团队：文件收件箱 + 队友线程 + 唤醒注入 |
| s16_team_protocols | s16 | 协议：request_id 握手 + 计划审批 + idle loop |
| s17_autonomous_agents | s17 | 自治：看板扫描 + 自动认领 + 60s 超时 + 身份重注入 |
| s18_worktree_isolation | s18 | worktree：git 目录隔离 + 任务绑定 + 变更保护 |
| s19_mcp_plugin | s19 | MCP 外部工具接入 |
| s20_comprehensive | s20 | 全部机制归位一个循环 |

> **设计决策（2025-08-16）**：流式输出与并行工具执行落在 s13——该章是 Rust 轨道
> 第一个引入 tokio 的章节，async SSE 流式与多线程并行工具执行和后台任务同属
> "异步与并发"主题的三个面。并行子代理留给 s15（队友线程是它的天然土壤）。
> Python 参考轨道没有这两个特性，属 Rust 轨道的前向扩展（对齐"改进前移"惯例）。
> ✅ s15 已兑现：队友线程（`run_spawn_teammate`）即并行 Agent 的落地形态。

## s01–s19 评估

### 数据总览

| 章节 | 行数 | 测试 | 增量 | 主题 |
|---|---|---|---|---|
| s01 | 705 | 10 | — | 基础循环 + bash 工具 |
| s02 | 1003 | 19 | +298 (+42%) | 5 工具 + match 分发 + safe_path |
| s03 | 1263 | 37 | +260 (+26%) | 三道权限闸门 + BufRead 注入 |
| s04 | 1714 | 60 | +451 (+36%) | Hook 系统 + 5 内置 Hook |
| s05 | 1907 | 66 | +193 (+11%) | 规划工具 + nag 提醒 |
| s06 | 2254 | 77 | +347 (+18%) | 子代理 spawn + 上下文隔离 |
| s07 | 2584 | 86 | +330 (+15%) | skill 按需加载 + 动态 system prompt |
| s08 | 3096 | 100 | +512 (+20%) | 四层压缩管线 + compact 工具 + reactive 应急 |
| s09 | 3538 | 108 | +442 (+14%) | .memory/ 持久记忆 + 选/提/合并 |
| s10 | 3663 | 112 | +125 (+4%) | 动态 system prompt 组装 + 缓存 |
| s11 | 4270 | 131 | +607 (+17%) | 错误分类恢复 + 退避/fallback |
| s12 | 4823 | 145 | +553 (+13%) | .tasks/ 持久任务图 + blockedBy 依赖 |
| s13 | 5684 | 157 | +861 (+18%) | 后台任务 + 流式 SSE + 并行工具（tokio 首章） |
| s14 | 6633 | 174 | +949 (+17%) | cron 定时调度 + durable 持久化 + select! 自动交付 |
| s15 | 7439 | 197 | +806 (+12%) | 团队：MessageBus 文件收件箱 + 队友任务 + 唤醒注入 |
| s16 | 8477 | 223 | +1038 (+14%) | 协议：request_id 握手 + 计划审批 + idle loop |
| s17 | 8758 | 234 | +281 (+3%) | 自治：看板扫描 + 自动认领 + 60s 超时 + 身份重注入 |
| s18 | 9388 | 250 | +630 (+7%) | worktree：git 目录隔离 + 任务绑定 + cwd 切换 |
| s19 | 10345 | 280 | +957 (+10%) | MCP：动态工具池 + .mcp.json 配置 + 外部工具即插即用 |
| s20 | 10470 | 285 | +125 (+1%) | 综合：全机制归位 + MCP 权限拦截 + Current time |

合计 98,014 行，累计 2751 测试（含 `example` 五子棋 crate 共 2775），全部通过（s07 `SKILL_REGISTRY`、s14 cron 静态状态测试并行时偶发竞态，`--test-threads=1` 稳定，见已知局限）。

### 各章实现

**s01 Agent Loop** — `while` 循环 + `bash` 工具。`ContentBlock` 一次性完整设计（Text/Thinking/ToolUse/ToolResult），`Thinking` 带 `#[serde(flatten)]` 保留 signature。`run_bash` 双线程管道读取避免死锁。

**s02 Tool Use** — 5 工具 + `match` 查表分发。每个工具 `#[derive(Deserialize)]` 参数结构体，反序列化时校验。`safe_path` 路径白名单（s03 被推翻）。

**s03 Permission** — 三道权限闸门（Gate1 硬拒 / Gate2 规则匹配 / Gate3 用户确认）。安全职责从工具内部上移到管线。`&mut impl BufRead` 依赖注入使交互逻辑可单测。

**s04 Hooks** — 4 事件类型 + 5 内置 Hook。`Option<String>` 短路语义。`permission_hook` 薄封装 s03，37 个测试直接通过。

**s05 TodoWrite** — 规划工具 + nag 提醒。双复位点（nag 注入后 + todo_write 成功后）。`Mutex` 向前兼容 s15。`TodoWriteInput.todos: Value` 容错模型嵌套序列化。

**s06 Subagent** — `task` 工具 spawn 子代理。全新 `messages[]`，30 轮上限，只返回摘要。`call_llm` 的 `system` 参数化，父/子不同 prompt。子代理无 task（防递归）、无 todo_write。

**s07 Skill Loading** — 两层知识注入。Layer1 system prompt 含 skill 目录（~100 tokens），Layer2 `load_skill` 返回完整内容（~2000 tokens）。`SKILL_REGISTRY` 内存 HashMap 查询，无路径穿越。

**s08 Context Compact** — 四层压缩管线（L3 budget → L1 snip → L2 micro → L4 summary）+ `compact` 工具。try/except 包裹 API + `reactive_compact` 应急。compact 走特殊 break 路径。首次重构 agent_loop 控制流而非只加 match 分支。

**s09 Memory** — `.memory/` 文件持久记忆 + `MEMORY.md` 索引常驻 system prompt。三子系统：select（LLM 选择，失败回退关键词匹配）→ inject（选中内容注入当前 user turn）→ extract（压缩前快照提取）+ consolidate（文件 ≥10 自动合并去重，上限 30 条）。内部 LLM 分级 token 预算（select 200 / extract 800 / consolidate 3000）。

**s10 System Prompt** — `PromptContext { tools, workspace, memories }` 运行时上下文；`assemble_system_prompt` 段落按需加载（identity/tools/workspace 恒载，memory 段仅当 MEMORY.md 非空）；`get_system_prompt` 确定性缓存（`serde_json::to_string` 做 key）。每轮工具执行后 `update_context` 刷新。

**s11 Error Recovery** — 主循环 LLM 调用包恢复层：`LlmError` 强类型分类（429 / 529 / prompt_too_long / 其他）、`with_retry` 指数退避（最多 10 次，`Retry-After` 头优先，连续 3 次 529 切 `FALLBACK_MODEL_ID`）、截断恢复状态机（8K→64K 升级不追加输出，64K 仍截断续写 ×3）、prompt_too_long 走 s08 LLM 摘要版 reactive compact（仅一次）；不可恢复错误截断 200 字符写 `[Error]` 进历史。恢复只包主循环，内部辅助调用维持单次直调。

**s12 Task System** — `.tasks/{id}.json` 持久任务图。`Task { id, subject, description, status, owner, blockedBy }` 磁盘 JSON 与 Python `asdict` 输出逐字段同构（blockedBy camelCase、owner null、`task_{unix}_{04d}` ID）。5 个任务工具（create/list/get/claim/complete），`can_start` 缺失依赖视为阻塞，complete 时报告解禁的下游任务。子代理不持任务工具。

**s13 Background Tasks** — 首个 tokio 章，主循环 async 化，三面并发：① 后台任务（对齐 Python s13）：bash schema 加 `run_in_background`，显式请求优先 + 慢关键词启发式兜底（词边界匹配，`makeCtx` 不误伤），`spawn_blocking` 执行，`<task_notification>` 注入且不复用 tool_use_id；② 流式 SSE 输出（前向扩展）：`ApiRequest.stream`，事件流增量重建 ContentBlock，text_delta 边收边打印（思考默认不显示，`STREAM_THINKING=1` 时灰色打 stderr），stop_reason 按内容兜底；③ 并行工具执行（前向扩展）：多条 tool_use 并行跑、按原序配对 tool_result；task 子代理串行（并行子代理留给 s15）。s11 恢复层（with_retry/截断升级）零改动复用。

**s14 Cron Scheduler** — 定时调度与执行解耦。`cron_scheduler_loop`（tokio 任务 + 1s interval）按五字段 cron 匹配判火，`fire_due_jobs` 纯函数（时间注入，分钟去重带日期、one-shot 自删、跨天不跳过）；`CRON_QUEUE` 解耦生产与消费，两条交付路径：agent_loop 循环顶部回合内注入 + main 的 `tokio::select!` 空闲唤醒（单一 turn-runner，无需 agent_lock）；`.scheduled_tasks.json` durable 数组持久化（启动加载、坏任务跳过）；3 新工具（schedule/list/cancel_cron），`MAX_JOBS=50` 上限；chrono 提供本地时间字段。

**s15 Agent Teams** — 一个 Lead + N 队友任务。`MessageBus` 文件收件箱（`.mailboxes/{agent}.jsonl`）：`bus_send` append 一行 JSON（from/to/content/type/ts 五字段，与 Python 同构）、`bus_read_inbox` 读全文+删（消费式）、`bus_peek` 非破坏探测；`run_spawn_teammate`（agent_loop 特判，同 task 先例）注册 `ACTIVE_TEAMMATES` 后起 tokio 任务：独立 system prompt/messages、4 个简化工具（bash/read/write/send_message）、上限 10 轮、每轮开头读自己收件箱注入 `<inbox>`、完成发 summary（type="result"）回 Lead；Lead 侧 `inbox_poller`（1s）在 `bus_peek("lead") || has_pending_background()` 时经 select! 第三路唤醒，`[Inbox]` 注入 history 跑自动轮；`announce_teammates_done` 全员结束后宣告一次。3 新工具（spawn_teammate/send_message/check_inbox，17→20）。前向修复：agent 名校验（黑名单拒绝 `/ \ . :` 空格与控制字符，中文名允许）防路径穿越（Python 版 `to="../x"` 可写出 `.mailboxes/`）；队友 LLM 复用 s11 `call_llm`（错误恢复继承）；s14 `sanitize_tool_pairs` 覆盖 inbox 纯文本注入形态（有回归测试）。队友标记（`[teammate]`/`[teammate:{name}]`/`[bus]`）走 stderr（对齐 [HOOK] 惯例，实测交错教训：后台队友的 stdout 打印会插入 Lead 流式回复中间）。

**s16 Team Protocols** — 结构化请求-响应协议层。`ProtocolState` 状态机（强类型 `ProtocolType`/`ProtocolStatus` 枚举）+ `PENDING_REQUESTS`（Mutex<HashMap>）追踪在途请求；两种协议一套机制：`shutdown_request/response`（Lead→队友，体面关机握手）、`plan_approval_request/response`（队友→Lead，计划审批），`request_id` 贯穿全链路；`match_response` 按 ID 关联 + **类型校验**（shutdown 请求不会被 plan 响应误批）+ 重复回复去重；`consume_lead_inbox` 统一消费（check_inbox 与唤醒分支共用，先路由协议再返回，避免消息被读走但协议状态没更新）；**队友 idle loop**（无轮数上限，LLM 停后每秒轮询 inbox，shutdown_request → 响应退出，新消息 → 继续工作，`teammate_idle`/`handle_inbox_message` 抽出可测）；MessageBus 加 `metadata` 字段（`bus_send_meta` 新增，`bus_send` 5 参不变零改动；旧消息 `#[serde(default="default_metadata")]` 归一空对象）；3 新 Lead 工具（request_shutdown/request_plan/review_plan，20→23）+ 队友 submit_plan（4→5）。Rust 保留 s15 的 select! 三路 + poller（Python 回退简单循环）——协议响应到达即自动唤醒 Lead；`[protocol]` 标记走 stderr（对齐 s15 惯例）。实测修复：队友窗口截断的孤儿 tool_result 发送前经 `sanitize_tool_pairs` 清理（s14 防线应用到队友循环，bob 多轮探索 API 400 实测）。实测已知局限（教学版未解决，Python 同）：无 `idle_notification`——Lead 盲等（模型用 bash sleep 轮询），s17 看板认领架构性消除；协议响应无送达回执——Lead 可能重复催信。

**s17 Autonomous Agents** — 队友自治：WORK → IDLE → SHUTDOWN 三阶段生命周期。`scan_unclaimed_tasks`（复用 s12 list_tasks/can_start）扫任务板三条件（pending +无 owner + 依赖完成）；`idle_poll` 60s 有界轮询（12×5s，tokio sleep 异步）——**收件箱优先**（shutdown_request 立即响应退出 `in idle`，其余消息整体注入），**任务板其次**（找到未认领 → `claim_task(owner=自己)` → `<auto-claimed>` 注入回WORK，失败黄字继续轮询），超时自动 SHUTDOWN；`idle_poll_once` 单次检查抽出可测；**身份重注入**（messages ≤3 时头部插 `<identity>`）；WORK 阶段 ≤10 轮上限；claim_task 补 owner 检查（s17 副本内，s12 冻结不动）；队友工具 5→8（+list_tasks/claim_task/complete_task，claim owner=队友名特判）；spawn 返回带`(autonomous)` 后缀。**前移**：prompt 加 `complete_task` 完成指示（实测队友只报 Done 不更新任务板，Python 无此句）。兑现 s16 文档承诺：看板认领从架构上消除"Lead 盲等"。

**s18 Worktree Isolation** — 每任务独立 git worktree。Task 加 `worktree` 字段（`#[serde(default)]` None→null 对齐 Python asdict 逐字段同构，磁盘兼容）；`.worktrees/` 系统：`validate_worktree_name`（`[A-Za-z0-9._-]{1,64}` 白名单，拒穿越）、`run_git`（Command + wait_timeout 30s + 双管道 + **进程组超时整组击杀**）、`create_worktree`（`worktree add -b wt/{name} HEAD` + 可选 bind + 事件日志）、`bind_task_to_worktree`（只写字段保持 pending）、`remove_worktree`（**变更保护**：未提交/未推送拒绝，discard 放行 + 删分支）、`keep_worktree`、`count_worktree_changes`（含 run_git "(no output)" 占位过滤——实测修复）；3 新 Lead 工具（create/remove/keep，23→26）；**队友 wt_ctx 状态机**：claim 成功切 cwd 到 `.worktrees/{name}`、complete 重置、idle 自动认领返回任务 id 后切换；`run_bash_at/run_read_at/run_write_at` 参数化（主循环 execute_sync 路径不变）；**write 越界显式检查**（resolve_path 只词法折叠、队友无权限系统——实测漏洞修复，对齐 Python safe_path）；list_tasks 带 `(wt:)` 后缀；`.gitignore` 加 `.worktrees/`。实测前置：必须从 git 仓库根启动。**前移**：prompt 加 `Create new files in your work directory as needed.`（实测队友探索而非创建，Python 无此句）。

**s19 MCP Plugin** — 外部能力即插即用。`MCPClient`（教学 mock：`register` 注册工具定义 + 函数指针 handler，`call_tool` 未知工具/异常 → `MCP error: ...`）；两个 mock 服务器工厂（docs: search/get_version 全 readOnly；deploy: trigger/status，trigger 带 destructive 注解——**仅注解不拦截**）；`normalize_mcp_name`（非 `[a-zA-Z0-9_-]` → `_`，字符遍历无 regex 依赖）；`connect_mcp` 三种返回（already connected / Unknown server + Available 列表 / Connected + Discovered N tools，`[mcp] connected` 红字，连接顺序写入 `MCP_STATE.order` 保证池顺序可复现）；**assemble_tool_pool**：27 内置 + 已连接 MCP 工具 → 统一池（`mcp__{safe_server}__{safe_tool}` 命名），运行时表闭包只捕获 (server, tool) 两个 String、调用时按名查全局客户端——等价 Python `lambda *, c=..., t=..., **kw` 且无生命周期问题；**双路径分发**：`dispatch_tool` 表命中 → 动态 handler，未命中 → execute_sync（静态 match 一字不动，冻结惯例）；agent_loop 循环尾 `response_uses_connect_mcp` 检测 → 重组装池（**下一轮生效**——即插即用时刻）；system prompt tools 段加 `MCP tools are prefixed mcp__{server}__{tool}.`、有连接时加 `Connected MCP servers:` 段；`PromptContext` 加 `connected_mcp` 字段进缓存键——**Rust 保留 s10 prompt 缓存且连接即失效**（Python 删了缓存，前移）；`Tool.name/description` 改 String（承载动态工具名）；队友工具集固定 8 个、线程不持有 MCP 表——**MCP 仅 Lead**（类型层面隔离，Python 靠"队友不注册 handler"效果同）。**前移：服务器注册表配置化**——启动时读 `.mcp.json`（候选链 `cwd/.mcp.json` → `cwd/tutorials/rust/.mcp.json`，第一个有教学条目的生效），容错跳过真实 CC 的 stdio 条目（根目录 codegraph 实测共存），handler 注册表（`mcp_handler_by_name`）是"配置声明工具 ↔ 代码提供实现"的桥，`build_client` 走 new+register 两步（模拟 initialize/listTools），文件缺失回退内置兜底（与文件内容一致）。实测：connect docs → `[mcp] tool pool reassembled` → 模型下一轮调 `mcp__docs__search` → `[docs] Found 3 results for 'agents'`；连 deploy 后调 `mcp__deploy__status`；重连 docs → already connected。

**s20 Comprehensive** — 全部机制归位一个循环（完结章）。对齐 Python s20 的综合集成：**MCP 工具接入权限管线**——`check_rules` 新增臂（`mcp__` 前缀且名含 `deploy` → Gate 3 用户确认，对齐 Python 的粗糙匹配，readOnly 的 status 也被拦），s19 的"仅注解"升级为"注解+拦截"；**Current time 段**——`append_current_time` 在 `get_system_prompt` 层拼接（时间进缓存键会让 s10 缓存每秒失效，故缓存存前缀、命中时拼此刻时间——缓存保留且时间新鲜）；**Skills catalog 恒包含段**（措辞对齐 Python，空技能 `(no skills found)` 占位）；transcript 对齐 `.jsonl` 每行一消息 + `[compact]`/`[reactive compact]` 标记（挂点 s08 已有，只改格式不动架构）。**收敛点**：Python s20 恢复 edit/glob/todo/task/skill/cron 后内置工具 = 27 = Rust 27，s19 的池大小差异消失。保留 Rust 超集：memory 提取管线、SSE 流式、尾部 5 条保留、事件驱动组装池、stderr 惯例——逐一记录。实测：管道模式下 Gate 3 必然拒绝（REPL 的 BufReader 吞掉后续管道内容，RawStdin 只见 EOF——默认拒绝安全兜底；y 放行需交互模式），模型正确汇报 Blocked by user。

### 架构演进

```
s01 ──→ s02 ──→ s03 ──→ s04 ──→ s05 ──→ s06 ──→ s07 ──→ s08 ──→ s09 ──→ s10 ──→ s11 ──→ s12 ──→ s13 ──→ s14 ──→ s15 ──→ s16 ──→ s17 ──→ s18 ──→ s19 ──→ s20
 │        │        │        │        │        │        │        │        │        │        │        │        │        │        │        │        │        │        │        │
循环     工具表   权限管线  Hook注册  todo+nag 子代理   skill    压缩管线  记忆     prompt   错误恢复  任务图    异步并发  定时调度  团队     协议     自治     worktree   MCP      综合
bash   5工具    Gate1-3  4事件    双复位点  spawn    两层加载  4层+应急  .memory/  段落组装  分类恢复  .tasks/   后台+SSE  cron     MessageBus  状态机   看板认领  目录隔离   动态池    归位
        match   注入BufRead 短路语义  Mutex    双system 动态prompt compact工具 选/提/合并 缓存      退避/fallback blockedBy 并行工具 select!唤醒 队友任务  request_id 60s超时  任务绑定   双路径    MCP拦截
                                                                                                                             唤醒注入     idle loop  身份重注入 cwd切换  mcp__工具   Current time
```

每章只加不删。核心循环只改两处：工具分发（加 match 分支）、循环流（Hook/nag/task/压缩管线/记忆注入/错误恢复/并行执行）。

### 跨版本不变量

| 组件 | 引入 | s01 | s02 | s03 | s04 | s05 | s06 | s07 | s08 | s09 | s10 | s11 | s12 | s13 | s14 | s15 | s16 | s17 | s18 | s19 | s20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ContentBlock` enum | s01 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `truncate_lines` | s01 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `run_bash/read/write/edit/glob` | s03 | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `DENY_LIST` / 权限纯函数 | s03 | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `Hooks` + trigger 函数 | s04 | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 个内置 Hook | s04 | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `run_todo_write` / `CURRENT_TODOS` | s05 | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `extract_text` / `spawn_subagent` | s06 | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `parse_frontmatter` / `load_skill` | s07 | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 压缩管线（snip/micro/budget/compact/reactive） | s08 | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 记忆函数（write/rebuild/select/load/extract/consolidate） | s09 | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `PromptContext` / assemble / get / update_context | s10 | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `LlmError` / `with_retry` / `RecoveryState` / 截断恢复 | s11 | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `Task` CRUD + 5 任务工具 | s12 | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 后台任务（should_run_background/start/collect） | s13 | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SSE 流式（call_llm_streaming/StreamBlock） | s13 | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 并行执行（spawn_blocking 批次 + tokio） | s13 | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| cron 调度（cron_matches/fire_due_jobs/3 工具 + chrono） | s14 | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 协议（ProtocolState/match_response/consume_lead_inbox） | s16 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| 队友协议（handle_inbox_message/teammate_idle/submit_plan） | s16 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| MessageBus metadata（bus_send_meta/default_metadata） | s16 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| 自治（scan_unclaimed_tasks/idle_poll/idle_poll_once） | s17 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ |
| 身份重注入（maybe_reinject_identity）+ WORK 10 轮上限 | s17 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ |
| worktree（validate/run_git/create/bind/remove/keep/log_event） | s18 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ |
| 队友 cwd 状态机（wt_path + run_*_at 参数化 + 越界检查） | s18 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ |
| MessageBus（bus_send/bus_read_inbox/bus_peek + agent 名白名单） | s15 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 队友（ACTIVE_TEAMMATES/run_teammate/run_spawn_teammate/teammate_tools） | s15 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Lead 唤醒（inbox_poller/format_inbox_block/announce_teammates_done） | s15 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MCP 客户端（MCPClient/normalize_mcp_name/connect_mcp + MOCK_SERVERS） | s19 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ |
| 动态工具池（assemble_tool_pool/dispatch_tool/response_uses_connect_mcp + MCP_STATE） | s19 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ |
| MCP prompt（connected_mcp 缓存键 + Connected MCP servers 段 + mcp__ 命名） | s19 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ |

| MCP 权限拦截（check_rules mcp__*deploy* 臂 + Gate 3） | s20 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ |
| Current time 段（缓存键外拼接 append_current_time） | s20 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ |
| Skills catalog 恒包含段（Python 措辞） | s20 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ |
| transcript .jsonl（每行一消息 + compact 标记） | s20 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ |

✓ = 完全不变  — = 尚未引入

### 已知局限（标注了修复版本）

| 问题 | 引入 | 计划修复 |
|---|---|---|
| `CURRENT_TODOS` 锁中毒静默失败 | s05 | 顺延（s16 落地未修——冻结章节惯例，改进只前移） |
| `SKILL_REGISTRY` 测试竞态（并行时偶发失败，`--test-threads=1` 稳定） | s07 | 顺延（同上；s15 `ACTIVE_TEAMMATES`、s16 `PENDING_REQUESTS` 同类，协议测试已用唯一 id 模式并行稳健） |
| cron 测试共享 `CRON_JOBS`/`CRON_QUEUE`/`LAST_FIRED` 静态（并行时 `cron_reset_state` 互相清状态，偶发失败，`--test-threads=1` 稳定） | s14 | 顺延（同上；s16 协议测试已验证唯一 id 模式可消除同类竞态，s17+ 可前移） |
| `check_rules` 内部重取 cwd | s03 | 顺延（同上） |
| `Hooks` 字段全 pub | s04 | 教学可接受 |
| `run_bash` 管道 expect | s01 | 教学可接受 |

### 与 Python 版的关键差异

| 维度 | Python | Rust |
|---|---|---|
| 工具参数校验 | `handler(**block.input)` 运行时 | `serde_json::from_value<T>(input)` 反序列化时 |
| 用户交互可测性 | `unittest.mock.patch('input')` | `&mut impl BufRead` 依赖注入 |
| 全局状态 | `global list` | `static Mutex<Vec>` |
| Hook 注册 | `HOOKS[event].append(cb)` 运行时 | `hooks.pre_tool_use.push(Box::new(cb))` 编译期 |
| API 认证 | SDK 自动处理 | 手动 x-api-key / Bearer 二选一 |
| `ast.literal_eval` 回退 | 有 | 无（实际场景不受影响） |

## 关键 Rust 惯例

- **自包含章节**：每章完整复制数据模型（`ContentBlock`/`Message`/`ApiRequest` 等），独立可读可运行。提取共享 crate 延后到全部 20 章稳定后。
- **阻塞 reqwest（s01–s12）→ tokio（s13 起）**：s01–s12 用 `reqwest::blocking` + `rustls-tls`；s13 起主循环 async 化（`#[tokio::main]` + 异步客户端 + `tokio::time::sleep`），子代理与内部辅助调用仍走非流式路径。
- **强类型工具输入**：每个工具 `#[derive(Deserialize)]` 结构体，反序列化时校验而非运行时手动取字段。
- **`BufRead` 注入**：Gate 3 用户确认接受 `&mut impl BufRead`，测试用 `Cursor<&str>` 模拟键盘输入。
- **`Option<String>` Hook 结果**：`Some(reason)` = 阻断/请求继续；`None` = 放行。
- **按行截断**：`truncate_lines()` 在行边界截断追加 `"..."`，不切半行不切 UTF-8。
- **中文注释**：模块级 `//!` 和节标题用中文，Rust 语义相关的行内注释用英文。


## 已知延期项

### 流式输出（已落地：s13）

s13 引入 tokio 后已实现：`call_llm_streaming` 内联 SSE 事件循环，边收 `text_delta` 边打印；
子代理保持非流式（只回传摘要），父代理流式——正是本节当初的规划（改动范围：`ApiRequest` 加
`stream: bool`、SSE 事件枚举、`agent_loop` 内联 SSE 循环、`spawn_subagent` 控制流不变）。

## 编写新章节流程

1. 复制上一章的 `src/main.rs` 作为起点
2. 读对应 Python `sXX_*/code.py` 获取参考行为
3. 读 `sXX_*/README.md` 获取叙述解释和图表
4. 添加新机制；保持已有机制不变
5. 如需新 crate，更新 `Cargo.toml` 依赖
6. 编写新机制的单元测试（纯函数优先）
7. 运行 `cargo test -p sXX_*` 和 `cargo run -p sXX_*` 验证
8. 更新本 README 的进度清单

**不要重构或重组已完成章节。** 每章完成后冻结。如果某个模式需要改进，仅在新章中应用。
