# s06: Subagent —— 大任务拆小，每个拿到的都是干净上下文

在 s05 基础上新增 `task` 工具，spawn 子 Agent 用全新 `messages[]` 跑独立循环。
循环、Hook、权限管线不动，增量只有子代理系统：

```text
  Parent Agent                           Subagent
  +------------------+                  +------------------+
  | messages=[...]   |                  | messages=[task]  | <-- fresh
  |                  |   dispatch       |                  |
  | tool: task       | ---------------> | own while loop   |
  |   description=...|                  |   bash/read/...  |
  |                  |   summary only   |   (max 30 turns) |
  | result = "..."   | <--------------- | return last text |
  +------------------+                  +------------------+
        ^                                      |
        |       intermediate results DISCARDED  |
        +--------------------------------------+
```

- **`task` 工具**：父 Agent 用它 spawn 子代理，参数只有 `description`。子代理跑完只返回摘要文本，中间的工具调用记录全部丢弃——上下文隔离。
- **子代理不能递归 spawn**：子代理工具集 `sub_tools()` 只有 bash/read/write/edit/glob 五个工具，**没有 `task`**（防递归）**没有 `todo_write`**（子代理不规划）。
- **30 轮安全上限**：`MAX_SUB_TURNS = 30`，超时返回摘要或回退文本。
- **子代理也走 Hook 管线**：PreToolUse（权限 + 日志）/ PostToolUse（大输出告警）在子代理的工具调用上也生效。
- **同步阻塞**：`spawn_subagent` 等待子代理完成后才返回，父循环继续处理后续工具调用。

核心原则：**子代理的价值是上下文隔离，不是并发。中间 30 轮的文件探索不会撑爆父对话，父对话的 120 条历史不会污染子代理的注意力。**

## 相对 s05 的改动

s06 是纯增量，没有删除：

| s05 | s06 |
|-----|-----|
| 6 个工具（含 todo_write） | 7 个工具（+ task） |
| 1 个 agent_loop | 2 个循环（父 agent_loop + spawn_subagent 内层循环） |
| 1 套 tools | 2 套（`all_tools()` 父 / `sub_tools()` 子） |
| 1 个 system prompt | 2 个（`system` 父 / `sub_system` 子） |
| `call_llm` 从 cfg 读 system | `call_llm` 接受 `system: &str` 参数（父传 `cfg.system`，子传 `cfg.sub_system`） |
| 无 `extract_text` | 从 content blocks 提取纯文本 |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s06_subagent
```

输入复杂任务，观察父 Agent 何时 spawn 子代理、子代理如何独立探索、只返回摘要。

可选环境变量同 s05：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **两套工具集** | `all_tools()` 7 个（父：+ task + todo_write），`sub_tools()` 5 个（子：无 task 防递归、无 todo_write） |
| **`call_llm` 参数化 system** | s06 把 `system` 从 `cfg` 字段提升为独立参数，父传 `&cfg.system`，子传 `&cfg.sub_system` |
| **子代理循环是简化版** | 无 nag 提醒、无 `rounds_since_todo`、无 `CURRENT_TODOS`。裸 for 循环 0..30 |
| **Hook 共享** | 子代理调 `trigger_pre_tool_use(hooks, ...)` 和 `trigger_post_tool_use(hooks, ...)`，权限和日志对子代理同样生效 |
| **`extract_text` 回退** | 子代理最后一条消息是 `tool_result`（无文本）时，倒查 messages 找最后一条 assistant 文本；全无为默认错误字符串 |
| **同步阻塞** | `spawn_subagent` 是普通函数调用，父循环等待子代理完成。s15 才引入并发 |

## 结构

```
s06_subagent/
├── Cargo.toml          # 依赖与 s05 相同，无新增
├── README.md
└── src/
    └── main.rs         # s05 全套 + sub_tools + extract_text + spawn_subagent + run_task
```

质量基线：`cargo build` 零错误零警告、`cargo test` 75 全部通过。

## 测试

```bash
cargo test -p s06_subagent
```

77 个单元测试，覆盖：
- `truncate_lines` / serde 契约模型 / 工具 I/O / 路径解析 / 权限管线 / Hook 系统（从 s05 携入，66 个）
- **`extract_text`**：纯字符串、Blocks 含文本、Blocks 混合 thinking、Blocks 无文本、空消息（5 个）
- **`sub_tools`**：数量 = 5、无 task、无 todo_write、有 bash（4 个）
- **`TaskInput` 反序列化**（1 个）
- **spawn_subagent 回退逻辑**：最后一条是 tool_result 时倒查 assistant 文本（1 个）

## 与 Python 版对比

对照 `../../python/s06_subagent/code.py`。子代理循环、工具集、安全上限、回退逻辑一一对应，差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 工具注册 | `TOOLS.append(task_tool)` 运行时 | `all_tools()` 数组字面量，编译期 |
| 子代理工具 | `SUB_TOOLS` 列表 | `sub_tools() -> [Tool; 5]` |
| system 切换 | 子代理直接用 `SUB_SYSTEM` 全局变量 | `call_llm` 接受 `system: &str`，父/子传不同引用 |
| Hook 共享 | 模块级 `trigger_hooks`，子代理直接调用 | `&Hooks` 引用传入 `spawn_subagent` |
| 子代理 todo_write | 无 | 无（对齐 Python） |
| 子代理 nag | 无 | 无（对齐 Python） |
| 权限钩子 | Python s06 沿 s05 简化：permission_hook 仅 deny-list、无 large_output_hook、越界由 safe_path 硬拒 | Rust 保持 s03/s04 完整 3 闸门 + large_output_hook（继承 s05 的已记录分歧） | Rust 轨"只加不删"，不跟随 Python 版裁剪 |
| 子代理 LLM 异常 | 不捕获，向上抛（父代理循环崩溃） | 捕获并返回 `Subagent error: {e}` 作为工具结果 | Rust 更防御：子代理失败不拖垮父代理 |

## 后续章节

| 章节 | 主题 | 在 s06 基础上增加 |
|------|------|--------------------|
| s07 | Skill Loading | 按需加载 skill 文件 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
