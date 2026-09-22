# Claude Code 详细介绍

> 出品方：Anthropic｜形态：CLI / 桌面｜模型：Claude 系（Sonnet / Opus）｜数据快照：2026-08，参数以官方文档为准
> 
> 一句话：终端里的编码 Agent——让 Claude 直接在你的代码库中读文件、改代码、跑命令、查资料，并持续迭代直到任务完成。

---

## 1. 定位与形态

Claude Code 是 2025 年引爆"Agentic Coding"浪潮的鼻祖产品：不再是你问一句、模型答一句，而是**把代码库交给 Agent**，让它自主完成从理解到修改到验证的完整循环。

- **CLI**：原生二进制（macOS / Linux / WSL）/ Homebrew / WinGet
- **管道模式**：`claude -p "query"` 单次执行，可接 stdin/stdout 做 CI 集成（审查 PR diff、生成 commit message、JSON 结构化输出、流式 JSON）
- **精简模式**：`claude --bare -p "query"` 跳过 hooks/skills/MCP/CLAUDE.md 自动发现（CI 推荐）
- **桌面应用**：额外提供 /schedule 持久化定时任务

## 2. 配置系统

| 层级 | 内容 |
|:--|:--|
| 项目级 | `CLAUDE.md`（项目规范）、`.claude/` 目录（skills、agents、commands、hooks） |
| 用户级 | `~/.claude/settings.json`（权限、hooks、模型偏好） |
| 优先级 | 项目配置 > 用户配置（更具体者生效） |

**settings.json 核心**：
- **权限匹配语法**：`allow` / `deny` / `ask` 三档，按工具 + 路径模式匹配（如 `Bash(npm run *)`），危险操作弹人工确认
- **hooks**：注册生命周期脚本（见第 4 节）
- 模型与温度、上下文预算等偏好

## 3. CLAUDE.md：项目记忆

项目根目录的 CLAUDE.md 是"每会话自动注入的项目规范"——它是四款产品中"项目记忆"概念的标准形态：

```text
# 项目定位
# 技术栈主线          # 告诉 Agent 用什么
# 目录架构
# 构建/测试/运行命令   # 关键：让 Agent 能自己验证
# 编码规范与约束       # 不要做什么
# 常用工作流          # 回答问题、改 bug、加功能各怎么走
```

**要点**：命令必须给全（Agent 才能自验证）；约束要精确（不要模糊）；按需更新（文档漂移是最大的坑）。

## 4. Hooks：17 个生命周期事件

Hooks 是在关键生命周期事件自动执行的脚本/HTTP 请求/LLM 判断——**确定性控制**，不依赖模型理解，直接阻止或修改行为。

| 事件 | 触发时机 | 可阻止 |
|:--|:--|:--|
| **SessionStart** / **SessionEnd** | 会话开始/结束 | — |
| **UserPromptSubmit** | 用户提交提示词后 | — |
| **PreToolUse** | 工具执行前 | ✅ |
| **PostToolUse** / **PostToolUseFailure** | 工具执行成功/失败后 | — |
| **PermissionRequest** | 显示权限对话框时 | — |
| **Notification** | 发送通知时 | — |
| **SubagentStart** / **SubagentStop** | 子代理启动/停止 | — |
| **TeammateIdle** | 团队成员空闲 | — |
| **TaskCompleted** | 任务完成 | — |
| **ConfigChange** | 配置文件变更 | — |
| **PreCompact** | 上下文压缩前 | — |
| **Stop** | Claude 响应完成时 | — |
| **WorktreeCreate** / **WorktreeRemove** | 建立/删除 worktree | — |

**4 种 Handler 类型**：

| 类型 | 说明 | 示例 |
|:--|:--|:--|
| command | 执行 Shell 脚本 | 自动格式化、安全扫描 |
| http | 发送 HTTP POST | 团队审计、外部通知 |
| prompt | LLM 判断（是/否） | 内容审查、意图检测 |
| agent | 子代理验证 | 复杂验证逻辑 |

Hook 执行时自动注入环境变量（事件名、工具名、工作目录、输入输出等）。⚠️ Hook 匹配器要精确——`".*"` 会拖慢所有交互。

### 4.1 Hook 配置实例（JSON）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash(npm *)",
        "hooks": [{
          "type": "command",
          "command": "scripts/check-npm-publish.sh",
          "timeout": 30
        }]
      },
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "prompt",
          "prompt": "这个文件修改是否涉及生产配置？只回答 yes/no",
          "decision": "block"
        }]
      }
    ],
    "PostToolUse": [{
      "matcher": "Bash(pytest*)",
      "hooks": [{
        "type": "agent",
        "agent": "verify-fix",
        "timeout": 120
      }]
    }]
  }
}
```

**机制要点**：matcher 精确匹配工具+参数（`".*"` 会拖慢所有交互）；`command` 同步阻塞、`prompt` 交给 LLM 判定（可 block）、`agent` 派子代理验证——三种 handler 覆盖"确定性脚本 → 语义判断 → 复杂验证"的完整拦截谱系。

## 5. Skills：三级渐进加载

### 5.1 激活匹配机制

```
Discovery(会话启动): 只读 name + description，零成本
    ↓ description 命中当前任务（关键词/意图匹配）
