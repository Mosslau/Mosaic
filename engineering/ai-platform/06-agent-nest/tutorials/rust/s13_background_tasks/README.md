# s13: Background Tasks — 慢操作放后台，主循环不阻塞

在 s12 基础上引入 tokio，主循环 async 化，一次落地"异步与并发"的三个面：
**后台任务**（对齐 Python s13）、**流式 SSE 输出**与**并行工具执行**（Rust 轨道前向扩展）。
s01–s12 全部机制保留（任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理照旧）。

```text
  Agent loop (async)
                  │
                  ▼
  ┌──────────────────────────────┐
  │ call_llm_streaming (SSE)     │  ← text_delta 边收边打印
  └───────────────┬──────────────┘
                  │ stop_reason == "tool_use"
                  ▼
  ┌──────────────────────────────┐
  │ tool exec (parallel)         │
  │  ...9 old tools              │
  │  bash: run_in_background?    │
  │    |- Yes -> background task │
  │    `- No  -> spawn_blocking  │
  │  task -> serial (s15)        │  ← 并行子代理留给 s15
  └───────────────┬──────────────┘
                  │
                  ▼
  ┌──────────────────────────────┐
  │ results + notifications      │
  │  tool_result (in order)      │
  │  <task_notification>         │
  └──────────────────────────────┘
```

## 三个面

### 1. 后台任务（对齐 Python s13）

- bash 工具 schema 新增 `run_in_background: boolean` 参数，模型显式请求慢命令丢后台；
- `should_run_background`：显式请求优先，未指定时 `is_slow_operation` 关键词启发式兜底
  （install/build/test/deploy/compile/docker/pip/npm/cargo/pytest/make，**词边界匹配**——
  `makeCtx`/`makefile`/`uninstall` 等子串不再误伤；复合词如 `cargo buildx` 不命中时可显式指定 flag）；
- `start_background_task`：`tokio::task::spawn_blocking` 跑 run_bash，立即返回 `bg_{n:04d}` ID，
  主循环不等待；状态存 `BACKGROUND_TASKS` / `BACKGROUND_RESULTS`（LazyLock<Mutex<HashMap>>）；
- `collect_background_results`：完成后格式化为 `<task_notification>` 注入对话。
  **通知不复用 tool_use_id**——原始 tool call 已用占位 tool_result 回复，
  后台完成是独立事件（一个 tool_use 只配对一个 tool_result 的 API 契约）。

### 2. 流式 SSE 输出（Rust 前向扩展）

- `ApiRequest` 加 `stream: bool`（skip_serializing_if，缺省不出现在请求体）；
- `call_llm_streaming`：SSE 事件流（`content_block_start/delta/stop`、`message_delta/stop`）
  增量重建 ContentBlock，`text_delta` 边收边打印（thinking 默认不显示，signature_delta 保留；
  `STREAM_THINKING=1` 时思考过程灰色打到 stderr，CC 风格）；
- 返回与 `call_llm` 相同形状的 `ApiResponse`——s11 的截断恢复/续写逻辑零改动复用；
- `stop_reason` 流式里不可靠时按内容兜底（对齐 CC 源码 needsFollowUp 的思路）。

### 3. 并行工具执行（Rust 前向扩展）

- 一条 assistant 消息的多个 tool_use：`spawn_blocking` 并行执行，
  **按原顺序 await 配对 tool_result**（API 要求 tool_use/tool_result 同序）；
- PreToolUse hook（含 Gate3 用户确认）串行先行，PostToolUse 按原序收尾；
- `task` 子代理串行（并行子代理留给 s15 队友线程——设计决策）。

## 相对 s12 的改动

| s12 | s13 |
|-----|-----|
| 全部机制（14 工具 + Hook + 权限 + nag + 子代理 + skill + 压缩 + 记忆 + prompt + 错误恢复 + 任务图） | 全部保留 |
| 阻塞 reqwest + `std::thread::sleep` | tokio 异步客户端 + `tokio::time::sleep` |
| `call_llm` 阻塞，一次性 JSON 响应 | `call_llm`（非流式，子代理/内部调用）+ `call_llm_streaming`（流式，父循环） |
| 工具串行执行 | 并行执行 + 后台任务 + 通知注入 |
| `fn main()` | `#[tokio::main]` + 异步 stdin |
| 依赖无 tokio | `tokio = { version = "1", features = ["full"] }` |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s13_background_tasks
```

试试这些 prompt：

1. `Run pip list in the background and find all Python files in this directory`
2. `Run npm install (use run_in_background) and while waiting, read package.json`
3. `Create a task to setup the project, then run pip list in the background`

观察重点：慢操作有没有被送到后台？`bg_id` 是否返回？模型生成时文字是否逐字流出？
后台通知有没有以 `<task_notification>` 格式注入？

可选环境变量同 s12：`EFFORT_LEVEL` / `MAX_TOKENS` / `ANTHROPIC_BETA` / `S01_DEBUG` / `FALLBACK_MODEL_ID`；
s13 新增 `STREAM_THINKING`（=1 时思考过程灰色流式打到 stderr，默认关）。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **全链 async** | 主循环、call_llm、with_retry、压缩/记忆/子代理全部 async 化；退避用 `tokio::time::sleep` 不阻塞 runtime |
| **with_retry 泛化** | `FnMut(String) -> Fut`：闭包收模型名（by value）+ async move 搬进 Future，避免生命周期纠缠；同步/异步闭包都兼容 |
| **流式重建即复用** | SSE 流结束时重建 ApiResponse，截断升级/续写/529 切换等 s11 逻辑原样工作 |
| **思考可见性** | thinking 只重建不显示（回传 API 必需）；`STREAM_THINKING=1` 时 `thinking_delta` 灰色打到 **stderr**（`[thinking] ` 前缀，CC 风格），与 stdout 的 text 分离、不污染主输出；默认关 |
| **spawn_blocking 隔离** | run_bash 可能阻塞 120s，同步 handler 一律经 blocking 线程池，不占 async worker |
| **顺序配对** | 槽位化执行：PreToolUse 串行阶段给每个 tool_use 落槽位，被拦/后台占位/串行子代理/并行批次的结果全部按槽位索引回填——tool_result 与 tool_use 严格同序（API 契约），混合场景（如 read_file + task + glob 同一条消息）也不会乱序 |
| **通知独立事件** | `<task_notification>` 不复用 tool_use_id；与 tool_result 合入同一条 user 消息 |
| **子代理非流式** | spawn_subagent 保持"拿完整响应"的阻塞语义（只回传摘要），控制流与 s06 一致；其内部工具执行也走 spawn_blocking，不阻塞 async worker |
| **共享状态线程安全** | `LazyLock<Mutex<HashMap>>`（HashMap::new 非 const，不能进 static 初始化） |
| **stdin 异步读** | `tokio::io::BufReader::new(tokio::io::stdin())`，REPL 不阻塞 runtime |

## 结构

```
s13_background_tasks/
├── Cargo.toml          # s12 依赖全集 + tokio(full)
├── README.md
└── src/
    └── main.rs         # 5684 行：s12 全套 + 后台任务/SSE 流式/并行执行（~880 行新增）
