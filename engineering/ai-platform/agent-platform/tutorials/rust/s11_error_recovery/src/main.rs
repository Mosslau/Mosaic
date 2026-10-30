//! s11: Error Recovery — 错误不是结束，是重试的开始
//!
//! 在 s10 基础上给主循环的 LLM 调用包上错误恢复层。
//! 保留 s01–s10 全部机制；压缩、记忆、子代理等内部辅助 LLM 调用维持原样（教学版范围）。
//!
//! 三种最常见的故障，三种恢复路径：
//!
//! ```text
//!   with_retry ── 1 次 LLM 调用
//!        │
//!        ▼
//!   ┌──────────────────────────┐
//!   │ 错误分类（LlmError）      │
//!   └──────────┬───────────────┘
//!              │
//!     ┌────────┼────────────┐
//!     │        │            │
//!  429/529  prompt_too_long  其他
//!     │        │            │
//!     ▼        ▼            ▼
//! ┌────────┐ ┌───────────┐ ┌───────────────┐
//! │指数退避 │ │reactive   │ │[unrecoverable] │
//! │+抖动×10 │ │compact    │ │写 [Error] 消息 │
//! │529×3 → │ │(仅1次)    │ │退出本轮        │
//! │切fallback│ └─────┬─────┘ └───────────────┘
//! └────────┘       │重试
//!                  ▼
//!            ┌──────────────────────────┐
//!            │ stop_reason == max_tokens│  输出被截断
//!            └──────────┬───────────────┘
//!                       │
//!                  ┌────┴─────┐
//!                未升级       已升级
//!                  │            │
//!                  ▼            ▼
//!            max_tokens   追加截断输出 +
//!            = 64K 重试   续写提示 ×3
//!            (不追加输出)
//! ```
//!
//! 对照 Python 版 ../../python/s11_error_recovery/code.py。
//! 运行：cargo run -p s11_error_recovery
//! 可选环境变量：EFFORT_LEVEL / MAX_TOKENS / ANTHROPIC_BETA / S01_DEBUG / FALLBACK_MODEL_ID

use std::env;
use std::fmt;
use std::io::{self, BufRead, Read, Write};
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use std::os::unix::process::CommandExt; // process_group(): 独立进程组，超时可整组击杀
use wait_timeout::ChildExt;
use rand::Rng; // s11: retry_delay 的随机抖动

