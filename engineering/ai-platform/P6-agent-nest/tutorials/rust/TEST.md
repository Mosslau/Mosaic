# Rust 轨道端到端测试手册

按机制递进给出 Rust 轨道的端到端测试路径，每条包含**输入**、**预期观察**、**验证点**，
所有输出标记均与代码逐一核对过。

**测试约定**：Rust 轨道每章复制上一章并新增一个机制，因此**测试最新一章 = 回归全部已有
机制**。本文档的 T1–T17 覆盖 s01–s20 的全部机制，全部通过当前最新累积章测试（s20 完结）。

| 项目 | 当前值 |
|---|---|
| 最新累积章（所有测试路径的载体） | `s20_comprehensive` |
| 覆盖机制 | s01–s20（循环/工具/权限/Hook/规划/子代理/技能/压缩+transcript/记忆/prompt 组装/错误恢复/任务系统/后台·流式·并行/cron/团队·协议·自治/worktree/MCP·外部工具池/综合集成·MCP 权限拦截·Current time） |
| 自动化测试总数 | 2775（`cargo test --workspace`，其中章节 2751 + `example` gomoku 24） |

## 0. 前置条件

- Rust 工具链（`cargo --version`）
- 仓库根目录 `.env` 已配置：`ANTHROPIC_API_KEY`、`MODEL_ID`（可选 `ANTHROPIC_BASE_URL` 网关、`ANTHROPIC_AUTH_TOKEN`、`FALLBACK_MODEL_ID` 备用模型）
- 设了 `ANTHROPIC_BASE_URL` 时自动忽略 `AUTH_TOKEN`，统一走 `x-api-key`（对齐 Python 版）
- 已安装依赖并编译过一次（首次编译约 1–2 分钟）

## 1. 启动（最新累积章）

```bash
# ⚠️ 必须从仓库根目录跑（不是在 rust/ 里）：
#   - skills/ 在根目录，从 rust/ 跑会扫描不到 → 技能注册表为空
#   - .memory/ 记忆目录、bash/read/write 的 workspace 都 = 进程 cwd = 根目录
cargo run --manifest-path rust/Cargo.toml -p s20_comprehensive
#                                          ^^^^^^^^^^^^^^^^^^^^^^^ 换成当前最新累积章
```

启动横幅（以 s20 为例）：

```
s20: Comprehensive Agent — 全部机制，归到一个循环
输入问题，回车发送。输入 q 退出。
```

交互要点：

| 操作 | 行为 |
|---|---|
| 输入问题回车 | 发送，进入代理循环 |
| `q` / `exit` | 退出（大小写不敏感） |
| 空行 | 忽略，不发送 |
| `Ctrl-D`（EOF） | 退出 |
| 输入提示符 | 青色 `s20 >> ` |

**行编辑限制**：用裸 `read_line` 读 stdin，没有 rustyline——不支持方向键历史、Ctrl-A/E 等
readline 编辑。输入错了整行重敲即可（终端自己的退格删字不受影响）。

**调试开关**：

```bash
S01_DEBUG=1 cargo run --manifest-path rust/Cargo.toml -p s20_comprehensive
# 打印每次 API 调用的原始请求/响应（走 stderr，pretty-print）。
# 变量名沿用了 s01 的 S01_DEBUG，后续章节没有改名。
CONTEXT_LIMIT=600000 cargo run --manifest-path rust/Cargo.toml -p s20_comprehensive
# 覆盖 L4 摘要阈值（字符，默认 300000 ≈ 10 万 token，面向 1M 上下文的 flash）。
```

## 2. 自动化回归

```bash
cd <仓库>/rust        # 或 cd 到 rust/ 目录
cargo test --workspace
# 期望：2775 个测试全绿（章节 2751 + example/gomoku 24），0 警告
```

每章新增机制都会带纯函数单元测试；本手册第 3 节是这些测试覆盖不到的**端到端行为**。

## 3. 测试路径（按机制递进）

| 编号 | 机制 | 来源章节 |
|---|---|---|
| T1 | 代理循环 + 工具 | s01–s02 |
| T2 | 权限三道闸门 | s03 |
| T3 | 规划 + nag | s05 |
| T4 | 子代理隔离 | s06 |
| T5 | 技能按需加载 | s07 |
| T6 | 持久记忆 | s09 |
| T7 | 四层压缩 | s08 |
| T8 | 错误恢复（升 token / 续写 / 退避 / fallback） | s11 |
| T9 | 任务系统（持久任务图 / 依赖 / 解禁） | s12 |
| T10 | 异步与并发（后台任务 / 流式 SSE / 并行工具） | s13 |
| T11 | 定时调度（cron 匹配 / durable 持久化 / 自动交付） | s14 |
| T12 | 团队（文件收件箱 / 队友线程 / 唤醒注入） | s15 |
| T13 | 协议（request_id 握手 / 计划审批 / idle loop） | s16 |
| T14 | 自治（看板扫描 / 自动认领 / 60s 超时 / 身份重注入） | s17 |
| T15 | worktree（目录隔离 / 任务绑定 / 变更保护） | s18 |
| T16 | MCP（连接服务器 / 动态工具池 / 双路径分发） | s19 |
| T17 | 综合（MCP 权限拦截 / Current time / Skills catalog / transcript） | s20 |

> Hook（s04）与 prompt 组装（s10）不单独列测试路径：Hook 通过 T1 的 `[HOOK]` 日志与
> T2 的权限行为观察；prompt 组装通过 T6 的 `[assembled]` 输出观察。

> **测试原则**：这些路径测的是 harness 机制，但**工具选择权在模型**——它可能用
> bash 代替 read_file、跳过 todo_write、不派子代理，这些都不算 bug。先观察"是否
> 调用目标工具"，未触发就按各条「要点」里的强化提示（显式点名工具名）重试；
> 内部行为（nag 注入等）用 `S01_DEBUG=1` 看原始请求。2025-08-16 实测暴露过
> 这类情况，T2 Gate3 / T3 / T4 的提示词已按实测倾向强化。

### T1 基础：代理循环 + 工具

**输入**：`列出当前目录的文件`

**预期观察**：
- `[HOOK] UserPromptSubmit: working in /Users/.../learn-claude-code`（灰色，stderr）——每次发消息都会打
- `[HOOK] bash({...})`（灰色，stderr）——log hook 记录工具调用
- 模型跑 `ls`，最终用文字回答文件列表

**验证点**：
- ✅ 能完整跑通「模型 → 工具 → 结果回灌 → 再回复」的循环
- ✅ 工具输出太长时会截断（50000 字符，按整行）

### T2 权限：三道闸门

**Gate 1（硬拒，不问用户）**：`执行 sudo whoami`

**预期**：工具结果直接返回 `Blocked: 'sudo' is on the deny list`，模型被告知被拦。

完整硬拒列表：`rm -rf /`、`sudo`、`shutdown`、`reboot`、`mkfs`、`dd if=`、`> /dev/sda`。
注意是**子串匹配**：`echo "no sudo needed"` 也会被误拦（教学代码，宁可误杀）。

**Gate 2 → 3（升级确认）**：`用 read_file 工具读取 /etc/hosts 的前 5 行`

**预期**：read_file 目标逃逸 workspace → 触发 Gate 3，**循环暂停**等输入：

```
⚠  Reading outside workspace
   Tool: read_file({...})
   Allow? [y/N]
```

