# s20: Comprehensive Agent — 全部机制，归到一个循环

s01–s19 全部机制在**同一个 agent_loop** 里协同：工具/权限/Hooks/规划/子代理/
技能/压缩(含 transcript 留底)/记忆/prompt 组装/错误恢复/任务图/后台·流式·
并行/cron/团队/协议/自治/worktree/MCP。对齐 Python s20 的综合集成：
**MCP 工具接入权限管线**（`mcp__*deploy*` 走 Gate 3 确认）、**Current time 段**
（缓存键外拼接，命中缓存也刷新）、**Skills catalog 恒包含段**、transcript 落盘
对齐 `.jsonl` 格式。

```text
 ┌─────────────────────────────────────────────────────────────────┐
 │ REPL（s20 >> ）                                                   │
 └───────────────────────────┬─────────────────────────────────────┘
                             ▼ 每轮 agent_loop
 ┌─────────────────────────────────────────────────────────────────┐
 │ ① cron 到期注入（s14）→ ② 后台通知注入（s13）→ ③ nag 提醒（s05）   │
 │ ④ 压缩管线 L1-L4（s08，含 write_transcript 落盘）                  │
 │ ⑤ update_context + get_system_prompt（s10，缓存 + Current time）  │
 │ ⑥ call_llm 流式（s13）+ 错误恢复（s11：升级/续写/reactive）        │
 │ ⑦ 工具执行：compact 特判 → PreToolUse 权限（s03/s04，              │
 │    含 mcp__*deploy* Gate 3）→ 后台判定（s13）→ dispatch_tool      │
 │    （s19：MCP 表 → execute_sync）→ PostToolUse → todo 复位         │
 │ ⑧ connect_mcp 后重组装动态池（s19）                                │
 └─────────────────────────────────────────────────────────────────┘
```

## 核心机制（s20 集成点）

### 1. MCP 工具接入权限管线（s19"仅注解" → s20"注解+拦截"）

- `check_rules` 新增臂：工具名 `mcp__` 前缀且**包含 `deploy`** → Gate 3 用户确认
- 对齐 Python 的粗糙匹配：`mcp__deploy__status`（readOnly）也会被拦——教学取舍
- 队友无 MCP 工具，天然不触发；Gate 3 复用 s03 RawStdin 确认路径

### 2. Current time 段（缓存键外拼接）

- system prompt 末尾追加 `Current time: {YYYY-MM-DDTHH:MM:SS}`（对齐 Python 的
  `isoformat(timespec='seconds')`）
- **设计坑**：时间若进 PromptContext 缓存键 → 每秒变化 → 缓存永远 miss。
  s20 方案：`append_current_time` 在 `get_system_prompt` 层拼接（缓存存前缀，
  命中时拼此刻时间）——**缓存保留且时间始终新鲜**

### 3. Skills catalog 恒包含段

- 措辞对齐 Python：`Skills catalog:\n{...}\nUse load_skill(name) when a skill is relevant.`
- 无条件包含（空技能时 `list_skills` 返回 `(no skills found)`，无空段）
- 段顺序对齐 Python：identity → tools → workspace → skills → memory → MCP

### 4. transcript 对齐（s08 已有，s20 对齐格式）

- `write_transcript` → `.transcripts/transcript_{ts}.jsonl`（**每行一条消息**，
  对齐 Python jsonl；s08 原为整数组 pretty JSON）
- compact 打印对齐：`[compact] transcript saved: {path}`（青）/
  `[reactive compact] transcript saved: {path}`（红）
- 保留 s08 前移：压缩保留尾部 5 条（Python 全量替换——Rust 更优，记录差异）

### 5. 收敛点：Python 27 内置 = Rust 27 内置

Python s20 把 s12+ 删掉的工具全部恢复（edit/glob/todo_write/task/load_skill/
compact/cron），内置工具集与 Rust 长期保留的 27 个**完全一致**——s19 的
"18 vs 27 池大小差异"在 s20 消失（27/29/31 两边相同）。

## 相对 s19 的改动

| s19 | s20 |
|-----|-----|
| MCP destructive 仅注解不拦截 | `mcp__*deploy*` 走 Gate 3 用户确认（权限管线接入） |
| system prompt 无时间段 | `Current time:` 段（缓存键外，命中也刷新） |
| skills 段条件包含 + 旧措辞 | **恒包含** + Python 措辞（Skills catalog / Use load_skill） |
| transcript 整数组 pretty JSON | `.jsonl` 每行一条消息 + 对齐的 compact 标记 |
| 段顺序 workspace → mcp → skills → memory | 对齐 Python：workspace → skills → memory → mcp |

## 运行

```bash
cd /Users/ninebot/code/mosslau/AgentNest   # 仓库根（git 上下文 + .mcp.json 候选链）
cargo run --manifest-path rust/Cargo.toml -p s20_comprehensive
```

**核心验证**：
`Connect to the deploy MCP server and check the status of service "api".`

预期观察：
- `[mcp] connected: deploy → ['trigger', 'status']`（红）
- 模型调 `mcp__deploy__status` → **`⚠ MCP destructive-looking tool` + `Allow? [y/N]`**
  （Gate 3 拦截）→ y 放行 → `[deploy] api: running (v1.4.2)`；n/EOF → `Blocked by user`
