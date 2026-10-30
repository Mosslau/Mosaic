//! s02: Tool Use — 在 s01 基础上新增 4 个工具 + 分发映射。
//!
//! s01 的循环完全保留，唯一的变动：硬编码的 `if name == "bash"` 换成
//! `match name { ... }` 查表分发。加一个工具 = 加一行 schema + 一个 handler。
//!
//! ```text
//! +----------+      +-------+      +---------+
//! |   User   | ---> |  LLM  | ---> |  Tool   |
//! |  prompt  |      |       |      |  map    |
//! +----------+      +---+---+      +----+----+
//!                       ^               |
//!                       |   tool_result |
//!                       +---------------+
//!                       (loop continues)
//! ```
//!
//! 对比 Python 版 ../../python/s02_tool_use/code.py。
//! 运行：cargo run -p s02_tool_use
//! 可选环境变量（同 s01）：EFFORT_LEVEL / MAX_TOKENS / ANTHROPIC_BETA / S01_DEBUG

use std::env;
use std::io::{self, BufRead, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use std::os::unix::process::CommandExt; // process_group(): 独立进程组，超时可整组击杀
use wait_timeout::ChildExt;

// ── Anthropic Messages API 的数据模型（同 s01） ──────────────────────────

/// 消息角色。serde 序列化为小写字符串 "user" / "assistant"。
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "lowercase")]
enum Role {
    User,
    Assistant,
}

/// 消息内容的 block。对应 API 里 content 数组的元素。
///
/// `#[serde(tag = "type")]` 表示用 JSON 里的 "type" 字段区分变体：
///   {"type": "text",        "text": "..."}
///   {"type": "tool_use",    "id": "...", "name": "...", "input": {...}}
///   {"type": "tool_result", "tool_use_id": "...", "content": "..."}
///
/// 一个枚举同时承担两个方向：
///   反序列化 <- 解析 API 返回的 assistant 回复（text + tool_use）
///   序列化   -> 把历史消息重新发给 API（包括我们构造的 tool_result）
#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(tag = "type", rename_all = "snake_case")]
enum ContentBlock {
    /// 模型的文字输出
    Text { text: String },
    /// 模型的思维链输出（部分模型/网关会返回这种 block，
    /// 缺了这个变体 serde 会因不认识的 "type" 而拒绝整个响应）
    Thinking {
        thinking: String,
        /// 兜底保存本变体未声明的字段（如网关返回的 "signature"）。
        /// 没有它，serde 反序列化时会丢弃未知字段，回传历史时签名丢失——
        /// 官方 API 在 thinking + 工具调用的多轮对话里要求回传 signature。
        /// flatten 表示序列化时把 map 里的键值"摊平"回 block 顶层。
        #[serde(flatten)]
        extra: serde_json::Map<String, serde_json::Value>,
    },
    /// 模型发出的工具调用请求（只出现在 assistant 消息里）
    ToolUse {
        id: String,               // 本次调用的唯一 ID，回结果时靠它配对
        name: String,             // 工具名，对应 tools 数组里的定义
        input: serde_json::Value, // 符合 input_schema 的参数，先按任意 JSON 接住
    },
    /// 工具执行结果（必须放在 user 消息里）
    ToolResult {
        tool_use_id: String, // 和 ToolUse.id 配对
        content: String,
    },
}

/// 消息内容：API 允许两种形态，所以用 untagged 枚举同时支持。
///   - 纯字符串: "content": "帮我看看目录"
///   - block 数组: "content": [{"type": "text", ...}, ...]
///
/// untagged 表示序列化/反序列化时不加任何标签，按外形自动匹配。
///
/// 注意与 ContentBlock::Text 的区别：本变体是用户消息的文本简写格式
/// （不走 block 数组），而 ContentBlock::Text 是 assistant 回复中的
/// 一个内容块，两者在 messages 数组中的语法位置不同。
#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(untagged)]
enum MessageContent {
    Text(String),
    Blocks(Vec<ContentBlock>),
}

/// 一条消息。整个 Agent 的"记忆"就是 Vec<Message>：
/// API 调用本身无状态，每轮都要把全部历史重新发一遍。
#[derive(Serialize, Deserialize, Clone, Debug)]
struct Message {
    role: Role,
    content: MessageContent,
}

impl Message {
    /// 构造一条纯文本的 user 消息（用户输入走这里）
    fn user_text(text: impl Into<String>) -> Self {
        Message {
            role: Role::User,
            content: MessageContent::Text(text.into()),
        }
    }

    /// 构造一条 assistant 消息，内容直接是 API 返回的 block 列表
    fn assistant_blocks(blocks: Vec<ContentBlock>) -> Self {
        Message {
            role: Role::Assistant,
            content: MessageContent::Blocks(blocks),
        }
    }

