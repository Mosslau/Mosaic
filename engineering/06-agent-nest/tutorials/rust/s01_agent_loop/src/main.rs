//! s01: Agent Loop -- 一个循环就够了
//!
//! 整个 AI coding agent 的秘密，就在这一个模式里：
//!
//! ```text
//! while stop_reason == "tool_use":
//!     response = LLM(messages, tools)
//!     execute tools
//!     append results
//!
//! +----------+      +-------+      +---------+
//! |   User   | ---> |  LLM  | ---> |  Tool   |
//! |  prompt  |      |       |      | execute |
//! +----------+      +---+---+      +----+----+
//!                       ^               |
//!                       |   tool_result |
//!                       +---------------+
//!                       (loop continues)
//! ```
//!
//! 对照 Python 版 ../../python/s01_agent_loop/code.py。
//! Rust 版不用官方 SDK，直接用 reqwest 打 HTTP，更贴近 API 契约本身。
//!
//! 运行：
//!     在仓库根目录准备 .env（见 .env.example），然后
//!     cargo run -p s01_agent_loop
//!
//! 可选环境变量（详见 README.md）：
//!     EFFORT_LEVEL=low|medium|high|xhigh|max   思考强度（output_config.effort）
//!     MAX_TOKENS=8000                          输出 token 上限
//!     ANTHROPIC_BETA=...                       anthropic-beta 头透传（如 1M 上下文）
//!     S01_DEBUG=1                              打印每次 API 调用的原始请求/响应

use std::env;
use std::io::{self, BufRead, Read, Write};
use std::process::{Command, Stdio};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use std::os::unix::process::CommandExt; // process_group(): 独立进程组，超时可整组击杀
use wait_timeout::ChildExt; // 给 std::process::Child 扩展 wait_timeout() 方法

// ── Anthropic Messages API 的数据模型 ─────────────────────────────────────
//
// messages 结构是 API 契约（POST /v1/messages）定义的，不是我们可以自由设计的：
//   - role 只有 user / assistant 两种（system prompt 是请求的独立顶层字段）
//   - 必须 user 开头，两种 role 严格交替
//   - assistant 的 content 里放 text / tool_use block
//   - 工具执行结果必须以 tool_result block 的形式包在 user 消息里回灌

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

// ── 工具定义与请求/响应结构 ───────────────────────────────────────────────

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
    /// 模型 ID（如 claude-sonnet-4-6 / deepseek-v4-pro[1m]）
    model: &'a str,
    /// system prompt：独立顶层参数，不在 messages 里（与 OpenAI 格式的区别之一）
    system: &'a str,
    /// 全部对话历史：API 无状态，每轮全量重发
    messages: &'a [Message],
    /// 工具定义数组：模型只能通过这里的 schema 感知工具
    tools: &'a [Tool],
    /// 输出 token 上限，必填（Anthropic 无默认值，OpenAI 可选）
    max_tokens: u32,
    /// 思考强度（新版 adaptive thinking 的控制旋钮）。
    /// None 时整个字段不出现在请求体里（skip_serializing_if），
    /// 服务器按模型默认 effort 处理 —— 保持"未配置即被动"的行为
    #[serde(skip_serializing_if = "Option::is_none")]
    output_config: Option<OutputConfig>,
}

/// 思考强度配置。合法值: "low" | "medium" | "high" | "xhigh" | "max"
/// （对齐 Claude Code 的 CLAUDE_CODE_EFFORT_LEVEL）。
/// 注意：是否生效取决于服务端/网关是否实现该参数，不被识别时应静默忽略
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

/// 唯一的工具：bash。读文件 cat、写文件 echo、跑测试 pytest，一个全覆盖。
fn bash_tool() -> Tool {
    Tool {
        name: "bash",
        description: "Run a shell command.",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "command": { "type": "string" }
            },
            "required": ["command"]
        }),
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

// ── 工具执行 ──────────────────────────────────────────────────────────────