// ── Anthropic Messages API 的数据模型（同 s01/s02/s03/s04/s05/s06/s07/s08/s09） ──

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

    /// s11 新增：构造纯文本 assistant 消息（错误恢复把 [Error] 写进历史时用，
    /// 让 REPL 像正常回复一样把错误展示给用户，而不是走 Err 分支弹掉上一条输入）
    fn assistant_text(text: impl Into<String>) -> Self {
        Message {
            role: Role::Assistant,
            content: MessageContent::Text(text.into()),
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

// ── s07 新增：skill 数据结构 ─────────────────────────────────────────────

/// 内存中的单个技能条目：name + description + 完整 SKILL.md 内容
#[derive(Clone)]
struct SkillInfo {
    #[allow(dead_code)]
    name: String,
    #[allow(dead_code)]
    description: String,
    content: String,
}

/// load_skill 工具的参数：技能名称
#[derive(Deserialize)]
struct LoadSkillInput {
    name: String,
}

// ── s08 新增：compact 工具的参数结构体 ──────────────────────────────────

/// compact 工具的参数：可选的聚焦描述
#[derive(Deserialize)]
#[allow(dead_code)]
struct CompactInput {
    #[serde(default)]
    focus: Option<String>,
}

// ── s09 新增：记忆系统数据结构 ──────────────────────────────────────────

/// 记忆文件元数据（从 YAML frontmatter 解析）
#[derive(Clone, Debug)]
struct MemoryInfo {
    filename: String,
    name: String,
    description: String,
    #[allow(dead_code)]
    mem_type: String,
    body: String,
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

// ── 9 个工具定义（同 s07 + compact） ──────────────────────────────────

fn all_tools() -> [Tool; 9] {
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
        // s07: new tool — load full skill content on demand
        Tool {
            name: "load_skill",
            description: "Load the full content of a skill by name. Use when you need detailed guidance for a specific domain (e.g. code-review, pdf-generation). The skill catalog is already in the system prompt.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "name": { "type": "string" }
                },
                "required": ["name"]
            }),
        },
        // s08: new tool — trigger context compaction
        Tool {
            name: "compact",
            description: "Summarize earlier conversation to free context space. Use when the conversation is getting long and you need to preserve important context while freeing up space.",
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "focus": { "type": "string" }
                }
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

// ── s07 新增：skill 注册表 + 扫描 ─────────────────────────────────────────
//
// 启动时扫描 skills/ 目录，解析每个 SKILL.md 的 YAML frontmatter，
// 存入 SKILL_REGISTRY。运行时 load_skill 只做 HashMap 查询，
// 不访问文件系统 — 没有路径穿越风险。

static SKILL_REGISTRY: Mutex<Option<HashMap<String, SkillInfo>>> = Mutex::new(None);

/// 解析 SKILL.md 的 YAML frontmatter，返回 (name, description, body)。
/// frontmatter 格式：
///   ---
///   name: code-review
///   description: Perform thorough code reviews...
///   ---
fn parse_frontmatter(text: &str) -> (String, String) {
    if !text.starts_with("---") {
        // 无 frontmatter：用第一行作为 description 的 fallback
        let first_line = text.lines().next().unwrap_or("").trim_start_matches('#').trim();
        return (String::new(), first_line.to_string());
    }
    // 找第二个 "---"（frontmatter 结束标记）
    let after_first = &text[3..]; // skip first "---"
    if let Some(end_idx) = after_first.find("\n---") {
        let yaml_str = after_first[..end_idx].trim();
        // 修复：用 serde_yaml 完整解析（支持 description: | 多行块、引号等）。
        // 之前的手工 strip_prefix 会把多行 description 解析成孤零零的 "|"。
        if let Ok(value) = serde_yaml::from_str::<serde_yaml::Value>(yaml_str) {
            let name = value
                .get("name")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            // 多行块折叠成单行：目录条目是一行一个技能，多行会打断格式
            let description = value
                .get("description")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .split_whitespace()
                .collect::<Vec<_>>()
                .join(" ");
            return (name, description);
        }
        // 解析失败（非法 YAML）时回退手工逐行
        let mut name = String::new();
        let mut description = String::new();
        for line in yaml_str.lines() {
            let trimmed = line.trim();
            if let Some(val) = trimmed.strip_prefix("name:") {
                name = val.trim().to_string();
            } else if let Some(val) = trimmed.strip_prefix("description:") {
                description = val.trim().to_string();
            }
        }
        (name, description)
    } else {
        (String::new(), String::new())
    }
}

/// 扫描 skills/ 目录，填充 SKILL_REGISTRY。
fn scan_skills(cwd: &Path) {
    let skills_dir = cwd.join("skills");
    if !skills_dir.exists() || !skills_dir.is_dir() {
        return;
    }

    let mut guard = match SKILL_REGISTRY.lock() {
        Ok(g) => g,
        Err(_) => return,
    };
    let registry = guard.get_or_insert_with(HashMap::new);

    // 读取目录条目
    let entries = match fs::read_dir(skills_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let manifest = path.join("SKILL.md");
        if !manifest.exists() {
            continue;
        }
        let raw = match fs::read_to_string(&manifest) {
            Ok(s) => s,
            Err(_) => continue,
        };
        let (name, description) = parse_frontmatter(&raw);
        let skill_name = if name.is_empty() {
            path.file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("unknown")
                .to_string()
        } else {
            name
        };
        let skill_desc = if description.is_empty() {
            raw.lines().next().unwrap_or("").trim_start_matches('#').trim().to_string()
        } else {
            description
        };
        registry.insert(
            skill_name.clone(),
            SkillInfo {
                name: skill_name,
                description: skill_desc,
                content: raw,
            },
        );
    }
}

/// 列出所有已注册的 skill（名字 + 一行描述）。
fn list_skills() -> String {
    let guard = match SKILL_REGISTRY.lock() {
        Ok(g) => g,
        Err(_) => return "(no skills found)".to_string(),
    };
    let registry = match guard.as_ref() {
        Some(r) => r,
        None => return "(no skills found)".to_string(),
    };
    if registry.is_empty() {
        return "(no skills found)".to_string();
    }
    let mut names: Vec<&String> = registry.keys().collect();
    names.sort();
    names
        .iter()
        .map(|name| {
            let s = &registry[*name];
            format!("- **{}**: {}", s.name, s.description)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// 构建包含 skill 目录的 system prompt。
// ── s10 新增：动态 system prompt 组装 ──────────────────────────────────

/// 运行时上下文，决定 system prompt 包含哪些段落
#[derive(Serialize, Clone)]
struct PromptContext {
    enabled_tools: Vec<String>,
    workspace: String,
    memories: String,
    skills: String,
}

// ── s10: prompt 段落字典（映射 Python PROMPT_SECTIONS） ──────────────

/// 静态 prompt 段落，按 topic 索引。预留 YAML/JSON 文件加载扩展。
fn prompt_sections() -> std::collections::HashMap<&'static str, &'static str> {
    let mut m = std::collections::HashMap::new();
    m.insert("identity", "You are a coding agent. Do not impersonate any specific AI assistant (Claude, GPT, etc.). Act, don't explain.");
    m
}

/// 按 context 选择段落、拼接 system prompt。
fn assemble_system_prompt(ctx: &PromptContext) -> String {
    let ps = prompt_sections();
    let mut sections: Vec<String> = Vec::new();

    // identity — 始终加载
    if let Some(id) = ps.get("identity") {
        sections.push(id.to_string());
    }

    // tools — 始终
    let tools = ctx.enabled_tools.join(", ");
    sections.push(format!("Available tools: {tools}."));

    // workspace — 始终
    sections.push(format!("Working directory: {}", ctx.workspace));

    // skills — 按需（s07 两层注入的第一层：目录进 prompt，正文 load_skill 时才给）
    if !ctx.skills.is_empty() {
        sections.push(format!("Available skills (call load_skill for full details):\n{}", ctx.skills));
    }

    // memory — 按需（MEMORY.md 存在且有内容）
    if !ctx.memories.is_empty() {
        sections.push(format!("Relevant memories:\n{}", ctx.memories));
    }

    sections.join("\n\n")
}

/// 缓存包装：context 不变时返回缓存。
fn get_system_prompt(ctx: &PromptContext) -> String {
    let key = serde_json::to_string(ctx).unwrap_or_default();
    static LK: std::sync::Mutex<Option<String>> = std::sync::Mutex::new(None);
    static LP: std::sync::Mutex<Option<String>> = std::sync::Mutex::new(None);
    if let (Ok(ref lk), Ok(ref lp)) = (LK.lock(), LP.lock()) {
        if let (Some(ref k), Some(ref p)) = (lk.as_ref(), lp.as_ref()) {
            if k.as_str() == key.as_str() { println!("  \x1b[90m[cache hit] system prompt unchanged\x1b[0m"); return p.to_string(); }
        }
    }
    let prompt = assemble_system_prompt(ctx);
    if let (Ok(mut lk), Ok(mut lp)) = (LK.lock(), LP.lock()) { *lk = Some(key); *lp = Some(prompt.clone()); }
    let mut loaded = vec!["identity", "tools", "workspace"];
    if !ctx.skills.is_empty() { loaded.push("skills"); }
    if !ctx.memories.is_empty() { loaded.push("memory"); }
    println!("  \x1b[32m[assembled] sections: {}\x1b[0m", loaded.join(", "));
    prompt
}

/// 从当前状态推导 context。
fn update_context(cwd: &Path) -> PromptContext {
    let tool_names: Vec<String> = all_tools().iter().map(|t| t.name.to_string()).collect();
    PromptContext { enabled_tools: tool_names, workspace: cwd.display().to_string(), memories: read_memory_index(cwd), skills: list_skills() }
}

/// 按名称加载完整 skill 内容。从 SKILL_REGISTRY 查询 — 无文件 I/O。
fn load_skill(name: &str) -> String {
    let guard = match SKILL_REGISTRY.lock() {
        Ok(g) => g,
        Err(_) => return "Error: skill registry unavailable".to_string(),
    };
    let registry = match guard.as_ref() {
        Some(r) => r,
        None => return "(no skills loaded)".to_string(),
    };
    match registry.get(name) {
        Some(skill) => skill.content.clone(),
        None => format!("Skill not found: {name}"),
    }
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

// ── 工具执行（同 s02/s03/s04/s05/s06/s07） ────────────────────────────────
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
        let resp = match call_llm(http, cfg, &cfg.model, &cfg.sub_system, &messages, &tools, cfg.max_tokens) {
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

// ── s09 新增：记忆系统（文件持久化 + 索引 + 按需注入） ──────────────────

fn memory_dir(cwd: &Path) -> PathBuf {
    let dir = cwd.join(".memory");
    fs::create_dir_all(&dir).ok();
    dir
}

fn write_memory_file(cwd: &Path, name: &str, mem_type: &str, description: &str, body: &str) {
    let slug = name.to_lowercase().replace(' ', "-").replace('/', "-");
    let filename = format!("{slug}.md");
    let filepath = memory_dir(cwd).join(&filename);
    let content = format!(
        "---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n"
    );
    // 记忆写入是 best-effort：磁盘满/权限错误不该让代理主循环崩溃，
    // 所以用 .ok() 静默吞错。教学代码刻意如此；生产实现应记日志或上报。
    fs::write(&filepath, content).ok();
    rebuild_index(cwd);
}

fn rebuild_index(cwd: &Path) {
    let dir = memory_dir(cwd);
    let mut lines: Vec<String> = Vec::new();
    let entries = match fs::read_dir(&dir) { Ok(e) => e, Err(_) => return };
    let mut files: Vec<_> = entries.flatten()
        .filter(|e| e.path().extension().map(|x| x == "md").unwrap_or(false))
        .filter(|e| e.file_name() != "MEMORY.md")
        .collect();
    files.sort_by_key(|e| e.file_name());
    for entry in &files {
        let raw = match fs::read_to_string(entry.path()) { Ok(s) => s, Err(_) => continue };
        let (name, description) = parse_frontmatter(&raw);
        let fname = entry.file_name().to_string_lossy().to_string();
        let display_name = if name.is_empty() { entry.path().file_stem().and_then(|s| s.to_str()).unwrap_or("unknown").to_string() } else { name };
        let desc = if description.is_empty() {
            // 修复：description 为空时回退正文首行（frontmatter 之后），截 80 字符
            // （对齐 Python 的 body.split("\n")[0][:80]）。
            // 之前的 raw.lines().next() 对 frontmatter 文件取到的是 "---"。
            let body_start = raw.find("\n---").map(|i| i + 4).unwrap_or(0);
            let body_line = raw[body_start..]
                .lines()
                .find(|l| !l.trim().is_empty())
                .unwrap_or("")
                .trim_start_matches('#')
                .trim();
            truncate_chars(body_line, 80).to_string()
        } else { description };
        lines.push(format!("- [{display_name}]({fname}) — {desc}"));
    }
    let index_path = dir.join("MEMORY.md");
    fs::write(&index_path, if lines.is_empty() { String::new() } else { lines.join("\n") + "\n" }).ok();
}

fn read_memory_index(cwd: &Path) -> String {
    let path = memory_dir(cwd).join("MEMORY.md");
    if !path.exists() { return String::new(); }
    fs::read_to_string(&path).unwrap_or_default().trim().to_string()
}

fn read_memory_file(cwd: &Path, filename: &str) -> Option<String> {
    let path = memory_dir(cwd).join(filename);
    if !path.exists() { return None; }
    fs::read_to_string(&path).ok()
}

fn extract_frontmatter_field(text: &str, field: &str) -> Option<String> {
    if !text.starts_with("---") { return None; }
    let after_first = &text[3..];
    let end_idx = after_first.find("\n---")?;
    for line in after_first[..end_idx].lines() {
        let trimmed = line.trim();
        if let Some(val) = trimmed.strip_prefix(&format!("{field}:")) {
            return Some(val.trim().to_string());
        }
    }
    None
}

fn list_memory_files(cwd: &Path) -> Vec<MemoryInfo> {
    let dir = memory_dir(cwd);
    let mut result = Vec::new();
    let entries = match fs::read_dir(&dir) { Ok(e) => e, Err(_) => return result };
    let mut files: Vec<_> = entries.flatten().collect();
    files.sort_by_key(|e| e.file_name());
    for entry in &files {
        let path = entry.path();
        if path.extension().map(|x| x != "md").unwrap_or(true) { continue; }
        if entry.file_name() == "MEMORY.md" { continue; }
        let raw = match fs::read_to_string(&path) { Ok(s) => s, Err(_) => continue };
        let (name, description) = parse_frontmatter(&raw);
        let mem_type = extract_frontmatter_field(&raw, "type").unwrap_or_else(|| "user".to_string());
        let fname = entry.file_name().to_string_lossy().to_string();
        let display_name = if name.is_empty() { path.file_stem().and_then(|s| s.to_str()).unwrap_or("unknown").to_string() } else { name };
        result.push(MemoryInfo { filename: fname, name: display_name, description, mem_type, body: raw });
    }
    result
}

fn select_relevant_memories(http: &reqwest::blocking::Client, cfg: &Config, cwd: &Path, messages: &[Message]) -> Vec<String> {
    let files = list_memory_files(cwd);
    if files.is_empty() { return vec![]; }
    let mut recent_texts: Vec<String> = Vec::new();
    for msg in messages.iter().rev() {
        if msg.role == Role::User {
            let text = extract_text(&msg.content);
            if !text.is_empty() { recent_texts.push(text); }
            if recent_texts.len() >= 3 { break; }
        }
    }
    let recent: String = recent_texts.into_iter().rev().collect::<Vec<_>>().join(" ");
    let recent = truncate_chars(&recent, 2000);
    if recent.trim().is_empty() { return vec![]; }

    // 路径 1: LLM 选择（精确，1 API 调用）
    let catalog_lines: Vec<String> = files.iter().enumerate()
        .map(|(i, f)| format!("{i}: {} — {}", f.name, f.description))
        .collect();
    let catalog = catalog_lines.join("\n");
    let prompt = format!(
        "Given the recent conversation and the memory catalog below, select the indices of memories that are clearly relevant. Return ONLY a JSON array of integers, e.g. [0, 3]. If none are relevant, return [].\n\nRecent conversation:\n{recent}\n\nMemory catalog:\n{catalog}"
    );
    let msgs = vec![Message::user_text(&prompt)];
    let tools: [Tool; 0] = [];
    // 内部辅助调用：不传 system、用固定 token 预算（对齐 Python 版）
    if let Ok(resp) = call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_SELECT_MAX_TOKENS) {
        let text = extract_text(&Message::assistant_blocks(resp.content).content);
        if let (Some(si), Some(ei)) = (text.find('['), text.rfind(']')) {
            if let Ok(indices) = serde_json::from_str::<Vec<usize>>(&text[si..ei+1]) {
                let mut selected: Vec<String> = Vec::new();
                for idx in indices {
                    if idx < files.len() {
                        selected.push(files[idx].filename.clone());
                        if selected.len() >= MAX_MEMORY_ITEMS { break; }
                    }
                }
                if !selected.is_empty() { return selected; }
            }
        }
    }

    // 路径 2: 关键词匹配（回退，0 API 调用）
    let keywords: Vec<String> = recent.split_whitespace().filter(|w| w.len() > 3).map(|w| w.to_lowercase()).collect();
    let mut selected: Vec<String> = Vec::new();
    for f in &files {
        let text = format!("{} {}", f.name, f.description).to_lowercase();
        if keywords.iter().any(|kw| text.contains(kw)) {
            selected.push(f.filename.clone());
            if selected.len() >= MAX_MEMORY_ITEMS { break; }
        }
    }
    selected
}

fn load_memories(http: &reqwest::blocking::Client, cfg: &Config, cwd: &Path, messages: &[Message]) -> String {
    let selected = select_relevant_memories(http, cfg, cwd, messages);
    if selected.is_empty() { return String::new(); }
    let mut parts = vec!["<relevant_memories>".to_string()];
    for filename in &selected {
        if let Some(content) = read_memory_file(cwd, filename) { parts.push(content); }
    }
    parts.push("</relevant_memories>".to_string());
    parts.join("\n\n")
}

/// 记忆提取门控：只在用户消息出现偏好信号词、或用户输入足够长时才提取。
/// 普通查询轮（"列出文件"）不产生记忆 —— memory ≠ transcript，提取是有条件的。
const MEMORY_SIGNALS: [&str; 12] = [
    "记住", "偏好", "喜欢", "讨厌", "以后", "总是", "从不", "不要",
    "remember", "prefer", "always", "never",
];

fn should_extract(messages: &[Message]) -> bool {
    let start = messages.len().saturating_sub(10);
    let mut user_len = 0usize;
    for msg in &messages[start..] {
        if msg.role != Role::User { continue; }
        let text = extract_text(&msg.content);
        user_len += text.chars().count();
        if MEMORY_SIGNALS.iter().any(|k| text.contains(k)) { return true; }
    }
    user_len > 200
}

/// 记忆条目分类：New=全新写入 / Update=同名覆盖 / Skip=内容重复丢弃。
fn classify_memory(existing: &[MemoryInfo], name: &str, desc: &str, body: &str) -> MemoryAction {
    let slug = format!("{}.md", name.to_lowercase().replace(' ', "-").replace('/', "-"));
    if existing.iter().any(|f| f.filename == slug) { return MemoryAction::Update; }
    if existing.iter().any(|f| f.description.trim() == desc.trim() && f.body.trim() == body.trim()) {
        return MemoryAction::Skip;
    }
    MemoryAction::New
}

enum MemoryAction { New, Update, Skip }

fn extract_memories(http: &reqwest::blocking::Client, cfg: &Config, cwd: &Path, messages: &[Message]) {
    // 门控：普通查询轮不提取（省 API 成本 + 治平凡事实噪声）
    if !should_extract(messages) { return; }
    let mut dialogue_parts: Vec<String> = Vec::new();
    let start = messages.len().saturating_sub(10);
    for msg in &messages[start..] {
        let role = if msg.role == Role::User { "user" } else { "assistant" };
        let text = extract_text(&msg.content);
        if !text.is_empty() { dialogue_parts.push(format!("{role}: {text}")); }
    }
    let dialogue = dialogue_parts.join("\n");
    if dialogue.trim().is_empty() { return; }
    let existing = list_memory_files(cwd);
    let existing_desc = if existing.is_empty() { "(none)".to_string() } else { existing.iter().map(|m| format!("- {}: {}", m.name, m.description)).collect::<Vec<_>>().join("\n") };
    // 收紧标准：只提取长期稳定的偏好/约束/决策；一次性查询结果一律不存。
    let prompt = format!(
        "Extract ONLY stable, long-term facts worth remembering: user preferences, \
         hard constraints, and durable project decisions.\n\
         DO NOT record: one-off query results, file line counts, directory listings, \
         README titles, command outputs, or anything already in the Existing list.\n\
         If nothing is worth remembering, return [].\n\
         Existing:\n{existing_desc}\n\nDialogue:\n{}",
        truncate_chars(&dialogue, 4000)
    );
    let msgs = vec![Message::user_text(&prompt)];
    let tools: [Tool; 0] = [];
    let resp = match call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_EXTRACT_MAX_TOKENS) { Ok(r) => r, Err(_) => return };
    let text = extract_text(&Message::assistant_blocks(resp.content).content);
    let (si, ei) = match (text.find('['), text.rfind(']')) { (Some(s), Some(e)) => (s, e+1), _ => return };
    let items: Vec<serde_json::Value> = match serde_json::from_str(&text[si..ei]) { Ok(v) => v, Err(_) => return };
    let mut new_count = 0;
    let mut updated = 0;
    let mut skipped = 0;
    for item in &items {
        let name = item["name"].as_str().unwrap_or("memory");
        let mt = item["type"].as_str().unwrap_or("user");
        let desc = item["description"].as_str().unwrap_or("");
        let body = item["body"].as_str().unwrap_or("");
        if desc.is_empty() || body.is_empty() { continue; }
        match classify_memory(&existing, name, desc, body) {
            MemoryAction::Update => { write_memory_file(cwd, name, mt, desc, body); updated += 1; }
            MemoryAction::New => { write_memory_file(cwd, name, mt, desc, body); new_count += 1; }
            MemoryAction::Skip => { skipped += 1; }
        }
    }
    if new_count + updated + skipped > 0 {
        println!("\n\x1b[33m[Memory: new {new_count}, updated {updated}, skipped {skipped}]\x1b[0m");
    }
}

/// 上次合并完成的时间戳（节流用）
static LAST_CONSOLIDATE: Mutex<Option<SystemTime>> = Mutex::new(None);

fn consolidate_memories(http: &reqwest::blocking::Client, cfg: &Config, cwd: &Path) {
    // 节流：合并 = 删光重写，太频繁会与提取互相打架（数量横跳）
    if let Ok(last) = LAST_CONSOLIDATE.lock() {
        if let Some(t) = *last {
            if t.elapsed().map(|d| d.as_secs() < CONSOLIDATE_MIN_INTERVAL_SECS).unwrap_or(true) { return; }
        }
    }
    let files = list_memory_files(cwd);
    if files.len() < CONSOLIDATE_THRESHOLD { return; }
    let catalog = files.iter().map(|f| format!("## {}\nname: {}\ndescription: {}\n{}", f.filename, f.name, f.description, f.body)).collect::<Vec<_>>().join("\n\n");
    let prompt = format!("Consolidate memory files. Merge duplicates, remove outdated, keep under 30. Keep entries identical to the input as-is; only merge true duplicates. Return JSON array [{{name,type,description,body}}].\n\n{}", truncate_chars(&catalog, 16000));
    let msgs = vec![Message::user_text(&prompt)];
    let tools: [Tool; 0] = [];
    let resp = match call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_CONSOLIDATE_MAX_TOKENS) { Ok(r) => r, Err(_) => return };
    let text = extract_text(&Message::assistant_blocks(resp.content).content);
    let (si, ei) = match (text.find('['), text.rfind(']')) { (Some(s), Some(e)) => (s, e+1), _ => return };
    let items: Vec<serde_json::Value> = match serde_json::from_str(&text[si..ei]) { Ok(v) => v, Err(_) => return };
    let dir = memory_dir(cwd);
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            if entry.path().extension().map(|x| x == "md").unwrap_or(false) && entry.file_name() != "MEMORY.md" {
                fs::remove_file(entry.path()).ok();
            }
        }
    }
    for item in &items {
        let name = item["name"].as_str().unwrap_or("memory");
        let mt = item["type"].as_str().unwrap_or("user");
        let desc = item["description"].as_str().unwrap_or("");
        let body = item["body"].as_str().unwrap_or("");
        if !desc.is_empty() && !body.is_empty() { write_memory_file(cwd, name, mt, desc, body); }
    }
    if let Ok(mut last) = LAST_CONSOLIDATE.lock() { *last = Some(SystemTime::now()); }
    println!("\n\x1b[33m[Memory: consolidated {} → {} memories]\x1b[0m", files.len(), items.len());
}

// ── s08 新增：四层压缩管线 ──────────────────────────────────────────────
//
// 执行顺序：L3(budget) → L1(snip) → L2(micro) → [token check] → L4(summary)
// 应急：reactive_compact —— API 报 prompt_too_long 时触发

/// 估算 messages 的字符数（简单替代 token 计数）
fn estimate_size(messages: &[Message]) -> usize {
    serde_json::to_string(messages).map(|s| s.len()).unwrap_or(0)
}

/// 消息的 content 中是否包含 tool_use block
fn message_has_tool_use(msg: &Message) -> bool {
    if msg.role != Role::Assistant {
        return false;
    }
    match &msg.content {
        MessageContent::Blocks(blocks) => blocks.iter().any(|b| matches!(b, ContentBlock::ToolUse { .. })),
        _ => false,
    }
}

/// 消息的 content 是否全是 tool_result block
fn is_tool_result_message(msg: &Message) -> bool {
    if msg.role != Role::User {
        return false;
    }
    match &msg.content {
        MessageContent::Blocks(blocks) => {
            !blocks.is_empty() && blocks.iter().all(|b| matches!(b, ContentBlock::ToolResult { .. }))
        }
        _ => false,
    }
}

/// 收集 messages 中所有 tool_result 的位置
fn collect_tool_results(messages: &[Message]) -> Vec<(usize, usize)> {
    let mut results = Vec::new();
    for (mi, msg) in messages.iter().enumerate() {
        if msg.role != Role::User {
            continue;
        }
        if let MessageContent::Blocks(blocks) = &msg.content {
            for (bi, block) in blocks.iter().enumerate() {
                if matches!(block, ContentBlock::ToolResult { .. }) {
                    results.push((mi, bi));
                }
            }
        }
    }
    results
}

// ── L3: tool_result_budget —— 大结果落盘 ────────────────────────────────

/// 将大输出持久化到磁盘，返回带路径引用的占位文本
fn persist_large_output(tool_use_id: &str, output: &str) -> String {
    if output.len() <= PERSIST_THRESHOLD {
        return output.to_string();
    }
    let dir = Path::new(".task_outputs").join("tool-results");
    fs::create_dir_all(&dir).ok();
    let path = dir.join(format!("{tool_use_id}.txt"));
    if !path.exists() {
        fs::write(&path, output).ok();
    }
    let preview = truncate_chars(&output, 2000);
    format!("<persisted-output>\nFull output: {}\nPreview:\n{}\n</persisted-output>", path.display(), preview)
}

/// L3: 检查最新一条消息的 tool_result 总大小，超 budget 时逐个落盘最大的结果
fn tool_result_budget(messages: &mut Vec<Message>, max_bytes: usize) {
    let Some(last) = messages.last() else { return };
    if last.role != Role::User { return; }
    let MessageContent::Blocks(ref blocks) = last.content else { return };

    // 找出所有 tool_result block
    let mut tool_indices: Vec<(usize, usize)> = Vec::new(); // (index, size)
    for (i, block) in blocks.iter().enumerate() {
        if let ContentBlock::ToolResult { content, .. } = block {
            tool_indices.push((i, content.len()));
        }
    }
    if tool_indices.is_empty() { return; }

    let total: usize = tool_indices.iter().map(|(_, s)| s).sum();
    if total <= max_bytes { return; }

    // 按大小降序排列，先处理最大的
    tool_indices.sort_by(|a, b| b.1.cmp(&a.1));
    // 需要在 mutable 上下文中修改 blocks —— 先收集再改
    let mut remaining = total;
    let blocks_mut = match &mut messages.last_mut().unwrap().content {
        MessageContent::Blocks(b) => b,
        _ => return,
    };

    for (idx, size) in &tool_indices {
        if remaining <= max_bytes { break; }
        if *size <= PERSIST_THRESHOLD { continue; }
        if let ContentBlock::ToolResult { tool_use_id, content } = &blocks_mut[*idx] {
            let tid = tool_use_id.clone();
            let persisted = persist_large_output(&tid, content);
            let new_size = persisted.len();
            remaining = remaining.saturating_sub(size.saturating_sub(new_size));
            blocks_mut[*idx] = ContentBlock::ToolResult {
                tool_use_id: tid,
                content: persisted,
            };
        }
    }
}

// ── L1: snip_compact —— 裁掉中间无关旧对话 ─────────────────────────────

/// 当消息数超过 max_messages 时，保留头部 SNIP_KEEP_HEAD 条 + 尾部，
/// 中间裁掉。不拆散 tool_use/tool_result 配对。
fn snip_compact(messages: &mut Vec<Message>) {
    if messages.len() <= SNIP_MAX_MESSAGES { return; }

    let keep_tail = SNIP_MAX_MESSAGES - SNIP_KEEP_HEAD;
    let mut head_end = SNIP_KEEP_HEAD;
    let mut tail_start = messages.len().saturating_sub(keep_tail);

    // 保护：不拆散 assistant(tool_use) → user(tool_result) 对
    if head_end > 0 && head_end < messages.len() && message_has_tool_use(&messages[head_end - 1]) {
        while head_end < messages.len() && is_tool_result_message(&messages[head_end]) {
            head_end += 1;
        }
    }
    if tail_start > 0 && tail_start < messages.len()
        && is_tool_result_message(&messages[tail_start])
        && message_has_tool_use(&messages[tail_start - 1])
    {
        tail_start -= 1;
    }

    if head_end >= tail_start { return; }
    let snipped = tail_start - head_end;

    let placeholder = Message::user_text(format!("[snipped {snipped} messages from conversation middle]"));
    let mut new_msgs: Vec<Message> = Vec::with_capacity(head_end + 1 + messages.len() - tail_start);
    new_msgs.extend_from_slice(&messages[..head_end]);
    new_msgs.push(placeholder);
    new_msgs.extend_from_slice(&messages[tail_start..]);
    *messages = new_msgs;
}

// ── L2: micro_compact —— 旧 tool_result 占位 ───────────────────────────

/// 保留最近 KEEP_RECENT 个 tool_result 的完整内容，其余替换为占位符。
fn micro_compact(messages: &mut Vec<Message>) {
    let positions = collect_tool_results(messages);
    if positions.len() <= KEEP_RECENT { return; }

    let keep_start = positions.len() - KEEP_RECENT;
    for (mi, bi) in positions.iter().take(keep_start) {
        if let MessageContent::Blocks(blocks) = &mut messages[*mi].content {
            if let ContentBlock::ToolResult { content, .. } = &mut blocks[*bi] {
                if content.len() > 120 {
                    *content = "[Earlier tool result compacted. Re-run if needed.]".to_string();
                }
            }
        }
    }
}

// ── L4: compact_history —— LLM 全量摘要 ─────────────────────────────────

/// 写入会话转录到 .transcripts/ 目录
fn write_transcript(messages: &[Message]) -> String {
    let dir = Path::new(".transcripts");
    fs::create_dir_all(dir).ok();
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    let path = dir.join(format!("transcript_{ts}.json"));
    let json = serde_json::to_string_pretty(messages).unwrap_or_default();
    fs::write(&path, &json).ok();
    path.display().to_string()
}

/// 调 LLM 对历史做摘要，保留目标、关键发现、文件变更、剩余工作
fn summarize_history(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &[Message],
) -> String {
    let conversation = serde_json::to_string(messages).unwrap_or_default();
    let truncated: String = conversation.chars().take(80000).collect();
    let prompt = format!(
        "Summarize this coding-agent conversation so work can continue.\n         Preserve: 1. current goal, 2. key findings/decisions, 3. files read/changed,          4. remaining work, 5. user constraints.\n         Be compact but concrete.\n\n{truncated}"
    );
    let summary_messages = vec![Message::user_text(&prompt)];
    let tools: [Tool; 0] = []; // 摘要不需要工具
    let resp = match call_llm(http, cfg, &cfg.model, "", &summary_messages, &tools, SUMMARIZE_MAX_TOKENS) {
        Ok(r) => r,
        Err(e) => return format!("(summary failed: {e})"),
    };
    extract_text(&Message::assistant_blocks(resp.content).content)
}

/// 尾部保留起点：最近 5 条原始消息不进摘要。
/// 若边界恰好落在 tool_use / tool_result 配对中间，回退一条保证配对完整
/// （模型消息序列里 tool_use 必须紧跟它的 tool_result）。
/// 修复：此前 compact_history 全量替换，当前回合的请求与刚读的文件正文
/// 随压缩瞬间蒸发，只剩摘要——"继续"接不上当前工作（实测教训）。
fn tail_keep_start(messages: &[Message]) -> usize {
    let mut tail_start = messages.len().saturating_sub(5);
    if tail_start > 0 && tail_start < messages.len()
        && is_tool_result_message(&messages[tail_start])
        && message_has_tool_use(&messages[tail_start - 1])
    {
        tail_start -= 1;
    }
    tail_start
}

/// L4: 老历史用 LLM 摘要替换，尾部最近 5 条原样保留
fn compact_history(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
) {
    let transcript_path = write_transcript(messages);
    println!("[transcript saved: {transcript_path}]");
    // 老历史摘要 + 保留尾部最近 5 条：目标与最新文件内容留在上下文里，
    // 压缩后模型仍能无缝继续当前工作
    let tail_start = tail_keep_start(messages);
    let summary = if tail_start == 0 {
        "(no older history to summarize)".to_string()
    } else {
        summarize_history(http, cfg, &messages[..tail_start])
    };
    let tail = messages[tail_start..].to_vec();
    *messages = vec![Message::user_text(format!("[Compacted]\n\n{summary}"))];
    messages.extend(tail);
}

// ── 应急：reactive_compact —— API 报 prompt_too_long 时触发 ─────────────

/// 保留尾部 5 条原始消息，其余用 LLM 摘要替换
fn reactive_compact(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
) {
    let transcript_path = write_transcript(messages);
    println!("[transcript saved: {transcript_path}]");
    let tail_start = tail_keep_start(messages);
    let summary = if tail_start == 0 {
        "(no older history to summarize)".to_string()
    } else {
        summarize_history(http, cfg, &messages[..tail_start])
    };
    let tail = messages[tail_start..].to_vec();
    *messages = vec![Message::user_text(format!("[Reactive compact]\n\n{summary}"))];
    messages.extend(tail);
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
// ── s08 新增：压缩参数常量 ────────────────────────────────────────────────

/// 消息数超过此值时触发 snip_compact
const SNIP_MAX_MESSAGES: usize = 50;
/// snip_compact 保留的头部消息数
const SNIP_KEEP_HEAD: usize = 3;
/// micro_compact 保留的最近 tool_result 数
const KEEP_RECENT: usize = 3;
/// 上下文大小估算阈值（字符数），超此值触发 L4 摘要
const CONTEXT_LIMIT: usize = 50000;
/// tool_result 落盘阈值（字符数），超此值触发 L3 持久化
const PERSIST_THRESHOLD: usize = 30000;

// ── s11 新增：错误恢复常量 ──────────────────────────────────────────────

/// max_tokens 截断后的升级上限（8K → 64K）
const ESCALATED_MAX_TOKENS: u32 = 64000;
/// 64K 仍截断时，续写提示的最大次数
const MAX_RECOVERY_RETRIES: u32 = 3;
/// with_retry 对瞬态错误（429/529）的最大尝试次数
const MAX_RETRIES: u32 = 10;
/// 指数退避的基数（毫秒）：500, 1000, 2000, ... 封顶 32000
const BASE_DELAY_MS: u64 = 500;
/// 退避上限（毫秒）
const MAX_DELAY_MS: u64 = 32000;
/// 连续多少次 529 过载后切换备用模型
const MAX_CONSECUTIVE_529: u32 = 3;
/// 续写提示：让模型直接从断点接着写，不道歉不复述
const CONTINUATION_PROMPT: &str =
    "Output token limit hit. Resume directly — no apology, no recap. Pick up mid-thought.";

// ── s09 新增：记忆系统常量 ──────────────────────────────────────────────

/// 记忆文件 ≥ 此值时触发 consolidate
const CONSOLIDATE_THRESHOLD: usize = 20;
/// 合并最小间隔：合并会删光重写全部记忆，太频繁会与提取互相打架（数量横跳）
const CONSOLIDATE_MIN_INTERVAL_SECS: u64 = 300;
/// 内部辅助调用的独立 token 预算（对齐 Python 版，与 MAX_TOKENS 主循环预算解耦）。
/// 主循环预算可被 MAX_TOKENS=300 压小以演示截断升级，但摘要/提取被截断是无声的
/// ——目标会在压缩中丢失、模型答非所问（实测教训）。
const SUMMARIZE_MAX_TOKENS: u32 = 2000;
const MEMORY_SELECT_MAX_TOKENS: u32 = 200;
const MEMORY_EXTRACT_MAX_TOKENS: u32 = 800;
const MEMORY_CONSOLIDATE_MAX_TOKENS: u32 = 3000;
/// 单次选择的最大记忆数
const MAX_MEMORY_ITEMS: usize = 5;

// ── 权限常量 ────────────────────────────────────────────────────────────

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

// ── s11 新增：错误分类与恢复状态 ────────────────────────────────────────
//
// Python 版靠异常类名 + 字符串匹配区分错误（ratelimit/overloaded/prompt too long）。
// Rust 版把分类结果做成强类型枚举：call_llm 在拿到 status code + 响应体的地方
// 直接分类，恢复逻辑 match 枚举，不再猜字符串。

/// LLM 调用的失败原因，按"能不能恢复"分类
enum LlmError {
    /// 429 限流 —— 瞬态，指数退避后重试（Retry-After 头优先）
    RateLimited { retry_after_secs: Option<u64> },
    /// 529 过载 —— 瞬态，退避重试；连续多次后切换备用模型
    Overloaded,
    /// 上下文超限 —— reactive compact 后重试一次
    PromptTooLong,
    /// 网络错误 / 解析失败 / 其他状态码 —— 不可恢复
    Other(String),
}

impl fmt::Display for LlmError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LlmError::RateLimited { retry_after_secs } => match retry_after_secs {
                Some(s) => write!(f, "429 限流（Retry-After: {s}s）"),
                None => write!(f, "429 限流"),
            },
            LlmError::Overloaded => write!(f, "529 过载"),
            LlmError::PromptTooLong => write!(f, "上下文超限"),
            LlmError::Other(msg) => write!(f, "{msg}"),
        }
    }
}