    /// 构造一条装着 tool_result 的 user 消息（工具结果回灌走这里）
    fn user_tool_results(results: Vec<ContentBlock>) -> Self {
        Message {
            role: Role::User,
            content: MessageContent::Blocks(results),
        }
    }
}

// ── s02 新增：每个工具强类型的参数结构体 ──────────────────────────────────
//
// s01 用 `input["command"].as_str()` 从任意 JSON 里取参数，
// 5 个工具之后这种做法散乱且容易出运行时错误。
// 改为每个工具一个 Deserialize 结构体，serde 帮你做类型校验和错误报告。

/// bash 工具的参数：一条 shell 命令
#[derive(Deserialize)]
struct BashInput {
    command: String,
}

/// read_file 工具的参数
#[derive(Deserialize)]
struct ReadInput {
    path: String,
    /// 可选的行数上限。None 读全文件。
    limit: Option<u32>,
}

/// write_file 工具的参数
#[derive(Deserialize)]
struct WriteInput {
    path: String,
    content: String,
}

/// edit_file 工具的参数：用 new_text 替换 old_text 第一次出现的位置
#[derive(Deserialize)]
struct EditInput {
    path: String,
    old_text: String,
    new_text: String,
}

/// glob 工具的参数：类 ls 的文件名模式
#[derive(Deserialize)]
struct GlobInput {
    pattern: String,
}

// ── 工具定义与请求/响应结构 ──────────────────────────────────────────────

/// 工具定义。序列化后就是 API tools 数组里的一项：
/// {"name": "bash", "description": "...", "input_schema": {...}}
/// 模型只能通过这个 schema 感知工具的存在和用法。
#[derive(Serialize)]
struct Tool {
    name: &'static str,
    description: &'static str,
    input_schema: serde_json::Value,
}

/// POST /v1/messages 的请求体。
/// 全部字段都是引用，序列化时零拷贝地指向调用方的数据。
#[derive(Serialize)]
struct ApiRequest<'a> {
    model: &'a str,
    system: &'a str,
    messages: &'a [Message],
    tools: &'a [Tool],
    max_tokens: u32,
    /// 思考强度（新版 adaptive thinking 的控制旋钮）。
    /// None 时整个字段不出现在请求体里（skip_serializing_if），
    /// 服务器按模型默认 effort 处理 —— 保持"未配置即被动"的行为
    #[serde(skip_serializing_if = "Option::is_none")]
    output_config: Option<OutputConfig>,
}

/// 思考强度配置（adaptive thinking 的控制旋钮）。
/// 合法值: "low" | "medium" | "high" | "xhigh" | "max"。
/// 低值减少思考深度节省 token，高值增加推理时间换取复杂任务准确率。
/// 注意：支持的模型代际不断演进，此处不作白名单校验，
/// 非法值由 API 网关报错——客户端保持向前兼容。
#[derive(Serialize)]
struct OutputConfig {
    effort: String,
}

/// API 响应体里我们关心的部分（其余字段如 usage、id 用不到就忽略）。
#[derive(Deserialize)]
struct ApiResponse {
    /// assistant 这一轮输出的 block 列表：若干 text + 若干 tool_use
    content: Vec<ContentBlock>,
    /// 为什么停止："tool_use" = 还想调工具（继续循环）；
    /// 其他（"end_turn" / "max_tokens" 等）= 说完收工（退出循环）。
    /// 循环的退出条件完全由这个字段决定 —— 这就是"模型自己决定何时停"。
    stop_reason: Option<String>,
}

// ── 5 个工具定义 ─────────────────────────────────────────────────────────
//
// 模型只能通过这里的 schema 感知工具的存在和参数形状。
// 加一个新工具 = 在这个数组里加一条。

fn all_tools() -> [Tool; 5] {
    [
        Tool {
            name: "bash",
            description: "Run a shell command.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "command": { "type": "string" } },
                "required": ["command"]
            }),
        },
        Tool {
            name: "read_file",
            description: "Read file contents. Use limit to restrict lines if the file is large.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "path": { "type": "string" },
                    "limit": { "type": "integer" }
                },
                "required": ["path"]
            }),
        },
        Tool {
            name: "write_file",
            description: "Write content to a file (creates parent directories).",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "path": { "type": "string" },
                    "content": { "type": "string" }
                },
                "required": ["path", "content"]
            }),
        },
        Tool {
            name: "edit_file",
            description: "Find exact text and replace once. Prefer over sed.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "path": { "type": "string" },
                    "old_text": { "type": "string" },
                    "new_text": { "type": "string" }
                },
                "required": ["path", "old_text", "new_text"]
            }),
        },
        Tool {
            name: "glob",
            description: "Find files matching a glob pattern (relative to project root).",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "pattern": { "type": "string" } },
                "required": ["pattern"]
            }),
        },
    ]
}

