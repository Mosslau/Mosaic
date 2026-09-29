# s07: Skill Loading —— 用到的时候才加载，别全塞 prompt 里

在 s06 基础上新增 `load_skill` 工具 + 启动时 skill 目录扫描。
两层注入设计：

```text
  Startup                         Runtime
  ┌──────────┐                   ┌──────────────────┐
  │ skills/  │                   │  Agent calls     │
  │  agent-builder/SKILL.md      │  load_skill(     │
  │  code-review/SKILL.md        │    "code-review") │
  │  mcp-builder/SKILL.md  ──→   │        │         │
  │  pdf/SKILL.md                │        ▼         │
  └────┬─────┘                   │  SKILL_REGISTRY  │
       │ scan_skills()            │  HashMap lookup  │
       ▼                          │        │         │
  ┌──────────────┐               │        ▼         │
  │ SKILL_REGISTRY│              │  full SKILL.md   │
  │ name+desc+    │              │  via tool_result │
  │ content       │              │  (~2000 tokens)  │
  └──────┬───────┘               └──────────────────┘
         │ build_system()
         ▼
  ┌──────────────────────────────┐
  │ SYSTEM prompt:               │
  │ "Skills available:           │
  │  - **agent-builder**: ...    │  ← Layer 1: cheap
  │  - **code-review**: ...      │    always present
  │  - **mcp-builder**: ...      │    ~100 tokens/skill
  │  - **pdf**: ..."             │
  └──────────────────────────────┘
```

- **`load_skill` 工具**：Agent 按名称加载完整 SKILL.md 内容。从 `SKILL_REGISTRY` HashMap 查询——启动时已将所有合法 SKILL.md 读进内存，无文件 I/O、无路径穿越风险。
- **启动时扫描**：`scan_skills()` 扫描 `skills/` 目录，解析每个 SKILL.md 的 YAML frontmatter，提取 `name` 和 `description`，存入 `SKILL_REGISTRY`。
- **动态 system prompt**：`build_system()` 根据扫描结果组装 system prompt，包含完整的 skill 目录。替代 s06 的静态 `format!` 字符串。
- **子代理不加载技能**：`sub_tools()` 仍是 5 个基础工具，`sub_system` 不注入 skill 目录。

核心原则：**知识按需加载，不堆满上下文。** 6500 行文档不塞进 system prompt，Agent 看到"我有哪些技能"的目录（~400 tokens），需要时才调 `load_skill` 拿完整内容。

## 相对 s06 的改动

| s06 | s07 |
|-----|-----|
| 7 个工具 | 8 个工具（+ load_skill） |
| 静态 system prompt（`format!`） | 动态 system prompt（`build_system()` + skill 目录） |
| 无 skill 机制 | `SKILL_REGISTRY: Mutex<Option<HashMap<...>>>` 内存注册表 |
| 无 YAML 解析 | `parse_frontmatter()` 解析 SKILL.md frontmatter |
| 无 `serde_yaml` 依赖 | 新增 `serde_yaml = "0.9"`（frontmatter 完整解析，失败回退手工逐行） |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s07_skill_loading
```

启动时会扫描 `../skills/` 目录，system prompt 自动包含 skill 目录。

可选环境变量同 s06：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG`。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **两层注入** | Layer1: system prompt 目录（便宜，每轮都带）。Layer2: tool_result 完整内容（贵，按需） |
| **启动时扫描** | `scan_skills()` 在 `load_config()` 中调用，保证 system prompt 在首次 LLM 调用前已包含目录 |
| **单路径** | `skills/` 相对于 cwd（即 `rust/skills/`），skills 目录已复制到 rust/ 下 |
| **内存查询** | `load_skill` 从 `SKILL_REGISTRY` HashMap 查询，不读文件系统——无路径穿越 |
| **`Mutex<Option<HashMap>>`** | 和 `CURRENT_TODOS` 模式一致。`None` = 未扫描，`Some` = 已填充 |
| **YAML frontmatter** | 手工解析 `name:` / `description:` 字段（简单可靠），不依赖完整 YAML 解析器 |
| **子代理无 skill** | `sub_tools()` 不加 `load_skill`，`sub_system` 不含目录 |

## 结构

```
s07_skill_loading/
├── Cargo.toml          # +serde_yaml
├── README.md
└── src/
    └── main.rs         # s06 全套 + SKILL_REGISTRY + scan/parse/list/build/load
```

质量基线：`cargo build` 零错误零警告、`cargo test` 83 全部通过。

## 测试

```bash
cargo test -p s07_skill_loading
```

86 个单元测试，覆盖：
- 基础工具 / 权限管线 / Hook 系统 / 子代理 / todo_write（从 s06 携入，77 个）
- **`parse_frontmatter`**：有效 YAML、无分隔符、空 frontmatter、仅 name（4 个）
- **`load_skill`**：找到返回内容、未找到返回错误（2 个）
- **`LoadSkillInput` 反序列化**（1 个）
- **`list_skills`**：返回排序后的目录字符串（1 个）

## 与 Python 版对比

对照 `../../python/s07_skill_loading/code.py`。两层注入、启动扫描、内存查询一一对应，差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| YAML 解析 | `yaml.safe_load()` | `serde_yaml` 完整解析；解析失败回退手工逐行 | 2025 审计修复：此前手工 `strip_prefix` 会把多行 `description: \|` 解析成 `"\|"`（agent-builder 实际受害），有回归测试 `parse_frontmatter_multiline_description`。多行描述折叠成单行（目录一行一个技能） |
| 注册表类型 | `dict[str, dict]` | `Mutex<Option<HashMap<String, SkillInfo>>>` |
| skills 路径 | `WORKDIR / "skills"`（cwd = 仓库根） | `cwd.join("skills")`（skills 在 rust/ 下） |
| system prompt | `build_system()` 模块级调用 | `build_system()` 在 `load_config()` 中调用 |

## 后续章节

| 章节 | 主题 | 在 s07 基础上增加 |
|------|------|--------------------|
| s08 | Context Compact | 四层上下文压缩管线 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