/// 瞬态 = 值得退避重试；非瞬态 = 重试也没用，直接交给外层。
/// with_retry 里用 match 直接分派，这个谓词留给测试断言语义。
#[cfg(test)]
impl LlmError {
    fn is_transient(&self) -> bool {
        matches!(self, LlmError::RateLimited { .. } | LlmError::Overloaded)
    }
}

/// 检查响应体是否在说"上下文太长"。
/// 覆盖官方字段名 + 各网关的常见措辞（对齐 Python 的 is_prompt_too_long_error：
/// prompt 与 long 同现、prompt_is_too_long、context_length_exceeded、max_context_window）
fn is_prompt_too_long_body(body: &str) -> bool {
    let b = body.to_lowercase();
    b.contains("prompt_too_long")
        || b.contains("prompt_is_too_long")
        || b.contains("context_length_exceeded")
        || b.contains("max_context_window")
        || b.contains("prompt is too long")
        || b.contains("prompt too long")
        || b.contains("too many tokens")
        // 兜底泛匹配（对齐 Python 的 ("prompt" in msg and "long" in msg)）：
        // 覆盖 "prompt was too long" 等未枚举措辞
        || (b.contains("prompt") && b.contains("long"))
}

/// 不可恢复错误写进历史的统一格式：截断到 200 字符（对齐 Python 的 [:200]）。
/// 用 truncate_chars 保证字符安全——错误体可能带着超大响应文本或中文，
/// 不截断会污染上下文，按字节切会 panic。
fn error_note(e: &LlmError) -> String {
    let msg = e.to_string();
    let preview = truncate_chars(&msg, 200);
    format!("[Error] {preview}")
}

