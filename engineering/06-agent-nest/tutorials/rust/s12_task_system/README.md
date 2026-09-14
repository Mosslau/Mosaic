# s12: Task System — 目标太大，拆成小任务

在 s11 基础上新增文件持久化的任务图。s01–s11 全部机制保留（错误恢复/权限/
Hook/压缩/记忆/技能/子代理照旧），只叠加任务系统。

```text
  Agent loop: dispatch
                  │
                  ▼
  ┌──────────────────────────────┐
  │ MATCH DISPATCH (14 tools)    │
  │  ...9 old tools              │
  │  create_task        <- NEW   │
  │  list_tasks         <- NEW   │
  │  get_task           <- NEW   │
  │  claim_task         <- NEW   │
  │  complete_task      <- NEW   │
  └───────────────┬──────────────┘
                  │
                  ▼
  ┌──────────────────────────────┐
  │ .tasks/ {id}.json            │
  │  Task { id, subject,         │
  │    description, status,      │
  │    owner, blockedBy }        │
  └───────────────┬──────────────┘
                  │
                  ▼
   状态机:
    pending --claim--> in_progress    （依赖全部 completed 才能认领）
    in_progress --complete--> completed
    completed --> 报告解禁的下游任务
    can_start: 依赖缺失或未完成 = 阻塞
```

- **`Task`**：serde 结构体，磁盘 JSON 与 Python `asdict` 输出逐字段同构
  （`blockedBy` 用 `#[serde(rename)]` 保持 camelCase，`owner: Option` → null）
- **`tasks_dir` / `task_path` / `save_task` / `load_task` / `list_tasks`**：
  `.tasks/{id}.json` 的 CRUD，全部以 `cwd` 为根（同记忆系统模式，测试可注入临时目录）
- **`new_task_id`**：`task_{unix秒}_{0000-9999 随机}`（rand crate，对齐 Python 格式）
- **`can_start`**：所有 blockedBy 必须存在且 completed；缺失依赖视为阻塞
- **`blocked_deps`**：未满足依赖列表，供 "Blocked by" 文案复用
- **`claim_task` / `complete_task`**：状态机 + 解禁报告（`Unblocked: ...`）
- **5 个工具**：create_task / list_tasks / get_task / claim_task / complete_task，
  `all_tools()` 9 → 14；子代理工具集不变（5 个，不给任务工具）

## 相对 s11 的改动

| s11 | s12 |
|-----|-----|
| 14 章机制全量（错误恢复为最新） | 全部保留 + 任务系统 |
| 无任务概念（只有 s05 会话内存 todo） | `.tasks/` 持久任务图 + blockedBy 依赖 |
| 9 个工具 | 14 个工具（+5 任务工具） |
| `update_context` 列出 9 工具 | 自动列出 14 工具（prompt 无需改代码） |

## 运行

```bash
cargo run -p s12_task_system
```

```text
s12 >> 用任务系统拆解"做一个小网站"：先建 3 个有依赖的任务
```

观察 `.tasks/` 目录：

```bash
ls .tasks/          # task_*.json
cat .tasks/任务.json  # id/subject/description/status/owner/blockedBy
```

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **磁盘格式对齐 Python** | `blockedBy` camelCase、`owner: null`、pretty JSON——两个轨道读写的文件可直接互换 |
| **缺失依赖 = 阻塞** | `can_start` 对不存在的依赖返回 false（对齐 Python：missing deps are blocked） |
| **解禁报告** | complete 时扫描 pending 且依赖现全部满足的下游任务，输出 `Unblocked: ...` 引导模型继续 |
| **owner 恒为 "agent"** | 多 agent 认领语义是 s15 队友线程的内容，s12 只保留字段 |
| **子代理无任务工具** | 任务系统是父代理的协调层；子代理专注执行，不参与任务图 |
| **比 Python 更防御** | Python 对不存在的任务 claim/complete 直接抛异常崩溃；Rust 返回 `Error: Task {id} not found` |

## 结构

```
s12_task_system/
├── Cargo.toml         # s11 依赖全集（无新增；rand 复用）
├── README.md
└── src/
    └── main.rs        # s11 全套 + Task/CRUD/依赖判定/5 工具
```

## 测试

```bash
cargo test -p s12_task_system -- --test-threads=1
```

145 测试（131 从 s11 + 14 新增）：ID 格式、字段往返、磁盘 JSON 与 Python schema 同构、
create 输入反序列化、排序与空列表、依赖语义（缺失/未完成/完成）、blocked_deps 过滤、
claim 状态机（成功/阻塞文案/错误状态/未知 ID）、complete 状态机 + 下游解禁报告、
三任务依赖链端到端（阻塞 → 逐个解禁 → 全 completed → 重启后仍在）。

## 与 Python 版对比

对照 `../../python/s12_task_system/code.py`。Task 字段、JSON 格式、ID 格式、状态机、
输出文案（`Created ...` / `Blocked by: ['...']` / `Unblocked: ...` / 图标 ○●✓）
一一对应。差异：

- **承载机制**：Rust 版保留 s11 完整功能（错误恢复 + 9 工具 + Hook + 压缩 + 记忆 +
  技能 + 子代理）——Python s12 为聚焦任务系统砍掉了这些（其 README 明说）
- **不存在的任务**：Python claim/complete 抛 FileNotFoundError 崩溃；Rust 返回
  `Error: Task {id} not found`（更防御）

## 后续章节

| 章节 | 主题 | 在 s12 基础上增加 |
|------|------|--------------------|
| s13 | Async & Concurrency | 后台任务 + 流式输出 + 并行工具执行 |
| s14 | Cron Scheduler | 定时调度线程 |
| s15 | Agent Teams | 队友线程来认领 .tasks/ 里的任务 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