```

## 测试

```bash
cargo test -p s13_background_tasks -- --test-threads=1
```

157 个单元测试（145 从 s12 携入 + 12 新增），覆盖：
- 后台任务：`is_slow_operation` 关键词命中（词边界，含 `makeCtx` 误判回归）、
  `should_run_background` 显式优先、
  通知格式与 200 字符截断、后台任务全生命周期（真实 echo 执行 + 轮询收集）
- SSE 流式：事件边界（`\n\n` 与 `\r\n\r\n`）、data 载荷解析与 [DONE] 跳过、
  文本/tool_use 增量重建、thinking signature 保留（含思考打印开关路径）、stop_reason 兜底
- 并行执行：execute_sync 分发（未知工具报错、bash 真实执行）
- s11 with_retry 测试转 `#[tokio::test]`（Cell 计数 + async move 闭包）

## 与 Python 版对比

对照 `../../python/s13_background_tasks/code.py`。后台任务机制一一对应：
bash schema 加 `run_in_background`、显式优先 + 启发式兜底、`bg_{n:04d}` ID、
`<task_notification>` 通知（不复用 tool_use_id）、占位 tool_result + 通知合入同一条 user 消息。
差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | s12 简化栈（8 工具，无错误恢复/记忆/技能） | s12 全量保留（14 工具 + 全部机制） |
| 后台线程 | `threading.Thread` + `threading.Lock` | `tokio::task::spawn_blocking` + `LazyLock<Mutex<HashMap>>` |
| 慢词启发式 | 朴素子串匹配（`makeCtx` 里的 "make" 会误命中） | **词边界匹配**（修复实测误判；有回归测试） |
| 后台范围 | 任意工具带 `run_in_background` flag 均可后台 | 仅 bash（flag 只在 bash schema 暴露，模型实际无法给其他工具设 flag，语义等价且更安全） |
| 流式输出 | 无（一次性 JSON 响应） | **前向扩展**：SSE 边收边打印 |
| 并行工具执行 | 无（串行） | **前向扩展**：spawn_blocking 并行 + 原序配对 |
| 通知收集时机 | 每轮工具循环后轮询 | 同（教学版同模式；真实 CC 用通知队列） |

## 后续章节

| 章节 | 主题 | 在 s13 基础上增加 |
|------|------|--------------------|
| s14 | Cron Scheduler | 定时调度线程 |
| s15 | Agent Teams | 队友线程来认领 .tasks/ 里的任务（并行子代理落这里） |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