/// max_tokens 升级目标：64000 与当前上限取较大值。
/// 用户通过 MAX_TOKENS 配了更大的上限（如 100000）时，升级不能反而降级。
fn escalated_limit(current: u32) -> u32 {
    ESCALATED_MAX_TOKENS.max(current)
}

/// 解析 Retry-After 头（秒）。只支持整数秒形式（HTTP-date 形式跳过，
/// 教学版足够——Anthropic 网关返回的就是整数秒）。
fn parse_retry_after(header: Option<&str>) -> Option<u64> {
    header?.trim().parse::<u64>().ok()
}

/// 按 status + 响应体把一次失败的 HTTP 响应分类成 LlmError
fn classify_http_error(status: u16, body: &str) -> LlmError {
    // 429/529 优先级最高：就算响应体顺带提到 overloaded 之类的词，也按状态码走
    if status == 429 {
        return LlmError::RateLimited { retry_after_secs: None };
    }
    // 官方 529；部分网关过载时返回 500/503 但 body 里带 "overloaded"，
    // 一并按过载处理（对齐 Python 的字符串匹配兜底）
    if status == 529 || ((status == 500 || status == 503) && body.to_lowercase().contains("overloaded")) {
        return LlmError::Overloaded;
    }
    if is_prompt_too_long_body(body) {
        return LlmError::PromptTooLong;
    }
    LlmError::Other(format!("API 返回 {status}: {body}"))
}

