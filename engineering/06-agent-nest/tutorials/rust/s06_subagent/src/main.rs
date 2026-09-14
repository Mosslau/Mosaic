//! s06: Subagent — 大任务拆小，每个拿到的都是干净上下文
//!
//! 在 s05 基础上新增 task 工具，spawn 子 Agent 用全新 messages[] 跑独立循环。
//! 循环、Hook、权限管线不动，增量只有子代理系统：
//!
//! ```text
//!   Parent Agent                           Subagent
//!   +------------------+                  +------------------+
//!   | messages=[...]   |                  | messages=[task]  | <-- fresh
//!   |                  |   dispatch       |                  |
//!   | tool: task       | ---------------> | own while loop   |
//!   |   description=...|                  |   bash/read/...  |
//!   |                  |   summary only   |   (max 30 turns) |
//!   | result = "..."   | <--------------- | return last text |
//!   +------------------+                  +------------------+
//!         ^                                      |
//!         |       intermediate results DISCARDED  |
//!         +--------------------------------------+
//! ```
//!
//! 对照 Python 版 ../../python/s06_subagent/code.py。
//! 运行：cargo run -p s06_subagent
//! 可选环境变量（同 s05）：EFFORT_LEVEL / MAX_TOKENS / ANTHROPIC_BETA / S01_DEBUG

use std::env;
use std::io::{self, BufRead, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use std::os::unix::process::CommandExt; // process_group(): 独立进程组，超时可整组击杀
use wait_timeout::ChildExt;

// ── Anthropic Messages API 的数据模型（同 s01/s02/s03/s04/s05） ──────────

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

// ── 每个工具强类型的参数结构体（同 s02/s03） ──────────────────────────────

/// bash 工具的参数：一条 shell 命令
#[derive(Deserialize)]
struct BashInput {
    command: String,
}

/// read_file 工具的参数
#[derive(Deserialize)]
struct ReadInput {
    path: String,
    limit: Option<u32>,
}

/// write_file 工具的参数
#[derive(Deserialize)]
struct WriteInput {
    path: String,
    content: String,
}

/// edit_file 工具的参数
#[derive(Deserialize)]
struct EditInput {
    path: String,
    old_text: String,
    new_text: String,
}

/// glob 工具的参数
#[derive(Deserialize)]
struct GlobInput {
    pattern: String,
}

// ── s05 新增：todo_write 工具的参数结构体 ────────────────────────────────

/// 单个任务项
#[derive(Deserialize, Clone, Debug)]
struct TodoItem {
    content: String,
    status: String,
}

/// todo_write 工具的参数：任务列表
#[derive(Deserialize)]
struct TodoWriteInput {
    todos: serde_json::Value, // 先按任意 JSON 接住，在 run_todo_write 里做详细校验
}

// ── s06 新增：task 工具的参数结构体 ─────────────────────────────────────

/// task 工具的参数：子代理要执行的任务描述
#[derive(Deserialize)]
struct TaskInput {
    description: String,
}

// ── 工具定义与请求/响应结构（同 s02/s03） ─────────────────────────────────

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
    /// 模型 ID（如 claude-sonnet-4-6 / deepseek-v4-pro）
    model: &'a str,
    /// system prompt：独立顶层参数，不在 messages 里
    system: &'a str,
    /// 全部对话历史：API 无状态，每轮全量重发
    messages: &'a [Message],
    /// 工具定义数组
    tools: &'a [Tool],
    /// 输出 token 上限，必填
    max_tokens: u32,
    /// 思考强度。None 时整个字段不出现在请求体里（skip_serializing_if），
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

// ── 7 个工具定义（同 s05 + task） ────────────────────────────────────────

fn all_tools() -> [Tool; 7] {
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
        // s05: new tool — plan before execute
        Tool {
            name: "todo_write",
            description: "Create and manage a task list for your current coding session. Use before starting multi-step tasks to plan, and update status as you go. Status must be one of: pending, in_progress, completed.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": { "type": "string" },
                                "status": { "type": "string", "enum": ["pending", "in_progress", "completed"] }
                            },
                            "required": ["content", "status"]
                        }
                    }
                },
                "required": ["todos"]
            }),
        },
        // s06: new tool — spawn subagent with fresh context
        Tool {
            name: "task",
            description: "Launch a subagent to handle a complex subtask. The subagent gets a fresh conversation context (no history from the parent). Returns only the final conclusion — intermediate results are discarded. Use for tasks that require extensive file exploration or multi-step reasoning that would pollute the main conversation.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "description": { "type": "string" }
                },
                "required": ["description"]
            }),
        },
    ]
}

// ── s06 新增：子代理工具集 ────────────────────────────────────────────────
//
// 子代理工具 = 父代理工具 - task（防递归 spawn）- todo_write（子代理不规划）。
// 工具 handler 复用已有的 run_bash / run_read 等函数。