Activation: 加载完整 SKILL.md（workflow/rules）
    ↓ 任务执行
Execution: 按 SKILL.md 执行，可运行附带脚本
```

**机制要点**：三级加载的本质是 **token 惰性分配**——description 是"索引"，SKILL.md 是"内容"，只有任务命中索引才付内容成本；description 写得好坏直接决定激活准确率（写得泛 → 误激活；写得窄 → 漏激活）。

Skill = 一个目录（SKILL.md + 可选脚本/参考资料），把领域知识封装为 AI 可加载模块：

1. **Discovery**：会话启动只加载 skill 名称 + 描述（最小 token 开销）
2. **Activation**：任务匹配时才读取完整 SKILL.md
3. **Execution**：按指令执行，可选运行附带脚本

SKILL.md 格式：`name` / `description`（触发条件写清楚）/ `workflow` / `rules`。项目级放 `.claude/skills/`，用户级放 `~/.claude/skills/`。

## 6. 子代理（Subagents）

写代码的与检查代码的分离——自己不批自己作业：

- 主 Agent 把子任务委派给 Subagent，Subagent 在独立上下文里跑子循环
- SubagentStart / SubagentStop hooks 可拦截启停
- 适合：代码审查、独立验证、并行探索

## 7. 自主循环：/loop 与 /schedule

```bash
/loop 15m babysit all my PRs. Auto-fix build issues   # 每 15 分钟
/loop 3h scan error logs, identify fixable bugs, create PRs
```

| 特性 | /loop (CLI) | /schedule (Desktop) |
|:--|:--|:--|
| 持久化 | 终端关闭即消失 | 跨重启存活 |
| 最大时长 | 3 天 | 无限制 |
| 限制 | 最多 50 任务/会话，内置 jitter（最多延迟 10% 间隔） | — |
| 适用 | 部署监控、PR 轮询 | 每日简报、周报 |

另有 `CronCreate` 工具支持程序化建定时任务（如 `"cron": "0 9 * * 1-5"`）。

## 8. 上下文压缩

长会话上下文会膨胀——`/compact` 把对话压缩为摘要释放 token；`PreCompact` hook 可在压缩前拦截（如先导出关键信息）。

## 9. MCP 与 Plugins

- **MCP**：通过 `claude mcp add` 接入外部工具服务器（stdio / SSE），让 Agent 获得"看和操作外部系统"的能力
- **Plugins**：把 Skills / Agents / Hooks / MCP 打包为可分享、可安装的单元（`.claude-plugin`），官方插件目录 `anthropics/claude-plugins-official` 是发现中枢

## 10. Agent Loop 设计

```text
用户指令
  → 上下文组装（CLAUDE.md + Skills 渐进加载 + 历史记忆）
  → [UserPromptSubmit hook]
  → 模型推理（Claude）
  → 工具调用 ──[PreToolUse hook: 可阻止]──> 执行 ──[PostToolUse/PostToolUseFailure hook]──> 结果回填
  → 模型继续推理（循环）……直到任务完成 / /compact 压缩 / 权限拦截 / 预算耗尽
  → [Stop hook] → [SessionEnd hook]
```

**设计特征**：
- **循环归属模型（自由），控制点归属 hooks（确定性）**——17 个事件覆盖工具调用前后、权限请求、压缩前、子代理启停、任务完成、worktree 生命周期
- 子代理循环：主 Agent 委派 Subagent 独立跑子循环
- /loop、/schedule 把循环从"单次会话内"延伸到"定时自驱动"
- **会话恢复与状态**：`/resume` 恢复中断会话（读过的文件、做过的分析），`/status` 查看会话状态——跨会话能力的事实源（README/05/AgentLoop02 均引用）
- 停止条件靠：任务完成判定 + 权限拦截 + /compact 兜底 + 会话级超时

## 11. 优劣势与适合场景

**优势**：hooks 控制粒度最细（17 事件 × 4 handler）；生态成熟（skills/plugins/MCP）；CLAUDE.md 项目记忆范式成为行业标准；CLI 管道化适合 CI。

**劣势**：闭源订阅；模型绑定 Claude；跨会话目标追踪弱于 Codex 的 goal 系统；企业级治理（多租户/审计）需自建。

**适合**：个人/资深开发者深度编码；CI 自动化（--bare 管道）；需要细粒度行为控制的团队。

**相关阅读**：机制与循环对比见 [../AgentLoop演进与设计/02-横向对比.md](../AgentLoop演进与设计/02-横向对比.md)。