- 输 `y` 或 `yes` → 放行执行；输**任何其他内容或直接 EOF** → 默认拒绝（工具结果里带拒绝理由）
- 破坏性 bash 关键词（`rm `、`> /etc/`、`chmod 777`、`-delete`）也会升级到这里

**要点**：
- ⚠️ **必须显式点名 `read_file` 工具**：实测中模型接到"读 ../README.md"会改用 bash
  （`head -n 20 ../README.md`）绕开 Gate 2——路径沙箱只约束文件工具，bash 等于
  给了模型一把 shell（架构性限制）。点名工具 + 给必然存在的绝对路径（`/etc/hosts`）
  才能稳定触发。测试时先输 `n` 观察默认拒绝，再重试输 `y` 观察放行。

**验证点**：
- ✅ Gate 1 无交互直接拦；Gate 3 默认拒绝（安全默认值）
- ✅ 路径边界是**按组件**判断的：试 `../rust2/...`（同名前缀兄弟目录）
  也会被拦——这是修复过的前缀绕过，有回归测试 `workspace_check_rejects_sibling_prefix`

### T3 规划：todo_write + nag 提醒

**输入**：`先用 todo_write 工具列出计划，再做这三件事：1) 统计 rust/ 下 .rs 文件数量 2) 看下 s01 的 README 标题 3) 汇总成一句话报告`

**预期观察**：
- 模型先调 `todo_write` 建 3 个 pending 任务，逐项执行并更新状态
- **nag 提醒**：同一回合内连续 ≥3 轮工具调用不更新 todos 时，注入
  `<reminder>Update your todos.</reminder>` 作为 user 消息催更（见下方观察方法）

**要点**：
- ⚠️ todo_write 是模型**可选**的：实测中"帮我做三件事"这种简单任务，模型 2 轮
  bash 就做完、完全跳过规划。显式点名（"先用 todo_write 列出计划"）才能稳定触发；
  若仍跳过，追加一句"请务必先调用 todo_write"。
- **nag 提醒终端不可见**（它注入到消息里，不打印）。观察方法：开 `S01_DEBUG=1`
  跑一个单回合 ≥3 轮工具的长任务（如"依次做 5 件小事：a) /etc/hosts 行数
  b) rust 下 toml 数量 c) 根目录最大 3 个文件 d) README 段落数 e) 一句话汇总"），
  在原始请求的 messages 里搜 `reminder`。
  注意计数器是 `agent_loop` 内的局部变量，**每回合重置**——跨回合不累计。

**验证点**：
- ✅ todo 状态流转 pending → in_progress → completed
- ✅ 单回合 ≥3 轮不碰 todo_write 时，debug 输出里出现 `<reminder>Update your todos.</reminder>`

### T4 子代理：task 上下文隔离

**输入**：`用 task 工具派一个子代理，分别统计 s01_agent_loop 和 s02_tool_use 两个 Rust 章节的 main.rs 行数，父代理只负责汇总结果`

**预期观察**：
```
[Subagent spawned]
[sub] bash: ...        ← 子代理的每次工具调用（前缀 [sub]）
[Subagent done]
```

**要点**：
- ⚠️ 子代理是模型**可选**的：一条 find 命令能搞定的统计，模型会自己直接干
  （实测中"帮我做三件事"的统计子任务就没派子代理）。显式点名 `task` 工具 +
  把任务描述成"独立子任务、父代理只汇总"更容易触发；若仍跳过，
  追加一句"请务必使用 task 工具"。

**验证点**：
- ✅ 子代理拿的是**全新消息列表**：看不到父代理的历史，也看不到 task/todo_write
  工具（子代理只有 5 个工具：bash/read/write/edit/glob），不会递归 spawn
- ✅ 父代理把子代理的最终文本汇总进回答
- ✅ 子代理同样走权限管线（危险命令照样被拦），30 轮上限防失控

### T5 技能：load_skill 按需加载

**输入**：`用 code-review 技能审查 s01_agent_loop/src/main.rs，输出要点即可`

**预期观察**：
- 模型调 `load_skill("code-review")`，拿到完整 SKILL.md 内容后开始审查
- 仓库自带的 4 个技能：`agent-builder`、`code-review`、`mcp-builder`、`pdf`

**验证点**：
- ✅ 技能内容是**调用时才加载**的（两层注入理念：prompt 只放目录、调用才给全文）
- ✅ 目录清单已接入 system prompt（skills 段）：模型在 system prompt 里
  就能看到全部 4 个技能名，不需要靠工具描述里的示例名猜。
  此集成点有回归测试 `assemble_prompt_includes_skill_catalog` 守护。

### T6 记忆：提取 → 持久化 → 注入

**第一步**：`记住：我喜欢用 4 空格缩进，讨厌尾随空格。`

**预期观察**（本轮模型停止时自动执行）：
```
[Memory: new N, updated M, skipped K]
```

> 提取有门控：只在用户消息含偏好信号词（记住/偏好/喜欢/讨厌/以后/总是/从不/不要/
> remember/prefer/always/never）或输入超 200 字符时才会提取；普通查询轮无此输出。

**第二步**：退出（`q`），查看磁盘：

```bash
ls .memory/        # 应有 MEMORY.md 索引 + 若干 <slug>.md 记忆文件
cat .memory/MEMORY.md
```

记忆文件是 YAML frontmatter（name/description/type）+ 正文。

**第三步**：重新启动，问 `我有什么偏好？`

**预期观察**：
- 启动首轮出现 `[assembled] sections: identity, tools, workspace, skills, memory`（绿色）——
  技能目录与 MEMORY.md 索引分别进 system prompt 的 skills / memory 段
- 相关记忆内容被注入到当前 user 消息（LLM 选择 + 关键词回退两条路径）
- 上下文没变时后续轮次打 `[cache hit] system prompt unchanged`（灰色）

**验证点**：
- ✅ 记忆跨进程存活（重启后仍在）
- ✅ system prompt 是运行时组装的，记忆变化会改变 prompt（缓存 key 含记忆内容，不会拿旧缓存）
- ✅ 普通查询轮（如"列出文件"）不产生新记忆——无 `[Memory: ...]` 输出（门控生效）

### T7 压缩：四层管线

**触发方式**（由易到难）：

| 层级 | 触发 | 观察 |
|---|---|---|
| L1 snip | 单条输出超长 | 输出按行截断 |
| L2 micro | 每轮 LLM 调用前自动 | 旧 tool_result 被替换为 `(compacted)` 标记，只留最近 3 条 |
| L3 summary | 历史估算超 50000 字符 | 早期历史被 LLM 摘要；**保留尾部最近 5 条原始消息**——当前回合的请求与最新工具结果不随压缩丢失，"继续"可无缝接上 |
| L4 reactive | API 报 prompt_too_long | `[reactive compact]` + 重试 |

另外模型可主动调 `compact` 工具 → `[compact]`；自动触发时打 `[auto compact]`。

**验证点**：
- ✅ 连续大输出多轮（比如反复 `cat` 大文件）后观察历史被压缩、对话仍能继续

### T8 错误恢复：截断升级 / 续写 / 退避 / fallback

s11 把主循环的 LLM 调用包进错误恢复层。三条路径的触发难度差别很大，
本路径**只保证能实测路径 1（截断）**，路径 2/3 靠单元测试覆盖。

**路径 1 实测（升 token + 续写）**：