/// 恢复状态：一次 agent_loop 调用内的所有恢复尝试共享这份状态。
/// 对齐 Python 的 RecoveryState。
struct RecoveryState {
    /// 输出截断：max_tokens 是否已经升过级（只升一次）
    has_escalated: bool,
    /// 输出截断：64K 后已续写次数
    recovery_count: u32,
    /// 连续 529 计数（成功一次就清零）
    consecutive_529: u32,
    /// 上下文超限：reactive compact 是否已经试过（只试一次）
    has_attempted_reactive_compact: bool,
    /// 当前使用的模型（529×3 后切到备用模型）
    current_model: String,
    /// 备用模型（FALLBACK_MODEL_ID，可能没配置）
    fallback_model: Option<String>,
}

impl RecoveryState {
    fn new(primary_model: &str, fallback_model: Option<String>) -> Self {
        RecoveryState {
            has_escalated: false,
            recovery_count: 0,
            consecutive_529: 0,
            has_attempted_reactive_compact: false,
            current_model: primary_model.to_string(),
            fallback_model,
        }
    }

    /// 记录一次 529。返回是否触发了模型切换（便于打日志）。
    /// 没有配置备用模型时只重置计数，继续用主模型重试。
    fn register_529(&mut self) -> bool {
        self.consecutive_529 += 1;
        if self.consecutive_529 >= MAX_CONSECUTIVE_529 {
            self.consecutive_529 = 0;
            if let Some(fb) = &self.fallback_model {
                self.current_model = fb.clone();
                return true;
            }
        }
        false
    }
}

/// 输出截断后的下一步动作：升 token / 续写 / 放弃
enum TruncationAction {
    /// 第一次截断：max_tokens 升到 64K，重试同一请求（不追加截断输出）
    Escalate,
    /// 64K 仍截断：保存截断输出 + 注入续写提示
    Continue,
    /// 续写次数用尽：放弃
    GiveUp,
}

/// max_tokens 截断的决策纯函数（供 agent_loop 和测试复用）
fn plan_truncation_recovery(state: &mut RecoveryState) -> TruncationAction {
    if !state.has_escalated {
        state.has_escalated = true;
        return TruncationAction::Escalate;
    }
    if state.recovery_count < MAX_RECOVERY_RETRIES {
        state.recovery_count += 1;
        return TruncationAction::Continue;
    }
    TruncationAction::GiveUp
}

/// 指数退避延迟：min(500 × 2^attempt, 32000)ms + 0~25% 随机抖动。
/// Retry-After 头（秒）优先级最高——服务器说等多久就等多久。
fn retry_delay(attempt: u32, retry_after_secs: Option<u64>) -> Duration {
    if let Some(secs) = retry_after_secs {
        return Duration::from_secs(secs);
    }
    let base_ms = (BASE_DELAY_MS << attempt.min(10)).min(MAX_DELAY_MS);
    // 抖动让并发重试错开时刻，避免同拍打回 API（CC 公式：+ random(0~25%)）
    let jitter_ms = rand::thread_rng().gen_range(0..=base_ms / 4);
    Duration::from_millis(base_ms + jitter_ms)
}

/// s11 核心：给 LLM 调用包上瞬态错误重试（429/529）。
///
/// - 429：指数退避后重试
/// - 529：退避重试；连续 MAX_CONSECUTIVE_529 次切换备用模型
/// - 非瞬态错误（PromptTooLong / Other）：立即向上抛，交给外层处理
/// - 重试 MAX_RETRIES 次仍失败：返回 Other("重试耗尽")
///
/// `call` 闭包接收当前模型名——529 切换模型后，下一次重试自动用新模型。
fn with_retry(
    state: &mut RecoveryState,
    mut call: impl FnMut(&str) -> Result<ApiResponse, LlmError>,
) -> Result<ApiResponse, LlmError> {
    for attempt in 0..MAX_RETRIES {
        match call(&state.current_model) {
            Ok(resp) => {
                // 成功一次就清零 529 计数——过载是连续概念
                state.consecutive_529 = 0;
                return Ok(resp);
            }
            Err(LlmError::RateLimited { retry_after_secs }) => {
                let delay = retry_delay(attempt, retry_after_secs);
                println!(
                    "  \x1b[33m[429 rate limit] retry {}/{}, wait {:.1}s\x1b[0m",
                    attempt + 1,
                    MAX_RETRIES,
                    delay.as_secs_f64()
                );
                std::thread::sleep(delay);
            }
            Err(LlmError::Overloaded) => {
                let switched = state.register_529();
                if switched {
                    println!(
                        "  \x1b[31m[529 x{}] switching to {}\x1b[0m",
                        MAX_CONSECUTIVE_529, state.current_model
                    );
                } else if state.consecutive_529 == 0 && state.fallback_model.is_none() {
                    // 无备用模型：计数被 reset，纯靠重试硬扛
                    println!(
                        "  \x1b[31m[529 x{}] no FALLBACK_MODEL_ID configured, continuing retry\x1b[0m",
                        MAX_CONSECUTIVE_529
                    );
                }
                let delay = retry_delay(attempt, None);
                println!(
                    "  \x1b[33m[529 overloaded] retry {}/{}, wait {:.1}s\x1b[0m",
                    attempt + 1,
                    MAX_RETRIES,
                    delay.as_secs_f64()
                );
                std::thread::sleep(delay);
            }
            // 非瞬态：不在这里重试，交给外层（reactive compact / 上报）
            Err(e) => return Err(e),
        }
    }
    Err(LlmError::Other(format!(
        "Max retries ({MAX_RETRIES}) exceeded"
    )))
}

// ── API 客户端（同 s01/s02/s03/s04/s05/s06/s07/s08/s09，s11 改为结构化错误） ──

/// 一次 LLM 调用：把全部历史 messages + 工具定义发给 API，返回模型的响应。
///
/// 注意这里没有任何"记忆"概念——API 是无状态的，
/// 模型之所以"记得"之前的事，纯粹因为我们把 messages 整个重发了一遍。
///
/// s11 变化：model 和 max_tokens 变成参数（模型可切换、token 可升级），
/// 错误返回强类型的 LlmError 而不是字符串。
fn call_llm(
    http: &reqwest::blocking::Client,
    cfg: &Config,
    model: &str,
    system: &str,
    messages: &[Message],
    tools: &[Tool],
    max_tokens: u32,
) -> Result<ApiResponse, LlmError> {
    let req = ApiRequest {
        model,
        system,
        messages,
        tools,
        max_tokens,
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

    let resp = builder
        .send()
        .map_err(|e| LlmError::Other(format!("HTTP 请求失败: {e}")))?;

    // 非 2xx 时把响应体读出来，里面通常有有用的错误信息（比如 overloaded）
    let status = resp.status();
    // s11: 先记下 Retry-After 头（429 时优先级最高），再读响应体。
    // headers() 在 consume body 之前取，读到的是原始头。
    let retry_after = parse_retry_after(
        resp.headers()
            .get("retry-after")
            .and_then(|v| v.to_str().ok()),
    );
    let body = resp
        .text()
        .map_err(|e| LlmError::Other(format!("读取响应体失败: {e}")))?;

    // 调试开关：打印原始响应体（尽量 pretty-print，非法 JSON 就原样打）
    if cfg.debug {
        let pretty = serde_json::from_str::<serde_json::Value>(&body)
            .and_then(|v| serde_json::to_string_pretty(&v))
            .unwrap_or_else(|_| body.clone());
        eprintln!("\x1b[90m[debug] <== HTTP {status}\n{pretty}\x1b[0m");
    }

    if !status.is_success() {
        // s11: 按状态码 + 响应体分类成强类型错误，恢复层按类型走不同路径
        let mut err = classify_http_error(status.as_u16(), &body);
        if let LlmError::RateLimited { retry_after_secs } = &mut err {
            *retry_after_secs = retry_after;
        }
        return Err(err);
    }

    // 先拿原始文本再手动解析：失败时能把响应体带出来，
    // 方便定位"网关返回了什么意料之外的东西"（最常见的调试场景）
    serde_json::from_str::<ApiResponse>(&body).map_err(|e| {
        let preview: String = body.chars().take(500).collect();
        LlmError::Other(format!("解析响应失败: {e}\n响应体前 500 字符:\n{preview}"))
    })
}

// ── 核心模式：s09 的循环 + 动态 system prompt 组装 ────────────────────
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
    cwd: &Path,
    messages: &mut Vec<Message>,
    hooks: &Hooks,
) -> Result<(), String> {
    let tools = all_tools();
    let mut rounds_since_todo: u32 = 0;
    // ── s11: 恢复状态与可变 max_tokens（一次 agent_loop 调用内共享） ──
    let mut recovery = RecoveryState::new(&cfg.model, cfg.fallback_model.clone());
    let mut max_tokens = cfg.max_tokens;

    // ── s09: 注入相关记忆到最近一条 user 消息 ──
    // ── s10: 动态 system prompt（每轮工具执行后重评估，见循环尾部） ──
    let mut ctx = update_context(cwd);
    let mut system = get_system_prompt(&ctx);

    let memories_content = load_memories(http, cfg, cwd, messages);
    let memory_turn = if !memories_content.is_empty() && !messages.is_empty() {
        let last_idx = messages.len() - 1;
        if matches!(messages[last_idx].content, MessageContent::Text(_)) { Some(last_idx) } else { None }
    } else { None };

    loop {
        // ── s05: nag reminder ──
        if rounds_since_todo >= 3 && !messages.is_empty() {
            messages.push(Message::user_text(
                "<reminder>Update your todos.</reminder>".to_string(),
            ));
            rounds_since_todo = 0;
        }

        // ── s09: 压缩前快照 —— 记忆提取要看完整原文，不能吃占位符/摘要 ──
        let pre_compress: Vec<Message> = messages.clone();

        // ── s08: 四层压缩管线（0 API 的便宜先跑） ──
        tool_result_budget(messages, 200_000);       // L3: 大结果落盘
        snip_compact(messages);                       // L1: 裁中间
        micro_compact(messages);                      // L2: 旧结果占位

        // ── s08: token 仍超阈值 → L4 LLM 摘要（1 API） ──
        if estimate_size(messages) > CONTEXT_LIMIT {
            println!("[auto compact]");
            compact_history(http, cfg, messages);
        }

        // ── s09: 把记忆内容拼到指定 user 消息前 ──
        let request_messages = if let Some(idx) = memory_turn {
            if idx < messages.len() {
                let mut modified = messages.clone();
                if let MessageContent::Text(ref text) = messages[idx].content {
                    modified[idx] = Message::user_text(format!("{memories_content}\n\n{text}"));
                }
                modified
            } else { messages.clone() }
        } else { messages.clone() };

        // 1. 把完整历史发给模型
        //    s11: with_retry 在内层吃掉瞬态错误（429/529 退避重试、529 切模型），
        //         非瞬态错误（PromptTooLong / Other）抛到外层按路径处理
        let resp = match with_retry(&mut recovery, |model| {
            call_llm(http, cfg, model, &system, &request_messages, &tools, max_tokens)
        }) {
            Ok(r) => r,
            // ── 路径2: 上下文超限 → reactive compact 后重试（仅一次） ──
            Err(LlmError::PromptTooLong) => {
                if !recovery.has_attempted_reactive_compact {
                    println!("[reactive compact]");
                    reactive_compact(http, cfg, messages);
                    recovery.has_attempted_reactive_compact = true;
                    continue;
                }
                // 压缩过一次还是超限：再压也不会变小，把错误写进历史退出
                println!("  \x1b[31m[unrecoverable] still too long after compact\x1b[0m");
                messages.push(Message::assistant_text(
                    "[Error] Context too large, cannot continue.",
                ));
                return Ok(());
            }
            // 不可恢复错误：写进历史让 REPL 当回复展示，
            // 而不是走 Err 分支弹掉用户上一条输入（对齐 Python 版）
            Err(e) => {
                // 打印截 100 字符、写入历史截 200 字符（对齐 Python 的 [:100]/[:200]）
                println!(
                    "  \x1b[31m[unrecoverable] {}\x1b[0m",
                    truncate_chars(&e.to_string(), 100)
                );
                messages.push(Message::assistant_text(error_note(&e)));
                return Ok(());
            }
        };

        // ── 路径1: 输出截断（stop_reason == max_tokens）──
        // 关键顺序：先检查截断再追加输出。第一次升级时不追加，
        // messages 保持原样，同一个请求用更大的 token 上限重发。
        if resp.stop_reason.as_deref() == Some("max_tokens") {
            match plan_truncation_recovery(&mut recovery) {
                TruncationAction::Escalate => {
                    let new_limit = escalated_limit(cfg.max_tokens);
                    println!(
                        "  \x1b[33m[max_tokens] escalating {} -> {new_limit}\x1b[0m",
                        cfg.max_tokens
                    );
                    max_tokens = new_limit;
                    continue;
                }
                TruncationAction::Continue => {
                    // 64K 仍截断：保存截断输出 + 注入续写提示，让模型接着写
                    messages.push(Message::assistant_blocks(resp.content.clone()));
                    messages.push(Message::user_text(CONTINUATION_PROMPT));
                    println!(
                        "  \x1b[33m[max_tokens] continuation {}/{MAX_RECOVERY_RETRIES}\x1b[0m",
                        recovery.recovery_count
                    );
                    continue;
                }
                TruncationAction::GiveUp => {
                    // 续写次数用尽：保留最后一次截断输出，退出本轮
                    messages.push(Message::assistant_blocks(resp.content.clone()));
                    println!("  \x1b[31m[max_tokens] recovery limit reached\x1b[0m");
                    return Ok(());
                }
            }
        }

        let stop_reason = resp.stop_reason.clone();
        messages.push(Message::assistant_blocks(resp.content.clone()));

        if stop_reason.as_deref() != Some("tool_use") {
            // ── s09: 用压缩前的快照提取记忆（本轮循环顶抓取，含完整原文） ──
            {
                extract_memories(http, cfg, cwd, &pre_compress);
                consolidate_memories(http, cfg, cwd);
            }
            if let Some(extra) = trigger_stop(hooks, messages) {
                messages.push(Message::user_text(extra));
                continue;
            }
            return Ok(());
        }

        rounds_since_todo += 1;

        let mut results: Vec<ContentBlock> = Vec::new();
        let mut compact_called = false;

        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                println!("[33m> {name}[0m");

                // ── s08: compact 工具 —— 立即摘要并 continue 下一轮 ──
                // 注意：compact 后不追加 tool_result，因为 compact_history
                // 已替换全部 messages，旧 tool_use_id 对应的 tool_use 不存在了。
                if name == "compact" {
                    println!("[compact]");
                    compact_history(http, cfg, messages);
                    compact_called = true;
                    break;
                }

                // PreToolUse hook
                if let Some(reason) = trigger_pre_tool_use(hooks, name, input) {
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: reason,
                    });
                    continue;
                }

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
                    "todo_write" => serde_json::from_value::<TodoWriteInput>(input.clone())
                        .map(run_todo_write)
                        .unwrap_or_else(|e| format!("Error: invalid todo_write params: {e}")),
                    "task" => serde_json::from_value::<TaskInput>(input.clone())
                        .map(|ti| run_task(http, cfg, hooks, ti))
                        .unwrap_or_else(|e| format!("Error: invalid task params: {e}")),
                    "load_skill" => serde_json::from_value::<LoadSkillInput>(input.clone())
                        .map(|li| load_skill(&li.name))
                        .unwrap_or_else(|e| format!("Error: invalid load_skill params: {e}")),
                    // s08: compact is intercepted before match; this branch is unreachable but satisfies exhaustive check
                    "compact" => "[Compacted]".to_string(),
                    other => format!("Error: unknown tool '{other}'"),
                };

                if name == "todo_write" {
                    rounds_since_todo = 0;
                }

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

        if compact_called {
            // compact 已替换全部 messages，直接 continue 下一轮
            continue;
        }
        messages.push(Message::user_tool_results(results));

        // ── s10: 每轮工具执行后重评估 context/system（对齐 Python 版）──
        // 工具可能新增记忆文件；缓存保证 context 没变时不重复组装
        ctx = update_context(cwd);
        system = get_system_prompt(&ctx);
    }
}


