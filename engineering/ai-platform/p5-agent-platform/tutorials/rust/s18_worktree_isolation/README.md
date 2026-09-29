# s18: Worktree Isolation — 各干各的，互不干扰

在 s17 基础上新增工作区隔离：**Task 绑定 git worktree + 队友 worktree cwd 上下文**。
每个任务在自己的 `.worktrees/{name}` 目录干活（独立分支 `wt/{name}`），
互不覆盖主仓库文件。s01–s17 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理/cron/团队/协议/自治 照旧）。

```text
 ┌───────────────────────────────────────────────┐
 │ WORK（≤10 轮 LLM）                              │
 │  身份重注入 → inbox 分发 → LLM → 工具执行        │
 │  （认领 worktree 任务后 cwd = .worktrees/{name}）│
 └───────────────┬───────────────────────────────┘
                 │ stop_reason != tool_use
                 ▼
 ┌───────────────────────────────────────────────┐
 │ IDLE（12×5s = 60s）                             │
 │  ① inbox 优先：shutdown_request → 响应退出       │
 │  ② 任务板：未认领 → claim(自己) → 回 WORK        │
 │     （绑定 worktree 的任务附带 Work directory）  │
 │  ③ 60s 无新工作 → SHUTDOWN                      │
 └───────────────┬───────────────────────────────┘
                 │ shutdown / timeout
                 ▼
 ┌───────────────────────────────────────────────┐
 │ SHUTDOWN：summary → lead、移除、finished         │
 └───────────────────────────────────────────────┘
```

## 工作区拓扑

```text
 ┌─────────────────────────────────────────────────────┐
 │ Main repo（AgentNest/，运行 cwd）                   │
 │                                                     │
 │  .worktrees/（工作区，队友在此干活）                │
 │    ├─ auth/  (branch: wt/auth)   ← Task #1          │
 │    ├─ ui/    (branch: wt/ui)      ← Task #2         │
 │    └─ events.jsonl  ← 生命周期事件日志              │
 │                                                     │
 │  .tasks/（任务板，与队友 cwd 分离）                 │
 │    └─ task_xxx.json (worktree: "auth")  ← 绑定关系  │
 └─────────────────────────────────────────────────────┘
```

## 核心机制

### 1. Worktree 系统（3 个 Lead 工具）

| 工具 | 行为 |
|------|------|
| `create_worktree(name, task_id="")` | 校验名（`[A-Za-z0-9._-]{1,64}`，拒 `../` 穿越）→ `git worktree add -b wt/{name} HEAD` → 可选绑定任务 → 事件日志 |
| `remove_worktree(name, discard_changes=false)` | **有未提交变更/未推送提交时拒绝**（提示 keep 或 discard）；discard 强制移除 + 删分支 |
| `keep_worktree(name)` | 保留供人工 review（分支不动），记录事件 |

- `bind_task_to_worktree`：只写任务 `worktree` 字段，**保持 pending**（供队友自动认领）
- 事件日志：`.worktrees/events.jsonl`（create/remove/keep + task_id + ts）

### 2. 队友 worktree cwd 上下文（s18 核心）

- 队友维护 `wt_path` 状态：**认领绑定 worktree 的任务 → cwd 切换到 `.worktrees/{name}`；complete 后重置回主仓库**
- 工具执行：bash/read/write 在 `wt_path` 下运行（无绑定时用主仓库）
- **write 越界拒绝**：`../` 逃出 worktree 被拦（`Error: Path escapes workspace`）——队友无权限系统兜底，这是隔离语义的底线
- auto-claimed 注入带 `\nWork directory: {path}`，模型知道该去哪干活

## 相对 s17 的改动

| s17 | s18 |
|-----|-----|
| 所有队友在主仓库干活（互相覆盖，s17 实测 bob 改过主 README） | 每任务独立 worktree，互不干扰 |
| Task 无 worktree 字段 | Task 加 `worktree: Option<String>`（磁盘兼容旧任务） |
| 队友 cwd 固定主仓库 | `wt_path` 状态机：claim 设置 / complete 重置 / idle 认领设置 |
| 队友 bash/read/write 走 execute_sync（workdir） | `run_bash_at/run_read_at/run_write_at` 参数化（主循环路径不变） |
| Lead 工具 23 个 | **26 个**（+ create_worktree / remove_worktree / keep_worktree） |
| list_tasks 无 worktree 标注 | 行格式带 `(wt:{name})` 后缀 |
| — | `.worktrees/events.jsonl` 生命周期审计 |

## 运行

```bash
# ⚠️ 必须从 git 仓库根启动（AgentNest/）——git worktree 命令需要仓库上下文
cd /Users/ninebot/code/mosslau/AgentNest
cargo run --manifest-path rust/Cargo.toml -p s18_worktree_isolation
```

**核心验证**：`Create 2 tasks and 2 worktrees (create_worktree auth, ui; bind them to the tasks), then spawn alice and bob. Watch them work in their own directories.`