// ── truncate_lines（从 s01 携入） ────────────────────────────────────────

/// 按行截断：在不超过 max_chars 的前提下保留完整行，截断时追加 "..."。
/// 避免把一行切成两半（chars 层面操作，也不会切出半个 UTF-8 字符）。
fn truncate_lines(text: &str, max_chars: usize) -> String {
    if text.chars().count() <= max_chars {
        return text.to_string();
    }
    let mut out = String::new();
    let mut used = 0usize;
    for line in text.lines() {
        let line_len = line.chars().count() + 1; // +1 是换行符
        // 加上这一行会超限就停（第一行就超限时 out 为空，走下面的字符级兜底）
        if used + line_len > max_chars {
            break;
        }
        out.push_str(line);
        out.push('\n');
        used += line_len;
    }
    // 兜底：第一行本身就超长，按字符截断
    if out.is_empty() {
        out = text.chars().take(max_chars).collect();
        out.push('\n');
    }
    out.push_str("...");
    out
}

// ── safe_path：路径沙箱 ──────────────────────────────────────────────────
//
// 文件工具只能操作工作目录内的路径（白名单校验，s03 权限系统的雏形）。
// canonicalize 解析符号链接和 `..`，确保 `../../etc/passwd` 被拦截。
//
// 注意 Rust 的 canonicalize() 在文件不存在时失败（与 Python Path.resolve()
// 不同），所以对不存在的文件降级为解析父目录再拼文件名。

fn safe_path(path: &str) -> Result<PathBuf, String> {
    let cwd = env::current_dir().map_err(|e| format!("Error: can't get cwd: {e}"))?;
    let target = cwd.join(path);
    // 先尝试全路径 canonicalize（文件已存在时），失败则解析父目录
    let full = if let Ok(canon) = target.canonicalize() {
        canon
    } else if let Some(parent) = target.parent() {
        let resolved_parent = parent
            .canonicalize()
            .map_err(|e| format!("Error: Invalid path '{path}': {e}"))?;
        // file_name() 只在路径以 .. 结尾时返回 None，此处不会发生，故 unwrap_or 是安全的。
        resolved_parent.join(target.file_name().unwrap_or(target.as_os_str()))
    } else {
        target
    };
    // 白名单：路径必须在工作目录内
    if !is_within_workspace(&full, &cwd) {
        return Err(format!("Error: Path escapes workspace: {path}"));
    }
    Ok(full)
}

/// 判断 path 是否在 cwd 内（含 cwd 本身）。必须按组件边界比较：
/// Path::starts_with 是字符串前缀比较，会把 /ws2 误判成 /ws 的子路径，
/// 从而放行同名前缀的兄弟目录（../ws2 也一样）。strip_prefix 按组件切分，
/// 且传入路径已经过 canonicalize 消除符号链接与 ".."，故成功 = 真在内部。
fn is_within_workspace(path: &Path, cwd: &Path) -> bool {
    path.strip_prefix(cwd).is_ok()
}

// ── 工具执行 ─────────────────────────────────────────────────────────────