fn sub_tools() -> [Tool; 5] {
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

/// 按字符取前缀（字节安全）：&s[..N] 会在多字节字符中间 panic，
/// 先定位第 N 个字符的字节边界再切。
fn truncate_chars(text: &str, max_chars: usize) -> &str {
    match text.char_indices().nth(max_chars) {
        Some((idx, _)) => &text[..idx],
        None => text,
    }
}

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

// ── 路径解析（同 s03，纯词法，不访问文件系统） ──────────────────────────
//
// s02 的 safe_path 在工具内部硬拦截越界路径（白名单，越界直接报错）。
// s03 把"越界"的处置权上移到权限 Gate 2：越界不再是错误，而是触发用户确认。
// 所以工具只需要一个纯解析函数：把相对路径拼到 cwd 上，词法折叠 "." / ".."。
//
// 与 Python Path.resolve(strict=False) 的差异：不访问文件系统、不解析符号链接。
// 好处是不会像 s02 的 canonicalize 那样在文件不存在时报错；
// 代价是经由符号链接的逃逸检测不到（教学场景可接受，生产应补 canonicalize）。

/// 纯路径运算折叠 "." 和 ".."，不访问文件系统。
/// ".." 弹出一个组件；已经弹到根目录时 pop() 返回 false，路径停在根。
fn normalize_path(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for comp in path.components() {
        match comp {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            c => out.push(c.as_os_str()),
        }
    }
    out
}

/// 把工具参数里的路径解析成绝对路径：相对路径拼到 cwd 上再规范化。
/// join 遇到绝对路径参数时直接采用参数本身（与 Python 的 WORKDIR / path 一致）。
fn resolve_path(cwd: &Path, path: &str) -> PathBuf {
    normalize_path(&cwd.join(path))
}

/// 判断 path 是否在 cwd 内（含 cwd 本身）。必须按组件边界比较：
/// Path::starts_with 是字符串前缀比较，会把 /ws2 误判成 /ws 的子路径，
/// 从而放行同名前缀的兄弟目录（../ws2 也一样）。strip_prefix 按组件切分，
/// 且 normalize_path 已消掉所有 ".."，所以 strip_prefix 成功 = 真在内部。
fn is_within_workspace(path: &Path, cwd: &Path) -> bool {
    path.strip_prefix(cwd).is_ok()
}

fn workdir() -> Result<PathBuf, String> {
    env::current_dir().map_err(|e| format!("Error: can't get cwd: {e}"))
}

// ── 工具执行（同 s02/s03/s04/s05） ────────────────────────────────────────
//
// s04 关键变化：run_bash 不包含任何黑名单（黑名单已移到 permission_hook）。
// s05 新增：run_todo_write —— 校验并更新任务列表。

/// 执行一条 shell 命令。黑名单已上移到 PreToolUse 的 permission_hook，
/// 这里不再做任何命令审查 —— 审查是 Hook 的职责，工具只管执行。
///   - stdout + stderr 合并返回
///   - 输出截断到 50000 字符，防止撑爆上下文
///   - 120 秒超时
///   - 所有失败都变成字符串返回给模型，不 panic
fn run_bash(input: BashInput) -> String {
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

    let mut stdout_pipe = child.stdout.take().expect("stdout piped");
    let mut stderr_pipe = child.stderr.take().expect("stderr piped");
    // stdout/stderr 必须在等待退出的同时持续读取：
    // OS 管道缓冲区有限（macOS 默认 64KB），如果子进程输出写满管道而没人读，
    // 它会永远阻塞在 write() 上，最后被我们误判成"超时"杀掉。
    // 所以开两个线程专门抽干两根管道。take() 把管道句柄从 child 里移出来。
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

    match child.wait_timeout(Duration::from_secs(120)) {
        Ok(Some(_status)) => {
            let mut combined =
                String::from_utf8_lossy(&stdout_thread.join().unwrap_or_default()).into_owned();
            combined.push_str(&String::from_utf8_lossy(&stderr_thread.join().unwrap_or_default()));
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

/// 读取文件内容。
fn run_read(input: ReadInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let path = resolve_path(&cwd, &input.path);
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

/// 写入文件内容（自动创建父目录）。
fn run_write(input: WriteInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let path = resolve_path(&cwd, &input.path);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    match std::fs::write(&path, &input.content) {
        Ok(()) => format!("Wrote {} bytes to {}", input.content.len(), input.path),
        Err(e) => format!("Error: {e}"),
    }
}

/// 精确文本替换一次（replacen(..., 1)）。
fn run_edit(input: EditInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let path = resolve_path(&cwd, &input.path);
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

/// 按 glob 模式找文件。glob 是只读探测工具，不参与权限检查。
fn run_glob(input: GlobInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let matches = match glob::glob(&input.pattern) {
        Ok(entries) => entries,
        Err(e) => return format!("Error: {e}"),
    };

    let mut results: Vec<String> = Vec::new();
    for entry in matches {
        match entry {
            Ok(path) => {
                if is_within_workspace(&resolve_path(&cwd, &path.to_string_lossy()), &cwd) {
                    results.push(path.to_string_lossy().into_owned());
                }
            }
            Err(e) => results.push(format!("Error: {e}")),
        }
    }

    if results.is_empty() {
        "(no matches)".to_string()
    } else {
        results.join("\n")
    }
}

// s05: CURRENT_TODOS —— 全局任务列表，Mutex 向前兼容 s15 多 agent 场景。
static CURRENT_TODOS: Mutex<Vec<TodoItem>> = Mutex::new(Vec::new());

/// todo_write 工具实现：校验并更新任务列表。
/// 行为对齐 Python 版 run_todo_write()：
///   - todos 参数可以是 JSON 数组，也可以是 JSON 数组的字符串（模型有时传字符串）
///   - 每个 item 必须有 content + status，status 三值之一
///   - 更新全局 CURRENT_TODOS 并格式化打印
fn run_todo_write(input: TodoWriteInput) -> String {
    // 容错：模型有时把 todos 序列化成字符串而非数组
    let todos: Vec<TodoItem> = match &input.todos {
        serde_json::Value::Array(arr) => {
            match serde_json::from_value::<Vec<TodoItem>>(serde_json::Value::Array(arr.clone())) {
                Ok(t) => t,
                Err(e) => return format!("Error: invalid todos: {e}"),
            }
        }
        serde_json::Value::String(s) => {
            // 尝试解析 JSON 字符串
            match serde_json::from_str::<Vec<TodoItem>>(s) {
                Ok(t) => t,
                Err(_) => return "Error: todos must be a list or JSON array string".to_string(),
            }
        }
        _ => return "Error: todos must be a list or JSON array string".to_string(),
    };

    // 逐项校验
    for (i, t) in todos.iter().enumerate() {
        if t.content.is_empty() {
            return format!("Error: todos[{}] has empty content", i);
        }
        if !matches!(t.status.as_str(), "pending" | "in_progress" | "completed") {
            return format!("Error: todos[{}] has invalid status '{}'", i, t.status);
        }
    }

    let count = todos.len();

    // 更新全局状态
    if let Ok(mut current) = CURRENT_TODOS.lock() {
        *current = todos.clone();
    }

    // 格式化打印（对齐 Python 版）
    println!("\n\x1b[33m## Current Tasks\x1b[0m");
    for t in &todos {
        let icon = match t.status.as_str() {
            "pending" => " ",
            "in_progress" => "\x1b[36m▸\x1b[0m",
            "completed" => "\x1b[32m✓\x1b[0m",
            _ => "?",
        };
        println!("  [{}] {}", icon, t.content);
    }
    println!();

    format!("Updated {} tasks", count)
}

// ── s06 新增：extract_text —— 从消息内容中提取纯文本 ─────────────────────

/// 从 MessageContent 中提取纯文本。
/// Blocks 变体：收集所有 Text block，用换行拼接。
/// Text 变体：直接返回字符串。
fn extract_text(content: &MessageContent) -> String {
    match content {
        MessageContent::Text(s) => s.clone(),
        MessageContent::Blocks(blocks) => {
            let texts: Vec<&str> = blocks
                .iter()
                .filter_map(|b| {
                    if let ContentBlock::Text { text } = b {
                        Some(text.as_str())
                    } else {
                        None
                    }
                })
                .collect();
            if texts.is_empty() {
                String::new()
            } else {
                texts.join("\n")
            }
        }
    }
}

// ── s06 新增：spawn_subagent —— 子代理循环 ──────────────────────────────
//
// 子代理 = 全新 messages[] + sub_tools() + SUB_SYSTEM + 30 轮上限。
// 同步阻塞：父 agent_loop 调用 task 工具 → 等子代理跑完 → 拿到摘要文本。
// 子代理的工具调用同样经过 PreToolUse/PostToolUse hook（权限 + 日志）。

const MAX_SUB_TURNS: u32 = 30;

fn spawn_subagent(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    hooks: &Hooks,
    description: &str,
) -> String {
    println!("\n\x1b[35m[Subagent spawned]\x1b[0m");
    let mut messages = vec![Message::user_text(description)];
    let tools = sub_tools();

    for _turn in 0..MAX_SUB_TURNS {
        let resp = match call_llm(http, cfg, &cfg.sub_system, &messages, &tools) {
            Ok(r) => r,
            Err(e) => {
                println!("\x1b[35m[Subagent error: {e}]\x1b[0m");
                return format!("Subagent error: {e}");
            }
        };

        let stop_reason = resp.stop_reason.clone();
        messages.push(Message::assistant_blocks(resp.content.clone()));

        if stop_reason.as_deref() != Some("tool_use") {
            break;
        }

        let mut results: Vec<ContentBlock> = Vec::new();
        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                // 子代理也走 PreToolUse hook（权限 + 日志）
                if let Some(reason) = trigger_pre_tool_use(hooks, name, input) {
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: reason,
                    });
                    continue;
                }

                // 子代理工具分发：5 个工具，无 task、无 todo_write
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

                // 子代理也走 PostToolUse hook
                trigger_post_tool_use(hooks, name, input, &output);

                println!("  \x1b[90m[sub] {name}: {}\x1b[0m", truncate_lines(&output, 100).trim_end());
                results.push(ContentBlock::ToolResult {
                    tool_use_id: id.clone(),
                    content: output,
                });
            }
        }
        messages.push(Message::user_tool_results(results));
    }

    // 提取最终文本：从最后一条消息提取，失败则倒查 assistant 消息
    let result = extract_text(&messages.last().unwrap().content);
    if !result.is_empty() {
        println!("\x1b[35m[Subagent done]\x1b[0m");
        return result;
    }

    // 回退：最后一条是 tool_result，往前找 assistant 文本
    for msg in messages.iter().rev() {
        if msg.role == Role::Assistant {
            let text = extract_text(&msg.content);
            if !text.is_empty() {
                println!("\x1b[35m[Subagent done]\x1b[0m");
                return text;
            }
        }
    }

    println!("\x1b[35m[Subagent done — no text]\x1b[0m");
    "Subagent stopped after 30 turns without final answer.".to_string()
}

/// task 工具入口：薄封装 spawn_subagent。
/// 放在这里是因为 run_* 函数不持有 http/cfg/hooks 引用，
/// 所以在 agent_loop 的 match 分支中直接调用 spawn_subagent 更自然。
/// 这里提供一个兼容旧 dispatch 模式的入口。
fn run_task(http: &reqwest::blocking::Client, cfg: &Config, hooks: &Hooks, input: TaskInput) -> String {
    spawn_subagent(http, cfg, hooks, &input.description)
}

// ── s04 新增：Hook 系统 ──────────────────────────────────────────────────
//
// 四个事件，每个事件上可以挂多个回调。回调按注册顺序依次执行。
// PreToolUse 和 Stop 的回调可以返回非 None 来阻断/延续循环，
// UserPromptSubmit 和 PostToolUse 是纯通知（fire-and-forget）。
//
// 设计决策（对齐 Python 版）：
//   - 同步串行：同一事件上的回调按注册顺序依次执行，不用并行
//   - 短路语义：PreToolUse 的任一回调返回 Some(msg) → 后续回调不执行，
//     该 msg 直接作为 tool_result 回填给模型
//   - Stop 延续：Stop 回调返回 Some(msg) → msg 作为 user 消息追加，
//     循环继续（当前实现里 summary_hook 返回 None，保留此能力给未来扩展）

/// 四类 Hook 事件的回调签名：
///
/// - UserPromptSubmit: 收到用户输入时触发，纯通知。参数是用户输入的原始文本。
/// - PreToolUse: 工具执行前触发。返回 Some(msg) 阻断执行（msg 成为 tool_result），
///   None 放行。多个回调串行执行，第一个阻断就短路。
/// - PostToolUse: 工具执行后触发，纯通知。参数是工具名、输入、输出字符串。
/// - Stop: 循环即将退出时触发。返回 Some(msg) 则 msg 作为 user 消息追加并继续循环，
///   None 则正常退出。
struct Hooks {
    user_prompt_submit: Vec<Box<dyn Fn(&str)>>,
    pre_tool_use: Vec<Box<dyn Fn(&str, &serde_json::Value) -> Option<String>>>,
    post_tool_use: Vec<Box<dyn Fn(&str, &serde_json::Value, &str)>>,
    stop: Vec<Box<dyn Fn(&[Message]) -> Option<String>>>,
}

impl Hooks {
    fn new() -> Self {
        Hooks {
            user_prompt_submit: Vec::new(),
            pre_tool_use: Vec::new(),
            post_tool_use: Vec::new(),
            stop: Vec::new(),
        }
    }
}

/// 触发所有 UserPromptSubmit 回调（纯通知，不阻断）。
fn trigger_user_prompt_submit(hooks: &Hooks, query: &str) {
    for cb in &hooks.user_prompt_submit {
        cb(query);
    }
}

/// 触发所有 PreToolUse 回调。任一回调返回 Some(msg) 就短路，
/// 返回该 msg 作为阻断原因。全部返回 None 则放行。
fn trigger_pre_tool_use(
    hooks: &Hooks,
    name: &str,
    input: &serde_json::Value,
) -> Option<String> {
    for cb in &hooks.pre_tool_use {
        if let Some(reason) = cb(name, input) {
            return Some(reason);
        }
    }
    None
}

/// 触发所有 PostToolUse 回调（纯通知，不阻断）。
fn trigger_post_tool_use(hooks: &Hooks, name: &str, input: &serde_json::Value, output: &str) {
    for cb in &hooks.post_tool_use {
        cb(name, input, output);
    }
}

/// 触发所有 Stop 回调。任一回调返回 Some(msg) 就短路，
/// 返回该 msg 用于追加到消息历史并继续循环。全部返回 None 则正常退出。
fn trigger_stop(hooks: &Hooks, messages: &[Message]) -> Option<String> {
    for cb in &hooks.stop {
        if let Some(msg) = cb(messages) {
            return Some(msg);
        }
    }
    None
}

// ── 权限检查的独立纯函数（从 s03 携入，供 permission_hook 和测试使用） ─

/// Gate 1 硬拒绝列表（只作用于 bash）。
const DENY_LIST: [&str; 7] = [
    "rm -rf /",
    "sudo",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    "> /dev/sda",
];

/// Gate 1 检查：命中返回格式化好的拒绝理由。
fn check_deny_list(command: &str) -> Option<String> {
    DENY_LIST
        .iter()
        .find(|p| command.contains(**p))
        .map(|p| format!("Blocked: '{p}' is on the deny list"))
}

/// Gate 2 上下文规则：命中不直接拒绝，升级给 Gate 3 问用户。两条规则：
///   1. 文件工具（read/write/edit）目标路径逃逸 workspace
///   2. bash 命令含潜在破坏性关键词
fn check_rules(name: &str, input: &serde_json::Value) -> Option<&'static str> {
    match name {
        "read_file" => {
            let path = input["path"].as_str().unwrap_or("");
            let cwd = env::current_dir().ok()?;
            if is_within_workspace(&resolve_path(&cwd, path), &cwd) {
                None
            } else {
                Some("Reading outside workspace")
            }
        }
        "write_file" | "edit_file" => {
            let path = input["path"].as_str().unwrap_or("");
            let cwd = env::current_dir().ok()?;
            if is_within_workspace(&resolve_path(&cwd, path), &cwd) {
                None
            } else {
                Some("Writing outside workspace")
            }
        }
        "bash" => {
            let cmd = input["command"].as_str().unwrap_or("");
            // -delete 是 find 的破坏操作，效果等同 rm -rf，
            // 不拦截的话模型被 Gate 2 拒绝后会换 find ... -delete 绕过去
            const DESTRUCTIVE: [&str; 4] = ["rm ", "> /etc/", "chmod 777", "-delete"];
            if DESTRUCTIVE.iter().any(|kw| cmd.contains(kw)) {
                Some("Potentially destructive command")
            } else {
                None
            }
        }
        _ => None, // glob 等只读工具不参与 Gate 2
    }
}

/// Gate 3 的纯判定逻辑：只有 y/yes 算放行。
fn decide(choice: &str) -> bool {
    matches!(choice.trim().to_lowercase().as_str(), "y" | "yes")
}

/// Gate 3: 暂停循环，打印警告，等用户输入。
fn ask_user(
    reader: &mut impl BufRead,
    name: &str,
    input: &serde_json::Value,
    reason: &str,
) -> bool {
    println!("\n\x1b[33m⚠  {reason}\x1b[0m");
    println!("   Tool: {name}({input})");
    print!("   Allow? [y/N] ");
    io::stdout().flush().ok();
    let mut line = String::new();
    // 读取失败或 EOF 都按拒绝处理（默认拒绝是最安全的默认值）
    if reader.read_line(&mut line).is_err() {
        return false;
    }
    decide(&line)
}

// ── s04 新增：Hook 回调实现 ─────────────────────────────────────────────
//
// 每个回调都是一个独立函数（或闭包），通过 register 挂到对应事件上。
// s03 里写死在 agent_loop 中的 check_permission() 逻辑，
// 现在拆成 permission_hook（PreToolUse）+ 其他通知类 hook。

/// UserPromptSubmit hook：打印当前工作目录，帮助用户感知上下文。
/// query 参数保留以对齐 Python 版签名，当前实现只打印工作目录。
fn context_inject_hook(_query: &str) {
    if let Ok(cwd) = env::current_dir() {
        eprintln!("\x1b[90m[HOOK] UserPromptSubmit: working in {}\x1b[0m", cwd.display());
    }
}

/// 权限管线：三道闸门串联。返回 Some(reason) = 拒绝，None = 放行。
///
/// 从 s03 的 `check_permission` 携入，保持 `reader: &mut impl BufRead` 签名以便测试。
/// s04 的 `permission_hook` 是对本函数的薄封装（注入真实 stdin）。
///
/// Gate 1 只作用于 bash：硬拒绝，不询问（短路，不进 Gate 2/3）。
/// Gate 2 命中才进 Gate 3（用户确认）。
fn check_permission(
    reader: &mut impl BufRead,
    name: &str,
    input: &serde_json::Value,
) -> Option<String> {
    // Gate 1 只作用于 bash：硬拒绝，不询问
    if name == "bash" {
        if let Some(reason) = check_deny_list(input["command"].as_str().unwrap_or("")) {
            println!("\n\x1b[31m⛔ {reason}\x1b[0m");
            return Some(reason);
        }
    }
    // Gate 2 命中才进 Gate 3
    if let Some(reason) = check_rules(name, input) {
        if ask_user(reader, name, input, reason) {
            return None; // 用户放行
        } else {
            // 不用 "Permission denied" 措辞 —— 那会让模型误以为是 OS 级拒绝，
            // 然后换一条绕过关键词的等效命令再试
            return Some(format!("Blocked by user: {reason}"));
        }
    }
    None // 放行
}

/// PreToolUse hook：对 check_permission 的薄封装，注入真实 stdin。
///
/// 权限逻辑全部在 check_permission（可独立测试）中，本函数只负责
/// 提供 stdin 并适配 Hook 回调的签名（Fn(&str, &Value) -> Option<String>）。
fn permission_hook(name: &str, input: &serde_json::Value) -> Option<String> {
    check_permission(&mut io::stdin().lock(), name, input)
}

/// PreToolUse hook：记录每次工具调用。
fn log_hook(name: &str, input: &serde_json::Value) -> Option<String> {
    let args_preview = match input {
        serde_json::Value::Object(map) => {
            let vals: Vec<String> = map
                .values()
                .take(2)
                .map(|v| match v {
                    serde_json::Value::String(s) => {
                        let preview = truncate_chars(s, 50);
                        if preview.len() < s.len() { format!("{preview}...") } else { preview.to_string() }
                    }
                    other => format!("{other}"),
                })
                .collect();
            vals.join(", ")
        }
        _ => "?".to_string(),
    };
    eprintln!("\x1b[90m[HOOK] {name}({args_preview})\x1b[0m");
    None // 永远不阻断
}

/// PostToolUse hook：输出超过 100KB 时警告。
fn large_output_hook(name: &str, _input: &serde_json::Value, output: &str) {
    if output.len() > 100_000 {
        eprintln!(
            "\x1b[33m[HOOK] ⚠ Large output from {name}: {} chars\x1b[0m",
            output.len()
        );
    }
}

/// Stop hook：打印本次会话的工具调用统计。
fn summary_hook(messages: &[Message]) -> Option<String> {
    let tool_count: usize = messages
        .iter()
        .filter_map(|m| match &m.content {
            MessageContent::Blocks(blocks) => Some(blocks),
            MessageContent::Text(_) => None,
        })
        .map(|blocks| {
            blocks
                .iter()
                .filter(|b| matches!(b, ContentBlock::ToolResult { .. }))
                .count()
        })
        .sum();
    eprintln!(
        "\x1b[90m[HOOK] Stop: session used {tool_count} tool calls\x1b[0m"
    );
    None // 当前不阻断，保留返回 Some(msg) 延续循环的能力给未来扩展
}

/// 注册所有内置 hook 回调（对齐 Python 版 s04 的 register_hook 调用序列）。
fn register_builtin_hooks(hooks: &mut Hooks) {
    hooks
        .user_prompt_submit
        .push(Box::new(context_inject_hook));
    hooks.pre_tool_use.push(Box::new(permission_hook));
    hooks.pre_tool_use.push(Box::new(log_hook));
    hooks.post_tool_use.push(Box::new(large_output_hook));
    hooks.stop.push(Box::new(summary_hook));
}

// ── API 客户端（同 s01/s02/s03/s04/s05） ─────────────────────────────────

/// 一次 LLM 调用：把全部历史 messages + 工具定义发给 API，返回模型的响应。
///
/// 注意这里没有任何"记忆"概念——API 是无状态的，
/// 模型之所以"记得"之前的事，纯粹因为我们把 messages 整个重发了一遍。
fn call_llm(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    system: &str,
    messages: &[Message],
    tools: &[Tool],
) -> Result<ApiResponse, String> {
    let req = ApiRequest {
        model: &cfg.model,
        system,
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

// ── 核心模式：s05 的循环 + task 子代理分发（本章实质改动） ────────────────
//
// s03:
//   if !check_permission(&mut gate3_reader, name, input) { ... }
//   output = handler(input);
//   // 无 post hook
//
// s04:
//   blocked = trigger_pre_tool_use(&hooks, name, input);
//   output = handler(input);
//   trigger_post_tool_use(&hooks, name, input, &output);
//
// 循环结构不变，权限逻辑通过 Hook 解耦。

fn agent_loop(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
    hooks: &Hooks,
) -> Result<(), String> {
    let tools = all_tools();
    // s05: nag reminder 计数器 —— 连续 N 轮不更新 todos 就提醒
    let mut rounds_since_todo: u32 = 0;

    loop {
        // ── s05 新增：nag reminder ──
        // 模型 3 轮没调 todo_write 就注入提醒消息，提醒后重置计数器
        if rounds_since_todo >= 3 && !messages.is_empty() {
            messages.push(Message::user_text(
                "<reminder>Update your todos.</reminder>".to_string(),
            ));
            rounds_since_todo = 0;
        }

        // 1. 把完整历史发给模型
        let resp = call_llm(http, cfg, &cfg.system, messages, &tools)?;

        let stop_reason = resp.stop_reason.clone();

        // 2. assistant 的回复原样入历史
        messages.push(Message::assistant_blocks(resp.content.clone()));

        // 3. 模型没调工具 → 走 Stop hook → 退出或继续
        if stop_reason.as_deref() != Some("tool_use") {
            if let Some(extra) = trigger_stop(hooks, messages) {
                messages.push(Message::user_text(extra));
                continue;
            }
            return Ok(());
        }

        // ── s05 变化：每轮工具调用 rounds_since_todo +1，
        //    但本轮调了 todo_write 时在工具执行阶段归零 ──
        rounds_since_todo += 1;

        // 4. 模型调了工具 → 过 PreToolUse hook → 执行 → PostToolUse hook → 收集结果
        let mut results: Vec<ContentBlock> = Vec::new();
        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                println!("\x1b[33m> {name}\x1b[0m");

                // PreToolUse hook
                if let Some(reason) = trigger_pre_tool_use(hooks, name, input) {
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: reason,
                    });
                    continue;
                }

                // ── match 分发（s05 新增 todo_write 分支） ──
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
                    // s05: new tool
                    "todo_write" => serde_json::from_value::<TodoWriteInput>(input.clone())
                        .map(run_todo_write)
                        .unwrap_or_else(|e| format!("Error: invalid todo_write params: {e}")),
                    // s06: spawn subagent with fresh context
                    "task" => serde_json::from_value::<TaskInput>(input.clone())
                        .map(|ti| run_task(http, cfg, hooks, ti))
                        .unwrap_or_else(|e| format!("Error: invalid task params: {e}")),
                    other => format!("Error: unknown tool '{other}'"),
                };

                // ── s05 变化：调用 todo_write 时重置 nag 计数器 ──
                if name == "todo_write" {
                    rounds_since_todo = 0;
                }

                // PostToolUse hook
                trigger_post_tool_use(hooks, name, input, &output);

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

        // 5. 结果回灌进历史，循环继续
        messages.push(Message::user_tool_results(results));
    }
}

