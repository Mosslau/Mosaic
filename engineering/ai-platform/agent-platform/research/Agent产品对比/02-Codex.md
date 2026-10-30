# Codex 详细介绍

> 出品方：OpenAI｜形态：CLI / 桌面（Codex.app）/ IDE｜模型：GPT-5.x / Codex 系｜数据快照：2026-08，参数以官方文档为准
> 
> 一句话：OpenAI 的编码 Agent——**沙箱安全** + **会话可重放** + **Goal 跨会话追踪**是其三大差异化。

---

## 1. 定位与形态

Codex 是 OpenAI 的编码 Agent，与 Claude Code 同赛道但设计取向不同：**安全边界和可重放性优先**。默认跑在沙箱里、每次会话可 checkpoint 回滚、目标跨会话持续追踪。

- CLI + 桌面应用（`codex` 命令 / Codex.app）
- 会话管理自动化（状态落盘 SQLite）
- 与 IDE 集成；支持多 Agent 并行

## 2. 沙箱模型（核心安全设计）

Codex 默认运行在 **workspace-write 沙箱**中：

| 操作 | 权限 |
|:--|:--|
| 读取项目文件 | 始终允许 |
| 写入项目文件 | 仅限 `writable_roots` 内 |
| 写入系统目录 | 需用户批准 |
| 网络访问 | 默认受限，需 `require_escalated` 升级 |
| Shell 命令 | 在沙箱内执行 |
| GUI 操作 | 通过 Computer Use（计算机使用） |

**设计含义**：循环的边界由沙箱强制，而非靠模型自觉——Agent 再怎么"自由"，也出不了沙箱；敏感操作必须显式升级权限。这是"把安全放进运行时"而非"靠提示词约束"的范本。

## 3. 工具系统（Tool Calling）

| 类别 | 工具示例 |
|:--|:--|
| 文件 I/O | Read、Write、Edit（apply_patch） |
| Shell | exec_command（带沙箱控制） |
| 交互 | write_stdin（向运行中的进程输入） |
| 搜索 | rg（ripgrep）、find、glob |
| 图像 | view_image（查看图片）、image_gen（生成图片） |
| 计划 | **update_plan**（创建/更新任务计划） |
| 目标 | **create_goal / update_goal / get_goal** |
| MCP | 任意 MCP 工具（如 codegraph_explore） |
| 用户输入 | request_user_input（Plan 模式下多选问答） |

注意工具清单里 **plan（计划）与 goal（目标）是一等公民**——循环不只是"调用工具"，而是"有计划地调用工具、朝着目标迭代"。

## 4. 会话与 Goal 系统（跨会话循环）

Codex 自动管理会话状态：

| 存储 | 内容 |
|:--|:--|
| `~/.codex/state_5.sqlite` | 会话状态 |
| `~/.codex/history.jsonl` | 历史记录 |
| `~/.codex/archived_sessions/` | 已归档会话 |
| `~/.codex/goals_1.sqlite` | **Goal 追踪** |

**Goal 系统**是 Codex 与 Claude Code 的关键分野：
- 每个 goal 带 **token 预算** 与完成状态
- 跨会话持续追踪——新会话 `get_goal` 恢复目标继续迭代
- 预算耗尽 = 硬停止条件
- 与 Claude Code 的 `/resume`（恢复对话上下文）是不同用途的机制

> 这正是 Loop Engineering 的实践形态：目标持久化 + 预算边界 + 跨会话续跑。

### 4.1 Goal 生命周期机制

```
create_goal(目标, token预算) → goals_1.sqlite 持久化
    ↓ 每次会话
get_goal(id) → 恢复目标 + 已耗预算 + 完成状态
    ↓ 迭代执行
update_goal(id, 进度) → 更新状态/预算消耗
    ↓ 判定
预算耗尽 → 强制停止（hard stop）｜目标完成 → 标记 done
```

**机制要点**：goal 是"跨会话循环的状态载体"——模型上下文可以丢，goal 不丢；**token 预算是硬边界**（不是建议值），超预算强制停止，这是企业成本可控的关键设计；goal 与 checkpoint 配合：checkpoint 保"会话内可回退"，goal 保"会话间可续跑"。

