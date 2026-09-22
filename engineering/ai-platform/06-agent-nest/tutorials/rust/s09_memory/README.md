# s09: Memory —— 压缩会丢细节，要有一层不丢的

在 s08 基础上新增文件系统持久记忆。`.memory/` 目录下每个记忆一个 `.md` 文件，
`MEMORY.md` 做索引常驻 system prompt，内容按需注入当前 user turn。

```text
  Startup (in load_config)              Runtime (in agent_loop)
  ┌──────────────────────┐             ┌──────────────────────┐
  │ scan_skills()        │             │ load_memories()      │
  │ → SKILL_REGISTRY     │             │ → select_relevant    │
  └──────────┬───────────┘             │   (keyword matching) │
             │                         └──────────┬───────────┘
             ▼                                    │
  ┌──────────────────────┐                        ▼
  │ build_system()       │             ┌──────────────────────┐
  │ "Skills: ...         │             │ 注入 <relevant_      │
  │  Memories:           │             │ memories> 到 user    │
  │  - [pref](file.md)   │             │ turn 第一条消息前     │
  │  - [fact](proj.md)"  │             └──────────┬───────────┘
  └──────────────────────┘                        │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ s08 压缩管线          │
                                       │ budget→snip→micro     │
                                       └──────────┬───────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ call_llm → tools     │
                                       └──────────┬───────────┘
                                                  │
                                          stop_reason != tool_use
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ extract_memories()   │
                                       │ (压缩前快照)          │
                                       │ → LLM 提取新记忆     │
                                       │ → write_memory_file  │
                                       └──────────┬───────────┘
                                                  │
                                         files ≥ 10?
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ consolidate_memories │
                                       │ → LLM 合并去重       │
                                       └──────────────────────┘
```

- **`write_memory_file`**：写单个记忆文件（YAML frontmatter + body），自动调 `rebuild_index`
- **`rebuild_index`**：扫描所有 `.md` 文件，生成 `MEMORY.md` 链接列表
- **`select_relevant_memories`**：LLM 选择（精确，1 API）→ 失败回退关键词匹配
- **`load_memories`**：把选中记忆的内容注入到当前 user turn（`<relevant_memories>` 标签）
- **`extract_memories`**：每轮结束后调 LLM 从压缩前的对话快照中提取新记忆
- **`consolidate_memories`**：文件 ≥10 时调 LLM 合并去重，限制在 30 条以内
- **`build_system`**：system prompt 追加 `Memories available:\n{index}`

核心原则：**记忆不参与压缩。** 提取使用压缩前的消息快照，保证 LLM 看到完整对话。
索引常驻 system prompt（~200 tokens），内容按需注入（~500 tokens/条）。

## 相对 s08 的改动

s09 是纯增量，不删任何功能：

| s08 | s09 |
|-----|-----|
| 9 个工具 | 9 个工具（不变） |
| 无持久记忆 | `.memory/` 目录 + 8 个记忆函数 |
| system prompt 含 skill 目录 | system prompt 含 skill 目录 + memory 索引 |
| agent_loop 直调 call_llm | agent_loop 先注入记忆 → 压缩 → call_llm → 提取 |
| agent_loop 签名 4 参数 | 5 参数（+ `cwd: &Path`） |

## 运行

```bash
cargo run -p s09_memory
```

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **压缩前快照** | `extract_memories` 使用压缩前的 `messages.clone()`，保证 LLM 看到完整对话 |
| **关键词回退** | `select_relevant_memories` 先试 LLM 选择，失败自动降级为 name+description 关键词匹配 |
| **索引常驻 prompt** | `MEMORY.md` 链接列表注入 system prompt，可被 prompt cache 缓存 |
| **自动去重** | 记忆文件 ≥10 时 `consolidate_memories` 自动触发，合并去重 |
| **`extract_frontmatter_field`** | s07 的 `parse_frontmatter` 只返回 name+description，s09 需要额外提取 `type` 字段 |

## 结构

```
s09_memory/
├── Cargo.toml          # 依赖与 s08 相同
├── README.md
└── src/
    └── main.rs         # s08 全套 + 8 个记忆函数 + agent_loop 注入/提取
```

质量基线：`cargo build` 零错误、`cargo test -- --test-threads=1` 103 全部通过。

## 测试

```bash
cargo test -p s09_memory -- --test-threads=1
```

108 个测试（100 从 s08 + 8 新增，含后续记忆调优与回归修复追加）：write/read 记忆、索引重建、frontmatter 字段提取、关键词匹配空目录、提取门控、记忆去重分类、索引描述回退、tail_keep_start 尾部保留。

## 与 Python 版对比

对照 `../../python/s09_memory/code.py`。记忆文件格式、索引结构、注入/提取逻辑一一对应。差异：Rust 版保留了 s08 完整功能（9 工具 + Hook + nag + compact + skill）——Python s09 为聚焦记忆系统砍掉了这些。

| 维度 | Python 版 | Rust 版 | 说明 |
|------|-----------|---------|------|
| 提取快照 | 循环顶部（压缩前）抓 `pre_compress` | 同（压缩前快照） | 2025 审计修复：此前在压缩后取快照，占位符/摘要会污染提取输入 |
| 索引描述回退 | description 空 → body 首行 `[:80]` | 同（正文首行截 80 字符，字符安全） | 2025 审计修复：此前回退 raw 首行（`"---"`），有回归测试 |
| frontmatter 解析 | `yaml.safe_load` | `serde_yaml`（s07 修复后） | 多行 description 折叠成单行 |
| 内部 LLM token 预算 | 分级：select 200 / extract 800 / consolidate 3000 | 同（固定分级常量，不传 system） | 2025 修复：此前统一 cfg.max_tokens + 传 system，MAX_TOKENS 压小时提取/合并被无声截断 |
| 默认 name | `memory_{timestamp}` | `"memory"` | 文件名冲突时覆盖，语义等价 |
| 提取 prompt | 枚举 4 类 type + 字段 schema | 噪声调优版文案（负例清单 + 门控） | 有意分歧（记忆噪声调优，见关键设计） |

## 后续章节

| 章节 | 主题 | 在 s09 基础上增加 |
|------|------|--------------------|
| s10 | System Prompt | 运行时动态组装 prompt |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