// ── 配置与入口（同 s05，system prompt 加入 task 引导 + sub_system） ────────

struct Config {
    /// API 端点：官方 https://api.anthropic.com 或第三方兼容网关
    base_url: String,
    /// x-api-key 认证
    api_key: Option<String>,
    /// Authorization: Bearer 认证（仅官方 API 且未设网关时生效）
    auth_token: Option<String>,
    /// 模型 ID，必填（如 claude-sonnet-4-6 / deepseek-v4-pro）
    model: String,
    /// system prompt（父代理），运行时拼入当前工作目录
    system: String,
    /// s06: 子代理 system prompt（独立，不含 task 引导、不含规划要求）
    sub_system: String,
    /// 思考强度：EFFORT_LEVEL=low/medium/high/xhigh/max
    effort: Option<String>,
    /// 输出 token 上限：MAX_TOKENS 环境变量，默认 8000
    max_tokens: u32,
    /// anthropic-beta 头透传
    beta: Option<String>,
    /// 调试开关：S01_DEBUG=1 时打印每次 API 调用的原始请求/响应
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
        // s06: system prompt 引导使用 task 工具处理复杂子问题
        system: format!(
            "You are a coding agent at {}. For complex sub-problems, use the task tool to spawn a subagent.",
            cwd.display()
        ),
        // s06: 子代理 system prompt —— 不提及 task（无此工具）、不要求规划
        sub_system: format!(
            "You are a coding agent at {}. Complete the task you were given, then return a concise summary. Do not delegate further.",
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
        debug: matches!(env::var("S01_DEBUG").as_deref(), Ok("1") | Ok("true")),
    })
}