/// 执行一条 shell 命令，行为对齐 Python 版 run_bash()：
///   - 危险命令黑名单直接拦截（最简陋的防护，s03 才认真做权限）
///   - stdout + stderr 合并返回
///   - 输出截断到 50000 字符，防止撑爆上下文
///   - 120 秒超时
///   - 所有失败都变成字符串返回给模型，不 panic ——
///     模型看到 "Error: ..." 会自己换条路重试，这是 agent 容错的基本手法
fn run_bash(input: BashInput) -> String {
    // 教学级黑名单：仅拦截最明显的破坏命令，不作为生产安全屏障。
    // > /dev/ 会误伤 echo 123 > /dev/null 等合法命令——s03 权限系统才是完整方案。
    let dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"];
    if dangerous.iter().any(|d| input.command.contains(d)) {
        return "Error: Dangerous command blocked".to_string();
    }

    // 用 sh -c 执行，等价于 Python 的 subprocess.run(..., shell=True)。
    // 工作目录默认继承当前进程目录。
    let mut child = match Command::new("sh")
        .arg("-c")
        .arg(&input.command)
        // 把 sh 及其所有后代放进独立进程组（pgid = sh 的 pid），
        // 超时才能整组击杀，连后台孙进程一起清理。
        .process_group(0)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => return format!("Error: {e}"),
    };

    // stdout/stderr 必须在等待退出的同时持续读取：
    // OS 管道缓冲区有限（macOS 默认 64KB），如果子进程输出写满管道而没人读，
    // 它会永远阻塞在 write() 上，最后被我们误判成"超时"杀掉。
    // 所以开两个线程专门抽干两根管道。take() 把管道句柄从 child 里移出来。
    let mut stdout_pipe = child.stdout.take().expect("stdout piped");
    let mut stderr_pipe = child.stderr.take().expect("stderr piped");
    let stdout_thread = std::thread::spawn(move || {
        let mut buf = Vec::new();
        stdout_pipe.read_to_end(&mut buf).ok();
        buf
    });
    let stderr_thread = std::thread::spawn(move || {
        let mut buf = Vec::new();
        stderr_pipe.read_to_end(&mut buf).ok();
        buf
    });

    // 最多等 120 秒；超时则杀掉子进程（读取线程会因管道关闭而自然结束）
    match child.wait_timeout(Duration::from_secs(120)) {
        Ok(Some(_status)) => {
            let mut combined =
                String::from_utf8_lossy(&stdout_thread.join().unwrap_or_default()).into_owned();
            combined.push_str(
                &String::from_utf8_lossy(&stderr_thread.join().unwrap_or_default()),
            );
            let trimmed = combined.trim();
            if trimmed.is_empty() {
                "(no output)".to_string()
            } else {
                // 截断到 50000 字符，防止撑爆上下文（按整行截断）
                truncate_lines(trimmed, 50000)
            }
        }
        Ok(None) => {
            // 超时：杀整个进程组而不是只杀 sh。kill 的负 pid 参数表示进程组，
            // 只 child.kill() 的话 sh -c "sleep 300 &" 的后台孙进程会变孤儿继续跑。
            let pid = child.id();
            let _ = Command::new("kill").arg("-KILL").arg(format!("-{pid}")).status();
            child.kill().ok();
            child.wait().ok();
            "Error: Timeout (120s)".to_string()
        }
        Err(e) => format!("Error: {e}"),
    }
}

/// 读取文件内容。s02 新增，行为对齐 Python 版 run_read()：
///   - safe_path 确保不越界
///   - 支持 limit 参数截断行数
fn run_read(input: ReadInput) -> String {
    let path = match safe_path(&input.path) {
        Ok(p) => p,
        Err(e) => return e,
    };
    let content = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(e) => return format!("Error: {e}"),
    };
    if let Some(limit) = input.limit {
        let lines: Vec<&str> = content.lines().collect();
        let limit = limit as usize;
        if limit < lines.len() {
            let shown = lines[..limit].join("\n");
            return format!("{shown}\n... ({} more lines)", lines.len() - limit);
        }
    }
    content
}

/// 写入文件内容。s02 新增：
///   - safe_path 确保不越界
///   - 自动创建父目录
fn run_write(input: WriteInput) -> String {
    let path = match safe_path(&input.path) {
        Ok(p) => p,
        Err(e) => return e,
    };
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    match std::fs::write(&path, &input.content) {
        Ok(()) => format!("Wrote {} bytes to {}", input.content.len(), input.path),
        Err(e) => format!("Error: {e}"),
    }
}

/// 精确文本替换一次。s02 新增：
///   - safe_path 确保不越界
///   - old_text 不存在时返回具体错误
///   - 只替换第一次出现（replacen(..., 1)）
fn run_edit(input: EditInput) -> String {
    let path = match safe_path(&input.path) {
        Ok(p) => p,
        Err(e) => return e,
    };
    let text = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(e) => return format!("Error: {e}"),
    };
    if !text.contains(&input.old_text) {
        return format!("Error: text not found in {}", input.path);
    }
    match std::fs::write(&path, text.replacen(&input.old_text, &input.new_text, 1)) {
        Ok(()) => format!("Edited {}", input.path),
        Err(e) => format!("Error: {e}"),
    }
}

/// 按 glob 模式找文件。s02 新增：
///   - 对每个匹配结果做 safe_path 白名单校验（避免 `../*.rs` 逃逸）
fn run_glob(input: GlobInput) -> String {
    let matches = match glob::glob(&input.pattern) {
        Ok(entries) => entries,
        Err(e) => return format!("Error: {e}"),
    };

    let mut results: Vec<String> = Vec::new();
    for entry in matches {
        match entry {
            Ok(path) => {
                // 对每个结果做路径安全校验
                let p = path.to_string_lossy().to_string();
                if safe_path(&p).is_ok() {
                    results.push(p);
                }
            }
            Err(e) => {
                // glob 模式匹配到某个路径时失败，记录但不中断
                results.push(format!("Error: {e}"));
            }
        }
    }

    if results.is_empty() {
        "(no matches)".to_string()
    } else {
        results.join("\n")
    }
}