/// 执行一条 shell 命令，行为对齐 Python 版 run_bash()：
///   - 危险命令黑名单直接拦截（最简陋的防护，s03 才认真做权限）
///   - stdout + stderr 合并返回
///   - 输出截断到 50000 字符，防止撑爆上下文
///   - 120 秒超时
///   - 所有失败都变成字符串返回给模型，不 panic ——
///     模型看到 "Error: ..." 会自己换条路重试，这是 agent 容错的基本手法
fn run_bash(command: &str) -> String {
    // 危险命令黑名单（教学级防护，防君子不防小人）
    let dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"];
    if dangerous.iter().any(|d| command.contains(d)) {
        return "Error: Dangerous command blocked".to_string();
    }

    // 用 sh -c 执行，等价于 Python 的 subprocess.run(..., shell=True)。
    // 工作目录默认继承当前进程目录，和 Python 版 cwd=os.getcwd() 一致。
    let child = Command::new("sh")
        .arg("-c")
        .arg(command)
        // 把 sh 及其所有后代放进独立进程组（pgid = sh 的 pid），
        // 超时才能整组击杀，连后台孙进程一起清理。
        .process_group(0)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();

    let mut child = match child {
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
            let out = stdout_thread.join().unwrap_or_default();
            let err = stderr_thread.join().unwrap_or_default();
            let mut combined = String::from_utf8_lossy(&out).into_owned();
            combined.push_str(&String::from_utf8_lossy(&err));
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

// ── API 客户端 ────────────────────────────────────────────────────────────

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
        output_config: cfg
            .effort
            .as_ref()
            .map(|e| OutputConfig { effort: e.clone() }),
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
        .header("anthropic-version", "2023-06-01")
        .json(&req);

    // beta 特性头（如官方 API 的 1M 上下文 context-1m-2025-08-07）。
    // 通用透传：环境变量 ANTHROPIC_BETA 配什么就发什么
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

// ── 核心模式：一个 while 循环，模型不停止就继续 ───────────────────────────
//
// 这是全部秘密。退出条件不看固定步数、不看关键词，
// 只看 API 返回的 stop_reason：是 "tool_use" 就继续，否则就停。
// 干几步、每步干什么、干没干完，全由模型判断。
fn agent_loop(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
) -> Result<(), String> {
    let tools = [bash_tool()];

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
        //    一个回复里可能有多个 tool_use（并行调用），
        //    对应的 tool_result 必须一个不少地放在紧随其后的同一条 user 消息里。
        let mut results: Vec<ContentBlock> = Vec::new();
        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                if name == "bash" {
                    // input 是任意 JSON，按 schema 取出 command 字段
                    let command = input["command"].as_str().unwrap_or("");
                    println!("\x1b[33m$ {command}\x1b[0m"); // 黄色打印命令
                    let output = run_bash(command);
                    // 终端只打印前 1000 字符防刷屏（按整行截断 + "..."），
                    // 给模型的 content 是完整输出
                    let preview = truncate_lines(&output, 1000);
                    println!("{preview}");
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: output,
                    });
                } else {
                    // 未知工具（模型幻觉出来的名字）：也必须回一条 tool_result，
                    // 否则这个 tool_use 没有配对结果，违反 API 契约，
                    // 下一轮请求会被 API 拒绝。错误以文本形式告知模型，它会自我纠正
                    eprintln!("\x1b[31m未知工具: {name}\x1b[0m");
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: format!("Error: unknown tool '{name}'"),
                    });
                }
            }
        }

        // 5. 结果回灌进历史，循环继续 —— 模型下一轮会"看到"工具输出
        messages.push(Message::user_tool_results(results));
    }
}

// ── 配置与入口 ────────────────────────────────────────────────────────────

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
            "You are a coding agent at {}. Use bash to solve tasks. Act, don't explain.",
            cwd.display()
        ),
        // 思考强度原样透传（小写），非法值交给服务端报错——
        // 客户端不做白名单，因为合法集合会随模型代际演进（high → xhigh → max）
        effort: env::var("EFFORT_LEVEL")
            .ok()
            .map(|v| v.trim().to_lowercase())
            .filter(|v| !v.is_empty()),
        max_tokens: env::var("MAX_TOKENS")
            .ok()
            .and_then(|v| v.parse::<u32>().ok())
            .unwrap_or(8000),
        beta: env::var("ANTHROPIC_BETA").ok().filter(|v| !v.is_empty()),
        // S01_DEBUG=1 或 true 开启；未设置、为空或为 0 都视为关闭
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

    println!("s01: Agent Loop");
    println!("输入问题，回车发送。输入 q 退出。\n");

    let mut history: Vec<Message> = Vec::new();
    let stdin = io::stdin();

    loop {
        print!("\x1b[36ms01 >> \x1b[0m");
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

// ── 单元测试 ──────────────────────────────────────────────────────────────
//
// 只测不依赖网络的纯逻辑：截断函数、serde 契约模型、黑名单。
// API 调用和 REPL 靠 S01_DEBUG 的实测 trace 验证（见 README）。
#[cfg(test)]
mod tests {
    use super::*;

    // ── truncate_lines ──

    #[test]
    fn truncate_under_limit_unchanged() {
        let text = "line1\nline2\nline3";
        assert_eq!(truncate_lines(text, 1000), text);
    }

    #[test]
    fn truncate_cuts_at_line_boundary() {
        // 每行 10 字符（含换行），上限 25 → 只留两行，绝不切第三行一半
        let text = "aaaaaaaaa\nbbbbbbbbb\nccccccccc";
        let out = truncate_lines(text, 25);
        assert_eq!(out, "aaaaaaaaa\nbbbbbbbbb\n...");
    }

    #[test]
    fn truncate_single_long_line_fallback() {
        // 第一行就超长：退回按字符截断，且不切坏多字节字符
        let text = "一二三四五六七八九十".repeat(10); // 100 个汉字
        let out = truncate_lines(&text, 20);
        assert!(out.ends_with("..."));
        // 20 个汉字 + 换行符 + "..."（3 字符）= 24
        assert_eq!(out.chars().count(), 24);
        // 前 20 个字符都是完整汉字，没有切出半个 UTF-8 字符
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
        // 网关返回带 signature 的 thinking block，解析后再序列化必须原样保留
        // （官方 API 在 thinking + 工具调用的多轮对话里要求回传签名）
        let raw = r#"{"type":"thinking","thinking":"hmm","signature":"sig-123"}"#;
        let block: ContentBlock = serde_json::from_str(raw).unwrap();
        let out = serde_json::to_value(&block).unwrap();
        assert_eq!(out["thinking"], "hmm");
        assert_eq!(out["signature"], "sig-123"); // flatten 兜底字段摊平原位
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

    // ── run_bash 黑名单（不依赖网络的快速路径） ──

    #[test]
    fn dangerous_command_blocked() {
        assert_eq!(
            run_bash("rm -rf / --no-preserve-root"),
            "Error: Dangerous command blocked"
        );
        assert!(run_bash("sudo ls").starts_with("Error: Dangerous"));
    }

    #[test]
    fn run_bash_captures_output() {
        assert_eq!(run_bash("echo hello"), "hello");
    }

    #[test]
    fn run_bash_empty_output_marker() {
        assert_eq!(run_bash("true"), "(no output)");
    }
}