```bash
# 用很小的 MAX_TOKENS 逼模型截断（环境变量在启动时读取，8000 → 300）
MAX_TOKENS=300 cargo run --manifest-path rust/Cargo.toml -p s11_error_recovery
```

**输入**：`写一个完整的 Rust 五子棋游戏（15x15 棋盘、命令行交互），代码写进 example/ 目录`

**预期观察**：
- 第一次截断：`[max_tokens] escalating 300 -> 64000`（黄色）——**重发同一个请求**，
  截断输出不追加进历史（S01_DEBUG=1 可见第二次请求的 messages 与第一次相同）
- 模型继续用 64K 上限输出；若 64K 仍被截断：`[max_tokens] continuation 1/3`（黄色），
  截断输出进历史 + 注入续写提示
- 续写超过 3 次：`[max_tokens] recovery limit reached`（红色），保留最后截断输出并退出本轮

**验证点**：
- ✅ 升级发生在"追加 assistant 消息"之前——messages 保持不变，纯换 token 上限重试
- ✅ 恢复状态是 agent_loop 内的局部变量，每回合独立（升级/续写计数不跨回合）
- ✅ 模型最终交付完整代码（300 token 被截断 → 升级后写全）

**路径 2（上下文超限）**：API 报 `prompt_too_long` 时打 `[reactive compact]` 后重试一次，
仍超限打 `[unrecoverable] still too long after compact`（红色）并把 `[Error]` 写进历史。
正常测试里几乎不可能触发——s08 的 L4 自动压缩（50000 字符阈值）远早于 API 上限介入。
分类逻辑由单元测试 `classify_http_error_prompt_too_long_variants` 守护。

**路径 3（429/529 退避 + fallback）**：依赖网关真实限流/过载，无法按需复现。
日志形态：`[429 rate limit] retry 2/10, wait 1.1s` / `[529 overloaded] retry 2/10, wait 1.1s`
（黄色）；连续 3 次 529 后 `[529 x3] switching to <FALLBACK_MODEL_ID>`（红色，
未配置 FALLBACK_MODEL_ID 时打 `no FALLBACK_MODEL_ID configured, continuing retry`）。
退避公式、Retry-After 优先级、切换决策由 `retry_delay_*` / `recovery_state_529_*` /
`with_retry_*` 系列单元测试守护。

**要点**：
- ⚠️ 恢复只包**主循环**的 LLM 调用：记忆选择/提取、历史摘要、子代理等内部辅助
  调用维持单次直调（失败静默或返回占位）——教学版范围，代码有注释说明。

### T9 任务系统：持久任务图 + 依赖 + 解禁

**输入**：`用任务系统拆解"做一个小网站"：先用 create_task 建 3 个任务（设计→编码→测试），
其中编码 blockedBy 设计、测试 blockedBy 编码；然后按依赖顺序 claim 和 complete`

**预期观察**：
- `[create] 设计` / `[create] 编码 (blockedBy: task_...)` / `[create] 测试 (blockedBy: ...)`（蓝色）
- 模型先 `list_tasks` 看全貌：`○ task_...: 设计 [pending]`、`● in_progress`、`✓ completed` 图标流转
- 认领被阻塞的任务 → 工具结果 `Blocked by: ['task_...']`（单引号列表，对齐 Python）
- 按序完成后：`[claim] 编码 → in_progress (owner: agent)`（青色）、`[complete] 设计 ✓`（绿色）、
  `[unblocked] 编码`（黄色）——complete 的返回里带 `Unblocked: 编码`

**第二步**：退出（`q`），检查磁盘并重启验证持久化：

```bash
ls .tasks/          # 3 个 task_*.json
cat .tasks/任一.json  # 有 blockedBy 字段（camelCase）、owner 字段
# 重启后问：列出所有任务
```

**预期观察**：重启后 `list_tasks` 显示 3 个任务的状态原样保留——跨会话恢复。

**验证点**：
- ✅ 任务状态机 pending → in_progress → completed，且**跳序认领被依赖挡住**
- ✅ 磁盘格式与 Python 版 asdict 输出同构（blockedBy/owner null），两轨文件可互换
- ✅ complete 自动报告下游解禁，引导模型继续推进依赖链
- ✅ 与 todo_write 分工：todo 是会话内存清单，任务是磁盘依赖图

**要点**：
- ⚠️ 任务工具选择权在模型：显式点名 `create_task`/`claim_task` 才能稳定触发
- 子代理（task 工具）**没有**任务工具——任务图是父代理的协调层

### T10 异步与并发：后台任务 / 流式 SSE / 并行工具

**输入**：`用 run_in_background 在后台跑 pip list（或其他慢命令），同时用 read_file 读 package.json；等后台完成的通知`

**预期观察**：
- **流式输出**：模型回复时文字**逐字流出**（text_delta 边收边打印），不是一次性整段出现；
  工具调用前有一段思考后直接打印 `> <工具名>`（黄色）
- **思考过程（可选）**：默认不显示；`STREAM_THINKING=1 cargo run --manifest-path rust/Cargo.toml -p s13_background_tasks`
  启动后，thinking_delta 以灰色 `[thinking] ...` 流式打到 **stderr**（与 stdout 的 text 分离，
  不污染主输出；thinking + signature 始终重建回传 API，多轮工具调用不受影响）
- **后台任务**：`[background] dispatched bg_0001: pip list`（黄色）→ 占位工具结果
  `[Background task bg_0001 started] Command: ... Result will be available when complete.`
- 主循环**没干等**：同一轮里模型继续做别的（如读文件）
- 后台完成后：`[background done] bg_0001: ... (N chars)`（绿色）+
  `[inject] 1 background notification(s)`（绿色）→ 模型看到
  `<task_notification>`（含 task_id/status/command/summary 的 XML）

**并行执行观察（S01_DEBUG=1 更直观）**：让模型"同时用 glob 找两个模式的 .rs 文件"
（一条消息里两个 tool_use）——两个工具结果几乎同时出现，且 tool_result 顺序与
tool_use 顺序一致（API 配对契约）。

**验证点**：
- ✅ 慢命令丢后台后主循环立即继续，模型没有被 120s 超时卡住
- ✅ 通知以 `<task_notification>` 注入，**不复用 tool_use_id**（工具配对语义）
- ✅ 后台任务仍在 bash 的 120s 超时内运行（超时杀进程组，不留孤儿）
- ✅ 流式重建的响应与 s11 错误恢复兼容：截断升级/续写路径照常工作
  （`MAX_TOKENS=300 cargo run --manifest-path rust/Cargo.toml -p s13_background_tasks` 可复现）

**要点**：
- 后台是模型**可选**的：显式点名 `run_in_background: true` 才能稳定触发；
  未指定时命中慢关键词（install/build/test/...，**词边界匹配**）的 bash 也会自动进后台（启发式兜底）
- 子代理（task 工具）**不并行**、**不流式**：串行执行、非流式调用——并行子代理是 s15 的内容

### T11 定时调度：cron 匹配 / durable 持久化 / 自动交付

**输入**：`用 schedule_cron 注册一个每 2 分钟执行的任务，提示词是"运行 date 命令并汇报"`

**预期观察**：
- `[cron register] cron_XXXXXX '*/2 * * * *' → 运行 date 命令并汇报`（紫色）
- 工具结果 `Scheduled cron_XXXXXX: '*/2 * * * *' → 运行 date 命令并汇报`
- `.scheduled_tasks.json` 落盘（durable 数组 JSON，字段与 Python 版同构）