// ── API 客户端（同 s01） ─────────────────────────────────────────────────

/// 一次 LLM 调用：把全部历史 messages + 工具定义发给 API，返回模型的响应。
///
/// 注意这里没有任何"记忆"概念——API 是无状态的，
/// 模型之所以"记得"之前的事，纯粹因为我们把 messages 整个重发了一遍。
fn call_llm(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &[Message],
    tools: &[Tool],
) -> Result<ApiResponse, String> {
    let req = ApiRequest {
        model: &cfg.model,
        system: &cfg.system,
        messages,
        tools,
        max_tokens: cfg.max_tokens,
        output_config: cfg.effort.as_ref().map(|e| OutputConfig { effort: e.clone() }),
    };

    // 调试开关：打印发出去的原始请求体（认证头在 header 里，不会被打出来）
    if cfg.debug {
        let req_json = serde_json::to_string_pretty(&req).unwrap_or_default();
        eprintln!(
            "\x1b[90m[debug] ==> POST {}/v1/messages\n{req_json}\x1b[0m",
            cfg.base_url
        );
    }

    let mut builder = http
        .post(format!("{}/v1/messages", cfg.base_url))
        // anthropic-version 是必传头，声明使用的 API 版本
        // 2023-06-01 是最老的稳定版，所有 Anthropic 兼容网关均支持。
        // 不升级到更新版本（如 2025-01-01）是为了保持与第三方网关的最大兼容性。
        .header("anthropic-version", "2023-06-01")
        .json(&req);

    // beta 特性头（如官方 API 的 1M 上下文 context-1m-2025-08-07）
    if let Some(beta) = &cfg.beta {
        builder = builder.header("anthropic-beta", beta);
    }

    // 认证方式二选一（对齐 Python 版的逻辑）：
    //   走官方 API 且设了 ANTHROPIC_AUTH_TOKEN -> Authorization: Bearer
    //   否则（含所有自定义网关）              -> x-api-key
    if let Some(token) = &cfg.auth_token {
        builder = builder.header("authorization", format!("Bearer {token}"));
    } else if let Some(key) = &cfg.api_key {
        builder = builder.header("x-api-key", key);
    }

    let resp = builder.send().map_err(|e| format!("HTTP 请求失败: {e}"))?;

    // 非 2xx 时把响应体读出来，里面通常有有用的错误信息（比如 overloaded）
    let status = resp.status();
    let body = resp.text().map_err(|e| format!("读取响应体失败: {e}"))?;

    // 调试开关：打印原始响应体（尽量 pretty-print，非法 JSON 就原样打）
    if cfg.debug {
        let pretty = serde_json::from_str::<serde_json::Value>(&body)
            .and_then(|v| serde_json::to_string_pretty(&v))
            .unwrap_or_else(|_| body.clone());
        eprintln!("\x1b[90m[debug] <== HTTP {status}\n{pretty}\x1b[0m");
    }

    if !status.is_success() {
        return Err(format!("API 返回 {status}: {body}"));
    }

    // 先拿原始文本再手动解析：失败时能把响应体带出来，
    // 方便定位"网关返回了什么意料之外的东西"（最常见的调试场景）
    serde_json::from_str::<ApiResponse>(&body).map_err(|e| {
        let preview: String = body.chars().take(500).collect();
        format!("解析响应失败: {e}\n响应体前 500 字符:\n{preview}")
    })
}

// ── 核心模式：与 s01 完全一致，唯一的变动在工具分发处 ────────────────────
//
// s01: 硬编码 `if name == "bash" { run_bash(...) }`
// s02: `match name` 查表分发，加工具不用碰循环