预期观察：
- `[worktree] created: auth at .../.worktrees/auth`（黄）→ `[bind] 任务 → worktree:auth`（黄）
- 队友认领后：`[teammate:alice] write_file: Wrote ... .worktrees/auth/...`——**cwd 在 worktree 内**
- 两个队友各写各的目录，互不覆盖
- `list_tasks` 行格式带 `(wt:auth)` / `(wt:ui)`
- `remove_worktree` 有未提交变更时拒绝（教学安全设计）

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **名称白名单** | `[A-Za-z0-9._-]{1,64}`——拒 `../` 路径穿越与非法字符（worktree 名直接拼路径，安全底线） |
| **bind 保持 pending** | 绑定只写字段不改变状态——任务仍待认领，队友认领后自动切目录 |
| **write 越界拒绝** | 队友的 read/write 显式 `is_within_workspace` 检查——resolve_path 只做词法折叠，而队友无权限系统（Gate 2/3 只在主循环），必须代码层兜底 |
| **变更保护** | `remove_worktree` 默认拒绝删除有未提交/未推送内容的工作区——防误删成果；`discard_changes` 显式放行 |
| **事件日志** | create/remove/keep 全记录（`.worktrees/events.jsonl`）——工作区生命周期可审计 |
| **主循环零改动** | `run_bash_at/run_read_at/run_write_at` 抽出，原函数转发 workdir——execute_sync 主循环路径不变（冻结惯例） |
| **cwd 状态机** | claim（成功）→ 切目录；complete → 重置；idle 自动认领 → 按任务绑定切目录 |

## 结构

```
s18_worktree_isolation/
├── Cargo.toml          # s17 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 9388 行：s17 全套 + Worktree Isolation（~590 行净增）
```

## 测试

```bash
cargo test -p s18_worktree_isolation -- --test-threads=1
```

250 个单元测试（234 从 s17 携入 + 16 新增），覆盖：
- `validate_worktree_name`：空/`.`/`..`/斜杠/空格/中文/超 64 拒绝；合法名放行
- **真实 git 生命周期**（临时仓库 git init + commit）：create（目录/分支/事件日志）、重名拒绝、
  非法名拒绝、remove 有变更拒绝 / discard 强制 / 不存在、keep 事件记录
- `count_worktree_changes`：干净 (0,0) / 写文件后 (≥1,0)（含 run_git 空输出占位过滤）
- `bind_task_to_worktree`：写字段 + 保持 pending；`resolve_task_worktree` 路径解析
- 隔离语义：`run_write_at` 越界（`../` 逃出 worktree）拒绝；`run_bash_at` 在指定 cwd 执行
- idle 自动认领绑定 worktree 的任务：返回任务 id + 注入含 `Work directory:`
- system prompt 含 worktree 提示、工具输入 serde（task_id/discard_changes 可选）

## 与 Python 版对比

对照 `../../python/s18_worktree_isolation/code.py`。名称校验规则、git 命令语义、
bind 保持 pending、remove 变更保护文案、事件日志格式、`[worktree]`/`[bind]` 标记颜色、
队友 cwd 状态机（claim 设置/complete 重置/idle 认领）——逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | 17 工具简化栈 | **26 工具全量**（s01–s17 全部机制照旧） |
| 名称校验 | `re.compile` | 字符遍历 + 长度（等效语义，无 regex 依赖） |
| git 调用 | `subprocess.run` 30s 超时 | `Command` + `wait_timeout`（run_bash 既有模式）+ 双管道读取 |
| **write 越界** | `safe_path(p, cwd)` 抛异常 | **显式 `is_within_workspace` 检查**（resolve_path 不查边界——队友无权限系统，必须代码层兜底，实测漏洞修复） |
| count 实现 | 独立 subprocess（无占位） | run_git 复用 + **"(no output)" 占位过滤**（空输出被占位污染的实测修复） |
| 输出通道 | print stdout | `[worktree]`/`[bind]` 走 stderr（轨道惯例） |
| **system prompt（前移）** | 无"创建文件"指示（实测队友探索而非创建） | + `Create new files in your work directory as needed.`——实测闭环改进 |
| 单元测试 | 无 | 16 个新增（含真实 git 生命周期测试——Python 不可测的） |

## 已知行为（TEST.md 注意事项同步）

- **必须从 git 仓库根启动**：`git worktree add` 需要仓库上下文——从 `rust/` 跑会直接
  `Git error`（Python 同坑）；`.worktrees/` 已入 .gitignore（含 .git 文件，误提交破坏仓库）；
- **remove 变更保护**：有未提交/未推送内容时拒绝删除（教学安全设计）——需 `discard_changes=true`
  显式放行，或 `keep_worktree` 保留审查；
- **队友 cwd 在 worktree 外仍可用**：无绑定时回主仓库（resolve 到主仓库 base）——
  教学版允许，真实 CC 强制 teammate 绑定；
- **bash 无路径沙箱**：隔离只约束 read/write（显式越界检查）——bash 在 worktree
  cwd 里可 `cd ..` / 绝对路径访问任意位置（Python 同，shell 自由；教学取舍）；
- **队友可能探索而非创建（实测现象，Rust 已前移缓解）**：worktree 是主仓库的
  完整 checkout，队友认领后可能"找文件"（读 docs/、.git、events.jsonl）而非
  创建新文件——实测 30+ 轮 bash 探索后 60s 超时退出，任务残留 in_progress
  （Python 同；与 s16"重构认证模块"探索循环同类）。**Rust 前移**：system prompt
  加 `Create new files in your work directory as needed.`（Python 无此句）；
  残余场景：任务描述建议明确"创建新文件 schema.sql"而非"写 schema.sql"；
- **`[worktree]`/`[bind]` 标记走 stderr**（轨道惯例）；
- **并行测试竞态**：worktree 测试用临时 git 仓库（cwd 注入，天然并行安全）；
  仅 s14 cron 继承竞态按 `--test-threads=1` 约定。

## 后续章节

| 章节 | 主题 | 在 s18 基础上增加 |
|------|------|--------------------|
| s19 | MCP Plugin | 外部工具接入同一工具池 |
| s20 | Comprehensive | 完整集成示例 |