// ── 配置与入口（system prompt 由 assemble_system_prompt 动态生成） ──────

struct Config {
    /// API 端点：官方 https://api.anthropic.com 或第三方兼容网关
    base_url: String,
    /// x-api-key 认证
    api_key: Option<String>,
    /// Authorization: Bearer 认证（仅官方 API 且未设网关时生效）
    auth_token: Option<String>,
    /// 模型 ID，必填（如 claude-sonnet-4-6 / deepseek-v4-pro）
    model: String,
    /// s11: 备用模型 ID（FALLBACK_MODEL_ID，可选）——连续 529 过载时切换
    fallback_model: Option<String>,
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

    // s07: 启动时扫描 skills/ 目录，填充 SKILL_REGISTRY
    scan_skills(&cwd);

    Ok(Config {
        base_url,
        api_key: env::var("ANTHROPIC_API_KEY").ok(),
        auth_token: if using_gateway {
            None // 对齐 Python 版：base_url 存在时 pop 掉 AUTH_TOKEN
        } else {
            env::var("ANTHROPIC_AUTH_TOKEN").ok()
        },
        model,
        // s11: 备用模型——只在连续 529 过载时切换，平时不参与调用
        fallback_model: env::var("FALLBACK_MODEL_ID")
            .ok()
            .filter(|v| !v.trim().is_empty()),
        // s06: 子代理 system prompt —— 不提及 task（无此工具）、不要求规划
        sub_system: format!(
            "You are a coding agent at {}. Do not impersonate any specific AI assistant (Claude, GPT, etc.). You are a coding agent — that is your identity.. Complete the task you were given, then return a concise summary. Do not delegate further.",
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
    let cwd = env::current_dir().expect("cwd");
    let mut hooks = Hooks::new();
    register_builtin_hooks(&mut hooks);

    println!("s11: Error Recovery — retry, escalate, compact, fallback");
    println!("输入问题，回车发送。输入 q 退出。\n");

    let mut history: Vec<Message> = Vec::new();
    let stdin = io::stdin();

    loop {
        print!("\x1b[36ms11 >> \x1b[0m");
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

        match agent_loop(&http, &cfg, &cwd, &mut history, &hooks) {
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
//   - 基础工具（从 s06 携入）
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
//   - parse_frontmatter YAML 解析
//   - scan_skills + list_skills
//   - load_skill 查询
//   - snip_compact 裁剪
//   - micro_compact 占位
//   - tool_result_budget 落盘
//   - estimate_size 估算
//   - write_memory_file + rebuild_index
//   - select_relevant_memories 关键词匹配
//   - extract_memories JSON 解析
//   - assemble_system_prompt 段落组装
//   - get_system_prompt 缓存命中
//   - classify_http_error 错误分类（s11）
//   - parse_retry_after Retry-After 头解析（s11）
//   - retry_delay 指数退避公式（s11）
//   - RecoveryState：529 切换备用模型 / 截断决策（s11）
//   - with_retry 瞬态重试语义（s11）
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
        let name = "_s07_read_limit.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "a\nb\nc\nd".into() });
        let out = run_read(ReadInput { path: name.into(), limit: Some(2) });
        assert_eq!(out, "a\nb\n... (2 more lines)");
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn write_and_read_temporary_file() {
        let name = "_s07_t.tmp";
        let _ = std::fs::remove_file(name);
        assert_eq!(
            run_write(WriteInput { path: name.into(), content: "hello s04".into() }),
            "Wrote 9 bytes to _s07_t.tmp"
        );
        let out = run_read(ReadInput { path: name.into(), limit: None });
        assert_eq!(out, "hello s04");
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn edit_nonexistent_text_returns_error() {
        let name = "_s07_e.tmp";
        let _ = std::fs::remove_file(name);
        run_write(WriteInput { path: name.into(), content: "line1\nline2".into() });
        let out =
            run_edit(EditInput { path: name.into(), old_text: "NOTHERE".into(), new_text: "".into() });
        assert!(out.starts_with("Error: text not found"));
        let _ = std::fs::remove_file(name);
    }

    #[test]
    fn edit_replaces_first_occurrence() {
        let name = "_s07_e2.tmp";
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

    // ── s07 新增：parse_frontmatter ──

    #[test]
    fn parse_frontmatter_with_yaml() {
        let text = "---\nname: code-review\ndescription: Review code thoroughly\n---\n\n# Code Review\n\nContent here.";
        let (name, _desc) = parse_frontmatter(text);
        assert_eq!(name, "code-review");
        assert_eq!(_desc, "Review code thoroughly");
    }

    #[test]
    fn parse_frontmatter_no_delimiters() {
        let text = "# Just a heading\n\nNo frontmatter here.";
        let (name, _desc) = parse_frontmatter(text);
        assert_eq!(name, "");
    }

    #[test]
    fn parse_frontmatter_empty_yaml() {
        let text = "---\n---\n\nContent after empty frontmatter.";
        let (name, _desc) = parse_frontmatter(text);
        assert_eq!(name, "");
        assert_eq!(_desc, "");
    }

    #[test]
    fn parse_frontmatter_name_only() {
        let text = "---\nname: pdf\n---\n\nContent.";
        let (name, _desc) = parse_frontmatter(text);
        assert_eq!(name, "pdf");
        assert_eq!(_desc, "");
    }

    #[test]
    fn parse_frontmatter_multiline_description() {
        // 回归：多行 description（description: |）曾被手工 strip_prefix
        // 解析成孤零零的 "|"（skills/agent-builder 实际受害）
        let text = "---\nname: agent-builder\ndescription: |\n  Design agents.\n  Use when needed.\n---\n\nBody";
        let (name, desc) = parse_frontmatter(text);
        assert_eq!(name, "agent-builder");
        assert_eq!(desc, "Design agents. Use when needed.");
    }

    // ── s07 新增：load_skill ──

    #[test]
    fn load_skill_returns_content() {
        // 手动填充 registry
        {
            let mut guard = SKILL_REGISTRY.lock().unwrap();
            let map = guard.get_or_insert_with(HashMap::new);
            map.insert("test-skill".to_string(), SkillInfo {
                name: "test-skill".to_string(),
                description: "A test skill".to_string(),
                content: "Full skill content here.".to_string(),
            });
        }
        let result = load_skill("test-skill");
        assert_eq!(result, "Full skill content here.");
    }

    #[test]
    fn load_skill_not_found() {
        // 先把 registry 初始化成 Some(空表)：registry 为 None 时 load_skill
        // 返回 "(no skills loaded)"，下面的断言会误失败。此测试与
        // load_skill_returns_content 并行跑、共享 SKILL_REGISTRY，不能依赖执行顺序。
        {
            let mut guard = SKILL_REGISTRY.lock().unwrap();
            guard.get_or_insert_with(HashMap::new);
        }
        let result = load_skill("nonexistent");
        assert!(result.contains("Skill not found"));
        assert!(result.contains("nonexistent"));
    }

    // ── s07 新增：LoadSkillInput 反序列化 ──

    #[test]
    fn load_skill_input_deserializes() {
        let json = serde_json::json!({"name": "code-review"});
        let input: LoadSkillInput = serde_json::from_value(json).unwrap();
        assert_eq!(input.name, "code-review");
    }

    // ── s07 新增：list_skills ──

    #[test]
    fn list_skills_returns_catalog() {
        // 清空并重新填充 registry
        {
            let mut guard = SKILL_REGISTRY.lock().unwrap();
            let map = guard.get_or_insert_with(HashMap::new);
            map.clear();
            map.insert("alpha".to_string(), SkillInfo {
                name: "alpha".to_string(),
                description: "First skill".to_string(),
                content: "a".to_string(),
            });
            map.insert("beta".to_string(), SkillInfo {
                name: "beta".to_string(),
                description: "Second skill".to_string(),
                content: "b".to_string(),
            });
        }
        let catalog = list_skills();
        assert!(catalog.contains("**alpha**: First skill"));
        assert!(catalog.contains("**beta**: Second skill"));
    }

    // ── s08 新增：compact 反序列化 ──

    #[test]
    fn compact_input_deserializes_with_focus() {
        let json = serde_json::json!({"focus": "security review"});
        let input: CompactInput = serde_json::from_value(json).unwrap();
        assert_eq!(input.focus, Some("security review".to_string()));
    }

    #[test]
    fn compact_input_deserializes_empty() {
        let json = serde_json::json!({});
        let input: CompactInput = serde_json::from_value(json).unwrap();
        assert_eq!(input.focus, None);
    }

    // ── s08 新增：estimate_size ──

    #[test]
    fn estimate_size_empty() {
        let msgs: Vec<Message> = vec![];
        assert_eq!(estimate_size(&msgs), 2);
    }

    #[test]
    fn estimate_size_with_content() {
        let msgs = vec![Message::user_text("hello")];
        let size = estimate_size(&msgs);
        assert!(size > 10);
    }

    // ── s08 新增：helper 函数 ──

    #[test]
    fn assistant_with_tool_use_detected() {
        let msg = Message::assistant_blocks(vec![
            ContentBlock::ToolUse {
                id: "1".into(), name: "bash".into(),
                input: serde_json::json!({"command": "ls"}),
            },
        ]);
        assert!(message_has_tool_use(&msg));
    }

    #[test]
    fn assistant_without_tool_use_not_detected() {
        let msg = Message::assistant_blocks(vec![
            ContentBlock::Text { text: "hello".into() },
        ]);
        assert!(!message_has_tool_use(&msg));
    }

    #[test]
    fn tool_result_message_detected() {
        let msg = Message::user_tool_results(vec![
            ContentBlock::ToolResult { tool_use_id: "1".into(), content: "ok".into() },
        ]);
        assert!(is_tool_result_message(&msg));
    }

    #[test]
    fn user_text_not_tool_result() {
        let msg = Message::user_text("hello");
        assert!(!is_tool_result_message(&msg));
    }

    // ── s08 新增：snip_compact ──

    #[test]
    fn snip_compact_under_limit_unchanged() {
        let mut msgs: Vec<Message> = (0..10).map(|i| Message::user_text(format!("msg{i}"))).collect();
        let original_len = msgs.len();
        snip_compact(&mut msgs);
        assert_eq!(msgs.len(), original_len);
    }

    #[test]
    fn snip_compact_over_limit_trims() {
        let mut msgs: Vec<Message> = (0..60).map(|i| Message::user_text(format!("msg{i}"))).collect();
        snip_compact(&mut msgs);
        assert!(msgs.len() < 60);
        let has_placeholder = msgs.iter().any(|m| {
            matches!(&m.content, MessageContent::Text(s) if s.contains("snipped"))
        });
        assert!(has_placeholder);
    }

    // ── s08 新增：micro_compact ──

    #[test]
    fn micro_compact_replaces_old_results() {
        let mut msgs = vec![
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old1".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old2".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old3".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old4".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "recent".into(), content: "important result".to_string(),
            }]),
        ];
        micro_compact(&mut msgs);
        // 5 results, KEEP_RECENT=3, first 2 compacted
        if let MessageContent::Blocks(blocks) = &msgs[0].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert!(content.contains("compacted"));
            }
        }
        if let MessageContent::Blocks(blocks) = &msgs[4].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert_eq!(content, "important result");
            }
        }
    }