fn agent_loop(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
) -> Result<(), String> {
    let tools = all_tools();

    loop {
        // 1. 把完整历史发给模型
        let resp = call_llm(http, cfg, messages, &tools)?;

        // 下面要先把 resp.content 整体 move 进 messages，所以 stop_reason
        // 先 clone 出来再用（否则 resp 被部分 move 后无法再借它的字段）
        let stop_reason = resp.stop_reason.clone();

        // 2. assistant 的回复原样入历史（text 和 tool_use block 都在里面）。
        //    clone 是因为后面第 4 步还要遍历 resp.content 执行工具
        messages.push(Message::assistant_blocks(resp.content.clone()));

        // 3. 模型没调工具 → 任务结束，退出循环
        if stop_reason.as_deref() != Some("tool_use") {
            return Ok(());
        }

        // 4. 模型调了工具 → 逐个执行，收集结果。
        //    一个回复里可能有多个 tool_use（模型可逻辑并行请求多个，这里顺序执行），
        //    对应的 tool_result 必须一个不少地放在紧随其后的同一条 user 消息里。
        //    match 分发：编译器会穷尽所有工具名，忘加分支编译不过。
        let mut results: Vec<ContentBlock> = Vec::new();
        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                // ── match 分发 ──
                let output = match name.as_str() {
                    "bash" => serde_json::from_value::<BashInput>(input.clone())
                        .map(run_bash)
                        .unwrap_or_else(|e| format!("Error: invalid bash params: {e}")),
                    "read_file" => serde_json::from_value::<ReadInput>(input.clone())
                        .map(run_read)
                        .unwrap_or_else(|e| format!("Error: invalid read_file params: {e}")),
                    "write_file" => serde_json::from_value::<WriteInput>(input.clone())
                        .map(run_write)
                        .unwrap_or_else(|e| format!("Error: invalid write_file params: {e}")),
                    "edit_file" => serde_json::from_value::<EditInput>(input.clone())
                        .map(run_edit)
                        .unwrap_or_else(|e| format!("Error: invalid edit_file params: {e}")),
                    "glob" => serde_json::from_value::<GlobInput>(input.clone())
                        .map(run_glob)
                        .unwrap_or_else(|e| format!("Error: invalid glob params: {e}")),
                    other => format!("Error: unknown tool '{other}'"),
                };

                println!("\x1b[33m> {name}\x1b[0m");
                // 终端只打印前 1000 字符防刷屏（按整行截断 + "..."），
                // 给模型的 content 是完整输出
                let preview = truncate_lines(&output, 1000);
                if !preview.is_empty() {
                    println!("{preview}");
                }

                results.push(ContentBlock::ToolResult {
                    tool_use_id: id.clone(),
                    content: output,
                });
            }
        }

        // 5. 结果回灌进历史，循环继续 —— 模型下一轮会"看到"工具输出
        messages.push(Message::user_tool_results(results));
    }
}

// ── 配置与入口（同 s01） ─────────────────────────────────────────────────

struct Config {
    /// API 端点：官方 https://api.anthropic.com 或第三方兼容网关
    base_url: String,
    /// x-api-key 认证（网关和官方都支持）
    api_key: Option<String>,
    /// Authorization: Bearer 认证（仅官方 API 且未设网关时生效）
    auth_token: Option<String>,
    /// 模型 ID，必填（如 claude-sonnet-4-6 / deepseek-v4-pro）
    model: String,
    /// system prompt，运行时拼入当前工作目录
    system: String,
    /// 思考强度：EFFORT_LEVEL=low/medium/high/xhigh/max，不设置则请求体不带 output_config
    effort: Option<String>,
    /// 输出 token 上限：MAX_TOKENS 环境变量，默认 8000
    max_tokens: u32,
    /// anthropic-beta 头透传（如 context-1m-2025-08-07 开官方 1M 上下文）
    beta: Option<String>,
    /// 调试开关：环境变量 S01_DEBUG=1 时打印每次 API 调用的原始请求/响应
    debug: bool,
}

/// 从环境/.env 读配置，逻辑对齐 Python 版：
///   - 设了 ANTHROPIC_BASE_URL（第三方网关）时忽略 AUTH_TOKEN，统一用 x-api-key
///   - MODEL_ID 必填
fn load_config() -> Result<Config, String> {
    // cargo run -p 时工作目录是 rust/，所以当前目录和上级目录的 .env 都试
    dotenvy::from_filename_override(".env").ok();
    dotenvy::from_filename_override("../.env").ok();

    let base_url = env::var("ANTHROPIC_BASE_URL")
        .unwrap_or_else(|_| "https://api.anthropic.com".to_string());
    let using_gateway = env::var("ANTHROPIC_BASE_URL").is_ok();

    let model = env::var("MODEL_ID")
        .map_err(|_| "缺少 MODEL_ID 环境变量，请检查 .env（参考 .env.example）".to_string())?;

    let cwd = env::current_dir().map_err(|e| e.to_string())?;

    Ok(Config {
        base_url,
        api_key: env::var("ANTHROPIC_API_KEY").ok(),
        auth_token: if using_gateway {
            None // 对齐 Python 版：base_url 存在时 pop 掉 AUTH_TOKEN
        } else {
            env::var("ANTHROPIC_AUTH_TOKEN").ok()
        },
        model,
        system: format!(
            "You are a coding agent at {}. Use tools to solve tasks. Act, don't explain.",
            cwd.display()
        ),
        effort: env::var("EFFORT_LEVEL")
            .ok()
            .map(|v| v.trim().to_lowercase())
            .filter(|v| !v.is_empty()),
        max_tokens: env::var("MAX_TOKENS")
            .ok()
            .and_then(|v| v.parse::<u32>().ok())
            .unwrap_or(8000),
        beta: env::var("ANTHROPIC_BETA").ok().filter(|v| !v.is_empty()),
        debug: matches!(
            env::var("S01_DEBUG").as_deref(),
            Ok("1") | Ok("true")
        ),
    })
}