### 4.2 Checkpoint 重放机制

会话按**分段（segment）**自动落盘快照，构成"任意一步可复现"的调试基础设施：

```text
会话执行 → 每段生成 checkpoint 快照（模型输入 + 工具调用 + 结果 + 上下文状态）
  → 重放: 从指定分段重建完整上下文再继续（复盘"模型当时看到了什么"）
  → 回滚: 丢弃该分段之后的所有执行（错了从断点重来）
```

**机制要点**：与 Goal 系统配合形成两层恢复能力（同 4.1）——**checkpoint 保"会话内可回退"，goal 保"会话间可续跑"**；这使"任意一步可复现"，是调试循环的黑盒终结者。

## 5. AGENTS.md：项目记忆

与 CLAUDE.md 同构的项目规范文件（`AGENTS.md`），编写原则：

- ✅ 写：项目定位、目录架构、技术栈主线、构建命令、文档规范、Codex 自定义配置（Agent/Command/Skill/MCP/Hook/Plugin 声明）
- ❌ 不写：模糊指令、一次性上下文、会过时的细节

## 6. 配置系统（config.toml）

```toml
# === 模型配置 ===      # 默认模型、推理努力级别
# === Provider 定义 ===  # 多 Provider 接入
# === 插件 ===           # 启用插件
# === 市场 ===           # skills 市场
# === 项目信任 ===        # 可信项目列表
# === 桌面 ===            # 桌面应用偏好
```

## 7. Skills / Plugins / Agents 子代理

- **Skills**：与 Claude Code 同构的三级渐进加载（Discovery → Activation → Execution），SKILL.md 含 `About` / `Workflow` / `Rules`；系统内置多个 Skills（含 imagegen），社区 Skills 可通过 skill-installer 安装
- **Plugins**：插件系统（文档、表格、演示等能力插件化）
- **Agents 子代理系统**：独立上下文运行子循环，支持并行（多 Agent 同时干活）

## 8. 可重放与调试

- 会话 checkpoint 落盘 → 任何一步可回滚 / 重放
- history.jsonl 完整记录 → 出问题可追溯"模型看到了什么、调了什么工具"
- 可重放是"调试 Agent 循环"的关键基础设施：不可重放的循环 = 黑盒

## 9. Agent Loop 设计

```text
（沙箱内）
用户目标 → update_plan 建计划 → 模型推理 → 工具调用（沙箱权限判定：writable_roots / require_escalated / 审批）
  → 结果回填 → 更新 plan → 继续（并行 agent 可同时跑多个子循环）
  → 会话结束 → checkpoint 落盘（state_5.sqlite / history.jsonl）
（跨会话）
create_goal（带 token 预算）→ 新会话 get_goal 恢复目标 → 继续迭代 → 预算耗尽或完成
```

**设计特征**：
- 循环边界靠**沙箱**（安全）而非模型自觉；approval 策略（auto-approve / ask）是执行闸门
- **plan 工具**让循环"有计划"（update_plan 追踪任务进度）
- **goal 工具**让循环"跨会话"（目标 + 预算 + 完成状态持久化）
- **checkpoint/replay**：任何一步可回滚重放，调试成本显著低于黑盒循环
- 并行子代理：多个循环同时跑，主循环汇总

## 10. 优劣势与适合场景

**优势**：沙箱安全模型最严格；goal 跨会话 + token 预算（企业成本可控）；checkpoint 可重放（可审计）；工具系统完整（plan/goal 一等公民）。

**劣势**：闭源订阅；模型绑定 OpenAI；沙箱对某些任务（需系统级操作）有摩擦；生态成熟度略逊 Claude Code 的 hooks 体系。

**适合**：OpenAI 生态重度用户；对沙箱隔离、可重放、跨会话目标追踪、成本预算有要求的企业场景。

**相关阅读**：机制与循环对比见 [../AgentLoop演进与设计/02-横向对比.md](../AgentLoop演进与设计/02-横向对比.md)。