    #[test]
    fn tail_keep_start_keeps_last_five() {
        let msgs: Vec<Message> = (0..8).map(|i| Message::user_text(format!("m{i}"))).collect();
        assert_eq!(tail_keep_start(&msgs), 3); // 8 - 5
    }

    #[test]
    fn tail_keep_start_zero_for_short_history() {
        let msgs: Vec<Message> = (0..3).map(|i| Message::user_text(format!("m{i}"))).collect();
        assert_eq!(tail_keep_start(&msgs), 0);
    }

    #[test]
    fn tail_keep_start_adjusts_for_tool_pair() {
        // 边界恰好落在 tool_use/tool_result 配对中间时回退一条：
        // 7 条消息 → tail_start=2，messages[2] 是 tool_result、messages[1] 是 tool_use
        // → 修正为 1（保留完整配对）
        let mut msgs: Vec<Message> = vec![Message::user_text("earlier")];
        msgs.push(Message::assistant_blocks(vec![ContentBlock::ToolUse {
            id: "t1".into(),
            name: "bash".into(),
            input: serde_json::json!({}),
        }]));
        msgs.push(Message::user_tool_results(vec![ContentBlock::ToolResult {
            tool_use_id: "t1".into(),
            content: "out".into(),
        }]));
        msgs.extend((0..4).map(|i| Message::user_text(format!("m{i}"))));
        assert_eq!(tail_keep_start(&msgs), 1);
    }

    // ── s09 新增：write_memory_file + rebuild_index ──