/// 交互式 REPL：读一行 → 追加进 history → 跑 agent_loop → 打印最终回复。
/// history 跨轮保留，所以有多轮对话记忆。
fn main() {
    let cfg = match load_config() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("配置错误: {e}");
            std::process::exit(1);
        }
    };
    let http = reqwest::blocking::Client::builder()
        // 总超时：reqwest blocking 默认无限等待，网关 hang 住会永远卡死。
        // 300s 覆盖长生成；连接超时单独收紧，快速暴露网络不通。
        .timeout(Duration::from_secs(300))
        .connect_timeout(Duration::from_secs(10))
        .build()
        .expect("build http client");

    println!("s02: Tool Use — 在 s01 基础上加了 4 个工具");
    println!("输入问题，回车发送。输入 q 退出。\n");

    let mut history: Vec<Message> = Vec::new();
    let stdin = io::stdin();

    loop {
        print!("\x1b[36ms02 >> \x1b[0m");
        io::stdout().flush().ok();

        let mut line = String::new();
        match stdin.lock().read_line(&mut line) {
            Ok(0) => break, // EOF (Ctrl-D)
            Ok(_) => {}
            Err(_) => break,
        }
        let query = line.trim();
        // 空行忽略；只有显式输入 q / exit 才退出
        if query.is_empty() {
            continue;
        }
        if query.eq_ignore_ascii_case("q") || query.eq_ignore_ascii_case("exit") {
            break;
        }

        history.push(Message::user_text(query));

        match agent_loop(&http, &cfg, &mut history) {
            Ok(()) => {
                // 打印模型最后的文本回复（history 末尾那条 assistant 消息）
                if let Some(last) = history.last() {
                    if let MessageContent::Blocks(blocks) = &last.content {
                        for block in blocks {
                            if let ContentBlock::Text { text } = block {
                                println!("{text}");
                            }
                        }
                    }
                }
                println!();
            }
            Err(e) => {
                // 出错时把刚才那条 user 输入弹出，避免历史里留下
                // "user 问了一句但 assistant 没回答"的破损状态
                history.pop();
                eprintln!("Error: {e}\n");
            }
        }
    }
}

// ── 单元测试 ─────────────────────────────────────────────────────────────
//
// 只测不依赖网络的纯逻辑：截断函数、serde 契约模型、黑名单、文件 I/O、glob。
// API 调用和 REPL 靠 S01_DEBUG 的实测 trace 验证（见 README）。
#[cfg(test)]
mod tests {
    use super::*;

    // ── truncate_lines（从 s01 携入） ──

    #[test]
    fn truncate_under_limit_unchanged() {
        let text = "line1\nline2\nline3";
        assert_eq!(truncate_lines(text, 1000), text);
    }

    #[test]
    fn truncate_cuts_at_line_boundary() {
        let text = "aaaaaaaaa\nbbbbbbbbb\nccccccccc";
        let out = truncate_lines(text, 25);
        assert_eq!(out, "aaaaaaaaa\nbbbbbbbbb\n...");
    }

    #[test]
    fn truncate_single_long_line_fallback() {
        let text = "一二三四五六七八九十".repeat(10);
        let out = truncate_lines(&text, 20);
        assert!(out.ends_with("..."));
        assert_eq!(out.chars().count(), 24);
        assert!(out.starts_with("一二三四五六七八九十"));
    }

    // ── serde 契约模型 ──

    #[test]
    fn user_text_message_serializes_as_plain_string() {
        let msg = Message::user_text("hello");
        let json = serde_json::to_value(&msg).unwrap();
        assert_eq!(json, serde_json::json!({"role": "user", "content": "hello"}));
    }

    #[test]
    fn thinking_signature_survives_round_trip() {
        let raw = r#"{"type":"thinking","thinking":"hmm","signature":"sig-123"}"#;
        let block: ContentBlock = serde_json::from_str(raw).unwrap();
        let out = serde_json::to_value(&block).unwrap();
        assert_eq!(out["thinking"], "hmm");
        assert_eq!(out["signature"], "sig-123");
    }

