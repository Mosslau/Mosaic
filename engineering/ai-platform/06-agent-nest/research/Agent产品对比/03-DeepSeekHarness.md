# DeepSeek Harness（dsh）详细介绍

> 出品方：DeepSeek AI｜形态：框架（Web UI / headless / SDK）｜模型：模型无关（DeepSeek 优先）
> 
> 一句话：**"Everything is a Plugin"** 的 Agent Harness——模型适配、工具注册、会话日志、甚至 Agent Loop 本身都是插件，全部可从配置替换。
> 
> 本环境（DSH Web UI @ 127.0.0.1:3080）即运行于其上，下文架构描述来自其源码官方文档。数据快照：2026-08（dsh v0.1.1-rc.2，developer preview，会有破坏性变更）。

---

## 1. 定位与哲学

> **Everything is a Plugin**：没有需要打补丁的特权核心。你通过挂载一个插件来扩展 dsh，注册是可回退的副作用（effect），插件卸载时自动解除。

dsh 不是"给你用的编码 Agent"，而是**"用来构建 Agent 的 Harness"**——你是它的架构师。核心哲学：

底层由 [Cordis](https://github.com/cordiverse/cordis) 插件框架驱动——插件向共享上下文贡献**服务**、**类型化事件**与**可逆副作用**。设计论文：《A Programming Paradigm for Spatiotemporal Composability》。

当前状态：**developer preview**，快速迭代中（会有破坏性变更）。运行：`npx @deepseek-ai/dsh web`。

## 2. Profiles / Bundles：启动时的插件树

一个运行中的 dsh 是一棵在 boot 时按有序层组合的插件树：

| 概念 | 说明 |
|:--|:--|
| **Profile** | 命名的组合（存在 Harness home），列出叠加的 bundles、装的树外插件、用户自己的 `cordis.patch.yml`；`web` 和 `headless` 是内置模板 |
| **Bundle** | Cordis 配置行 + 代码的分发格式——插入的任何东西都可被上层 patch 覆盖 |
| **Patch** | 按行 id 替换整个配置或插入新行；层序：profile 的 bundles → profile patch → home 级 patch → `--patch` 覆盖 |

`dsh --profile web --dump-config` 可查看本机实际启动的整棵树——任何打印出来的行都可以用你自己的 patch 替换。

- `dsh-base`：每个 profile 的第一层（模型适配、工具、持久化、沙箱与审批策略、设置、凭据、遥测）
- `dsh-web-app`：加浏览器应用；`dsh-headless`：无服务器的单次运行器

## 3. 核心包（Cordis 树的关键节点）

| 包 | 职责 | ctx key |
|:--|:--|:--|
| core/session | 追加式 `SessionEvent` 日志 + 内存存储 | `ctx.sessions` |
| core/system-prompt | Prompt 分区与工具 schema 组装 | `ctx.systemPrompt` |
| core/tools | 作用域工具注册 + 护栏执行管道 | `ctx.tools` |
| core/agent | `Agent` 接口、活体注册表、`agent/*` 事件 | `ctx.agents` |
| core/agent-loop | 实现该接口的默认 driver（可替换！） | `ctx.agentLoop` |
| core/scope | 按 agent 作用域注册原语 | 库，无 key |
| llm/llm | 消息/流词汇 + 模型适配器接缝 | `ctx.llm` |

> 关键点：**loop 是可替换的**——`Agent` 接口零循环依赖，UI、hooks、编排器都对着接口编程，换 driver 不碰其他代码。

## 4. 三层事件域（扩展点设计）

| 域 | 事件 | 用途 |
|:--|:--|:--|
| **Session 事件** | `session/event`（turn/*、step/*、user/message、assistant/*、tool/*） | 持久事实，append-only，必须跨重载存活 |
| **Agent 事件** | `agent/*`（inbox、step、status、request、validation、continuation） | 活体协调：观察或拦截飞行中的工作 |
| **Capability 事件** | `fs/*`、`tools/*`、`telemetry/*` | 把策略/适配器挂到接缝，不 import loop |

**选域准则**：事实要跨重载存活 → Session 事件；要拦截飞行中的 Agent → agent/*；要给能力接缝挂策略 → capability 事件。

## 5. Turn / Step 生命周期（核心 Loop 设计）

**一个 step = 一次模型请求 + 它调用的工具；一个 turn = 零或多个 step**——turn 打开于首个输入被认领，关闭于"无欠账"。

```text
turn/start
  claim 输入（next-step 输入 + 一条排队消息）
  组装 prompt 分区 + 工具 schema
  → agent/pre-step            # waterfall：拒绝(reject) 或 进入(enter)
     · 拒绝或首个 enter 为空 → 零 step 关 turn（日志记录这次尝试）
  step/start
    输入以 user/message 追加
    从日志派生模型历史（deriveMessages）
    agent/request → llm/stream → assistant/chunk* → assistant/message
    tool/call* → tools/pre-execute → tools/execute → tools/post-execute → tool/result*
  step/end
  · 工具还欠请求，或 next-step 输入到达 → claim → 下一 step
  → agent/turn-stopping       # 串行终检点
turn/end
```

**瀑布拦截点**（监听者必须调 `next()` 委派）：`agent/pre-step`、`agent/request`、`llm/stream`、三个 `tools/*`；`agent/turn-stopping` 是串行、无 `next()`。

**pre-step 决策**：`{ kind: 'reject' }` 或 `{ kind: 'enter', messages }`——决定"模型这一步看到什么"；拒绝不保留已认领消息，插入的后续消息留给下一边界。

## 6. 事件日志：单一事实源

> 这是"可回放循环"的工程化终极形态：不是"尽力记录"，而是**架构上不可能出现日志里重建不出来的模型输入**。

- **"Model-visible means logged"**（模型可见的必须已落日志）——运行时不变式强制：任何到达模型请求的内容必须能从日志重建
- `deriveMessages()` 从日志投影模型历史；**fork、resume、transcripts、遥测、持久化全部派生自同一条流**
- `assistant/chunk` 保留原始流，保证重放与 UI 保真；`assistant/message` 记录每次成功调用（含 max-tokens 结束），空内容不进派生历史但事件保留用量与来源序列

## 7. 失败恢复与上下文压缩

- **agent/request-error** 瀑布：收到请求坐标 + 规范化失败事实 + 重试策略；监听者可返回 `{ kind: 'retry' }` 拥有恢复，否则保留原始错误
- **compaction 插件**（dsh-compaction-basic）：用 `agent/pre-step` 做上下文压力检测、用 `agent/request-error` 处理规范溢出；触发后先做工具结果剪枝，再选摘要；**剪枝或摘要推进了"代际替换"才开新重试 turn**，否则原始错误保持权威
- 恢复发生在"失败的 step 关闭之后、turn 关闭之前"的窗口

### 7.1 Cordis 插件三要素（怎么写一个插件）

| 要素 | 机制 | 示例 |
|:--|:--|:--|
| **Service** | 插件向共享上下文贡献服务（`ctx.xxx`） | `ctx.tools` 注册工具 |
| **Event** | 类型化事件，插件间解耦通信 | `agent/pre-step` 拦截 |
| **Effect** | 可逆副作用——注册在插件卸载时自动解除 | `registerTool()` 返回解绑函数 |

**机制要点**：没有特权核心——loop、工具、日志全是插件；`registrations are effects that unwind when their plugin unloads`（注册是副作用，卸载即解除）——这是"可组合性"的根基：任何插件可拔插而不留残余。

### 7.2 一个完整 turn 的事件序列（日志视角）

> 本节为 §5 生命周期的日志视图，细节以 §5 为准。

```text
turn/start                        [session/event]
  agent/inbox/claimed {message}   [agent/*]
  agent/pre-step → enter          [waterfall]
  step/start                      [session/event]
  user/message                    [session/event]
  agent/request → llm/stream      [waterfall]
  assistant/chunk*                [session/event, 原始流保真]
  assistant/message               [session/event, 记录 usage+sourceEventSeqs]
  tool/call → pre → execute → post [tools/*, waterfall]
  tool/result                     [session/event]
  step/end                        [session/event]
  agent/turn-stopping             [串行终检]
turn/end                          [session/event]
```

**机制要点**：持久事实（session/event）与活体控制（agent/*）严格分离——重放/恢复/审计读前者，实时拦截/状态读后者；`assistant/chunk` 保留原始流保证 UI 保真，`assistant/message` 的 `sourceEventSeqs` 精确指向构成它的 chunks。

## 8. Agent 生命周期

Agent 的创建、恢复与销毁由 `AgentRegistry` 管理，生命周期事件落在 `agent/*` 事件域（活体协调，非持久事实）：

- **创建/恢复**：`ctx.agents.create()` / `resume()`（加载持久化会话，重铸作用域），发布经 `SessionStore.enter()` + `AgentRegistry.enter()` 双检查，并发同 id 创建只有一个能进入，败者回滚
- **注册表**：`register` / `get` / `list` / `roots`（无属主的活体根）；运行时属主（`isOwnedBy`）与持久会话血缘独立
- **Initiator 作用域**：每个 driver 的生命周期跑在发起者边界内，并行 driver 相互隔离；`agent/created` 在作用域就绪后发一次；`agent/disposed` 保证确切离场
- **AgentHandle**：`{ agent, dispose() }`——dispose 是消费者能力，停 loop、等退出、注销、删会话、解作用域

## 9. 插件生态（packages 即能力清单）

> 与 Claude Code / Codex 的"内置 + 钩子"不同，dsh 的这些能力**全是可装卸的插件**——需要 goal 就挂 goal 插件，不需要就摘掉。

goal（目标）、plan（计划）、todo、skill、subagent、sandbox、hooks、schedule（cron）、workflow、compaction（压缩）、mcp、lsp、terminal、code-runtime、e2b、spill、workspace、jobs、guard（护栏）、acp（Agent Client Protocol 桥）、api、web、client、sdk、boot、bundle、host……

## 10. Agent Loop 设计特征

- **turn/step 两段式**：step 是最小可审计单元（一次请求+工具），turn 是有界的一组（有输入则开、无欠账则关）——粒度清晰才能谈治理
- **循环可替换**：`Agent` 接口零循环依赖，默认 driver 可整体换掉
- **事件日志单一事实源**：重放/恢复/遥测/审计同源，"model-visible means logged" 不变式
- **四位置瀑布拦截**：pre-step / request / llm-stream / tools——策略以插件挂载，不侵入核心
- **失败可恢复**：request-error 瀑布 + compaction 代际推进，重试有明确语义
- **三硬边界停止**：无进展检测 / 最大迭代 / token·预算上限，停止由代码验证而非模型自评（标准设计见 [../AgentLoop演进与设计/03-标准设计.md](../AgentLoop演进与设计/03-标准设计.md)）

## 11. 优劣势与适合场景

**优势**：唯一 MIT 完全开源可深度定制者；插件化架构（loop 可换、能力可装卸）；事件日志单一事实源（可观测性最强）；模型无关；DeepSeek 模型 prefix-cache 长会话成本优化。

**劣势**：developer preview（破坏性变更）；无开箱即用的完整 GUI 产品体验（是框架不是成品）；学习曲线陡（要懂 Cordis 概念）；生态仍在建设。

**适合**：Harness 深度定制者；需要严格可观测/可回放的企业底座；想自建 Agent 平台引擎的团队（配 [../AgentLoop演进与设计/03-标准设计.md](../AgentLoop演进与设计/03-标准设计.md) 食用最佳）。
