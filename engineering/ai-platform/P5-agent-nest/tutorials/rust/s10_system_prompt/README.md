# s10: System Prompt —— 运行时组装，不硬编码

在 s09 基础上把硬编码的 system prompt 拆成独立段落，运行时按真实状态动态组装。
四个段落（identity/tools/workspace/memory），缓存避免重复拼接。

```text
  update_context()
       │
       ▼
  ┌──────────────────────────┐
  │ PromptContext {          │
  │   tools, workspace,      │
  │   memories               │
  │ }                        │
  └──────────┬───────────────┘
             │
             ▼
  ┌──────────────────────────┐
  │ get_system_prompt(ctx)   │
  │                          │
  │  context changed?        │
  │   ┌─ Yes → assemble()    │
  │   │        → cache       │
  │   └─ No  → return cached │
  └──────────┬───────────────┘
             │
             ▼
  ┌──────────────────────────┐
  │ SYSTEM PROMPT            │
  │                          │
  │ You are a coding agent.  │
  │ Available tools: bash,   │
  │ read_file, write_file... │
  │ Working directory: /path │
  │ Relevant memories:       │
  │ - [pref](file.md)        │
  └──────────────────────────┘
```

- **`PromptContext`**：运行时上下文结构（tools + workspace + memories），`Serialize` 用于缓存 key
- **`assemble_system_prompt`**：按 context 选段落。identity/tools/workspace 始终加载，memory 按 MEMORY.md 是否存在加载
- **`get_system_prompt`**：缓存包装。`serde_json::to_string(&ctx)` 做确定性 key，context 不变时返回缓存，打印 `[cache hit]`
- **`update_context`**：从当前状态推导 context：`all_tools()` 取工具列表、cwd、`read_memory_index()`

## 相对 s09 的改动

| s09 | s10 |
|-----|-----|
| `build_system()` 静态拼接 | `assemble_system_prompt()` + `get_system_prompt()` 动态组装 + 缓存 |
| system prompt 启动时算一次 | 每轮工具执行后刷新 context，必要时重算 |
| 无 `PromptContext` | `PromptContext { tools, workspace, memories }` |

## 运行

```bash
cargo run -p s10_system_prompt
```

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **段落按需加载** | memory 段只在 MEMORY.md 存在且有内容时才加载，不是始终带 |
| **确定性缓存 key** | `serde_json::to_string` 而非 `hash()`，避免进程随机化和嵌套类型失败 |
| **真实状态判断** | 段落加载取决于磁盘文件是否存在，不是消息里的关键词 |
| **每轮刷新** | 工具执行后可能新增记忆文件，需要 `update_context` 重新检查 |

## 结构

```
s10_system_prompt/
├── Cargo.toml
├── README.md
└── src/
    └── main.rs         # s09 全套 + PromptContext + assemble/get/update
```

## 测试

```bash
cargo test -p s10_system_prompt -- --test-threads=1
```

112 测试（108 从 s09 + 4 新增，含后续修复/调优追加）：无记忆时 prompt 不含 memory 段、有记忆时含记忆内容、get_system_prompt 返回非空字符串、skills 目录集成、UTF-8 截断安全、tail_keep_start 尾部保留。

## 与 Python 版对比

对照 `../../python/s10_system_prompt/code.py`。段落结构、缓存机制、按需加载逻辑一一对应。差异：Rust 版保留 s09 完整功能（9 工具 + Hook + nag + compact + skill + 压缩 + 记忆）——Python s10 只有 3 个基础工具。

| 维度 | Python 版 | Rust 版 | 说明 |
|------|-----------|---------|------|
| identity 文案 | `You are a coding agent. Act, don't explain.` | 前加 `Do not impersonate any specific AI assistant (Claude, GPT, etc.).` | 沿自 s09 build_system，防模型扮演具体助手 |
| tools 段 | `if tools:` 条件加载 | 无条件 push | enabled_tools 恒非空，行为无差 |
| 每轮刷新 | 每轮工具执行后 `update_context` + `get_system_prompt` | 同（2025 审计修复：此前每回合只组装一次，与自己的"每轮刷新"文档不符） | 缓存保证 context 未变时不重复组装 |

## 后续章节

| 章节 | 主题 | 在 s10 基础上增加 |
|------|------|--------------------|
| s11 | Error Recovery | 错误分类恢复 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