**无人值守自动交付**（核心验证点）：注册后**不输入任何内容**，等 1–2 分钟：
- 调度任务 `[cron fire] cron_XXXXXX → 运行 date 命令并汇报`（紫色）
- 主循环被唤醒：`[queue processor] delivering scheduled work`（紫色）
- 模型自动跑 `date` 并汇报——**不需要人推**

**其余验证**：
- `列出现在所有的定时任务` → list_crons 行格式 `  cron_XXXXXX: '*/2 * * * *' → ... [recurring, durable]`
- `注册一个 1 分钟后的一次性提醒(recurring=false)，内容是"检查构建状态"` → 触发后自动消失（
  `[cron fire]` 后不再出现在 list_crons）
- `取消刚才的周期性任务并确认` → `[cron cancel]` + `Cancelled cron_XXXXXX` + 文件同步移除
- 退出重启 → `[cron] loaded N durable job(s)` 恢复任务（重启后当前分钟命中会立即触发一次，
  属预期行为——`LAST_FIRED` 是内存态）

**验证点**：
- ✅ 调度线程独立运行：agent 空闲时也能自动触发、自动执行（不消耗用户输入）
- ✅ 五字段 cron 语义：`*/2`、`0 9 * * *`、`1-5`、`13 * 5`（DOM/DOW OR）由单元测试矩阵守护
- ✅ durable 跨重启恢复；session-only（durable=false）不落盘
- ✅ 长回合进行中的触发在下一轮循环顶部注入（`[inject cron]`）——回合内路径 A

**要点**：
- 校验是硬性的：非法 cron 表达式直接返回 `Error: ...`（如 `Expected 5 fields`）
- 作业数上限 50：超限返回 `Too many scheduled jobs (max 50). Cancel one first.`
- 触发时间按**本地时区**解释；进程关闭调度即停（durable 只保任务定义）

### T12 团队：文件收件箱 / 队友线程 / 唤醒注入

**输入**：`Spawn alice as a backend developer. Ask her to create a file called schema.sql with a users table.`

**预期观察**：
- 工具结果 `Teammate 'alice' spawned as backend developer`
- `[teammate] alice spawned as backend developer`（青）
- `.mailboxes/alice.jsonl` 出现（Lead 的初始 prompt 经 teammate 工具参数直接传入，
  队友线程启动后自行工作）

**无人值守自动汇报**（核心验证点）：spawn 后**不输入任何内容**，等 1–2 分钟：
- 队友干完 → `[teammate] alice finished`（绿）
- Lead 收件箱有货 → `[wake: 1 inbox + 0 background -> new turn]`（黄）
- 主循环被唤醒自动跑一轮（`[Inbox]\nFrom alice: ...` 注入）——**不需要人推**
- 全部排空后：`[all teammates done]`（绿）

**其余验证**：
- `Check your inbox for alice's result.` → check_inbox 行格式 `  [alice] ...`（消费式，
  再查返回 `(inbox empty)`）
- `Send a message to alice: please verify the schema.` → `Sent to alice` + `[bus] lead → alice: ...`
- 重复 spawn 同名队友 → `Teammate 'alice' already exists`
- `.mailboxes/` 目录内 JSONL 单行 JSON：`{"from":...,"to":...,"content":...,"type":...,"ts":...}`

**验证点**：
- ✅ 队友独立运行：自己的 system prompt / messages / 4 工具（bash/read/write/send_message）
- ✅ 文件收件箱消费式读写 + peek 非破坏（轮询不丢消息）
- ✅ Lead 空闲被异步唤醒（后台队友与后台任务共用唤醒条件）
- ✅ 消息经 `.mailboxes/*.jsonl` 可见、可审计

**要点**：
- 队友上限 10 轮：`MAX_TEAMMATE_ROUNDS`，防死循环（真实 CC 用 idle loop）；
  **s16 起为 idle loop（无轮数上限，靠 shutdown 协议退出，见 T13）**
- 队友工具不触发权限闸门（后台线程无法交互确认；真实 CC 用权限冒泡，s16 引入）
- agent 名校验（黑名单）：拒绝 `/ \ . :` 空格与控制字符，中文名（如「小红」）允许；`../` 类名字被拒（Python 教学版可路径穿越，Rust 前向修复）

### T13 协议：request_id 握手 / 计划审批 / idle loop

**输入**：`Spawn alice as a backend dev. Ask her to create a file called config.py. Then request her shutdown.`

**预期观察**：
- `Teammate 'alice' spawned as backend dev` + `[teammate] alice spawned`（stderr）
- alice 干活 → `[teammate] alice finished` 前先进入 idle（无输出，等待收件箱）
- `[protocol] shutdown_request → alice (req_xxxxxx)`（紫）——Lead 侧 request_shutdown
- alice idle 轮询收到 → `[protocol] alice approved shutdown (req_xxxxxx)`（紫）
- Lead 自动唤醒（s16 保留 poller）：`[protocol] shutdown ✓ (req_xxxxxx: approved)`（绿）
- `[teammate] alice finished` + summary 汇报 + `[all teammates done]`

**计划审批**（第二个场景）：
- `Spawn bob with a refactoring task. Have him submit a plan first.`
- bob 调 `submit_plan` → `Plan submitted (req_xxxxxx). Waiting for approval...`
- Lead 收到 `plan_approval_request`（check_inbox 行格式 `  [bob] [plan_approval_request req:req_xxxxxx] ...`）
- `review_plan` 批准 → bob 收到 `[Plan approved] Proceed with the task.` 继续干活
- 拒绝路径：`[Plan rejected] Feedback: ...`

**验证点**：
- ✅ request_id 在请求与响应间一致（.mailboxes/ 内消息 metadata 可审计）
- ✅ `PENDING_REQUESTS` 状态机：pending → approved/rejected；重复回复被忽略
- ✅ 类型校验：shutdown 请求不会被 plan 响应误批（`[protocol] type mismatch` 红字）
- ✅ 队友 idle 后能收到 shutdown_request 并体面退出（不再 10 轮即死）
- ✅ `consume_lead_inbox` 统一消费：check_inbox 与自动唤醒都先路由协议

**要点**：
- 协议状态是内存态：`PENDING_REQUESTS` 不落盘，重启即失
- 队友 idle 无超时：不关机就驻留（靠 shutdown 协议退出）
- 执行门控未实现：submit_plan 后队友仍可调 bash/write（教学版靠模型自觉）
- `[protocol]` 标记走 stderr（对齐 s15 标记惯例）

### T14 自治：看板扫描 / 自动认领 / 60s 超时 / 身份重注入

**输入**：`Create 3 tasks on the board, then spawn alice and bob. Watch them auto-claim and work.`

**预期观察**：
- `Teammate 'alice' spawned as backend dev (autonomous)`（带 **autonomous 后缀**）
- 队友进入 IDLE：`[idle] alice auto-claimed: 设计`（绿）——**自动认领看板任务**
- alice/bob 各自认领不同任务、并行完成：`[complete] ... ✓`
- 有 blockedBy 依赖的任务：前置完成后才被认领（`[idle] bob auto-claimed: 编码`）
- 全部做完后：`[idle] alice timeout (60s)`（红）→ `[teammate] alice finished`
  —— **60s 无新任务自动关机**

**IDLE 阶段关机**（第二个场景）：
- 队友 idle 中执行 `request_shutdown` → `[protocol] alice approved shutdown in idle (req_xxx)`（紫）
  —— **立即响应，不等下一轮 WORK**