    #[test]
    fn tool_use_deserializes_from_api_response() {
        let raw = r#"{"type":"tool_use","id":"call_1","name":"bash","input":{"command":"ls"}}"#;
        let block: ContentBlock = serde_json::from_str(raw).unwrap();
        match block {
            ContentBlock::ToolUse { id, name, input } => {
                assert_eq!(id, "call_1");
                assert_eq!(name, "bash");
                assert_eq!(input["command"], "ls");
            }
            other => panic!("expected ToolUse, got {other:?}"),
        }
    }

    #[test]
    fn tool_result_serializes_into_user_message() {
        let msg = Message::user_tool_results(vec![ContentBlock::ToolResult {
            tool_use_id: "call_1".into(),
            content: "ok".into(),
        }]);
        let json = serde_json::to_value(&msg).unwrap();
        assert_eq!(json["role"], "user");
        assert_eq!(json["content"][0]["type"], "tool_result");
        assert_eq!(json["content"][0]["tool_use_id"], "call_1");
    }

    // ── bash ──

    #[test]
    fn dangerous_command_blocked() {
        assert_eq!(
            run_bash(BashInput { command: "rm -rf / --no-preserve-root".into() }),
            "Error: Dangerous command blocked"
        );
        assert!(run_bash(BashInput { command: "sudo ls".into() }).starts_with("Error: Dangerous"));
    }

    #[test]
    fn run_bash_captures_output() {
        assert_eq!(run_bash(BashInput { command: "echo hello".into() }), "hello");
    }

    #[test]
    fn run_bash_empty_output_marker() {
        assert_eq!(run_bash(BashInput { command: "true".into() }), "(no output)");
    }

    // ── read_file ──

    #[test]
    fn read_nonexistent_file_returns_error() {
        let out = run_read(ReadInput { path: "/_nope_".into(), limit: None });
        assert!(out.starts_with("Error:"));
    }

    #[test]
    fn read_file_with_limit() {
        let name = "_s02_read_limit.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "a\nb\nc\nd".into() });
        let out = run_read(ReadInput { path: name.into(), limit: Some(2) });
        assert_eq!(out, "a\nb\n... (2 more lines)");
        let _ = std::fs::remove_file(name);
    }

    // ── safe_path ──

    #[test]
    fn safe_path_rejects_escape() {
        let result = safe_path("../");
        assert!(result.is_err());
        assert!(result.unwrap_err().starts_with("Error: Path escapes"));
    }

    // ── write / read round trip ──

    #[test]
    fn write_and_read_temporary_file() {
        let name = "_s02_t.tmp";
        let _ = std::fs::remove_file(name);
        assert_eq!(
            run_write(WriteInput { path: name.into(), content: "hello s02".into() }),
            "Wrote 9 bytes to _s02_t.tmp"
        );
        let out = run_read(ReadInput { path: name.into(), limit: None });
        assert_eq!(out, "hello s02");
        let _ = std::fs::remove_file(name);
    }

    // ── edit_file ──

    #[test]
    fn edit_nonexistent_text_returns_error() {
        let name = "_s02_e.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "line1\nline2".into() });
        let out = run_edit(EditInput { path: name.into(), old_text: "NOTHERE".into(), new_text: "".into() });
        assert!(out.starts_with("Error: text not found"));
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn edit_replaces_first_occurrence() {
        let name = "_s02_e2.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "aaa\nbbb\naaa".into() });
        run_edit(EditInput { path: name.into(), old_text: "aaa".into(), new_text: "xxx".into() });
        let content = run_read(ReadInput { path: name.into(), limit: None });
        assert_eq!(content, "xxx\nbbb\naaa");
        let _ = std::fs::remove_file(name);
    }

    // ── glob ──

    #[test]
    fn glob_no_matches() {
        let out = run_glob(GlobInput { pattern: "ZZZZZZZZ_NOMATCH".into() });
        assert_eq!(out, "(no matches)");
    }

    #[test]
    fn glob_matches_something() {
        let out = run_glob(GlobInput { pattern: "src/*.rs".into() });
        assert!(out.contains("main.rs"));
    }


    /// 回归测试：字符串前缀判断会把 /tmp/ws2 误认为 /tmp/ws 的子路径（Gate 2 绕过）。
    #[test]
    fn workspace_check_rejects_sibling_prefix() {
        let cwd = Path::new("/tmp/ws");
        assert!(is_within_workspace(&Path::new("/tmp/ws/file.txt"), &cwd));
        assert!(is_within_workspace(&cwd, &cwd));
        assert!(!is_within_workspace(&Path::new("/tmp/ws2/secret.txt"), &cwd));
        assert!(!is_within_workspace(&Path::new("/tmp"), &cwd));
    }
}