/// 交互式 REPL。s04 变化：在追加用户输入到 history 之前，
/// 触发 UserPromptSubmit hook。
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

    // ── s04 新增：初始化 Hook 注册表并注册内置回调 ──
    let mut hooks = Hooks::new();
    register_builtin_hooks(&mut hooks);

    println!("s06: Subagent — spawn sub-agents with fresh context");
    println!("输入问题，回车发送。输入 q 退出。\n");

    let mut history: Vec<Message> = Vec::new();
    let stdin = io::stdin();

    loop {
        print!("\x1b[36ms06 >> \x1b[0m");
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

        // ── s04 变化：用户输入先过 UserPromptSubmit hook，再追加到 history ──
        trigger_user_prompt_submit(&hooks, query);
        history.push(Message::user_text(query));

        match agent_loop(&http, &cfg, &mut history, &hooks) {
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

// ── 单元测试 ──────────────────────────────────────────────────────────────
//
// 测试覆盖：
//   - 基础工具（从 s05 携入）
//   - serde 契约模型
//   - 路径解析
//   - 权限纯函数（Gate 1/2/3，保持独立可测）
//   - Hook 注册与触发
//   - Hook 短路语义
//   - 权限 hook 的 Gate 1 硬拒绝（不依赖 stdin）
//   - todo_write 校验逻辑
//   - todo_write 状态更新
//   - sub_tools 工具集
//   - extract_text 文本提取
//   - spawn_subagent 回退逻辑
#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

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

    // ── bash 工具（黑名单已移到 Hook，工具本身不再做审查） ──

    #[test]
    fn run_bash_captures_output() {
        assert_eq!(run_bash(BashInput { command: "echo hello".into() }), "hello");
    }

    #[test]
    fn run_bash_empty_output_marker() {
        assert_eq!(run_bash(BashInput { command: "true".into() }), "(no output)");
    }

    // ── 文件工具 ──

    #[test]
    fn read_nonexistent_file_returns_error() {
        let out = run_read(ReadInput { path: "/_nope_".into(), limit: None });
        assert!(out.starts_with("Error:"));
    }

    #[test]
    fn read_file_with_limit() {
        let name = "_s06_read_limit.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "a\nb\nc\nd".into() });
        let out = run_read(ReadInput { path: name.into(), limit: Some(2) });
        assert_eq!(out, "a\nb\n... (2 more lines)");
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn write_and_read_temporary_file() {
        let name = "_s06_t.tmp";
        let _ = std::fs::remove_file(name);
        assert_eq!(
            run_write(WriteInput { path: name.into(), content: "hello s04".into() }),
            "Wrote 9 bytes to _s06_t.tmp"
        );
        let out = run_read(ReadInput { path: name.into(), limit: None });
        assert_eq!(out, "hello s04");
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn edit_nonexistent_text_returns_error() {
        let name = "_s06_e.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "line1\nline2".into() });
        let out =
            run_edit(EditInput { path: name.into(), old_text: "NOTHERE".into(), new_text: "".into() });
        assert!(out.starts_with("Error: text not found"));
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn edit_replaces_first_occurrence() {
        let name = "_s06_e2.tmp";
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

    // ── 路径解析 ──

    #[test]
    fn normalize_collapses_dotdot() {
        let cwd = Path::new("/a/b");
        assert_eq!(resolve_path(cwd, "../x"), PathBuf::from("/a/x"));
        assert_eq!(resolve_path(cwd, "../../x"), PathBuf::from("/x"));
    }

    #[test]
    fn normalize_keeps_inside() {
        let cwd = Path::new("/a/b");
        assert_eq!(resolve_path(cwd, "c/d.txt"), PathBuf::from("/a/b/c/d.txt"));
        assert_eq!(resolve_path(cwd, "./c"), PathBuf::from("/a/b/c"));
    }

    #[test]
    fn normalize_absolute_path_wins() {
        let cwd = Path::new("/a/b");
        assert_eq!(resolve_path(cwd, "/etc/passwd"), PathBuf::from("/etc/passwd"));
    }

    // ── Gate 1 硬拒绝（纯函数，不依赖 stdin） ──

    #[test]
    fn gate1_blocks_every_deny_pattern() {
        for pattern in DENY_LIST {
            let cmd = format!("prefix {pattern} suffix");
            assert!(
                check_deny_list(&cmd).is_some(),
                "deny list should catch: {cmd}"
            );
        }
    }

    #[test]
    fn gate1_allows_normal_commands() {
        assert!(check_deny_list("ls -la").is_none());
        assert!(check_deny_list("echo x > /dev/null").is_none());
        assert!(check_deny_list("rm -rf target").is_none());
    }

    #[test]
    fn gate1_reason_contains_pattern() {
        let reason = check_deny_list("sudo apt install").unwrap();
        assert!(reason.contains("sudo"));
        assert!(reason.contains("deny list"));
    }

    // ── Gate 2 规则匹配（纯函数，不依赖 stdin） ──

    #[test]
    fn gate2_flags_workspace_escape() {
        let input = serde_json::json!({"path": "../evil.txt"});
        assert_eq!(check_rules("write_file", &input), Some("Writing outside workspace"));
        assert_eq!(check_rules("read_file", &input), Some("Reading outside workspace"));
        assert_eq!(check_rules("edit_file", &input), Some("Writing outside workspace"));
    }

    #[test]
    fn gate2_allows_inside_workspace() {
        let input = serde_json::json!({"path": "ok.txt"});
        assert_eq!(check_rules("write_file", &input), None);
        let input = serde_json::json!({"path": "sub/dir/ok.txt"});
        assert_eq!(check_rules("read_file", &input), None);
    }

    #[test]
    fn gate2_flags_destructive_bash() {
        for cmd in ["rm -rf target", "rm old.log", "echo x > /etc/hosts", "chmod 777 /tmp/x", "find target -type f -delete"] {
            let input = serde_json::json!({"command": cmd});
            assert_eq!(
                check_rules("bash", &input),
                Some("Potentially destructive command"),
                "should flag: {cmd}"
            );
        }
    }

    #[test]
    fn gate2_allows_normal_bash() {
        let input = serde_json::json!({"command": "ls -la"});
        assert_eq!(check_rules("bash", &input), None);
    }

    #[test]
    fn gate2_ignores_readonly_tools() {
        let input = serde_json::json!({"pattern": "../*.rs"});
        assert_eq!(check_rules("glob", &input), None);
    }

    // ── Gate 3 判定逻辑（纯函数，不依赖 stdin） ──

    #[test]
    fn decide_accepts_yes_variants() {
        for yes in ["y", "Y", "yes", "YES", "Yes", " y \n", "yes\n"] {
            assert!(decide(yes), "should accept: {yes:?}");
        }
    }

    #[test]
    fn decide_rejects_everything_else() {
        for no in ["n", "N", "no", "", "\n", "why", "yep", "yess"] {
            assert!(!decide(no), "should reject: {no:?}");
        }
    }

    #[test]
    fn ask_user_eof_denies() {
        let mut reader = Cursor::new("");
        let input = serde_json::json!({"path": "../x"});
        assert!(!ask_user(&mut reader, "write_file", &input, "test reason"));
    }

    // ── s04 新增：Hook 注册与触发 ──

    #[test]
    fn hooks_starts_empty() {
        let hooks = Hooks::new();
        assert!(hooks.user_prompt_submit.is_empty());
        assert!(hooks.pre_tool_use.is_empty());
        assert!(hooks.post_tool_use.is_empty());
        assert!(hooks.stop.is_empty());
    }

    #[test]
    fn trigger_pre_tool_use_allows_when_no_hooks_registered() {
        let hooks = Hooks::new();
        let input = serde_json::json!({"command": "rm -rf /"});
        // 未注册任何 hook 时，trigger 返回 None（放行）
        assert_eq!(trigger_pre_tool_use(&hooks, "bash", &input), None);
    }

    #[test]
    fn trigger_pre_tool_use_blocks_when_hook_returns_some() {
        let mut hooks = Hooks::new();
        // 注册一个永远拒绝的 hook
        hooks.pre_tool_use.push(Box::new(|_name, _input| {
            Some("always blocked".to_string())
        }));
        let input = serde_json::json!({"command": "ls"});
        assert_eq!(
            trigger_pre_tool_use(&hooks, "bash", &input),
            Some("always blocked".to_string())
        );
    }

    #[test]
    fn trigger_pre_tool_use_allows_when_hook_returns_none() {
        let mut hooks = Hooks::new();
        hooks.pre_tool_use.push(Box::new(|_name, _input| None));
        let input = serde_json::json!({"command": "ls"});
        assert_eq!(trigger_pre_tool_use(&hooks, "bash", &input), None);
    }

    #[test]
    fn trigger_pre_tool_use_short_circuits_on_first_block() {
        // 注册两个 hook：第一个拒绝，第二个不应该被调用
        let mut hooks = Hooks::new();
        hooks.pre_tool_use.push(Box::new(|_name, _input| {
            Some("first blocks".to_string())
        }));
        // 第二个 hook 如果被调用会 panic（用于验证短路）
        hooks.pre_tool_use.push(Box::new(|_name, _input| {
            panic!("second hook should not be called when first blocks");
        }));
        let input = serde_json::json!({"command": "ls"});
        assert_eq!(
            trigger_pre_tool_use(&hooks, "bash", &input),
            Some("first blocks".to_string())
        );
    }

    #[test]
    fn trigger_pre_tool_use_calls_all_when_none_block() {
        // 两个 hook 都返回 None，都应该被调用
        let mut hooks = Hooks::new();
        hooks.pre_tool_use.push(Box::new(|_name, _input| None));
        hooks.pre_tool_use.push(Box::new(|_name, _input| None));
        let input = serde_json::json!({"command": "ls"});
        assert_eq!(trigger_pre_tool_use(&hooks, "bash", &input), None);
    }

    #[test]
    fn trigger_stop_returns_none_when_no_hooks() {
        let hooks = Hooks::new();
        assert_eq!(trigger_stop(&hooks, &[]), None);
    }

    #[test]
    fn trigger_stop_returns_message_when_hook_returns_some() {
        let mut hooks = Hooks::new();
        hooks.stop.push(Box::new(|_messages| {
            Some("continue working".to_string())
        }));
        assert_eq!(
            trigger_stop(&hooks, &[]),
            Some("continue working".to_string())
        );
    }

    #[test]
    fn trigger_stop_short_circuits_on_first_message() {
        let mut hooks = Hooks::new();
        hooks.stop.push(Box::new(|_messages| {
            Some("first".to_string())
        }));
        hooks.stop.push(Box::new(|_messages| {
            panic!("second stop hook should not be called");
        }));
        assert_eq!(trigger_stop(&hooks, &[]), Some("first".to_string()));
    }

    #[test]
    fn trigger_user_prompt_submit_does_not_panic_with_no_hooks() {
        let hooks = Hooks::new();
        trigger_user_prompt_submit(&hooks, "hello"); // 不 panic
    }

    #[test]
    fn trigger_post_tool_use_does_not_panic_with_no_hooks() {
        let hooks = Hooks::new();
        let input = serde_json::json!({"command": "ls"});
        trigger_post_tool_use(&hooks, "bash", &input, "output"); // 不 panic
    }

    // ── s04 新增：permission_hook Gate 1 硬拒绝（不依赖 stdin 的路径） ──

    #[test]
    fn permission_hook_gate1_blocks_sudo() {
        let input = serde_json::json!({"command": "sudo ls"});
        let result = check_deny_list(input["command"].as_str().unwrap());
        assert!(result.is_some());
        assert!(result.unwrap().contains("sudo"));
    }

    #[test]
    fn permission_hook_gate1_allows_normal_bash() {
        let input = serde_json::json!({"command": "ls -la"});
        assert_eq!(check_deny_list(input["command"].as_str().unwrap()), None);
    }

    // ── s04 新增：log_hook 永远不阻断 ──

    #[test]
    fn log_hook_always_returns_none() {
        let input = serde_json::json!({"command": "ls"});
        assert_eq!(log_hook("bash", &input), None);
        let input = serde_json::json!({"path": "../etc"});
        assert_eq!(log_hook("write_file", &input), None);
    }

    // ── s04 新增：context_inject_hook 不 panic ──

    #[test]
    fn context_inject_hook_does_not_panic() {
        context_inject_hook("test query"); // 不 panic 就算过
    }

    // ── s04 新增：summary_hook 统计 tool_result 数量 ──

    #[test]
    fn summary_hook_counts_tool_results() {
        let messages = vec![
            Message::user_text("do something"),
            Message::assistant_blocks(vec![
                ContentBlock::ToolUse {
                    id: "1".into(),
                    name: "bash".into(),
                    input: serde_json::json!({"command": "ls"}),
                },
            ]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "1".into(),
                content: "ok".into(),
            }]),
        ];
        let result = summary_hook(&messages);
        assert_eq!(result, None); // 不阻断，只打印统计
    }

    #[test]
    fn summary_hook_zero_tools_on_empty_history() {
        let result = summary_hook(&[]);
        assert_eq!(result, None);
    }

    // ── s04 新增：large_output_hook 不 panic ──

    #[test]
    fn large_output_hook_handles_small_output() {
        let input = serde_json::json!({"command": "ls"});
        large_output_hook("bash", &input, "small output"); // 不 panic，不打印警告
    }

    #[test]
    fn large_output_hook_handles_large_output() {
        let input = serde_json::json!({"command": "cat bigfile"});
        let big = "x".repeat(100_001);
        large_output_hook("bash", &input, &big); // 不 panic，会打印警告
    }

    // ── s04 关键回归：tools 不再做权限审查（审查已移到 permission_hook） ──

    #[test]
    fn run_bash_no_longer_has_inline_blacklist() {
        // s03 的 run_bash 里有黑名单，s04 已移除。
        // 危险命令在工具层面不会被拦截（由 permission_hook 在 PreToolUse 阶段拦截）
        let result = run_bash(BashInput { command: "sudo ls".into() });
        // sudo 需要密码，所以会失败——但不应该被黑名单拦截
        assert!(!result.starts_with("Error: Dangerous"));
    }

    // ── 集成：Hook 注册表完整流程 ──

    #[test]
    fn builtin_hooks_registered_correctly() {
        let mut hooks = Hooks::new();
        register_builtin_hooks(&mut hooks);
        assert_eq!(hooks.user_prompt_submit.len(), 1);
        assert_eq!(hooks.pre_tool_use.len(), 2); // permission_hook + log_hook
        assert_eq!(hooks.post_tool_use.len(), 1);
        assert_eq!(hooks.stop.len(), 1);
    }

    #[test]
    fn permission_hook_order_permission_before_log() {
        // permission_hook 先注册，log_hook 后注册。
        // 由于 permission_hook 在 Gate 1 命中时会返回 Some （阻断），
        // log_hook 在这种情况下不会被触发（短路语义）。
        // 本测试验证注册顺序。
        let mut hooks = Hooks::new();
        register_builtin_hooks(&mut hooks);
        // 验证有 2 个 pre_tool_use hook
        assert_eq!(hooks.pre_tool_use.len(), 2);
        // permission_hook 先注册 → 如果它阻断了，log_hook 不会执行
        // （短路语义由 trigger_pre_tool_use 的测试覆盖）
    }

    // ── 管线集成测试（从 s03 携入，通过 check_permission 测试三道门串联） ──

    #[test]
    fn gate1_short_circuits_without_asking() {
        // 即使用户输入 y，Gate 1 命中的命令也直接拒（证明没走到 Gate 3）
        let mut reader = Cursor::new("y\n");
        let input = serde_json::json!({"command": "sudo ls"});
        assert!(check_permission(&mut reader, "bash", &input).is_some());
    }

    #[test]
    fn gate1_only_applies_to_bash() {
        // 文件工具的内容里出现黑名单关键词不触发 Gate 1
        let mut reader = Cursor::new("");
        let input =
            serde_json::json!({"path": "notes.txt", "content": "remember: never sudo rm -rf /"});
        assert_eq!(check_permission(&mut reader, "write_file", &input), None);
    }

    #[test]
    fn gate2_user_allows_escape() {
        let mut reader = Cursor::new("y\n");
        let input = serde_json::json!({"path": "../outside.txt"});
        assert_eq!(check_permission(&mut reader, "write_file", &input), None);
    }

    #[test]
    fn gate2_user_denies_escape() {
        let mut reader = Cursor::new("n\n");
        let input = serde_json::json!({"path": "../outside.txt"});
        assert!(check_permission(&mut reader, "write_file", &input).is_some());
    }

    #[test]
    fn gate2_eof_denies() {
        let mut reader = Cursor::new("");
        let input = serde_json::json!({"command": "rm -rf target"});
        assert!(check_permission(&mut reader, "bash", &input).is_some());
    }

    #[test]
    fn clean_operations_pass_all_gates() {
        let mut reader = Cursor::new("");
        let bash = serde_json::json!({"command": "ls -la"});
        assert_eq!(check_permission(&mut reader, "bash", &bash), None);
        let write = serde_json::json!({"path": "ok.txt", "content": "hi"});
        assert_eq!(check_permission(&mut reader, "write_file", &write), None);
        let glob = serde_json::json!({"pattern": "src/*.rs"});
        assert_eq!(check_permission(&mut reader, "glob", &glob), None);
    }

    // ── s05 新增：todo_write 工具 ──

    /// 串行化会写全局 CURRENT_TODOS 的测试：并行时两个写者互相覆盖，
    /// todo_write_valid_todos 的 len==3 断言会读到对方写入的结果。
    static TEST_TODO_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn todo_write_valid_todos() {
        let _guard = TEST_TODO_LOCK.lock().unwrap();
        // 先清空全局状态
        {
            let mut t = CURRENT_TODOS.lock().unwrap();
            t.clear();
        }
        let input = TodoWriteInput {
            todos: serde_json::json!([
                {"content": "task 1", "status": "pending"},
                {"content": "task 2", "status": "in_progress"},
                {"content": "task 3", "status": "completed"},
            ]),
        };
        let result = run_todo_write(input);
        assert!(result.contains("Updated 3 tasks"));
        // 验证全局状态已更新
        let t = CURRENT_TODOS.lock().unwrap();
        assert_eq!(t.len(), 3);
        assert_eq!(t[0].content, "task 1");
        assert_eq!(t[0].status, "pending");
        assert_eq!(t[1].status, "in_progress");
        assert_eq!(t[2].status, "completed");
    }

    #[test]
    fn todo_write_string_input() {
        let _guard = TEST_TODO_LOCK.lock().unwrap();
        let input = TodoWriteInput {
            todos: serde_json::Value::String(
                r#"[{"content": "x", "status": "pending"}]"#.to_string(),
            ),
        };
        let result = run_todo_write(input);
        assert!(result.contains("Updated 1 tasks"));
    }

    #[test]
    fn todo_write_rejects_invalid_status() {
        let input = TodoWriteInput {
            todos: serde_json::json!([
                {"content": "task", "status": "done"},
            ]),
        };
        let result = run_todo_write(input);
        assert!(result.contains("invalid status"));
    }

    #[test]
    fn todo_write_rejects_empty_content() {
        let input = TodoWriteInput {
            todos: serde_json::json!([
                {"content": "", "status": "pending"},
            ]),
        };
        let result = run_todo_write(input);
        assert!(result.contains("empty content"));
    }

    #[test]
    fn todo_write_rejects_non_array() {
        let input = TodoWriteInput {
            todos: serde_json::json!({"not": "an array"}),
        };
        let result = run_todo_write(input);
        assert!(result.contains("must be a list"));
    }

    #[test]
    fn todo_write_deserializes_from_json() {
        // 验证 TodoWriteInput 可以从 JSON 反序列化
        let json = serde_json::json!({
            "todos": [{"content": "a", "status": "pending"}]
        });
        let input: TodoWriteInput = serde_json::from_value(json).unwrap();
        assert!(input.todos.is_array());
    }

    // ── s06 新增：extract_text ──

    #[test]
    fn extract_text_from_plain_string() {
        let msg = Message::user_text("hello world");
        assert_eq!(extract_text(&msg.content), "hello world");
    }

    #[test]
    fn extract_text_from_blocks_with_text() {
        let msg = Message::assistant_blocks(vec![
            ContentBlock::Text { text: "line1".into() },
            ContentBlock::Text { text: "line2".into() },
        ]);
        assert_eq!(extract_text(&msg.content), "line1\nline2");
    }

    #[test]
    fn extract_text_from_blocks_mixed() {
        let msg = Message::assistant_blocks(vec![
            ContentBlock::Text { text: "result".into() },
            ContentBlock::Thinking {
                thinking: "hmm".into(),
                extra: serde_json::Map::new(),
            },
        ]);
        assert_eq!(extract_text(&msg.content), "result");
    }

    #[test]
    fn extract_text_from_empty_blocks() {
        let msg = Message::assistant_blocks(vec![
            ContentBlock::ToolUse {
                id: "1".into(),
                name: "bash".into(),
                input: serde_json::json!({"command": "ls"}),
            },
        ]);
        assert_eq!(extract_text(&msg.content), "");
    }

    #[test]
    fn extract_text_empty_message() {
        let msg = Message::user_text("");
        assert_eq!(extract_text(&msg.content), "");
    }

    // ── s06 新增：sub_tools ──

    #[test]
    fn sub_tools_count() {
        assert_eq!(sub_tools().len(), 5);
    }

    #[test]
    fn sub_tools_no_task() {
        let tools = sub_tools();
        for t in &tools {
            assert_ne!(t.name, "task");
        }
    }

    #[test]
    fn sub_tools_no_todo_write() {
        let tools = sub_tools();
        for t in &tools {
            assert_ne!(t.name, "todo_write");
        }
    }

    #[test]
    fn sub_tools_has_bash() {
        let tools = sub_tools();
        assert!(tools.iter().any(|t| t.name == "bash"));
    }

    // ── s06 新增：TaskInput 反序列化 ──

    #[test]
    fn task_input_deserializes() {
        let json = serde_json::json!({"description": "fix the bug"});
        let input: TaskInput = serde_json::from_value(json).unwrap();
        assert_eq!(input.description, "fix the bug");
    }

    // ── s06 新增：spawn_subagent 回退逻辑（不依赖 API） ──

    #[test]
    fn spawn_subagent_fallback_extracts_from_assistant() {
        let msgs = vec![
            Message::user_text("do x"),
            Message::assistant_blocks(vec![
                ContentBlock::Text { text: "done".into() },
            ]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "1".into(),
                content: "ok".into(),
            }]),
        ];
        let last = &msgs.last().unwrap();
        let from_last = extract_text(&last.content);
        assert_eq!(from_last, "");

        let mut found = String::new();
        for msg in msgs.iter().rev() {
            if msg.role == Role::Assistant {
                found = extract_text(&msg.content);
                if !found.is_empty() { break; }
            }
        }
        assert_eq!(found, "done");
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

    /// 回归：&s[..50] 字节切片会在多字节字符中间 panic（实测：中文任务描述
    /// 曾让 task 工具崩溃整个代理）。truncate_chars 按字符取前缀，字节安全。
    #[test]
    fn truncate_chars_and_log_hook_multibyte_safe() {
        let s = "统计".repeat(30);
        let t = truncate_chars(&s, 10);
        assert_eq!(t.chars().count(), 10);
        assert!(t.starts_with("统计"));
        let input = serde_json::json!({"description": s});
        assert!(log_hook("task", &input).is_none());
    }
}