    // 测试辅助：每个用例用独立的临时目录当作 cwd。
    // 记忆系统落在 <cwd>/.memory 下，若所有测试共享 Path::new(".")，
    // 并行执行时各自的 remove_dir_all 会互相删掉对方的文件（race）。
    fn test_cwd(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("lcc-s10-test-{}-{tag}", std::process::id()));
        let _ = fs::remove_dir_all(&dir); // 清理上次运行可能留下的残留
        dir
    }

    #[test]
    fn write_and_read_memory() {
        let cwd = test_cwd("write");
        write_memory_file(&cwd, "test-pref", "user", "Test preference", "Use tabs");
        let files = list_memory_files(&cwd);
        assert!(files.iter().any(|f| f.name == "test-pref"));
        let content = read_memory_file(&cwd, "test-pref.md");
        assert!(content.unwrap().contains("Use tabs"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn memory_index_contains_entry() {
        let cwd = test_cwd("index");
        write_memory_file(&cwd, "idx-test", "project", "Test index", "Index body");
        let index = read_memory_index(&cwd);
        assert!(index.contains("idx-test"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn rebuild_index_desc_falls_back_to_body_first_line() {
        // 回归：description 为空时，索引描述应回退正文首行并截 80 字符
        // （对齐 Python 的 body.split("\n")[0][:80]）；曾把 raw 首行 "---" 当描述
        let cwd = test_cwd("desc-fallback");
        let dir = memory_dir(&cwd);
        fs::create_dir_all(&dir).ok();
        let long_first: String = format!("# {}", "长".repeat(200));
        fs::write(
            dir.join("no-desc.md"),
            format!("---\nname: no-desc\ntype: project\ndescription:\n---\n\n{long_first}\nbody..."),
        )
        .ok();
        rebuild_index(&cwd);
        let index = read_memory_index(&cwd);
        assert!(index.contains("长"), "索引应包含正文首行内容");
        assert!(!index.contains("— ---"), "索引不应出现 frontmatter 标记作为描述");
        // 80 字符截断：200 个"长"只留 80 个
        assert!(index.contains(&"长".repeat(80)));
        assert!(!index.contains(&"长".repeat(81)));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn memory_info_has_type_field() {
        let cwd = test_cwd("type");
        write_memory_file(&cwd, "type-test", "feedback", "Type check", "Body");
        let files = list_memory_files(&cwd);
        let mem = files.iter().find(|f| f.name == "type-test").unwrap();
        assert_eq!(mem.mem_type, "feedback");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn extract_frontmatter_field_works() {
        let text = "---\nname: test\ntype: project\n---\n\nBody";
        assert_eq!(extract_frontmatter_field(text, "type"), Some("project".to_string()));
        assert_eq!(extract_frontmatter_field(text, "name"), Some("test".to_string()));
        assert_eq!(extract_frontmatter_field(text, "missing"), None);
    }

    // ── s10 新增：assemble_system_prompt ──

    #[test]
    fn assemble_prompt_without_memories() {
        let ctx = PromptContext {
            enabled_tools: vec!["bash".into(), "read_file".into()],
            workspace: "/test".into(),
            memories: String::new(),
            skills: String::new(),
        };
        let prompt = assemble_system_prompt(&ctx);
        assert!(prompt.contains("bash"));
        assert!(prompt.contains("/test"));
        assert!(!prompt.contains("Relevant memories"));
        assert!(!prompt.contains("Available skills"));
    }

    #[test]
    fn assemble_prompt_with_memories() {
        let ctx = PromptContext {
            enabled_tools: vec!["bash".into()],
            workspace: "/test".into(),
            memories: "- [pref](pref.md)".into(),
            skills: String::new(),
        };
        let prompt = assemble_system_prompt(&ctx);
        assert!(prompt.contains("Relevant memories"));
        assert!(prompt.contains("pref"));
    }

    #[test]
    fn assemble_prompt_includes_skill_catalog() {
        // 回归测试：s10 重构 4 段式 prompt 时曾漏接技能目录（s07 两层注入的第一层），
        // 导致模型看不到可用技能名。此测试守住 skills 段落与缓存 key 的集成点。
        let ctx = PromptContext {
            enabled_tools: vec!["bash".into()],
            workspace: "/test".into(),
            memories: String::new(),
            skills: "- **code-review**: Review code\n- **pdf**: Generate PDFs".into(),
        };
        let prompt = assemble_system_prompt(&ctx);
        assert!(prompt.contains("Available skills"));
        assert!(prompt.contains("code-review"));
        assert!(prompt.contains("pdf"));
    }

    #[test]
    fn get_system_prompt_returns_string() {
        let ctx = PromptContext {
            enabled_tools: vec!["bash".into()],
            workspace: "/tmp".into(),
            memories: String::new(),
            skills: String::new(),
        };
        let result = get_system_prompt(&ctx);
        assert!(!result.is_empty());
    }

    #[test]
    fn select_relevant_memories_empty_when_no_files() {
        let cwd = test_cwd("empty");
        let msgs = vec![Message::user_text("hello world")];
        let result = select_relevant_memories(
            &reqwest::blocking::Client::new(),
            &Config { sub_system: "".into(), model: "".into(), fallback_model: None, base_url: "".into(), api_key: None, auth_token: None, max_tokens: 8000, effort: None, beta: None, debug: false },
            &cwd, &msgs);
        assert!(result.is_empty());
        let _ = fs::remove_dir_all(&cwd);
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

    // ── 记忆噪声调优（s09/s10 同步）──

    #[test]
    fn classify_memory_dedup() {
        let existing = vec![MemoryInfo {
            filename: "code-style.md".into(),
            name: "code-style".into(),
            description: "Use 4 spaces".into(),
            mem_type: "preference".into(),
            body: "Indent with 4 spaces".into(),
        }];
        // 同名 → 更新（覆盖）
        assert!(matches!(classify_memory(&existing, "code style", "New desc", "New body"), MemoryAction::Update));
        // 内容完全相同 → 跳过
        assert!(matches!(classify_memory(&existing, "other", "Use 4 spaces", "Indent with 4 spaces"), MemoryAction::Skip));
        // 全新 → 新增
        assert!(matches!(classify_memory(&existing, "other", "other desc", "other body"), MemoryAction::New));
    }

    #[test]
    fn should_extract_gating() {
        assert!(should_extract(&[Message::user_text("记住我喜欢 4 空格缩进")]));
        assert!(should_extract(&[Message::user_text("please remember to use tabs")]));
        assert!(!should_extract(&[Message::user_text("列出当前目录的文件")]));
        assert!(should_extract(&[Message::user_text(&"长".repeat(201))]));
    }

    // ── s11 新增：错误分类与恢复 ──

    /// with_retry 测试用的最小合法响应
    fn ok_resp() -> ApiResponse {
        ApiResponse {
            content: vec![],
            stop_reason: Some("end_turn".into()),
        }
    }

    #[test]
    fn classify_http_error_rate_limited() {
        assert!(matches!(
            classify_http_error(429, "{\"error\":\"rate limit\"}"),
            LlmError::RateLimited { retry_after_secs: None }
        ));
    }

    #[test]
    fn classify_http_error_overloaded() {
        // 官方 529
        assert!(matches!(
            classify_http_error(529, "{\"error\":\"overloaded\"}"),
            LlmError::Overloaded
        ));
        // 部分网关用 500/503 + body 里带 overloaded
        assert!(matches!(
            classify_http_error(500, "internal server error: overloaded"),
            LlmError::Overloaded
        ));
        assert!(matches!(
            classify_http_error(503, "overloaded_error"),
            LlmError::Overloaded
        ));
    }

    #[test]
    fn classify_http_error_prompt_too_long_variants() {
        for body in [
            "{\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",\"message\":\"prompt is too long\"}}",
            "prompt too long",
            "prompt_is_too_long",
            "context_length_exceeded",
            "max_context_window exceeded",
            "your prompt contains too many tokens",
            // 泛匹配兜底（Python 的 ("prompt" in msg and "long" in msg)）
            "the prompt was too long to process",
        ] {
            assert!(
                matches!(classify_http_error(400, body), LlmError::PromptTooLong),
                "body 应该被分类为 PromptTooLong: {body}"
            );
        }
    }

    #[test]
    fn classify_http_error_other() {
        assert!(matches!(
            classify_http_error(400, "invalid api key"),
            LlmError::Other(_)
        ));
        assert!(matches!(
            classify_http_error(500, "plain internal error"),
            LlmError::Other(_)
        ));
    }

    #[test]
    fn parse_retry_after_variants() {
        assert_eq!(parse_retry_after(Some("5")), Some(5));
        assert_eq!(parse_retry_after(Some(" 12 ")), Some(12));
        assert_eq!(parse_retry_after(Some("abc")), None);
        assert_eq!(parse_retry_after(Some("")), None);
        assert_eq!(parse_retry_after(None), None);
    }

    #[test]
    fn retry_delay_retry_after_priority() {
        // Retry-After 头优先级最高，精确按秒等，无抖动
        assert_eq!(retry_delay(0, Some(42)), Duration::from_secs(42));
    }

    #[test]
    fn retry_delay_exponential_and_cap() {
        // 基础值 min(500 × 2^attempt, 32000)ms，抖动 0~25%：
        // attempt 0 -> [500, 625]
        for _ in 0..50 {
            let d = retry_delay(0, None);
            assert!(d >= Duration::from_millis(500) && d <= Duration::from_millis(625));
        }
        // attempt 1 -> [1000, 1250]
        for _ in 0..50 {
            let d = retry_delay(1, None);
            assert!(d >= Duration::from_millis(1000) && d <= Duration::from_millis(1250));
        }
        // attempt 6+ 封顶 -> [32000, 40000]
        for _ in 0..50 {
            let d = retry_delay(6, None);
            assert!(d >= Duration::from_millis(32000) && d <= Duration::from_millis(40000));
            let d30 = retry_delay(30, None);
            assert!(d30 >= Duration::from_millis(32000) && d30 <= Duration::from_millis(40000));
        }
    }

    #[test]
    fn llm_error_is_transient() {
        assert!(LlmError::RateLimited { retry_after_secs: None }.is_transient());
        assert!(LlmError::Overloaded.is_transient());
        assert!(!LlmError::PromptTooLong.is_transient());
        assert!(!LlmError::Other("x".into()).is_transient());
    }

    #[test]
    fn llm_error_display() {
        assert_eq!(format!("{}", LlmError::Overloaded), "529 过载");
        assert_eq!(format!("{}", LlmError::PromptTooLong), "上下文超限");
        assert_eq!(format!("{}", LlmError::Other("boom".into())), "boom");
        assert_eq!(
            format!("{}", LlmError::RateLimited { retry_after_secs: Some(7) }),
            "429 限流（Retry-After: 7s）"
        );
    }

    #[test]
    fn recovery_state_529_switch_after_three() {
        let mut state = RecoveryState::new("primary", Some("fallback".into()));
        assert!(!state.register_529()); // 1
        assert!(!state.register_529()); // 2
        assert!(state.register_529()); // 3 -> 切换
        assert_eq!(state.current_model, "fallback");
        assert_eq!(state.consecutive_529, 0); // 切换后计数清零
    }

    #[test]
    fn recovery_state_529_no_fallback_keeps_retrying() {
        let mut state = RecoveryState::new("primary", None);
        assert!(!state.register_529());
        assert!(!state.register_529());
        assert!(!state.register_529()); // 3 -> 重置计数继续重试
        assert_eq!(state.current_model, "primary");
        assert_eq!(state.consecutive_529, 0);
    }

    #[test]
    fn plan_truncation_escalate_then_continue_then_give_up() {
        let mut state = RecoveryState::new("primary", None);
        // 第一次截断：升级
        assert!(matches!(plan_truncation_recovery(&mut state), TruncationAction::Escalate));
        assert!(state.has_escalated);
        // 64K 仍截断：续写 ×3
        for i in 1..=3 {
            assert!(matches!(
                plan_truncation_recovery(&mut state),
                TruncationAction::Continue
            ));
            assert_eq!(state.recovery_count, i);
        }
        // 第 4 次截断：放弃
        assert!(matches!(plan_truncation_recovery(&mut state), TruncationAction::GiveUp));
        assert_eq!(state.recovery_count, 3); // 计数不再增长
    }

    #[test]
    fn with_retry_success_first_try() {
        let mut calls = 0;
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            calls += 1;
            Ok(ok_resp())
        });
        assert!(r.is_ok());
        assert_eq!(calls, 1);
        assert_eq!(state.current_model, "primary");
    }

    #[test]
    fn with_retry_reraises_non_transient_immediately() {
        let mut calls = 0;
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            calls += 1;
            Err(LlmError::PromptTooLong)
        });
        assert!(matches!(r, Err(LlmError::PromptTooLong)));
        assert_eq!(calls, 1); // 不重试，立即向上抛
    }

    #[test]
    fn with_retry_retries_transient_then_succeeds() {
        // Retry-After: 0 -> 立即重试，测试不需要真实 sleep
        let mut calls = 0;
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            calls += 1;
            if calls == 1 {
                Err(LlmError::RateLimited { retry_after_secs: Some(0) })
            } else {
                Ok(ok_resp())
            }
        });
        assert!(r.is_ok());
        assert_eq!(calls, 2);
    }

    #[test]
    fn with_retry_exhausts_after_max_retries() {
        let mut calls = 0;
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            calls += 1;
            Err(LlmError::RateLimited { retry_after_secs: Some(0) })
        });
        assert!(matches!(r, Err(LlmError::Other(msg)) if msg.contains("Max retries")));
        assert_eq!(calls, MAX_RETRIES as usize);
    }

    #[test]
    fn error_note_truncates_long_error_char_safe() {
        // 超长错误体必须截断，否则响应体全文进历史污染上下文（对齐 Python [:200]）
        let long_ascii: String = "A".repeat(1000);
        let note = error_note(&LlmError::Other(long_ascii));
        assert!(note.starts_with("[Error] "));
        assert_eq!(note.chars().count(), "[Error] ".chars().count() + 200);
        assert!(note.ends_with('A'));

        // 中文按字符截断：不 panic、不产生半个字符
        let long_cn: String = "错".repeat(1000);
        let note_cn = error_note(&LlmError::Other(long_cn));
        assert!(note_cn.starts_with("[Error] 错"));
        assert_eq!(note_cn.chars().count(), "[Error] ".chars().count() + 200);
        assert_eq!(note_cn.chars().filter(|&c| c == '错').count(), 200);
    }

    #[test]
    fn escalated_limit_never_lowers_configured_limit() {
        // 默认 8000 → 64000
        assert_eq!(escalated_limit(8000), 64000);
        // 用户配了更大的上限（MAX_TOKENS=100000）→ 升级不能反而降级
        assert_eq!(escalated_limit(100000), 100000);
    }

    #[test]
    fn with_retry_passes_current_model_into_closure() {        // 验证 with_retry 每轮都用 state.current_model 调闭包：
        // 模拟一次 529 切换后（直接改状态），下一次重试应该看到 fallback 模型。
        // 用 RateLimited + Retry-After: 0 走重试路径且不真实 sleep。
        let mut calls = 0;
        let mut state = RecoveryState::new("primary", Some("fallback".into()));
        state.register_529(); // 1
        state.register_529(); // 2
        state.register_529(); // 3 -> 切到 fallback
        assert_eq!(state.current_model, "fallback");
        let r = with_retry(&mut state, |model| {
            calls += 1;
            assert_eq!(model, "fallback"); // 闭包收到的是切换后的模型
            if calls == 1 {
                Err(LlmError::RateLimited { retry_after_secs: Some(0) })
            } else {
                Ok(ok_resp())
            }
        });
        assert!(r.is_ok());
        assert_eq!(calls, 2);
    }
}
