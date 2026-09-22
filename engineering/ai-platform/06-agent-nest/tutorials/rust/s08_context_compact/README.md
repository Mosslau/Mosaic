# s08: Context Compact —— 上下文总会满，要有办法腾地方

在 s07 基础上新增四层压缩管线 + `compact` 工具。
预处理在每次 LLM 调用前执行：便宜的 0-API 压缩先跑，贵的 1-API 摘要后跑。

```text
  messages[]
       │
       ▼
  ┌──────────────────────┐
  │ tool_result_budget   │  L3: 大结果落盘（>30KB → 文件）
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ snip_compact         │  L1: 消息 >50 条裁中间（头3+尾47）
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ micro_compact        │  L2: 旧 tool_result → 占位符
  └──────────┬───────────┘
             │
             ▼
       ┌───────────┐
       │ estimate  │ > CONTEXT_LIMIT?
       └─────┬─────┘
             │
        ┌────┴────┐
       Yes        No
        │           │
        ▼           ▼
  ┌──────────┐  ┌──────────┐
  │ L4:      │  │ call_llm │
  │ compact  │  └────┬─────┘
  │ _history │       │
  │ (1 API)  │  ┌────┴────┐
  └──────────┘  │prompt_too│
                │ _long?   │
                └────┬─────┘
                     │
                ┌────┴────┐
               Yes        No
                │           │
                ▼           ▼
          ┌──────────┐  ┌──────────┐
          │reactive  │  │ execute  │
          │_compact  │  │ tools    │
          │(1 API)   │  └──────────┘
          └──────────┘
```

- **L3 `tool_result_budget`**：最新一条消息中 tool_result 总大小超 200KB 时，按大小降序逐个将 >30KB 的结果落盘到 `.task_outputs/tool-results/`，原地替换为路径引用。
- **L1 `snip_compact`**：消息 >50 条时保留头部 3 + 尾部 47，中间裁掉。保护 tool_use/tool_result 配对不被拆散。
- **L2 `micro_compact`**：超过最近 3 个的旧 tool_result 内容替换为 `[Earlier tool result compacted]` 占位符。
- **L4 `compact_history`**：前三层后仍超 `CONTEXT_LIMIT`(50KB) 时，调 LLM 对全部历史做摘要，替换为 `[Compacted]` 消息。
- **应急 `reactive_compact`**：API 返回 `prompt_too_long` 时保留尾部 5 条原始消息，其余用 LLM 摘要替换。
- **`compact` 工具**：模型可以主动调用，立即触发 L4 摘要并 break 当前工具执行循环。

核心原则：**便宜的先跑，贵的后跑。** L1-L3 是 0 API 的纯文本操作，L4 和 reactive 才花 1 个 API 调用。

## 相对 s07 的改动

s08 是纯增量，不删任何功能：

| s07 | s08 |
|-----|-----|
| 8 个工具 | 9 个工具（+ compact） |
| agent_loop 直接调 call_llm | agent_loop 前插四层预处理 + try/except 包裹 |
| 无压缩 | 5 个压缩函数 + 3 个辅助函数 |
| 无 compact 工具 | compact 立即摘要 + break 本轮 |

## 运行

```bash
cargo run -p s08_context_compact
```

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **执行顺序** | L3 → L1 → L2 → L4。L3 必须在 L2 之前——L2 会替换旧结果内容，L3 需要在那之前落盘 |
| **try/except 包裹 API** | `call_llm` 外层 `loop { match { Ok → break, Err → reactive → retry } }`，最多重试 1 次 |
| **compact break 路径** | 立即摘要 → break for 循环 → 直接 continue 外层 loop。不追加 tool_result（摘要已替换全部消息，旧 tool_use_id 不存在，追加会导致 API 400） |
| **保留 s07 全部功能** | Hook、权限、子代理、nag、todo_write、skill loading 全部不变 |

## 测试

```bash
cargo test -p s08_context_compact
```

100 个测试（86 从 s07 + 14 新增，含审计回归追加）：compact 反序列化、estimate_size、message_has_tool_use、is_tool_result_message、snip_compact 裁剪/不变、micro_compact 占位/保留、tail_keep_start 尾部保留（修复回归）。

## 与 Python 版对比

对照 `../../python/s08_context_compact/code.py`。四层管线、compact 工具、reactive 应急一一对应。差异：Rust 版保留了 s07 的完整 Hook 系统（4 事件 + 5 内置 Hook）、nag reminder、完整 DENY_LIST（7 条）——Python s08 为教学聚焦砍掉了这些。

低影响差异（2025 审计记录，不修代码）：

| 维度 | Python 版 | Rust 版 | 影响 |
|------|-----------|---------|------|
| `summarize_history` 调用 | 不传 system，max_tokens=2000 | 传 `cfg.system`（技能目录），max_tokens=8000 | 摘要预算更大、多带一份目录，语义等价 |
| 会话存档 | `.transcripts/*.jsonl`（逐行 JSON） | `.transcripts/*.json`（pretty 数组） | 格式不同，用途相同（崩溃后回溯） |
| L1 占位文案 | `[snipped N messages]` | `[snipped N messages from conversation middle]` | 文案超集，模型所见含义相同 |
| 空摘要回退 | `(empty summary)` 兜底 | 无兜底（错误走 `(summary failed: ...)`） | 摘要为空时替换消息为空串，罕见 |
| compact_history | 全量替换（单条摘要） | **老历史摘要 + 保留尾部最近 5 条** | 2025 实测修复：全量替换会让当前回合的请求与文件正文随压缩蒸发，"继续"接不上当前工作（Rust 轨改进前移，CC 真实实现同此模式） |
| summarize_history 调用 | 不传 system，max_tokens=2000 | 同（不传 system + 固定 2000） | 2025 修复：此前传 system + cfg.max_tokens，MAX_TOKENS 压小时摘要被无声截断 |