**验证点**：
- ✅ 任务板三条件：pending + 无 owner + 依赖完成（`scan_unclaimed_tasks`）
- ✅ 认领后任务状态 in_progress + owner=队友名（`.tasks/` 可审计）
- ✅ claim 失败不注入（owner 冲突时黄字 `claim failed`，继续轮询）
- ✅ WORK ≤10 轮、IDLE 60s 超时（常量对齐 Python 10/5/60）
- ✅ 身份重注入：刚 spawn 首轮 WORK 前注入 `<identity>`
- ✅ 收件箱优先：idle 中 shutdown_request 不被任务板饿死

**要点**：
- 任务认领无文件锁：多队友并发抢单靠 owner 检查兜底（教学版，真实 CC 用 proper-lockfile）
- 队友的 claim_task owner=自己的名字（不是 "agent"）
- 60s 超时是自动关机机制：无任务即退出，不无限驻留
- ⚠️ **实测：队友可能不调 complete_task**（只报 Done 就超时退出，任务板残留
  in_progress）——system prompt 未显式指示（Python 同）；Lead 可手动补
  complete_task 或 `rm .tasks/` 重置；若队友虚报完成，Lead 需自行验证产物
- ⚠️ **实测：双提示符**（cron/wake 空信号迭代多打一个 `s18 >> `）——s14 同款，
  无功能影响

### T15 worktree：目录隔离 / 任务绑定 / 变更保护

**输入**：`Create 2 tasks and 2 worktrees (create_worktree auth, ui; bind them to the tasks), then spawn alice and bob. Watch them work in their own directories.`

**⚠️ 前置**：必须从 **git 仓库根**（AgentNest/）启动——`git worktree add` 需要仓库上下文，从 rust/ 跑直接 `Git error`。

**预期观察**：
- `[worktree] created: auth at .../.worktrees/auth`（黄）→ `[bind] 任务 → worktree:auth`（黄）
- 队友认领后 `[teammate:alice] write_file: Wrote ... .worktrees/auth/...`——**cwd 在 worktree 内**
- 两个队友各写各的目录，互不覆盖（隔离验证）
- `list_tasks` 行格式带 `(wt:auth)` / `(wt:ui)` 后缀
- `.worktrees/events.jsonl` 有 create 事件记录

**变更保护**（第二场景）：
- 队友在 worktree 里写完文件后，`remove_worktree auth`（不带 discard）→ **拒绝**：
  `Worktree 'auth' has N uncommitted file(s) and 0 unpushed commit(s)...`
- `remove_worktree auth discard_changes=true` → 强制移除 + 目录消失
- `keep_worktree auth` → `Worktree 'auth' kept for review (branch: wt/auth)` + keep 事件

**验证点**：
- ✅ 任务绑定保持 pending（`bind_task_to_worktree` 只写字段）
- ✅ 队友认领绑定任务后 cwd 切换到 worktree（`resolve_task_worktree`）
- ✅ complete 后 cwd 重置回主仓库
- ✅ write 越界拒绝：队友无法 `../` 逃出 worktree 写主仓库（`Error: Path escapes workspace`）
- ✅ 名称校验：`../evil` / 非法字符被拒（`Error: Invalid worktree name`）

**要点**：
- ⚠️ **实测：队友可能探索而非创建**（worktree 是主仓库 checkout，模型倾向
  "找文件"）——30+ 轮 bash 探索后超时退出、任务残留 in_progress；Rust 已
  前移 prompt 指示（`Create new files in your work directory as needed.`），
  任务描述建议明确"创建新文件 xxx"；残余场景 Lead 手动补 complete_task
- `.worktrees/` 是运行时产物（已入 .gitignore——含 .git 文件，误提交破坏仓库）
- 事件日志格式：`{"type":"create|remove|keep","worktree":...,"task_id":...,"ts":...}`
- `[worktree]`/`[bind]` 标记走 stderr（轨道惯例）

### T16 MCP：连接服务器 / 动态工具池 / 双路径分发

**输入**：`Connect to the docs MCP server and search for "agents".`

**预期观察**：
- `[mcp] connected: docs → ['search', 'get_version']`（红）→
  `Connected to MCP server 'docs'. Discovered 2 tools: search, get_version`
- `[mcp] tool pool reassembled`（本轮重组装）
- 模型**下一轮**调 `mcp__docs__search`（新工具进池生效）→ `[docs] Found 3 results for 'agents'`
- system prompt 出现 `Connected MCP servers: docs` 段（`[assembled]` 而非 `[cache hit]`）

**配置场景**（前移：.mcp.json 配置驱动）：
- 启动横幅：`[mcp] config loaded: 2 server(s) from .../tutorials/rust/.mcp.json`
  （根目录真实 CC 配置的 codegraph 条目被容错跳过并提示，不报错）
- 编辑 `tutorials/rust/.mcp.json` 加一个服务器（`handler` 用注册表里的名字，
  如 `docs_search`），重启进程后 `connect_mcp` 即可连接——**改文件需重启**
- 可用列表：`Unknown server 'nope'. Available: deploy, docs`（配置键排序）
- 未知 handler 名 → 连接报配置错误（`MCP config: unknown handler ...`）

**第二场景**（deploy + 幂等）：
- 输入 `Connect to the deploy MCP server and check the status of service "api".`
  → `[mcp] connected: deploy → ['trigger', 'status']` → 模型调 `mcp__deploy__status`
  → `[deploy] api: running (v1.4.2)`
- 重连 docs → `MCP server 'docs' already connected`（幂等）
- 问模型"有哪些 MCP 工具"→ 应能列出 4 个并识别 trigger 是 destructive（注解透传）

**验证点**：
- ✅ 连接顺序确定性：池 = 27 内置 + docs(2) + deploy(2)（`mcp__docs__search` 在
  `mcp__deploy__trigger` 之前）
- ✅ 双路径分发：`mcp__*` 走运行时表，内置工具照常走 execute_sync
- ✅ 缓存失效：连接前后 system prompt 不同（`[assembled]`），连接后不变（`[cache hit]`）
- ✅ 队友侧无 MCP：spawn 的队友工具集固定 8 个（不调 connect_mcp / mcp__*）

**要点**：
- 工具池在**连接后的下一轮**生效——connect_mcp 当轮执行完才重组装（教学时序）
- MCP 仅 Lead：队友线程不持有运行时表（类型层面隔离，Python 靠"队友不注册 handler"）
- `[mcp] connected` 走 stdout（Lead 专属工具，不进队友线程；队友标记仍走 stderr）
- destructive 仅注解不拦截（教学版，真实 CC 需人工确认）
- 未知服务器：`Unknown server 'nope'. Available: docs, deploy`

### T17 综合：MCP 权限拦截 / Current time / Skills catalog / transcript

**输入 1（MCP 权限拦截）**：`Connect to the deploy MCP server and check the status of service "api".`

**预期观察**：
- `[mcp] connected: deploy → ['trigger', 'status']`（红）
- 模型调 `mcp__deploy__status` → **`⚠ MCP destructive-looking tool (requires approval)`**
  + `Allow? [y/N]`（Gate 3 拦截——readOnly 的 status 也被拦，Python 粗糙匹配对齐）
- ⚠️ **管道模式必拒**：REPL 的 stdin BufReader 把后续管道内容吞进缓冲，
  Gate 3 的 RawStdin 读 OS 层 fd 只见 EOF → 默认拒绝 → `Blocked by user: ...`
  （安全兜底；**y 放行只能在交互模式**，输入 y 回车）
