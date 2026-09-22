# s05: TodoWrite —— 规划工具 + nag 提醒

在 s04 的 Hook 系统上新增一个 `todo_write` 工具和 nag 提醒机制。
循环、Hook、权限管线全部不动，核心增量只有三样：

```text
  +---------+      +-------+      +---------------------+
  |  User   | ---> |  LLM  | ---> | MATCH DISPATCH      |
  | prompt  |      |       |      |  bash               |
  +---------+      +---+---+      |  read_file          |
                       ^         |  write_file         |
                       | result  |  edit_file          |
                       +---------+  glob               |
                                    todo_write ← NEW   |
                                  +---------------------+
                                        |
                         in-memory CURRENT_TODOS
                                        |
                        if rounds_since_todo >= 3:
                          inject <reminder>
```

- **`todo_write` 工具**：模型用它规划多步任务，每个 item 有 `content` + `status`（pending / in_progress / completed）。存储在内存 `CURRENT_TODOS` 中，每轮更新时格式化打印任务列表。
- **nag 提醒**：`rounds_since_todo` 计数器追踪模型连续多少轮没更新任务列表。到达 3 轮时，在 LLM 调用前注入 `<reminder>Update your todos.</reminder>` 消息，注入后计数器归零。
- **双复位点**：计数器在 nag 注入后归零（防止 spam）；模型主动调 `todo_write` 时也归零（模型规划了就不提醒）。

核心原则：**模型不需要被强制规划——但需要被提醒。提醒机制是"建议"而非"强制"，模型可以选择忽略（代价是多等 3 轮又被提醒一次）。**

## 相对 s04 的改动

s05 是纯增量，没有任何删除：

| s04 | s05 |
|-----|-----|
| 5 个工具（bash/read/write/edit/glob） | 6 个工具（+ todo_write） |
| 无任务规划机制 | `CURRENT_TODOS: Mutex<Vec<TodoItem>>` 内存状态 |
| 无监督机制 | `rounds_since_todo` 计数器 + `<reminder>` 注入 |
| system prompt: "All destructive operations require user approval." | system prompt: "Before starting any multi-step task, use todo_write to plan..." |

`agent_loop` 的增量改动：
1. 循环顶部新增 nag 注入逻辑（`rounds_since_todo >= 3` 时注入 reminder）
2. 工具分发 match 新增 `"todo_write"` 分支
3. `todo_write` 执行成功后计数器归零（第二个复位点）
4. 每轮工具调用 `rounds_since_todo += 1`

Hook 系统、5 个原有工具、权限管线、API 客户端全部不动。

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s05_todo_write
```

输入多步任务，观察模型如何用 `todo_write` 规划步骤、逐步更新状态。

可选环境变量同 s04：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **`todos: Value` 容错** | `TodoWriteInput.todos` 用 `serde_json::Value` 而非 `Vec<TodoItem>`，运行时检查是 Array 还是 String（模型有时把数组序列化成 JSON 字符串） |
| **两层校验** | 第一层 serde 反序列化校验形状（有 content？有 status？），第二层手工校验规则（status 三值之一？content 非空？），错误信息精确到索引 `todos[2]` |
| **`Mutex` 向前兼容** | `CURRENT_TODOS` 用 `Mutex<Vec<TodoItem>>` 而非 `static mut`，当前单线程零开销，s15 多 agent 场景不需要回头改 |
| **双复位点语义** | nag 注入后归零（防 spam）、`todo_write` 成功后归零（模型主动规划了）。复位放在 PreToolUse hook 之后——避免被拒工具误复位 |
| **nag 直接注入 messages** | nag 不通过 Hook 系统——它是循环内部控制逻辑，不是扩展机制。UserPromptSubmit 事件语义对不上 |
| **Hook 系统不动** | `permission_hook`、`log_hook`、`large_output_hook`、`summary_hook`、`context_inject_hook` 全部保持 s04 行为 |

## 结构

```
s05_todo_write/
├── Cargo.toml          # 依赖与 s04 相同，无新增
├── README.md
└── src/
    └── main.rs         # 1907 行：s04 全套 + todo_write 工具 + nag 提醒（~190 行新增）
```

质量基线：`cargo build` 零错误、`cargo test` 66 全部通过。

## 测试

```bash
cargo test -p s05_todo_write
```

66 个单元测试，覆盖：
- `truncate_lines` 截断边界、serde 契约模型（从 s01 携入）
- bash / read / write / edit / glob 工具 I/O（从 s02 携入）
- `resolve_path` 词法折叠（从 s03 携入）
- Gate 1/2/3 权限纯函数（从 s03 携入）
- Hook 注册与触发、短路由语义（从 s04 携入）
- permission_hook / log_hook / large_output_hook / summary_hook（从 s04 携入）
- **`todo_write` 正常流程**：有效输入 → 更新 CURRENT_TODOS → 返回 "Updated N tasks"
- **`todo_write` 字符串容错**：todos 传 JSON 字符串而非数组 → 正确解析
- **`todo_write` 非法 status**：`"done"` 被判为非法 → 错误信息含 `invalid status`
- **`todo_write` 空 content**：空字符串被拒绝 → 错误信息含 `empty content`
- **`todo_write` 非数组输入**：传 object → 错误信息含 `must be a list`
- **`TodoWriteInput` 反序列化**：serde 正常解析 JSON

## 与 Python 版对比

对照 `../../python/s05_todo_write/code.py`。工具 schema、nag 逻辑、双复位点语义一一对应，差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 全局任务列表 | `CURRENT_TODOS: list[dict]`（模块级变量，无锁） | `static CURRENT_TODOS: Mutex<Vec<TodoItem>>` |
| 参数容错 | `json.loads` → `ast.literal_eval` 回退（支持单引号） | `serde_json::from_str` 仅 JSON（不处理 Python 字面量） |
| 校验粒度 | `"content" not in t`（允许空字符串） | serde 强制要求 + 额外判空（更严格） |
| nag 注入 | 注入后 `rounds_since_todo = 0` | 同 |
| `todo_write` 复位 | `if block.name == "todo_write": rounds_since_todo = 0` | 同，语义位置一致 |
| 权限钩子 | Python s05 把 permission_hook 简化为**仅 deny-list**、删除了 large_output_hook、越界校验移入 safe_path 硬拒 | Rust 保持 s03/s04 的**完整 3 闸门** + large_output_hook | Rust 轨"只加不删"惯例：本章新增机制落地即可，不跟随 Python 版对本机制的临时简化（Python 各章为聚焦主题会裁剪旧机制，Rust 不会） |

## 后续章节

| 章节 | 主题 | 在 s05 基础上增加 |
|------|------|--------------------|
| s06 | Subagent | 独立 messages 的子 Agent |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