- system prompt 带 `Current time:` 段（`[assembled]` 时可见，缓存命中时也刷新）
- 压缩触发时 `[compact] transcript saved: .transcripts/transcript_*.jsonl`

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **MCP 进权限管线** | s19 的注解只是教学提示；s20 把 MCP 工具纳入既有 Gate 2/3——综合章"所有机制协同"的落点 |
| **时间在缓存键外** | 时间若进 PromptContext 缓存键，缓存每秒失效；前缀缓存 + 命中时拼接时间——保留 s10 缓存前移且时间新鲜 |
| **Skills 恒包含** | Python s20 无条件给目录——模型始终知道技能存在；空目录给 `(no skills found)` 占位 |
| **transcript 只加不改** | 写档挂点 s08 已有（compact/reactive 入口），s20 只对齐格式与标记——冻结惯例 |
| **保留 Rust 超集** | memory 提取管线/流式/词边界启发式/尾部保留/事件驱动池——均为行为等价或更优，逐一记录 |
| **每轮组装决策** | Python 每轮 `assemble_tool_pool()`；Rust 保留事件驱动（connect_mcp 后重组装）——可观察行为一致，省每轮克隆 |

## 结构

```
s20_comprehensive/
├── Cargo.toml          # s19 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 10470 行：s01–s19 全量 + 综合集成（+125 行净增 + 5 测试）
../.mcp.json            # MCP 服务器配置（docs/deploy，s19 起共享）
.transcripts/           # 会话转录（压缩前落盘，已入 .gitignore）
```

## 测试

```bash
cargo test -p s20_comprehensive -- --test-threads=1
```

285 个单元测试（280 从 s19 携入 + 5 新增），覆盖：
- `check_rules`：`mcp__deploy__trigger`/`mcp__deploy__status` 命中 Gate 2；
  `mcp__docs__search`/普通 bash 放行
- `check_permission`（Cursor 注入）：y 放行 / n → `Blocked by user` / 非 deploy 不问
- Current time 段：格式 `YYYY-MM-DDTHH:MM:SS`（19 字符）、缓存命中路径也带时间
- `write_transcript`：`.jsonl` 扩展名、每行合法 JSON、消息数与行数一致
- Skills catalog 恒包含：空技能 `(no skills found)` 段仍出现
- 继承 280 全绿（含 s19 的 MCP 全套 + s08 压缩管线 + s18 真实 git 生命周期）

## 与 Python 版对比

对照 `../../python/s20_comprehensive/code.py`。MCP 权限拦截（name 含 "deploy" 粗糙匹配）、
Current time 段、Skills catalog 措辞、transcript jsonl 格式与 compact 标记、
段顺序——逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 内置工具 | 27（s20 恢复 edit/glob/todo/task/skill/cron） | **27**（长期保留，收敛一致） |
| prompt 缓存 | 无（每轮重建） | **保留** + Current time 缓存键外拼接（更优） |
| compact 保留 | 全量替换为摘要 | **尾部 5 条保留**（s08 实测修复，更优） |
| memory | 只注入 MEMORY.md 索引（提取管线已删） | **s09 全管线保留**（超集） |
| 工具池组装 | 每轮 assemble_tool_pool | 事件驱动（connect_mcp 后重组装，行为一致） |
| 流式 | 无 | **SSE 流式**（s13 前移） |
| 队友打印 | terminal_print 线程抑制 | **stderr 惯例**（s15，更早解决） |
| 回合串行 | agent_lock | 单线程 REPL + tokio（天然串行） |
| 摘要输出 | `[Compacted]\n\n{summary}` | 同（保留尾部后同样式） |
| 单元测试 | 无 | 285 个（5 新增 + 280 继承） |

## 已知行为（TEST.md 注意事项同步）

- **MCP deploy 需要确认**：`mcp__deploy__trigger` 和 `mcp__deploy__status`（粗糙匹配）
  都会触发 Gate 3；管道输入 EOF 按拒绝处理（默认拒绝）；队友无 MCP 不触发；
- **Current time 在缓存键外**：`[cache hit]` 时时间段仍刷新（同秒内两次调用
  时间字符串相同属正常）；assemble_system_prompt 纯函数不含时间（可测）；
- **transcript 是压缩副产品**：只在 compact/reactive_compact 时写档——普通会话
  不产生 `.transcripts/`；秒级时间戳同秒两次压缩会覆盖同名文件（Python 同）；
- **skills 段恒包含**：空技能显示 `(no skills found)`（Python 同措辞）；
- **27 = 27 收敛**：s19 记录的"18 vs 27 池差异"在 s20 消失（Python 恢复了工具）；
- **每轮组装 vs 事件驱动**：池内容可观察一致；事件驱动省每次全表克隆；
- **并行测试竞态**：仅 s14 cron 继承竞态按 `--test-threads=1` 约定（同前各章）。

## 完结

s20 是 Rust 轨道的最终章——s01–s20 全部落地：
**98,014 行 / 2,775 测试**（含 example 24）。Python 参考轨道的全部机制均已对齐，
Rust 前移改进（缓存、流式、stderr 惯例、尾部保留、配置驱动等）逐一记录在
各章 README 的对比表中。