- `mcp__docs__search` 不触发拦截（非 deploy）

**输入 2（Current time / Skills catalog）**：`What time is it? What skills are available?`
- system prompt 含 `Current time: 2026-08-26T20:18:05` 段（`[assembled]` 时可见；
  `[cache hit]` 时时间仍刷新——缓存键外拼接）
- 含 `Skills catalog:` + `Use load_skill(name) when a skill is relevant.`（恒包含）

**输入 3（transcript，可选，需触发压缩）**：长会话或显式 `compact`
- `[compact] transcript saved: .transcripts/transcript_*.jsonl`（青）→ 每行一条消息
- 压缩后模型仍能继续（尾部 5 条保留，s08 前移）

**验证点**：
- ✅ MCP deploy 工具经 Gate 3（y 放行 / n·EOF 拒绝，Cursor 单测覆盖）
- ✅ Current time 段格式 `%Y-%m-%dT%H:%M:%S`、缓存命中仍刷新
- ✅ Skills catalog 恒包含（空技能 `(no skills found)`）
- ✅ transcript `.jsonl` 每行合法 JSON

## 4. 输出标记速查表

| 标记 | 颜色 | 含义 |
|---|---|---|
| `[HOOK] UserPromptSubmit: working in ...` | 灰 | 用户输入事件（stderr） |
| `[HOOK] bash({...})` | 灰 | 工具调用日志（stderr） |
| `[HOOK] ⚠ Large output from ...` | 黄 | 输出超 100k 字符 |
| `Blocked: 'xxx' is on the deny list` | — | Gate 1 硬拒（作为工具结果返回给模型） |
| `⚠ Reading/Writing outside workspace` + `Allow? [y/N]` | 黄 | Gate 3 确认 |
| `[Subagent spawned] / [Subagent done]` | 紫 | 子代理生命周期 |
| `[sub] bash: ...` | 灰 | 子代理的工具调用 |
| `[Memory: new N, updated M, skipped K]` | 黄 | 提取结果：新增 / 覆盖更新 / 去重跳过 |
| `[Memory: consolidated X → Y memories]` | 黄 | 记忆合并（超阈值） |
| `[assembled] sections: ...` | 绿 | system prompt 组装 |
| `[cache hit] system prompt unchanged` | 灰 | prompt 缓存命中 |
| `[auto compact] / [reactive compact] / [compact]` | — | 压缩管线触发 |
| `[max_tokens] escalating 8000 -> 64000` | 黄 | 输出截断 → 升级 token 上限重发同一请求 |
| `[max_tokens] continuation 1/3` | 黄 | 64K 仍截断 → 保存输出 + 注入续写提示 |
| `[max_tokens] recovery limit reached` | 红 | 续写 3 次后放弃（保留最后截断输出） |
| `[429 rate limit] retry 2/10, wait 1.1s` | 黄 | 限流 → 指数退避重试（Retry-After 头优先） |
| `[529 overloaded] retry 2/10, wait 1.1s` | 黄 | 过载 → 指数退避重试 |
| `[529 x3] switching to <model>` | 红 | 连续 3 次过载 → 切换备用模型 |
| `[unrecoverable] ...` | 红 | 不可恢复错误 → `[Error]` 写进历史，本轮结束 |
| `[create] 设计 (blockedBy: ...)` | 蓝 | 创建任务 |
| `[claim] 编码 → in_progress (owner: agent)` | 青 | 认领任务（依赖满足） |
| `[complete] 设计 ✓` | 绿 | 完成任务 |
| `[unblocked] 编码` | 黄 | 下游任务解禁 |
| `[background] dispatched bg_0001: pip list` | 黄 | 慢命令丢后台，返回 bg_id |
| `[background done] bg_0001: ... (N chars)` | 绿 | 后台任务完成（通知已生成） |
| `[inject] 1 background notification(s)` | 绿 | `<task_notification>` 注入本轮 user 消息 |
| `[debug] ==> POST .../v1/messages (stream)` | 灰 | 流式请求调试（S01_DEBUG=1，stderr） |
| `[cron] scheduler started` | 紫 | 调度任务启动 |
| `[cron] loaded N durable job(s)` | 紫 | 启动时恢复持久化任务 |
| `[cron register] cron_XXXXXX 'cron' → prompt` | 紫 | 注册定时任务 |
| `[cron fire] cron_XXXXXX → prompt` | 紫 | 定时触发入队 |
| `[cron cancel] cron_XXXXXX` | 红 | 取消定时任务 |
| `[inject cron] prompt` | 紫 | 触发注入为 user 消息（回合内/空闲轮） |
| `[queue processor] delivering scheduled work` | 紫 | 空闲唤醒自动交付 |
| `[teammate] alice spawned as backend dev` | 青 | 队友线程启动（stderr，同 [HOOK]） |
| `[teammate] alice finished` | 绿 | 队友完成并汇报 Lead（stderr） |
| `[bus] lead → alice: please check schema` | 黄 | 收件箱消息流转（stderr） |
| `[wake: 1 inbox + 0 background -> new turn]` | 黄 | 异步唤醒轮（收件箱/后台就绪） |
| `[all teammates done]` | 绿 | 所有队友结束且输出排空 |
| `[protocol] shutdown_request → alice (req_xxxxxx)` | 紫 | 协议请求发出（stderr） |
| `[protocol] alice approved shutdown (req_xxxxxx)` | 紫 | 队友确认关机（stderr） |
| `[protocol] shutdown ✓ / plan ✗ (req_xxx: approved)` | 绿/红 | 协议状态更新（stderr） |
| `[protocol] unknown request_id: ...` | 红 | 无效 request_id（stderr） |
| `[protocol] type mismatch: expected X, got Y` | 红 | 响应类型与请求不匹配（stderr） |
| `[protocol] req_xxx already approved, ignoring duplicate` | 黄 | 重复回复被忽略（stderr） |
| `[idle] alice auto-claimed: 设计` | 绿 | 队友自动认领看板任务（stderr） |
| `[idle] alice found inbox messages` | 青 | idle 收到新消息回 WORK（stderr） |
| `[idle] alice claim failed: ...` | 黄 | 认领失败（owner 冲突等），继续轮询（stderr） |
| `[idle] alice timeout (60s)` | 红 | 60s 无新任务 → 自动关机（stderr） |
| `[protocol] alice approved shutdown in idle (req_xxx)` | 紫 | IDLE 阶段收到关机立即响应（stderr） |
| `[worktree] created: auth at ...` | 黄 | 创建 git worktree（stderr） |
| `[worktree] removed: auth` | 黄 | 移除 worktree（stderr） |
| `[worktree] kept: auth` | 青 | 保留 worktree 供审查（stderr） |
| `[bind] 任务 → worktree:auth` | 黄 | 任务绑定 worktree（stderr） |

新章节的输出标记落地后追加到本表。

## 5. 已知行为与注意事项

1. **从 rust/ 目录跑** → 技能注册表为空（`load_skill` 只会回 `(no skills loaded)`），
   `.memory/` 和 workspace 也都变成 rust/ 子目录。永远从根目录跑。
2. **Gate 3 在管道输入下默认拒绝**：`echo y | cargo run ...` 这种自动化测试里，
   确认行读到 EOF 按拒绝处理，不会误放行。
