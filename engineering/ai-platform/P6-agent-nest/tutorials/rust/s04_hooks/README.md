# s04: Hooks —— 挂在循环上，不写进循环里

在 s03 的权限管线基础上，把硬编码的权限检查抽成 Hook 回调机制，
循环只负责触发事件，扩展逻辑全部挂在事件上：

```text
  User types query
       │
       ▼
  ┌──────────────────┐
  │ UserPromptSubmit │ ── trigger_hooks() before LLM
  └────────┬─────────┘
           ▼
  ┌────────────┐     ┌─────────────────────────────┐
  │  messages  │────▶│  LLM (stop_reason=tool_use?)│
  └────────────┘     │   No ──▶ Stop hooks ──▶ exit │
                     │   Yes ──▶ tool_use block ──┐ │
                     └────────────────────────────┘ │
                                                    ▼
                                          ┌──────────────────┐
                                          │ PreToolUse hooks │
                                          │  permission_hook │
                                          │  log_hook        │
                                          └───────┬──────────┘
                                                  │ (not blocked)
                                          ┌───────▼──────────┐
                                          │ TOOL_HANDLERS[x] │
                                          └───────┬──────────┘
                                                  │
                                          ┌───────▼──────────┐
                                          │ PostToolUse hooks│
                                          │  large_output    │
                                          └───────┬──────────┘
                                                  │
                                          results ──▶ back to messages
```

- **PreToolUse hooks**：工具执行前触发，短路由语义（第一个返回 `Some(...)` 的 hook 决定拦截结果，后续不执行）。内置 `permission_hook`（承载 s03 的三道闸门）+ `log_hook`（旁路日志）。
- **PostToolUse hooks**：工具执行后触发，同样短路。内置 `large_output_hook`（输出超阈值时提示模型使用 read_file 而非依赖截断输出）。
- **UserPromptSubmit hooks**：用户提交输入后、LLM 调用前触发，用于上下文注入。内置 `context_inject_hook`。
- **Stop hooks**：LLM 返回 `end_turn` 时触发，用于摘要等收尾工作。内置 `summary_hook`（统计工具调用次数）。

核心原则：**循环不知道权限、不知道日志、不知道输出截断 —— 它只知道在适当的时机触发 Hook，其余都是外部注入的。**

## 相对 s03 的删改

Hook 系统不是纯新增，而是把 s03 硬编码的权限管线**迁移**到 Hook 回调：

| s03 的做法 | s04 的做法 |
|-----------|-----------|
| `agent_loop` 直接调用 `check_permission()`（硬编码） | `agent_loop` 调用 `trigger_pre_tool_use()`，权限逻辑在注册的 `permission_hook` 中 |
| `run_bash` 内无黑名单（s03 已移到 Gate 1） | `run_bash` 同样无黑名单，权限完全在 hook 层 |
| 权限函数散落在主文件 | 权限纯函数保留（`check_deny_list` / `check_rules` / `decide` / `check_permission`），供 `permission_hook` 复用和测试 |
| 无 hook 机制 | 4 组事件 × 各自回调 Vec，闭包短路由 |

`agent_loop` 的实质改动：`check_permission()` 调用 → `trigger_pre_tool_use()` 调用。执行前/后、请求前/后各插入 hook 触发点。

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s04_hooks
```

工具触发前会走 hook 管线，有风险的操作用户会看到询问提示。

可选环境变量同 s03：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **Hook 注册表** | `Hooks` 结构体含 4 个 `Vec<Box<dyn Fn(...)>>`，回调在 `register_builtin_hooks()` 中注册 |
| **短路由语义** | `trigger_pre_tool_use()` / `trigger_stop()` 等遍历回调，第一个 `Some(...)` 立即返回，后续不执行 |
| **闭包动态分发** | 使用 `Box<dyn Fn(...)>` trait object，无泛型——简单直观，教学场景首选 |
| **权限纯函数保留** | s03 的 `check_deny_list` / `check_rules` / `decide` / `check_permission` 完整保留为独立纯函数，`permission_hook` 只做薄封装注入 `stdin` |
| **stdin 依赖注入** | Gate 3 读输入仍走 `&mut impl BufRead` 参数，测试喂 `Cursor` 模拟键盘 |
| **Hook 可扩展** | 新增 hook 只需：写回调函数 → `hooks.pre_tool_use.push(Box::new(...))`，循环代码零改动 |
| **"Blocked by permission gate."** | 被拦截的工具回填此固定文案，让模型感知并调整策略——而非 `"Permission denied."`（避免模型误以为是 OS 级权限错误） |

## 结构

```
s04_hooks/
├── Cargo.toml          # 依赖与 s03 相同，无新增
├── README.md
└── src/
    └── main.rs         # 1714 行：s03 全套 + Hook 系统（~450 行新增）
```

质量基线：`cargo build` 零错误、`cargo clippy` 零警告。

## 测试

```bash
cargo test -p s04_hooks
```

60 个单元测试，覆盖：
- `truncate_lines` 截断边界、serde 契约模型（从 s01 携入）
- bash / read / write / edit / glob 工具 I/O（从 s02 携入）
- `resolve_path` 词法折叠（从 s03 携入）
- Gate 1/2/3 权限纯函数：黑名单全命中、规则匹配、y/yes 判定、EOF 拒绝（从 s03 携入）
- **Hook 注册与触发**：10 个测试覆盖 4 组事件的注册、触发、短路由语义
- **permission_hook Gate 1**：硬拒绝不依赖 stdin，直接返回拦截
- **log_hook**：始终返回 `None`（旁路，不拦截工具执行）
- **context_inject_hook**：不 panic，正常注入上下文
- **summary_hook**：正确统计 tool_result 数量
- **large_output_hook**：小输出不触发、大输出触发提示
- **回归测试**：`run_bash` 不再含内联黑名单（黑名单已移到 hook）
- **管线集成**：`check_permission` 三闸门全流程集成测试（6 个）

## 与 Python 版对比

对照 `../../python/s04_hooks/code.py`。Hook 注册结构、短路由语义、回调签名一一对应，差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| Hook 存储 | `dict[str, list[Callable]]` | `Hooks` struct 含 4 个 `Vec<Box<dyn Fn(...)>>` |
| 回调注册 | `hooks["pre_tool_use"].append(fn)` | `hooks.pre_tool_use.push(Box::new(fn))` |
| 短路由实现 | `for hook in hooks: if result := hook(...): return result` | `for hook in &hooks: if let Some(r) = hook(...) { return Some(r) }` |
| 类型安全 | 鸭子类型，回调签名靠约定 | 编译期 `Fn(...)` trait bound 强制签名 |
| 单元测试 | 无 | 58 个 |

## 后续章节

| 章节 | 主题 | 在 s04 基础上增加 |
|------|------|--------------------|
| s05 | TodoWrite | 计划工具 + reminder |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
