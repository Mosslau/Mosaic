# s11: Error Recovery —— 错误不是结束，是重试的开始

在 s10 基础上给**主循环的 LLM 调用**包上错误恢复层。保留 s01–s10 全部机制；
压缩、记忆、子代理等内部辅助 LLM 调用维持原样（教学版范围）。

三种最常见的故障，三种恢复路径：

```text
  with_retry ── 1 次 LLM 调用（可重试至 10 次）
       │
       ▼
  ┌─────────────────────────────┐
  │ classify_http_error()       │  状态码 + 响应体 → LlmError
  └──────────┬──────────────────┘
             │
    ┌────────┼──────────┐
    │        │          │
 429/529  prompt_too_long  其他
    │        │          │
    ▼        ▼          ▼
 指数退避  reactive    [unrecoverable]
 +抖动×10  compact     error_note() 截断
 529×3 →   (仅1次)     写 [Error] 进历史
 切fallback 重试       本轮结束
             │
             ▼
  ┌─────────────────────────────┐
  │ stop_reason == max_tokens?  │  输出被截断（先检查再追加！）
  └──────────┬──────────────────┘
             │
        ┌────┴────┐
      未升级      已升级
        │          │
        ▼          ▼
   max_tokens   追加截断输出 +
   = 64K 重试   续写提示 ×3
   (不追加输出)  (超限放弃)
```

- **`LlmError`**：强类型错误分类（`RateLimited` / `Overloaded` / `PromptTooLong` / `Other`）。
  Python 版靠异常类名 + 字符串匹配猜错误类型，Rust 版在 `call_llm` 拿到状态码和响应体
  的地方直接分类，恢复逻辑 match 枚举
- **`classify_http_error`**：429 → 限流；529（或 5xx + body 含 "overloaded"，兼容网关）→ 过载；
  响应体命中 prompt-too-long 措辞 → 超限；其余 → 不可恢复
- **`with_retry`**：瞬态错误（429/529）指数退避重试，最多 10 次；非瞬态立即向上抛。
  闭包接收当前模型名——529 切换后下一轮自动用新模型
- **`retry_delay`**：`min(500 × 2^attempt, 32000)ms + 0~25% 随机抖动`；`Retry-After`
  头优先级最高
- **`RecoveryState`**：一次 agent_loop 调用内共享的恢复状态（升级/续写/529 计数/
  compact 标记/当前模型），对齐 Python 的 `RecoveryState`
- **`plan_truncation_recovery`**：截断决策纯函数——首次升级、64K 后续写 ×3、超限放弃
- **`error_note` / `escalated_limit`**：不可恢复错误截断 200 字符写进历史（防大错误体
  污染上下文）；升级目标取 `max(64000, 当前上限)`（防 MAX_TOKENS 配大了反被降级）

## 相对 s10 的改动

| s10 | s11 |
|-----|-----|
| `call_llm` 返回 `Result<ApiResponse, String>` | 返回 `Result<ApiResponse, LlmError>`，签名加 `model`/`max_tokens` 参数 |
| 错误直接 `return Err(e)` 退出 | 三条恢复路径（升级/续写、compact、退避+fallback） |
| `max_tokens` 固定 `cfg.max_tokens` | 首轮截断升级 64K，仍截断续写 ×3 |
| 429/529 无处理 | `with_retry` 指数退避，连续 3 次 529 切 `FALLBACK_MODEL_ID` |
| prompt_too_long 内层 retry loop + `MAX_REACTIVE_RETRIES` | 并入 `RecoveryState`（bool 标记，仅试一次） |
| 不可恢复错误弹掉用户上一条输入 | `[Error]` 截断后写进历史当回复展示（对齐 Python） |

## 运行

```bash
cargo run -p s11_error_recovery
```

观察错误恢复（实测截断路径）：

```bash
MAX_TOKENS=300 cargo run -p s11_error_recovery
# 让模型写个长程序 → 看到 [max_tokens] escalating 300 -> 64000
```

可选环境变量：`FALLBACK_MODEL_ID`（连续 529 过载时切换的备用模型）。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **先检查截断再追加输出** | 第一次升级时 messages 保持不变，同一个请求换更大的 token 上限重发；截断输出只在"64K 仍截断"时才进历史 |
| **强类型分类** | 分类逻辑集中在 `call_llm`（状态码 + 响应体 + header 都在手边），恢复层 match 枚举，不猜字符串 |
| **Retry-After 真正接线** | Python 版 `retry_delay` 有 `retry_after` 参数但调用处从未传入（死代码）；Rust 版从响应头解析 |
| **恢复只包主循环** | 记忆选择/提取、历史摘要、子代理等内部辅助调用维持单次直调——教学版范围，代码有注释 |
| **状态每回合独立** | `RecoveryState` 是 agent_loop 局部变量，升级/续写/切换不跨回合 |
| **字符安全截断** | 错误体可能带超大响应文本或中文，`error_note` 用 `truncate_chars` 截 200 字符，杜绝字节切片 panic |

## 结构

```
s11_error_recovery/
├── Cargo.toml         # s10 依赖 + rand（退避抖动）
├── README.md
└── src/
    └── main.rs        # s10 全套 + LlmError/with_retry/RecoveryState/截断恢复
```

## 测试

```bash
cargo test -p s11_error_recovery -- --test-threads=1
```

131 测试（112 从 s10 + 19 新增）：错误分类（7 种超限措辞）、Retry-After 解析与优先级、
退避公式区间（含封顶）、529×3 切换与无 fallback 分支、截断决策状态机、with_retry 五种
语义（成功/上抛/重试/耗尽/模型传递）、错误注记字符安全截断、升级下限。

重试类测试用 `Retry-After: 0` 让退避立即结束，避免测试里真实 sleep。

## 与 Python 版对比

对照 `../../python/s11_error_recovery/code.py`。三条恢复路径、常量（64000/10 次/500ms 基数/
3 次续写/3 次 529）、日志文案一一对应。差异：

- **承载机制**：Rust 版保留 s10 完整功能（9 工具 + Hook + nag + 子代理 + skill + 压缩 +
  记忆 + prompt 组装）——Python s11 只有 3 个基础工具
- **reactive compact**：Python 教学版只保留尾部 5 条消息；Rust 用 s08 的 LLM 摘要版
  （更接近 CC 真实实现）
- **错误分类**：Python 字符串匹配；Rust 状态码 + 强类型枚举。超限措辞：Rust 显式短语列表 + `(prompt∧long)` 泛匹配兜底（2025 审计修复，覆盖 "prompt was too long" 类措辞）
- **Retry-After**：Python 有参数未接线；Rust 真实解析响应头
- **MAX_TOKENS**：Python 硬编码 8000；Rust 读环境变量，升级从当前上限出发且不降级
- **不可恢复文案**：Python `[Error] {异常类名}: {msg[:200]}`；Rust `[Error] {Display 文案截 200 字符}`（无类名前缀，内容等价）
- **s09 遗留机制**：压缩前提取快照、索引描述回退（s09 审计修复）随本章一并携入

## 后续章节

| 章节 | 主题 | 在 s11 基础上增加 |
|------|------|--------------------|
| s12 | Task System | `.tasks/` 持久任务图（依赖、状态、跨会话恢复） |
| s13 | Async & Concurrency | 后台任务 + 流式输出 + 并行工具执行 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