3. **记忆提取有门控**：只在用户消息含偏好信号词（记住/偏好/喜欢/讨厌/以后/总是/
   从不/不要/remember/prefer/always/never）或用户输入超 200 字符时才提取——普通查询轮
   零提取、零 API 成本。提取输出形如 `[Memory: new N, updated M, skipped K]`
   （新增/覆盖更新/去重跳过），失败静默跳过。合并有 300 秒节流 + 阈值 20 条，
   防止"删光重写"与提取互相打架。
4. **记忆写入是 best-effort**：磁盘/权限错误被静默吞掉（教学取舍，代码有注释说明）。
5. **超时语义**：bash 120s 超时；HTTP 总超时 300s、连接超时 10s。
   超时会**杀整个进程组**（包括后台孙进程，不会留孤儿）。
6. **错误恢复只包主循环**：429/529 退避重试、max_tokens 升级/续写、prompt_too_long 的
   reactive compact 只作用于主循环的 LLM 调用；记忆选择/提取、历史摘要、子代理等内部
   辅助调用维持单次直调（教学版范围）。恢复状态是 agent_loop 局部变量，每回合独立。
   升级只升一次（当前上限 → 64000）、续写最多 3 次、reactive compact 只试一次——
   超过即放弃，把 `[Error]` 写进历史当回复展示（不弹掉用户输入）。
   重试上限 10 次；`FALLBACK_MODEL_ID` 未配置时 529 纯靠重试硬扛。
7. **内部辅助调用有独立 token 预算**（s08 起）：摘要 2000 / 记忆选择 200 / 提取 800 /
   合并 3000，且不传 system——与 MAX_TOKENS 主循环预算解耦。否则 `MAX_TOKENS=300`
   实测时摘要被无声截断，压缩后目标丢失、模型答非所问（2025-08 实测教训）。
8. `S01_DEBUG` 这个环境变量名是历史沿袭（从 s01 一路复制未改名），对后续章节同样生效。
9. **任务系统**：`.tasks/` 在 `.gitignore` 里（运行时产物不入库）；任务 ID 有随机后缀但
   并发创建仍有极小碰撞概率（教学版不处理，Python 同）；claim/complete 对不存在的
   任务返回 `Error: Task {id} not found`（Python 会直接崩溃，Rust 更防御）；
   owner 恒为 "agent"，多 agent 认领是 s15 的内容。
10. **s13 异步与并发**：主循环是 tokio 多线程 runtime，但 REPL 的 stdin 读入是异步
   等待，不占 worker；同步工具 handler 走 `spawn_blocking`（阻塞池），bash 120s 超时
   语义不变（超时杀整个进程组）。后台任务状态在进程内存里（`BACKGROUND_TASKS`），
   退出即丢——与 `.tasks/` 磁盘持久化不同（那是 s12 任务系统的跨会话语义）。
   流式输出下 `[Error]` 写历史的路径不变，但**已流式打印过的文本不会重复打印**
   （main 里有去重标记）。
11. **慢词启发式是词边界匹配**（s13 审计修复）：`is_slow_operation` 只命中独立单词，
    `makeCtx`/`makefile`/`uninstall`/`rebuild` 等**子串不再被误丢后台**（实测教训：
    某次 mock 脚本里的 JS 函数名 `makeCtx` 含 "make"，语法检查命令被朴素子串匹配
    送进后台——模型一脸困惑，但后台机制本身照常工作，结果经 `<task_notification>`
    送了回来）。代价：复合词（`cargo buildx` 等）不命中，模型可用
    `run_in_background=true` 显式指定。
12. **cron 调度（s14）**：调度在 Agent 进程内——进程关闭调度即停，durable 只保任务
    定义跨重启（需要"进程关闭也定时跑"请用系统 crontab）。`LAST_FIRED` 是内存态：
    重启后当前分钟命中会立即触发一次（预期行为）。时间按本地时区解释；
    `MAX_JOBS=50` 上限；非法表达式在注册/加载两处被拒（不会拖垮调度）。
    `.scheduled_tasks.json` 是运行时产物（已入 .gitignore）。
    唤醒信号只在队列**空→非空转变**时发送一次，主循环会**排空积压信号**——
    回合中途触发不会造成 `s14 >> ` 提示符刷屏（2026-08 实测修复）。
    bash 子进程 stdin 显式关闭（EOF）：读 stdin 的命令（`cat`/交互程序）立即返回,
    不会挂起 agent 等终端输入（2026-08 实测修复；s14 起生效,s01–s13 为冻结旧行为）。
    **Gate 3 确认直读 fd 0**（`libc::read`,RawStdin）：绕开 std 全局 stdin 锁——
    REPL 的 tokio stdin 后台读线程持锁等待输入时,`io::stdin().lock()` 会阻塞,
    定时轮里任何工具都会卡到按 Enter（2026-08 实测修复）。代价：Gate 3 询问
    期间与 REPL 输入等待者并存,极端情况下首个 y/n 可能被 REPL 吃掉,
    再按一次即可（默认拒绝兜底）。
    **发送前配对清理**（`sanitize_tool_pairs`）：cron 注入的纯文本 user 消息
    会让压缩管线（auto compact 尾部保留）的"单对配对"假设失效——tool_result
    留在尾部、对应 tool_use 被摘要进头部时,API 返回 400 `unexpected tool_use_id
    found in tool_result`（2026-08 实测修复；只清理发送副本,不污染历史）。
    压缩阈值按 deepseek-v4-flash（V4 家族 1M 上下文）调大：L4 摘要默认
    300K 字符（≈10 万 token），`CONTEXT_LIMIT` 环境变量可覆盖（128K 网关勿超
    ~350K）；L1 120 条 / L2 保留 8 个结果 / L3 单结果 100K 落盘（2026-08 调整）。
    前三层 0 API,频繁触发属正常,不必担心。
    cron 单测共享 `CRON_JOBS` 等静态状态：并行执行时 `cron_reset_state` 互相
    清状态,偶发失败,`--test-threads=1` 稳定（与 s07 `SKILL_REGISTRY` 竞态同类）。
13. **团队（s15）**：收件箱是文件（`.mailboxes/*.jsonl`），进程退出即残留——
    下次启动 Lead 会读到上次的消息（教学版不清理，Python 同）；收件箱读写无锁
    （read+unlink 竞态可接受，教学取舍；真实 CC 用 proper-lockfile）。
    队友上限 10 轮（`MAX_TEAMMATE_ROUNDS`），回合窗口 20 条（对齐 Python
    `messages[-20:]`）；LLM 错误时队友打印一行错误后退出（Python 静默退出）。
    **队友工具不触发权限 hook**：Gate 3 需 stdin 交互，后台队友任务不可行
    （真实 CC 用权限冒泡，s16 引入）；Lead 侧 send_message/check_inbox 走正常
    主循环管线（含 hook）。**agent 名校验**（黑名单，≤64 字节，拒绝 `/ \ . :` 空格与控制字符，中文允许）：
    `../` 类名字被拒——Python 教学版 `to="../x"` 可把消息写到 `.mailboxes/` 之外
    （Rust 前向修复）。队友的 LLM 调用复用 s11 错误恢复（退避/重试），比 Python
    的裸调用更防御。唤醒条件 = `bus_peek("lead") || has_pending_background()`，
    与 cron 唤醒共用"排空积压信号"防御，回合中途的多个唤醒合并为一次注入。
    队友标记（`[teammate]`/`[teammate:{name}]`/`[bus]`）统一走 **stderr**（对齐
    [HOOK] 惯例）——队友线程与 Lead 流式输出共用 stdout 会互相插入（实测交错
    教训），`2>log.txt` 可单独收集诊断、`1>reply.txt` 拿到干净的模型回复。
    `ACTIVE_TEAMMATES` 静态与 cron 静态同类：并行测试偶发竞争，`--test-threads=1` 稳定。
