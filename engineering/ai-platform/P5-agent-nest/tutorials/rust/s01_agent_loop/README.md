# s01: Agent Loop — 一个循环就够了

AI Coding Agent 的最小核心实现。整个 agent 的秘密就在一个 `while` 循环里：

```
while stop_reason == "tool_use":
    response = LLM(messages, tools)
    execute tools
    append results
```

## 工作流程

```
+----------+      +-------+      +---------+
|   User   | ---> |  LLM  | ---> |  Tool   |
|  prompt  |      |       |      | execute |
+----------+      +---+---+      +----+----+
                      ^               |
                      |   tool_result |
                      +---------------+
                      (loop continues)
```

1. 用户输入问题，追加到消息历史
2. 全部历史 + 工具定义发给 LLM（Anthropic Messages API）
3. 模型返回 `stop_reason`：
   - `"tool_use"` → 执行 bash 命令，结果回灌历史，回到步骤 2
   - 其他 → 任务结束，输出最终回复

退出条件不看固定步数、不看关键词，完全由模型自己判断「干没干完」。

## 运行

```bash
# 1. 在仓库根目录创建 .env（参考 .env.example）
#    二选一：Anthropic 官方 API，或 Anthropic 兼容网关（DeepSeek/GLM/Kimi/MiniMax）
ANTHROPIC_API_KEY=sk-ant-...
MODEL_ID=claude-sonnet-4-6
# ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic   # 走网关时设置
# MODEL_ID=deepseek-v4-pro[1m]        # DeepSeek 的 1M 上下文变体就是模型名后缀

# 2. 启动交互式 REPL（工作目录建议为 rust/）
cargo run -p s01_agent_loop
```

可选环境变量：

| 变量 | 作用 | 默认 |
|------|------|------|
| `EFFORT_LEVEL` | 思考强度 low/medium/high/xhigh/max，请求体加 `output_config.effort` | 不带该字段 |
| `MAX_TOKENS` | 输出 token 上限 | 8000 |
| `ANTHROPIC_BETA` | `anthropic-beta` 头透传（如官方 1M 上下文 `context-1m-2025-08-07`） | 不带该头 |
| `S01_DEBUG` | =1 打印原始请求/响应 | 关闭 |

在 REPL 中输入问题即可，输入 `q` 或 `exit` 退出（空行忽略不退出）。
支持多轮对话，历史跨轮保留。

## 调试开关

环境变量 `S01_DEBUG=1` 时，打印每次 API 调用的原始请求/响应
（pretty-print，走 stderr 灰色输出，认证头不会被打出来）：

```bash
S01_DEBUG=1 cargo run -p s01_agent_loop
```

观察 messages 逐轮膨胀、tool_use/tool_result 配对、usage/cache 统计，都靠它。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **直调 HTTP** | 用 `reqwest` 直接调用 Anthropic Messages API，不依赖官方 SDK |
| **无状态 API** | 模型不记任何事，每轮都要把全部历史重新发送 |
| **唯一工具 bash** | 读文件、写文件、编译、测试，一个命令全覆盖 |
| **同步阻塞** | s01 循环天然是顺序执行的，不需要 tokio 异步 |
| **serde 契约模型** | `#[serde(tag="type")]` 枚举映射 content block，编译期锁死 API 结构 |
| **thinking/signature 保留** | `#[serde(flatten)]` 兜底未知字段，思维链签名无损 round-trip（官方 API 多轮工具调用要求回传） |
| **effort 可配** | `EFFORT_LEVEL` → `output_config.effort`，未设置则字段不出现在请求体；合法集合不硬编码，随模型代际演进 |
| **输出截断** | 工具输出按整行截断到 50000 字符（追加 `...`），防止撑爆上下文；终端预览截断到 1000 字符 |
| **双超时** | 子进程 120 秒（双线程抽管道防死锁）；HTTP 总超时 300s + 连接超时 10s |
| **错误不 panic** | 所有失败都变成字符串返回给模型，模型看到 `Error:` 会自己换路重试 |
| **并行 tool_use 契约** | 一条 assistant 消息的多个 tool_use，对应 tool_result 收进同一条 user 消息回灌（串行执行） |

## 结构

```
s01_agent_loop/
├── Cargo.toml
├── README.md
└── src/
    └── main.rs      # 全部代码(705行): 数据模型、API客户端、工具执行、Agent Loop、配置与REPL
```

质量基线：`cargo build` 零错误、`cargo clippy` 零警告。

## 测试

```bash
cargo test -p s01_agent_loop
```

10 个单元测试，覆盖不依赖网络的纯逻辑：`truncate_lines` 截断边界、
serde 契约模型（含 thinking signature round-trip）、bash 黑名单。
API 调用和 REPL 交互靠 `S01_DEBUG=1` 的实测 trace 验证。

## 与 Python 版对比

对照 `../../python/s01_agent_loop/code.py`（139 行）。循环骨架、REPL、bash 工具
三者行为一一对应，差异如下：

| 维度 | Python 版 | Rust 版 | 差异原因 |
|------|-----------|---------|----------|
| API 调用 | 官方 `anthropic` SDK | reqwest 直调 HTTP | 教学目的：让 API 契约显性化 |
| 消息模型 | dict + SDK 对象混用 | serde 枚举，编译期校验 | 静态类型 vs 动态 duck typing |
| thinking block | SDK 自动处理（含 signature） | 手动建模 + flatten 保留 signature | SDK 替 Python 版隐式解决了 round-trip 问题 |
| 进程超时 | `subprocess.run(timeout=120)` 一行 | `wait_timeout` + 双线程抽管道 | Rust 标准库无内置超时；管道缓冲区死锁需显式处理 |
| 输出截断 | `out[:50000]` 按字符硬切 | `truncate_lines(50000)` 整行截断 + `...` 后缀 | Rust 版不留半行，此惯例自 s02 起全轨沿用 |
| HTTP 超时 | SDK 默认 10 分钟 | 显式 300s + 连接 10s | reqwest blocking 默认无限等待，必须自己设 |
| 调试观测 | 无 | `S01_DEBUG=1` 打印原始请求/响应 | Rust 版新增 |
| 终端预览 | `output[:200]` 硬截断 | 整行截断 1000 字符 + `...` | Rust 版新增 |
| 空行退出 | 空行即退出 | 空行忽略，仅 q/exit 退出 | Rust 版新增 |
| 危险命令 | 简陋黑名单 | 同款黑名单（s03 才认真做权限） | 刻意保持一致 |

行数差异（139 → 705）的去向：约 120 行数据模型（Python 靠 dict 免写）、
约 60 行进程/管道的显式处理（Python 的 subprocess 隐式搞定）、
debug 开关和更细的注释。Rust 版的"多出来的代码"正是 Python 生态
替你隐式完成的部分——这是两种语言哲学差异的实物对照。

## 后续章节

| 章节 | 主题 | 在 s01 基础上增加 |
|------|------|--------------------|
| s02 | Tool Use | 多个工具并行调用 |
| s03 | Permission | 权限控制系统 |
| s04 | Hooks | 生命周期钩子 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