1.  **协议（s16）**：`PENDING_REQUESTS` 是内存态（不落盘，重启即失，对齐
    Python）；队友 idle 无轮数上限（靠 shutdown 协议退出，不再 10 轮即死）；
    执行门控未实现——`submit_plan` 后队友仍可调 bash/write（教学版靠模型
    自觉等待审批，对齐 Python 注释）；消息 JSON 新增 `metadata` 字段（旧消息
    经 `#[serde(default="default_metadata")]` 归一为空对象，`Value::Default`
    是 Null 必须归一）；`[protocol]`/`[bus]` 标记走 stderr；`PENDING_REQUESTS`
    静态与 cron/ACTIVE_TEAMMATES 同类：协议测试用**唯一 request_id + 只查自己记录**
    （不做全局 len/is_empty 断言），并行稳健；cron 竞态仍按 `--test-threads=1` 约定。
    **Lead 盲等（实测现象，教学版未解决）**：无 `idle_notification`——Lead
    不知道队友空闲/完成，实测模型用 `bash sleep` 长轮询 + `send_message`
    催促（s17 用 idle_poll + 看板认领架构性消除；真实 CC 有 idle_notification）。
    **协议无送达回执（实测现象，教学版未解决）**：`plan_approval_response`
    自动送达队友（idle 注入），但 Lead 模型不知情，实测 `review_plan` 后模型
    又手动催信（双重通知，无害但冗余）——教学版取舍，非缺陷。
2.  **自治（s17）**：任务认领无文件锁——"读-改-写"非原子，多队友并发抢单
    靠 owner 检查兜底（对齐 Python；真实 CC 用 proper-lockfile 任务锁）；
    IDLE 阶段只特判 shutdown_request（其余消息整体注入 `<inbox>` 让模型自行
    理解，不调 handle_inbox_message，对齐 Python）；60s 超时自动关机（s16
    的无限驻留行为改变）；WORK ≤10 轮（防无限干活）；身份重注入首轮必触发
    （刚 spawn 时 messages 仅 1 条）；`[idle]` 标记走 stderr；任务板走文件系统
    （cwd 注入，测试天然并行安全），`PENDING_REQUESTS` 沿用 s16 唯一 id 模式。

16. **worktree（s18）**：必须从 **git 仓库根**启动（`git worktree add` 需要仓库
    上下文，从 rust/ 跑直接 Git error，Python 同坑）；`.worktrees/` 含 .git 文件
    （已入 .gitignore，误提交破坏仓库）；remove 默认拒绝有未提交/未推送内容的
    worktree（教学安全设计，`discard_changes=true` 显式放行）；队友 cwd 在无绑定
    时回主仓库（教学版允许，真实 CC 强制绑定）；`run_write_at` 显式越界检查
    （resolve_path 只词法折叠，队友无权限系统——实测漏洞修复，对齐 Python
    safe_path）；count 用 run_git 时需过滤 "(no output)" 占位（空输出污染
    计数，实测修复）；`[worktree]`/`[bind]` 标记走 stderr。
    **并行竞态补充**：s15 的 `has_pending_background_reflects_completed_tasks`
    （注入式）与 s13 后台生命周期测试共享 `BACKGROUND_TASKS` 全局——s18 测试集
    扩大后并行偶发竞争（collect 互相消费），同类 cron 竞态，`--test-threads=1` 稳定。
17. **MCP（s19）**：工具池在连接后的**下一轮**生效（connect_mcp 当轮执行，
    新工具下轮进 API 请求——教学时序，对齐 Python）；MCP 仅 Lead（队友工具集
    固定 8 个，线程不持有 MCP 表——类型层面隔离）；`normalize_mcp_name` 在
    mock 名上是空操作（docs/deploy/search/get_version/trigger/status 本就合法，
    规范化是真实服务器名的教学机制）；destructive 仅注解不拦截（真实 CC 需
    人工确认）；`MCP_STATE` 是内存态（重启即失，对齐 Python）；`[mcp] connected`
    走 stdout（Lead 专属，不进队友线程）；**测试用 `reset_mcp_state()` 先清后连**
    （mock 服务器名只有 docs/deploy 两个，无法用唯一名隔离，`--test-threads=1`
    下单线程确定）。
18. **综合（s20）**：`mcp__*deploy*` 工具走 Gate 3（名字含 "deploy" 即拦，
    readOnly 的 status 也被拦——Python 粗糙匹配对齐）；**管道模式必拒**（REPL
    stdin BufReader 缓冲吞掉后续管道行，RawStdin 只见 EOF，默认拒绝是安全兜底；
    交互模式输入 y 才放行）；Current time 段在缓存键外（`[cache hit]` 时仍刷新，
    同秒两次调用时间串相同属正常）；Skills catalog 恒包含（空技能
    `(no skills found)`）；transcript 只在压缩时写档（普通会话无 `.transcripts/`，
    秒级时间戳同秒压缩会覆盖，Python 同）；Python s20 内置工具恢复为 27 =
    Rust 27（池大小差异消失）；工具池组装保留事件驱动（Python 每轮组装，
    可观察行为一致）。

## 6. 故障排查

| 症状 | 原因 / 解法 |
|---|---|
| 启动报 `缺少 MODEL_ID 环境变量` | 根目录 `.env` 缺失或字段不全，对照 `.env.example` |
| API 401 / 403 | key 无效；或网关场景下误设了 `ANTHROPIC_AUTH_TOKEN`（设 BASE_URL 时会被忽略，改 API_KEY） |
| 模型回复「load_skill 找不到」 | 从 rust/ 目录启动了（技能注册表为空）；或技能名不在目录里 |
| 卡住不动 | 网关 hang：HTTP 总超时 300s 后返回错误；bash 卡死等 120s 超时 |
| 输出出现 `\x1b[3...` 乱码 | 终端不支持 ANSI 颜色（少见）；不影响功能 |
| 改动代码后行为没变 | cargo 有编译缓存，确认重新编译；`cargo clean -p <章节名>` 后重跑 |

## 7. 一键冒烟（不消耗 token）

```bash
cd <仓库>          # 仓库根目录
echo q | cargo run --quiet --manifest-path rust/Cargo.toml -p s20_comprehensive
# 期望：打印横幅 + 提示符后立即退出，退出码 0
```

## 8. 扩展指南（s20 完结）

s20 为最终章，后续不再有新章节；如需扩展按以下清单：

1. **换章节名**：第 1/7 节和顶部表格里的 `s16_team_protocols` → 新章节 crate 名（新章节必是新的累积章，所有既有测试路径原样复用）
2. **加测试路径**：在第 3 节追加 `### T16 …`（输入 / 预期观察 / 验证点），并把索引表里的 T16+ 行改成具体机制
3. **补标记**：新机制的输出标记进第 4 节速查表
4. **改已知行为**：第 5 节按需增删（例：s12 落地后按任务系统语义更新对应条目）
5. **更新数量**：顶部表格的自动化测试总数、第 2 节的期望值随 `cargo test --workspace` 实测刷新
