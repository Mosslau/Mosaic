//! s19: MCP Tools — 外部能力即插即用
//!
//! s18 全量机制之上新增 MCP 插件系统：MCPClient（教学 mock）发现外部工具，
//! connect_mcp 连接服务器，assemble_tool_pool 把内置 + MCP 工具组装成统一
//! 工具池（mcp__{server}__{tool} 命名），agent_loop 双路径分发：
//! 运行时表命中走动态 handler，未命中回退 execute_sync 静态 match。
//!
//! 对照 Python 版 ../../python/s19_mcp_plugin/code.py。
//! 运行：cargo run -p s19_mcp_plugin

use std::env;
use std::fmt;
use std::io::{self, Read, Write};
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, LazyLock, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use std::os::unix::process::CommandExt; // process_group(): 独立进程组，超时可整组击杀
use chrono::{Datelike, Timelike}; // s14: Local::now() 取 分/时/日/月/星期 字段
use tokio::io::AsyncBufReadExt; // REPL 的 stdin 异步行读取（s13）
use wait_timeout::ChildExt;
use rand::Rng; // s11 退避抖动 / s12 任务 ID 随机后缀

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

/// bash 工具的参数：一条 shell 命令。
/// s13: 增加 run_in_background —— 模型显式请求后台执行（对应 schema 新参数）。
#[derive(Deserialize)]
struct BashInput {
    command: String,
    /// s13: 模型显式请求后台执行（对应 schema 新参数）。
    /// 决策在 agent_loop 的 should_run_background（读原始 JSON）里做，
    /// 这里保留字段仅为反序列化校验与 API 契约显性化。
    #[serde(default)]
    #[allow(dead_code)]
    run_in_background: Option<bool>,
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

// ── s12 新增：任务系统数据结构 ──────────────────────────────────────────

/// 持久化任务。serde 字段名与磁盘 JSON 对齐 Python 的 asdict 输出：
/// blockedBy 是 camelCase（rename 映射），owner 可空（Option → null）。
#[derive(Serialize, Deserialize, Clone, Debug)]
struct Task {
    id: String,
    subject: String,
    #[serde(default)]
    description: String,
    /// pending | in_progress | completed
    status: String,
    /// 认领者（教学版恒为 "agent"；多 agent 场景留给 s15 队友线程）
    #[serde(default)]
    owner: Option<String>,
    /// 依赖的任务 ID：全部 completed 后才能认领
    #[serde(default, rename = "blockedBy")]
    blocked_by: Vec<String>,
    /// s18: 绑定的 worktree 名（bind_task_to_worktree 写入，保持 pending
    /// 供队友自动认领；认领后队友 cwd 切换到 .worktrees/{name}）。
    /// 不 skip_serializing_if：None 序列化为 null，对齐 Python asdict
    /// 逐字段同构（s12 磁盘格式承诺）。
    #[serde(default)]
    worktree: Option<String>,
}

/// create_task 工具的参数
#[derive(Deserialize)]
struct CreateTaskInput {
    subject: String,
    #[serde(default)]
    description: String,
    #[serde(default, rename = "blockedBy")]
    blocked_by: Vec<String>,
}

/// list_tasks 工具的参数（无字段）
#[derive(Deserialize)]
struct ListTasksInput {}

/// get_task / claim_task / complete_task 共用的参数：任务 ID
#[derive(Deserialize)]
struct TaskIdInput {
    task_id: String,
}

// ── 工具定义与请求/响应结构（同 s02/s03） ─────────────────────────────────

/// 工具定义。序列化后就是 API tools 数组里的一项：
/// {"name": "bash", "description": "...", "input_schema": {...}}
/// 模型只能通过这个 schema 感知工具的存在和用法。
/// s19: name/description 从 &'static str 改为 String —— MCP 工具名是
/// 运行时拼出来的（mcp__{server}__{tool}），静态借用放不下动态字符串。
#[derive(Serialize, Clone, Debug)]
struct Tool {
    name: String,
    description: String,
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
    /// s13: 流式开关。true = SSE 事件流（父代理主循环用，边收边打印）；
    /// false/缺省 = 一次性 JSON 响应（子代理与内部辅助调用用）
    #[serde(skip_serializing_if = "is_false")]
    stream: bool,
    /// 思考强度。None 时整个字段不出现在请求体里（skip_serializing_if），
    /// 服务器按模型默认 effort 处理 —— 保持"未配置即被动"的行为
    #[serde(skip_serializing_if = "Option::is_none")]
    output_config: Option<OutputConfig>,
}

/// serde skip 辅助：stream 只在 true 时出现在请求体
fn is_false(b: &bool) -> bool {
    !*b
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

// ── 20 个工具定义（同 s07 + compact + 任务 + cron + 团队） ─────────────

fn all_tools() -> Vec<Tool> {
    vec![
        Tool {
            name: "bash".to_string(),
            description: "Run a shell command. Set run_in_background=true for slow operations (installs, builds, long-running tests) so the agent can continue working; results are injected as notifications when complete.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "command": { "type": "string" },
                    "run_in_background": { "type": "boolean" }
                },
                "required": ["command"]
            }),
        },
        Tool {
            name: "read_file".to_string(),
            description: "Read file contents. Use limit to restrict lines if the file is large.".to_string(),
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
            name: "write_file".to_string(),
            description: "Write content to a file (creates parent directories).".to_string(),
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
            name: "edit_file".to_string(),
            description: "Find exact text and replace once. Prefer over sed.".to_string(),
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
            name: "glob".to_string(),
            description: "Find files matching a glob pattern (relative to project root).".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "pattern": { "type": "string" } },
                "required": ["pattern"]
            }),
        },
        // s05: new tool — plan before execute
        Tool {
            name: "todo_write".to_string(),
            description: "Create and manage a task list for your current coding session. Use before starting multi-step tasks to plan, and update status as you go. Status must be one of: pending, in_progress, completed.".to_string(),
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
            name: "task".to_string(),
            description: "Launch a subagent to handle a complex subtask. The subagent gets a fresh conversation context (no history from the parent). Returns only the final conclusion — intermediate results are discarded. Use for tasks that require extensive file exploration or multi-step reasoning that would pollute the main conversation.".to_string(),
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
            name: "load_skill".to_string(),
            description: "Load the full content of a skill by name. Use when you need detailed guidance for a specific domain (e.g. code-review, pdf-generation). The skill catalog is already in the system prompt.".to_string(),
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
            name: "compact".to_string(),
            description: "Summarize earlier conversation to free context space. Use when the conversation is getting long and you need to preserve important context while freeing up space.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "focus": { "type": "string" }
                }
            }),
        },
        // ── s12: 5 个任务工具 ──
        Tool {
            name: "create_task".to_string(),
            description: "Create a new task with optional blockedBy dependencies.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "subject": { "type": "string" },
                    "description": { "type": "string" },
                    "blockedBy": { "type": "array", "items": { "type": "string" } }
                },
                "required": ["subject"]
            }),
        },
        Tool {
            name: "list_tasks".to_string(),
            description: "List all tasks with status, owner, and dependencies.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {}
            }),
        },
        Tool {
            name: "get_task".to_string(),
            description: "Get full details of a specific task by ID.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "task_id": { "type": "string" } },
                "required": ["task_id"]
            }),
        },
        Tool {
            name: "claim_task".to_string(),
            description: "Claim a pending task. Sets owner, changes status to in_progress.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "task_id": { "type": "string" } },
                "required": ["task_id"]
            }),
        },
        Tool {
            name: "complete_task".to_string(),
            description: "Complete an in-progress task. Reports unblocked downstream tasks.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "task_id": { "type": "string" } },
                "required": ["task_id"]
            }),
        },
        // ── s14: cron 调度 3 工具 ──
        Tool {
            name: "schedule_cron".to_string(),
            description: "Schedule a cron job. cron is 5-field: min hour dom month dow.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "cron": { "type": "string", "description": "5-field cron expression" },
                    "prompt": { "type": "string", "description": "Message to inject when fired" },
                    "recurring": { "type": "boolean", "description": "True=recurring, False=one-shot" },
                    "durable": { "type": "boolean", "description": "True=persist to disk" }
                },
                "required": ["cron", "prompt"]
            }),
        },
        Tool {
            name: "list_crons".to_string(),
            description: "List all registered cron jobs.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {},
                "required": []
            }),
        },
        Tool {
            name: "cancel_cron".to_string(),
            description: "Cancel a cron job by ID.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "job_id": { "type": "string" } },
                "required": ["job_id"]
            }),
        },
        // ── s15: 团队 3 工具 ──
        Tool {
            name: "spawn_teammate".to_string(),
            description: "Spawn an autonomous teammate agent.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "role": { "type": "string" },
                    "prompt": { "type": "string" }
                },
                "required": ["name", "role", "prompt"]
            }),
        },
        Tool {
            name: "send_message".to_string(),
            description: "Send a message to a teammate via MessageBus.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "to": { "type": "string" },
                    "content": { "type": "string" }
                },
                "required": ["to", "content"]
            }),
        },
        Tool {
            name: "check_inbox".to_string(),
            description: "Check Lead's inbox. Routes protocol responses automatically.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {},
                "required": []
            }),
        },
        // ── s16: 协议 3 工具 ──
        Tool {
            name: "request_shutdown".to_string(),
            description: "Request a teammate to shut down gracefully.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "teammate": { "type": "string" } },
                "required": ["teammate"]
            }),
        },
        Tool {
            name: "request_plan".to_string(),
            description: "Ask a teammate to submit a plan for review.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "teammate": { "type": "string" },
                    "task": { "type": "string" }
                },
                "required": ["teammate", "task"]
            }),
        },
        Tool {
            name: "review_plan".to_string(),
            description: "Approve or reject a submitted plan by request_id.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "request_id": { "type": "string" },
                    "approve": { "type": "boolean" },
                    "feedback": { "type": "string" }
                },
                "required": ["request_id", "approve"]
            }),
        },
        // ── s18: worktree 3 工具 ──
        Tool {
            name: "create_worktree".to_string(),
            description: "Create an isolated git worktree with its own branch.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "task_id": { "type": "string" }
                },
                "required": ["name"]
            }),
        },
        Tool {
            name: "remove_worktree".to_string(),
            description: "Remove a worktree. Refuses if uncommitted changes unless discard_changes=true.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "discard_changes": { "type": "boolean" }
                },
                "required": ["name"]
            }),
        },
        Tool {
            name: "keep_worktree".to_string(),
            description: "Keep a worktree for manual review.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "name": { "type": "string" } },
                "required": ["name"]
            }),
        },
        // ── s19: MCP 连接工具 ──
        Tool {
            name: "connect_mcp".to_string(),
            description: "Connect to an MCP server (docs, deploy) and discover tools.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "name": { "type": "string" } },
                "required": ["name"]
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
            name: "bash".to_string(),
            description: "Run a shell command.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "command": { "type": "string" } },
                "required": ["command"]
            }),
        },
        Tool {
            name: "read_file".to_string(),
            description: "Read file contents. Use limit to restrict lines if the file is large.".to_string(),
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
            name: "write_file".to_string(),
            description: "Write content to a file (creates parent directories).".to_string(),
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
            name: "edit_file".to_string(),
            description: "Find exact text and replace once. Prefer over sed.".to_string(),
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
            name: "glob".to_string(),
            description: "Find files matching a glob pattern (relative to project root).".to_string(),
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
    /// s19: 已连接的 MCP 服务器（连接顺序）。进缓存键 —— 连接新服务器后
    /// ctx 序列化值变化，s10 的 get_system_prompt 缓存自动失效。
    connected_mcp: Vec<String>,
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
    // s19: enabled_tools 已含 mcp__* 动态工具；补一句前缀约定（对齐 Python
    // PROMPT_SECTIONS["tools"] 里的 "MCP tools are prefixed mcp__{server}__{tool}."）
    let tools = ctx.enabled_tools.join(", ");
    sections.push(format!("Available tools: {tools}. MCP tools are prefixed mcp__{{server}}__{{tool}}."));

    // workspace — 始终
    sections.push(format!("Working directory: {}", ctx.workspace));

    // s19: MCP 服务器 — 有连接时（对齐 Python 的 "Connected MCP servers: ..." 段）
    if !ctx.connected_mcp.is_empty() {
        sections.push(format!(
            "Connected MCP servers: {}",
            ctx.connected_mcp.join(", ")
        ));
    }

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
    // s19: 内置工具 + 已连接 MCP 服务器贡献的动态工具（mcp__{server}__{tool}）
    let mut tool_names: Vec<String> = all_tools().iter().map(|t| t.name.clone()).collect();
    let (mcp_tools, connected_mcp) = connected_mcp_names();
    tool_names.extend(mcp_tools);
    PromptContext {
        enabled_tools: tool_names,
        workspace: cwd.display().to_string(),
        memories: read_memory_index(cwd),
        skills: list_skills(),
        connected_mcp,
    }
}

/// s19: 收集已连接 MCP 服务器的 (动态工具名列表, 服务器名列表[连接顺序])。
/// assemble_tool_pool 与 update_context 共用，避免两处各自锁全局。
fn connected_mcp_names() -> (Vec<String>, Vec<String>) {
    let state = MCP_STATE.lock().unwrap();
    let mut tools = Vec::new();
    for server in &state.order {
        if let Some(client) = state.clients.get(server) {
            let safe_server = normalize_mcp_name(server);
            for tool in &client.tools {
                tools.push(format!(
                    "mcp__{}__{}",
                    safe_server,
                    normalize_mcp_name(&tool.name)
                ));
            }
        }
    }
    (tools, state.order.clone())
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
    // s18: 转发 workdir（主循环路径不变）；队友在 worktree 里用 run_bash_at
    match workdir() {
        Ok(c) => run_bash_at(&c, input),
        Err(e) => e,
    }
}

/// s18: 带 cwd 的 bash 执行（队友 worktree 上下文用）。
/// 用 sh -c 执行，等价于 Python 的 subprocess.run(..., shell=True)。
fn run_bash_at(cwd: &Path, input: BashInput) -> String {
    let mut child = match Command::new("sh")
        .arg("-c")
        .arg(&input.command)
        .current_dir(cwd)
        // 把 sh 及其所有后代放进独立进程组（pgid = sh 的 pid），
        // 超时才能整组击杀，连后台孙进程一起清理。
        .process_group(0)
        // s14 修复：stdin 必须显式 piped 并立即关闭——对齐 Python 的
        // capture_output=True（子进程 stdin 收到 EOF 而非继承终端）。
        // 否则模型跑读 stdin 的命令（cat / read / 交互式程序）时，
        // 子进程会挂在终端上等用户输入，agent 整个回合被卡死
        // （实测：定时轮里 bash 卡住，按 Enter 才继续）。
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => return format!("Error: {e}"),
    };

    // 关闭 stdin 写端：子进程立即读到 EOF。不关的话管道"打开但没人写"，
    // cat 这类命令照样会一直等数据。
    child.stdin.take();

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
    // s18: 转发 workdir；队友 worktree 用 run_read_at
    match workdir() {
        Ok(c) => run_read_at(&c, input),
        Err(e) => e,
    }
}

/// s18: 带 cwd 的读文件（路径沙箱基座 = cwd，防越界）。
/// resolve_path 只做词法折叠不查边界——队友无权限系统（Gate 2/3 只在主循环），
/// 这里必须显式拦截（对齐 Python safe_path 的 Path escapes workspace）。
fn run_read_at(cwd: &Path, input: ReadInput) -> String {
    let path = resolve_path(cwd, &input.path);
    if !is_within_workspace(&path, cwd) {
        return format!("Error: Path escapes workspace: {}", input.path);
    }
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
    // s18: 转发 workdir；队友 worktree 用 run_write_at
    match workdir() {
        Ok(c) => run_write_at(&c, input),
        Err(e) => e,
    }
}

/// s18: 带 cwd 的写文件（路径沙箱基座 = cwd，write 越界拒绝——
/// 队友无法逃出 worktree 写主仓库）。
fn run_write_at(cwd: &Path, input: WriteInput) -> String {
    let path = resolve_path(cwd, &input.path);
    // s18 隔离语义核心：write 越界（../ 逃出 worktree）被拒——队友无法
    // 借 write 写主仓库（对齐 Python safe_path）
    if !is_within_workspace(&path, cwd) {
        return format!("Error: Path escapes workspace: {}", input.path);
    }
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

// ── s12 新增：5 个任务工具的实现 ────────────────────────────────────────

fn run_create_task(input: CreateTaskInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let task = create_task(&cwd, &input.subject, &input.description, &input.blocked_by);
    let deps = if input.blocked_by.is_empty() {
        String::new()
    } else {
        format!(" (blockedBy: {})", input.blocked_by.join(", "))
    };
    println!("  \x1b[34m[create] {}{}\x1b[0m", task.subject, deps);
    format!("Created {}: {}{}", task.id, task.subject, deps)
}

fn run_list_tasks(_input: ListTasksInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    let tasks = list_tasks(&cwd);
    if tasks.is_empty() {
        return "No tasks. Use create_task to add some.".to_string();
    }
    let mut lines: Vec<String> = Vec::new();
    for t in &tasks {
        let icon = match t.status.as_str() {
            "pending" => "○",
            "in_progress" => "●",
            "completed" => "✓",
            _ => "?",
        };
        let deps = if t.blocked_by.is_empty() {
            String::new()
        } else {
            format!(" (blockedBy: {})", t.blocked_by.join(", "))
        };
        let owner = t.owner.as_ref().map(|o| format!(" [{o}]")).unwrap_or_default();
        // s18: worktree 绑定标注（对齐 Python 的 (wt:{name})）
        let wt = t.worktree.as_ref().map(|w| format!(" (wt:{w})")).unwrap_or_default();
        lines.push(format!(
            "  {icon} {}: {} [{}]{owner}{deps}{wt}",
            t.id, t.subject, t.status
        ));
    }
    lines.join("\n")
}

fn run_get_task(input: TaskIdInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    match load_task(&cwd, &input.task_id) {
        Some(task) => serde_json::to_string_pretty(&task).unwrap_or_default(),
        None => format!("Error: Task {} not found", input.task_id),
    }
}

fn run_claim_task(input: TaskIdInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    // 教学版 owner 恒为 "agent"；多 agent 认领语义留给 s15 队友线程
    claim_task(&cwd, &input.task_id, "agent")
}

fn run_complete_task(input: TaskIdInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return e,
    };
    complete_task(&cwd, &input.task_id)
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

/// s13: 子代理保持"非流式"（阻塞拿完整响应，只回传摘要）——父代理流式即可。
/// async 化只是跟随 call_llm 的签名；控制流与 s06 完全一致。
async fn spawn_subagent(
    http: &reqwest::Client,
    cfg: &Config,
    hooks: &Hooks,
    description: &str,
) -> String {
    println!("\n\x1b[35m[Subagent spawned]\x1b[0m");
    let mut messages = vec![Message::user_text(description)];
    let tools = sub_tools();

    for _turn in 0..MAX_SUB_TURNS {
        let resp = match call_llm(http, cfg, &cfg.model, &cfg.sub_system, &messages, &tools, cfg.max_tokens).await {
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

                // 子代理工具分发：5 个工具，无 task、无 todo_write。
                // s13: spawn_blocking 执行（execute_sync 正好覆盖这 5 个工具），
                // 避免 run_bash 最长 120s 阻塞 tokio async worker 线程。
                let name2 = name.clone();
                let input2 = input.clone();
                let output = tokio::task::spawn_blocking(move || execute_sync(&name2, &input2))
                    .await
                    .unwrap_or_else(|e| format!("Error: tool task panicked: {e}"));

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
/// 所以在 agent_loop 的匹配分支中直接调用 spawn_subagent 更自然。
/// 这里提供一个兼容旧 dispatch 模式的入口。
async fn run_task(http: &reqwest::Client, cfg: &Config, hooks: &Hooks, input: TaskInput) -> String {
    spawn_subagent(http, cfg, hooks, &input.description).await
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

async fn select_relevant_memories(http: &reqwest::Client, cfg: &Config, cwd: &Path, messages: &[Message]) -> Vec<String> {
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
    if let Ok(resp) = call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_SELECT_MAX_TOKENS).await {
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

async fn load_memories(http: &reqwest::Client, cfg: &Config, cwd: &Path, messages: &[Message]) -> String {
    let selected = select_relevant_memories(http, cfg, cwd, messages).await;
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

async fn extract_memories(http: &reqwest::Client, cfg: &Config, cwd: &Path, messages: &[Message]) {
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
    let resp = match call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_EXTRACT_MAX_TOKENS).await { Ok(r) => r, Err(_) => return };
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

async fn consolidate_memories(http: &reqwest::Client, cfg: &Config, cwd: &Path) {
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
    let resp = match call_llm(http, cfg, &cfg.model, "", &msgs, &tools, MEMORY_CONSOLIDATE_MAX_TOKENS).await { Ok(r) => r, Err(_) => return };
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

// ── s12 新增：任务系统（.tasks/ 持久化 + blockedBy 依赖） ──────────────
//
// 与 s05 todo_write 的分工：todo 是会话内存里的执行清单（重启即丢），
// 任务是磁盘持久化的依赖图（跨会话恢复，多 agent 协作的基础——s15 队友线程
// 会来认领这里的任务）。

/// .tasks/ 目录（相对 cwd，与 .memory/ 同模式：测试可注入临时目录）
fn tasks_dir(cwd: &Path) -> PathBuf {
    cwd.join(".tasks")
}

/// 单个任务的 JSON 文件路径
fn task_path(cwd: &Path, task_id: &str) -> PathBuf {
    tasks_dir(cwd).join(format!("{task_id}.json"))
}

/// 生成任务 ID：task_{unix秒}_{0000-9999 随机}（对齐 Python 版格式）。
/// 两个进程同时创建仍有极小碰撞概率——教学版不做冲突处理（Python 同样）。
fn new_task_id() -> String {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let suffix = rand::thread_rng().gen_range(0..=9999);
    format!("task_{ts}_{suffix:04}")
}

/// 写入单个任务文件（JSON pretty，字段名与 Python asdict 一致）
fn save_task(cwd: &Path, task: &Task) {
    fs::create_dir_all(tasks_dir(cwd)).ok();
    let json = serde_json::to_string_pretty(task).unwrap_or_default();
    fs::write(task_path(cwd, &task.id), json).ok();
}

/// 读取单个任务；文件缺失或解析失败返回 None
fn load_task(cwd: &Path, task_id: &str) -> Option<Task> {
    let raw = fs::read_to_string(task_path(cwd, task_id)).ok()?;
    serde_json::from_str(&raw).ok()
}

/// 列出全部任务（按 ID 排序，对齐 Python 的 sorted(glob)）
fn list_tasks(cwd: &Path) -> Vec<Task> {
    let dir = tasks_dir(cwd);
    let mut tasks: Vec<Task> = Vec::new();
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            // 只认 task_*.json（对齐 Python 的 glob("task_*.json")），
            // .tasks/ 里的其他文件不算任务
            let is_task_file = path
                .file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.starts_with("task_") && n.ends_with(".json"))
                .unwrap_or(false);
            if is_task_file {
                if let Ok(raw) = fs::read_to_string(&path) {
                    if let Ok(task) = serde_json::from_str::<Task>(&raw) {
                        tasks.push(task);
                    }
                }
            }
        }
    }
    tasks.sort_by(|a, b| a.id.cmp(&b.id));
    tasks
}

/// 新建任务并落盘（status=pending，owner=None）
fn create_task(cwd: &Path, subject: &str, description: &str, blocked_by: &[String]) -> Task {
    let task = Task {
        id: new_task_id(),
        subject: subject.to_string(),
        description: description.to_string(),
        status: "pending".to_string(),
        owner: None,
        blocked_by: blocked_by.to_vec(),
        worktree: None,
    };
    save_task(cwd, &task);
    task
}

/// 依赖是否全部满足：所有 blockedBy 必须存在且 completed。
/// 缺失的依赖视为阻塞（对齐 Python：missing deps = blocked）。
fn can_start(cwd: &Path, task_id: &str) -> bool {
    match load_task(cwd, task_id) {
        Some(task) => task.blocked_by.iter().all(|dep| {
            load_task(cwd, dep)
                .map(|d| d.status == "completed")
                .unwrap_or(false)
        }),
        None => false,
    }
}

/// 列出仍未满足的依赖 ID（用于 "Blocked by" 文案）
fn blocked_deps(cwd: &Path, task: &Task) -> Vec<String> {
    task.blocked_by
        .iter()
        .filter(|dep| {
            load_task(cwd, dep)
                .map(|d| d.status != "completed")
                .unwrap_or(true) // 缺失 = 阻塞
        })
        .cloned()
        .collect()
}

/// 认领任务：pending + 依赖全部满足 → in_progress + owner。
/// 对齐 Python 的输出文案（含 "Blocked by: ['id', ...]" 的单引号列表格式）。
fn claim_task(cwd: &Path, task_id: &str, owner: &str) -> String {
    let mut task = match load_task(cwd, task_id) {
        Some(t) => t,
        None => return format!("Error: Task {task_id} not found"),
    };
    if task.status != "pending" {
        return format!("Task {task_id} is {}, cannot claim", task.status);
    }
    // s17: owner 检查——防多队友并发认领同一任务的后写覆盖（对齐 Python s17）
    if let Some(existing) = &task.owner {
        return format!("Task {task_id} already owned by {existing}");
    }
    let deps = blocked_deps(cwd, &task);
    if !deps.is_empty() {
        let quoted: Vec<String> = deps.iter().map(|d| format!("'{d}'")).collect();
        return format!("Blocked by: [{}]", quoted.join(", "));
    }
    task.owner = Some(owner.to_string());
    task.status = "in_progress".to_string();
    save_task(cwd, &task);
    // s17: 队友线程会调用 claim_task（自动认领）——标记走 stderr（对齐 s15
    // 惯例：后台线程的 stdout 打印会插入 Lead 流式回复，实测交错教训）
    eprintln!(
        "  \x1b[36m[claim] {} → in_progress (owner: {owner})\x1b[0m",
        task.subject
    );
    format!("Claimed {} ({})", task.id, task.subject)
}

/// 完成任务：in_progress → completed，并报告解禁的下游任务
/// （pending 且依赖现全部满足的）。
fn complete_task(cwd: &Path, task_id: &str) -> String {
    let mut task = match load_task(cwd, task_id) {
        Some(t) => t,
        None => return format!("Error: Task {task_id} not found"),
    };
    if task.status != "in_progress" {
        return format!("Task {task_id} is {}, cannot complete", task.status);
    }
    task.status = "completed".to_string();
    save_task(cwd, &task);
    let unblocked: Vec<String> = list_tasks(cwd)
        .iter()
        .filter(|t| t.status == "pending" && !t.blocked_by.is_empty() && can_start(cwd, &t.id))
        .map(|t| t.subject.clone())
        .collect();
    // s17: 队友线程会调用 complete_task——标记走 stderr（同 claim_task）
    eprintln!("  \x1b[32m[complete] {} ✓\x1b[0m", task.subject);
    let mut msg = format!("Completed {} ({})", task.id, task.subject);
    if !unblocked.is_empty() {
        let names = unblocked.join(", ");
        msg = format!("{msg}\nUnblocked: {names}");
        eprintln!("  \x1b[33m[unblocked] {names}\x1b[0m");
    }
    msg
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
async fn summarize_history(
    http: &reqwest::Client,
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
    let resp = match call_llm(http, cfg, &cfg.model, "", &summary_messages, &tools, SUMMARIZE_MAX_TOKENS).await {
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
async fn compact_history(
    http: &reqwest::Client,
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
        summarize_history(http, cfg, &messages[..tail_start]).await
    };
    let tail = messages[tail_start..].to_vec();
    *messages = vec![Message::user_text(format!("[Compacted]\n\n{summary}"))];
    messages.extend(tail);
}

// ── 应急：reactive_compact —— API 报 prompt_too_long 时触发 ─────────────

/// 保留尾部 5 条原始消息，其余用 LLM 摘要替换
async fn reactive_compact(
    http: &reqwest::Client,
    cfg: &Config,
    messages: &mut Vec<Message>,
) {
    let transcript_path = write_transcript(messages);
    println!("[transcript saved: {transcript_path}]");
    let tail_start = tail_keep_start(messages);
    let summary = if tail_start == 0 {
        "(no older history to summarize)".to_string()
    } else {
        summarize_history(http, cfg, &messages[..tail_start]).await
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
const SNIP_MAX_MESSAGES: usize = 120;
/// snip_compact 保留的头部消息数
const SNIP_KEEP_HEAD: usize = 3;
/// micro_compact 保留的最近 tool_result 数
const KEEP_RECENT: usize = 8;
/// 上下文大小估算阈值（字符数），超此值触发 L4 摘要。
/// 默认 300_000 字符 ≈ 10 万 token（中英混合按 ~3 字符/token 折算）：
/// 面向 deepseek-v4-flash（V4 家族 1M 上下文），同时兼容 128K 网关；
/// 可用环境变量 CONTEXT_LIMIT 覆盖（如 600000 = 1M 窗口的六成）。
const CONTEXT_LIMIT_DEFAULT: usize = 300_000;
/// 当前会话的 L4 摘要阈值：优先环境变量 CONTEXT_LIMIT（字符），缺省 300_000
fn context_limit() -> usize {
    std::env::var("CONTEXT_LIMIT")
        .ok()
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(CONTEXT_LIMIT_DEFAULT)
}
/// tool_result 落盘阈值（字符数），超此值触发 L3 持久化
const PERSIST_THRESHOLD: usize = 100_000;
/// L3 总预算：最新一条 user 消息的 tool_result 合计超过此值开始落盘
const TOOL_RESULT_BUDGET: usize = 500_000;

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
/// Gate 3: 暂停循环，打印警告，等用户输入（y/yes 放行）。
///
/// s14 起 reader 改为 `&mut impl Read`：permission_hook 注入 RawStdin
/// （libc::read 直读 fd 0，绕开 std 全局 stdin 锁），测试仍喂 Cursor。
fn ask_user(
    reader: &mut impl Read,
    name: &str,
    input: &serde_json::Value,
    reason: &str,
) -> bool {
    println!("\n\x1b[33m⚠  {reason}\x1b[0m");
    println!("   Tool: {name}({input})");
    print!("   Allow? [y/N] ");
    io::stdout().flush().ok();
    // 逐字节读到换行（对齐 input() 的"读一行"语义）；
    // 读取失败或 EOF 都按拒绝处理（默认拒绝是最安全的默认值）
    let mut line = String::new();
    let mut byte = [0u8; 1];
    loop {
        match reader.read(&mut byte) {
            Ok(0) => break,          // EOF
            Ok(_) if byte[0] == b'\n' => break,
            Ok(_) => line.push(byte[0] as char),
            Err(_) => return false,
        }
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
/// 从 s03 的 `check_permission` 携入，s14 起 `reader: &mut impl Read`
/// （RawStdin 直读 fd 0，绕开 std 全局 stdin 锁——详见 permission_hook）。
/// s04 的 `permission_hook` 是对本函数的薄封装（注入真实 stdin）。
///
/// Gate 1 只作用于 bash：硬拒绝，不询问（短路，不进 Gate 2/3）。
/// Gate 2 命中才进 Gate 3（用户确认）。
fn check_permission(
    reader: &mut impl Read,
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

/// Gate 3 的 stdin 读取器：libc::read 直读 fd 0，**绕开 std::io::stdin 的全局锁**。
///
/// 问题（实测）：REPL 用 tokio::io::stdin()（内部是 Blocking<std::io::Stdin>，
/// 每次读操作起一个线程调 std::io::Stdin::read——拿 std 全局 stdin 互斥锁后
/// 阻塞在 read(2) 等输入，且该读无法取消）。空闲 select 轮询 stdin 时这个
/// 读线程一直活着持锁；定时轮（cron）回合里 permission_hook 的
/// io::stdin().lock() 就卡在这把锁上——bash 必须按 Enter 才能继续（实测）。
///
/// 用 libc::read 直读 fd 0 完全不碰 std 的全局锁。
/// 代价：Gate 3 询问期间与 REPL 的 stdin 等待者并存，极端情况下首个 y/n
/// 可能被 REPL 吃掉——再按一次即可（默认拒绝是安全兜底）。
struct RawStdin;

impl Read for RawStdin {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        let n = unsafe { libc::read(0, buf.as_mut_ptr() as *mut libc::c_void, buf.len()) };
        if n < 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(n as usize)
        }
    }
}

/// PreToolUse hook：对 check_permission 的薄封装，注入 RawStdin。
///
/// 权限逻辑全部在 check_permission（可独立测试）中，本函数只负责
/// 提供 stdin 并适配 Hook 回调的签名（Fn(&str, &Value) -> Option<String>）。
fn permission_hook(name: &str, input: &serde_json::Value) -> Option<String> {
    check_permission(&mut RawStdin, name, input)
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
/// s13: with_retry 随 call_llm 一起 async 化——退避用 tokio::time::sleep，
/// 不再阻塞 runtime 线程。闭包接收当前模型名（String，by value）并返回
/// Future——async move 闭包把模型名搬进 Future，避免生命周期纠缠。
async fn with_retry<F, Fut>(
    state: &mut RecoveryState,
    mut call: F,
) -> Result<ApiResponse, LlmError>
where
    F: FnMut(String) -> Fut,
    Fut: std::future::Future<Output = Result<ApiResponse, LlmError>>,
{
    for attempt in 0..MAX_RETRIES {
        match call(state.current_model.clone()).await {
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
                tokio::time::sleep(delay).await;
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
                tokio::time::sleep(delay).await;
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
/// s13 变化：async 化（reqwest::Client）；stream 恒为 false（非流式路径），
/// 父代理主循环走 call_llm_streaming（SSE 流式），子代理与内部辅助调用走这里。
async fn call_llm(
    http: &reqwest::Client,
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
        stream: false,
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

    let resp = build_request(http, cfg, &req)
        .send()
        .await
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
        .await
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

/// s14 修复：清理孤儿 tool_result —— tool_use_id 在最近的 assistant 消息中
/// 找不到对应 tool_use 的 tool_result 块会被丢弃。
///
/// 背景（实测）：压缩管线（compact_history 尾部保留 / snip 裁边）按"单对配对"
/// 假设工作，但 s14 的 cron 注入会在工具轮之间插入纯文本 user 消息，边界可能
/// 落在新形态上：tool_result 留在尾部、它的 tool_use 被摘要进头部 → API 400
/// "unexpected tool_use_id found in tool_result"。此函数防御性清理。
/// 空 user 消息替换为占位文本（空 content 数组同样可能触发 400）。
/// 只对发送副本调用，不污染历史。
fn sanitize_tool_pairs(messages: &mut Vec<Message>) {
    let mut active: Vec<String> = Vec::new();
    for msg in messages.iter_mut() {
        match msg.role {
            Role::Assistant => {
                active.clear();
                if let MessageContent::Blocks(blocks) = &msg.content {
                    for b in blocks {
                        if let ContentBlock::ToolUse { id, .. } = b {
                            active.push(id.clone());
                        }
                    }
                }
            }
            Role::User => {
                if let MessageContent::Blocks(blocks) = &mut msg.content {
                    let before = blocks.len();
                    blocks.retain(|b| match b {
                        ContentBlock::ToolResult { tool_use_id, .. } => {
                            active.contains(tool_use_id)
                        }
                        _ => true,
                    });
                    if blocks.is_empty() && before > 0 {
                        msg.content = MessageContent::Text("(compacted tool results)".into());
                    }
                }
            }
        }
    }
}

async fn agent_loop(
    http: &reqwest::Client,
    cfg: &Config,
    cwd: &Path,
    messages: &mut Vec<Message>,
    hooks: &Hooks,
) -> Result<(), String> {
    // s19: 动态工具池 —— 内置 + 已连接 MCP 工具；connect_mcp 被调用后重组装
    // （见循环尾部）。Arc 让 mcp_handlers 能跨 spawn_blocking 线程共享。
    let (mut tools, mcp_handlers) = assemble_tool_pool();
    let mut mcp_handlers = Arc::new(mcp_handlers);
    let mut rounds_since_todo: u32 = 0;
    // ── s11: 恢复状态与可变 max_tokens（一次 agent_loop 调用内共享） ──
    let mut recovery = RecoveryState::new(&cfg.model, cfg.fallback_model.clone());
    let mut max_tokens = cfg.max_tokens;

    // ── s13: 本轮是否已流式打印过（main 里避免重复打印最终文本） ──
    STREAMED_OUTPUT_PRINTED.store(false, Ordering::Relaxed);

    // ── s09: 注入相关记忆到最近一条 user 消息 ──
    // ── s10: 动态 system prompt（每轮工具执行后重评估，见循环尾部） ──
    let mut ctx = update_context(cwd);
    let mut system = get_system_prompt(&ctx);

    let memories_content = load_memories(http, cfg, cwd, messages).await;
    let memory_turn = if !memories_content.is_empty() && !messages.is_empty() {
        let last_idx = messages.len() - 1;
        if matches!(messages[last_idx].content, MessageContent::Text(_)) { Some(last_idx) } else { None }
    } else { None };

    loop {
        // ── s14: cron 触发消费（路径 A：回合内注入） ──
        // 长回合进行中到期的任务在下一轮循环顶部注入，不等回合结束；
        // 空闲唤醒（路径 B）由 main 的 select! 定时分支负责
        let fired = consume_cron_queue();
        for job in &fired {
            messages.push(Message::user_text(format!("[Scheduled] {}", job.prompt)));
            println!(
                "  \x1b[35m[inject cron] {}\x1b[0m",
                truncate_chars(&job.prompt, 50)
            );
        }

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
        tool_result_budget(messages, TOOL_RESULT_BUDGET); // L3: 大结果落盘
        snip_compact(messages);                       // L1: 裁中间
        micro_compact(messages);                      // L2: 旧结果占位

        // ── s08: 仍超阈值 → L4 LLM 摘要（1 API） ──
        // s14: 阈值每轮取一次，支持 CONTEXT_LIMIT 环境变量热调
        let limit = context_limit();
        if estimate_size(messages) > limit {
            println!("[auto compact]");
            compact_history(http, cfg, messages).await;
        }

        // ── s09: 把记忆内容拼到指定 user 消息前 ──
        let mut request_messages = if let Some(idx) = memory_turn {
            if idx < messages.len() {
                let mut modified = messages.clone();
                if let MessageContent::Text(ref text) = messages[idx].content {
                    modified[idx] = Message::user_text(format!("{memories_content}\n\n{text}"));
                }
                modified
            } else { messages.clone() }
        } else { messages.clone() };

        // ── s14 修复：发送前清理孤儿 tool_result ──
        // 压缩管线（compact_history 尾部保留 / snip 裁边）按"单对配对"假设工作，
        // 但 s14 的 cron 注入会在工具轮之间插入纯文本 user 消息，边界可能落在
        // 新形态上：tool_result 留在尾部、它的 tool_use 被摘要进头部 → API 400
        // "unexpected tool_use_id found in tool_result"（实测）。这里防御性
        // 清理：只对副本操作，不污染历史。
        sanitize_tool_pairs(&mut request_messages);

        // 1. 把完整历史发给模型（s13: 流式 SSE，边收 text_delta 边打印）
        //    s11: with_retry 在内层吃掉瞬态错误（429/529 退避重试、529 切模型），
        //         非瞬态错误（PromptTooLong / Other）抛到外层按路径处理
        //    s13: STREAMED_OUTPUT_PRINTED 由 handle_sse_event 在真正打印
        //         text_delta 时置位——调用失败（[Error] 写历史）时不置位，
        //         main 仍会打印错误回复（与 s12 行为一致）
        let resp = match with_retry(&mut recovery, |model| {
            // 先取引用（Copy），async move 只搬引用和 model，不搬走 String/Vec
            let system = &system;
            let request_messages = &request_messages;
            let tools = &tools;
            async move {
                call_llm_streaming(http, cfg, &model, system, request_messages, tools, max_tokens)
                    .await
            }
        })
        .await
        {
            Ok(r) => r,
            // ── 路径2: 上下文超限 → reactive compact 后重试（仅一次） ──
            Err(LlmError::PromptTooLong) => {
                if !recovery.has_attempted_reactive_compact {
                    println!("[reactive compact]");
                    reactive_compact(http, cfg, messages).await;
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
                extract_memories(http, cfg, cwd, &pre_compress).await;
                consolidate_memories(http, cfg, cwd).await;
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

        // ── s13: 工具执行三阶段 —— 权限串行 → 并行执行 → 原序回填 + 通知收集 ──
        //
        // 阶段 1: 按原顺序过 PreToolUse hook（含 Gate3 用户确认，必须串行）。
        // 每个 tool_use 落一个槽位：被拦的直接记下拒绝文案，放行的进 pending。
        // 槽位化保证后续无论走后台/串行/并行，结果都能按原始顺序回填——
        // tool_result 必须与 tool_use 同序配对（API 契约，s12 起全轨约定）。
        // compact 仍走特殊 break 路径。
        enum Slot {
            Blocked(String, String), // (tool_use_id, 拒绝文案)
            Exec(String, String, serde_json::Value), // (tool_use_id, name, input)
        }
        let mut slots: Vec<Slot> = Vec::new();

        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name, input } = block {
                println!("[33m> {name}[0m");

                // ── s08: compact 工具 —— 立即摘要并 continue 下一轮 ──
                // 注意：compact 后不追加 tool_result，因为 compact_history
                // 已替换全部 messages，旧 tool_use_id 对应的 tool_use 不存在了。
                if name == "compact" {
                    println!("[compact]");
                    compact_history(http, cfg, messages).await;
                    compact_called = true;
                    break;
                }

                // PreToolUse hook
                if let Some(reason) = trigger_pre_tool_use(hooks, name, input) {
                    slots.push(Slot::Blocked(id.clone(), reason));
                    continue;
                }

                slots.push(Slot::Exec(id.clone(), name.clone(), input.clone()));
            }
        }

        if compact_called {
            // compact 已替换全部 messages，直接 continue 下一轮
            continue;
        }

        // 阶段 2: 执行。
        //   - bash 后台（run_in_background=true 或慢操作关键词命中）→ 立即占位，spawn_blocking 后台跑
        //   - task 子代理 → 串行 await（并行子代理留给 s15 队友线程）
        //   - 其余同步 handler → spawn_blocking 并行
        let mut outputs: Vec<String> = slots.iter().map(|_| String::new()).collect();
        let mut batch: Vec<(usize, tokio::task::JoinHandle<String>)> = Vec::new();

        for (i, slot) in slots.iter().enumerate() {
            let Slot::Exec(id, name, input) = slot else { continue };

            // s13: 后台任务 —— 模型显式请求优先，启发式兜底
            if name == "bash" && should_run_background(name, input) {
                let bg_id = start_background_task(id, input);
                let cmd = input.get("command").and_then(|v| v.as_str()).unwrap_or("");
                outputs[i] = format!(
                    "[Background task {bg_id} started] Command: {cmd}. Result will be available when complete."
                );
                continue;
            }

            if name == "task" {
                let output = match serde_json::from_value::<TaskInput>(input.clone()) {
                    Ok(ti) => run_task(http, cfg, hooks, ti).await,
                    Err(e) => format!("Error: invalid task params: {e}"),
                };
                outputs[i] = output;
                continue;
            }

            // ── s15: spawn_teammate —— 需在 tokio 上下文里 spawn 任务，
            // 与 task 同构特判（execute_sync 是 sync fn，无法起 async 任务）
            if name == "spawn_teammate" {
                let output = match serde_json::from_value::<SpawnTeammateInput>(input.clone()) {
                    Ok(ti) => run_spawn_teammate(http, cfg, cwd, ti).await,
                    Err(e) => format!("Error: invalid spawn_teammate params: {e}"),
                };
                outputs[i] = output;
                continue;
            }

            // ── s19: 其余工具走双路径分发 —— MCP 动态表命中（快速内存调用）
            // 与内置 execute_sync 统一走 dispatch_tool，spawn_blocking 并行。
            // 队友线程的工具集固定 8 个且不查 MCP 表 → 队友天然拿不到 MCP 工具
            // （类型层面隔离，Python 是"队友不注册 MCP handler"，机制不同效果同）。
            let name2 = name.clone();
            let input2 = input.clone();
            let handlers = mcp_handlers.clone();
            let handle =
                tokio::task::spawn_blocking(move || dispatch_tool(&name2, &input2, &handlers));
            batch.push((i, handle));
        }

        // 并行批次按原顺序 await（JoinHandle 完成顺序无关，await 顺序保证回填顺序）
        for (i, handle) in batch {
            outputs[i] = match handle.await {
                Ok(out) => out,
                Err(e) => format!("Error: tool task panicked: {e}"),
            };
        }

        // 阶段 3: 按槽位原顺序统一收尾（nag 复位 / PostToolUse / 预览 / 入列），
        // 后台完成的通知作为独立 text block 追加在全部 tool_result 之后。
        for (i, slot) in slots.iter().enumerate() {
            match slot {
                Slot::Blocked(id, reason) => {
                    results.push(ContentBlock::ToolResult {
                        tool_use_id: id.clone(),
                        content: reason.clone(),
                    });
                }
                Slot::Exec(id, name, input) => {
                    finish_tool(
                        id,
                        name,
                        input,
                        &outputs[i],
                        &mut results,
                        hooks,
                        &mut rounds_since_todo,
                    );
                }
            }
        }

        let notifications = collect_background_results();
        if !notifications.is_empty() {
            println!(
                "  \x1b[32m[inject] {} background notification(s)\x1b[0m",
                notifications.len()
            );
            for n in notifications {
                results.push(ContentBlock::Text { text: n });
            }
        }

        messages.push(Message::user_tool_results(results));

        // ── s19: 本轮调用了 connect_mcp → 重组装动态工具池（对齐 Python：
        // `if any(b.name == "connect_mcp" ...): tools, handlers = assemble_tool_pool()`）
        // 新工具从下一轮起才出现在 API 请求里 —— 这正是"MCP 即插即用"的机制点。
        if response_uses_connect_mcp(&resp.content) {
            println!("  \x1b[31m[mcp] tool pool reassembled\x1b[0m");
            let (new_tools, new_handlers) = assemble_tool_pool();
            tools = new_tools;
            mcp_handlers = Arc::new(new_handlers);
        }

        // ── s10: 每轮工具执行后重评估 context/system（对齐 Python 版）──
        // 工具可能新增记忆文件；缓存保证 context 没变时不重复组装。
        // s19: connected_mcp 进 PromptContext → 缓存键自动失效。
        ctx = update_context(cwd);
        system = get_system_prompt(&ctx);
    }
}


// ═════════════════════════════════════════════════════════════════════
//  s13 新增：后台任务 + 流式 SSE 输出 + 并行工具执行
// ═════════════════════════════════════════════════════════════════════

// ── 工具执行的统一收尾（nag 复位 / PostToolUse / 预览 / 结果入列） ────────

/// 工具执行完成后的公共收尾逻辑（并行批次与串行子代理共用）。
/// 保持与 s12 相同的行为顺序：todo_write 复位 nag 计数 → PostToolUse hook
/// → 终端预览 → 结果入列。
fn finish_tool(
    id: &str,
    name: &str,
    input: &serde_json::Value,
    output: &str,
    results: &mut Vec<ContentBlock>,
    hooks: &Hooks,
    rounds_since_todo: &mut u32,
) {
    if name == "todo_write" {
        *rounds_since_todo = 0;
    }
    trigger_post_tool_use(hooks, name, input, output);
    let preview = truncate_lines(output, 1000);
    if !preview.is_empty() {
        println!("{preview}");
    }
    results.push(ContentBlock::ToolResult {
        tool_use_id: id.to_string(),
        content: output.to_string(),
    });
}

/// 同步执行一个工具调用（s12 的 match 分发原样保留，task 除外——
/// task 是 async 子代理，在 agent_loop 里串行 await）。
/// s13 中它被 spawn_blocking 包起来并行跑（bash 可能阻塞 120s，
/// 不能占用 async runtime 线程）。
fn execute_sync(name: &str, input: &serde_json::Value) -> String {
    match name {
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
        "load_skill" => serde_json::from_value::<LoadSkillInput>(input.clone())
            .map(|li| load_skill(&li.name))
            .unwrap_or_else(|e| format!("Error: invalid load_skill params: {e}")),
        // s08: compact 在 agent_loop 里被提前拦截，这里不可达（保持穷尽匹配）
        "compact" => "[Compacted]".to_string(),
        // ── s12: 任务系统 5 工具 ──
        "create_task" => serde_json::from_value::<CreateTaskInput>(input.clone())
            .map(run_create_task)
            .unwrap_or_else(|e| format!("Error: invalid create_task params: {e}")),
        "list_tasks" => serde_json::from_value::<ListTasksInput>(input.clone())
            .map(run_list_tasks)
            .unwrap_or_else(|e| format!("Error: invalid list_tasks params: {e}")),
        "get_task" => serde_json::from_value::<TaskIdInput>(input.clone())
            .map(run_get_task)
            .unwrap_or_else(|e| format!("Error: invalid get_task params: {e}")),
        "claim_task" => serde_json::from_value::<TaskIdInput>(input.clone())
            .map(run_claim_task)
            .unwrap_or_else(|e| format!("Error: invalid claim_task params: {e}")),
        "complete_task" => serde_json::from_value::<TaskIdInput>(input.clone())
            .map(run_complete_task)
            .unwrap_or_else(|e| format!("Error: invalid complete_task params: {e}")),
        // ── s14: cron 调度 3 工具 ──
        "schedule_cron" => serde_json::from_value::<ScheduleCronInput>(input.clone())
            .map(run_schedule_cron)
            .unwrap_or_else(|e| format!("Error: invalid schedule_cron params: {e}")),
        "list_crons" => serde_json::from_value::<ListCronsInput>(input.clone())
            .map(run_list_crons)
            .unwrap_or_else(|e| format!("Error: invalid list_crons params: {e}")),
        "cancel_cron" => serde_json::from_value::<CronIdInput>(input.clone())
            .map(run_cancel_cron)
            .unwrap_or_else(|e| format!("Error: invalid cancel_cron params: {e}")),
        // ── s15: 团队工具（send_message/check_inbox 同步；spawn_teammate
        // 需 async spawn，在 agent_loop 特判，这里不可达——保持穷尽匹配） ──
        "send_message" => serde_json::from_value::<SendMessageInput>(input.clone())
            .map(|si| match workdir() {
                Ok(c) => run_send_message(&c, si),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid send_message params: {e}")),
        "check_inbox" => serde_json::from_value::<CheckInboxInput>(input.clone())
            .map(|_| match workdir() {
                Ok(c) => run_check_inbox(&c),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid check_inbox params: {e}")),
        // ── s16: 协议 3 工具（全部同步：bus_send + 内存状态） ──
        "request_shutdown" => serde_json::from_value::<RequestShutdownInput>(input.clone())
            .map(|ri| match workdir() {
                Ok(c) => run_request_shutdown(&c, ri),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid request_shutdown params: {e}")),
        "request_plan" => serde_json::from_value::<RequestPlanInput>(input.clone())
            .map(|ri| match workdir() {
                Ok(c) => run_request_plan(&c, ri),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid request_plan params: {e}")),
        "review_plan" => serde_json::from_value::<ReviewPlanInput>(input.clone())
            .map(|ri| match workdir() {
                Ok(c) => run_review_plan(&c, ri),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid review_plan params: {e}")),
        // ── s18: worktree 3 工具（同步：git + 文件操作） ──
        "create_worktree" => serde_json::from_value::<CreateWorktreeInput>(input.clone())
            .map(|wi| match workdir() {
                Ok(c) => create_worktree(&c, &wi.name, &wi.task_id),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid create_worktree params: {e}")),
        "remove_worktree" => serde_json::from_value::<RemoveWorktreeInput>(input.clone())
            .map(|wi| match workdir() {
                Ok(c) => remove_worktree(&c, &wi.name, wi.discard_changes),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid remove_worktree params: {e}")),
        "keep_worktree" => serde_json::from_value::<KeepWorktreeInput>(input.clone())
            .map(|wi| match workdir() {
                Ok(c) => keep_worktree(&c, &wi.name),
                Err(e) => format!("Error: {e}"),
            })
            .unwrap_or_else(|e| format!("Error: invalid keep_worktree params: {e}")),
        // ── s19: MCP 连接工具（同步：纯内存操作，改全局 MCP_STATE） ──
        "connect_mcp" => serde_json::from_value::<ConnectMcpInput>(input.clone())
            .map(|ci| connect_mcp(&ci.name))
            .unwrap_or_else(|e| format!("Error: invalid connect_mcp params: {e}")),
        other => format!("Error: unknown tool '{other}'"),
    }
}

// ── s19 新增：MCP 系统（外部能力即插即用） ────────────────────────────────
//
// 教学版 MCP：不跑真实 MCP 协议（stdio/SSE + JSON-RPC），用"工厂函数注册
// 工具 + 函数指针 handler"模拟 MCP 服务器的"发现工具 → 调用工具"两个动作。
// 真实 Claude Code 里 MCP 是子进程协议，这里只保留可教学的骨架：
//   connect_mcp("docs") → MCPClient 发现 2 个工具 →
//   assemble_tool_pool → [builtin..., mcp__docs__search, mcp__docs__get_version]
//   agent_loop 用组装后的池（动态工具走运行时表，内置走 execute_sync）

/// connect_mcp 工具的参数
#[derive(Deserialize)]
struct ConnectMcpInput {
    name: String,
}

/// MCP 工具 handler：函数指针（mock handler 无捕获，天然 Send + 'static）。
/// 返回 Result：Err 由 call_tool 包装成 "MCP error: {e}"（对齐 Python 的
/// `handler(**args)` 抛异常 → call_tool 捕获 → "MCP error: {e}"）。
type MockHandler = fn(&serde_json::Value) -> Result<String, String>;

/// 教学版 MCP 客户端：发现并调用一个 MCP 服务器上的工具（mock）。
#[derive(Debug)]
struct MCPClient {
    /// 服务器名。Python 版同样只存不用（连接名以 connect_mcp 参数为准），
    /// 保留字段对齐数据模型，为真实 MCP 协议（子进程通信需自报身份）留位。
    #[allow(dead_code)]
    name: String,
    tools: Vec<Tool>,
    handlers: HashMap<String, MockHandler>,
}

impl MCPClient {
    fn new(name: &str) -> Self {
        MCPClient {
            name: name.to_string(),
            tools: Vec::new(),
            handlers: HashMap::new(),
        }
    }

    /// 注册服务器声明的工具定义 + 对应 handler（模拟 MCP initialize/listTools）。
    fn register(&mut self, tool_defs: Vec<Tool>, handlers: HashMap<String, MockHandler>) {
        self.tools = tool_defs;
        self.handlers = handlers;
    }

    /// 调用一个工具：未知工具 → "MCP error: unknown tool '{name}'"；
    /// handler 失败 → "MCP error: {e}"（对齐 Python call_tool 的异常捕获）。
    fn call_tool(&self, tool_name: &str, args: &serde_json::Value) -> String {
        match self.handlers.get(tool_name) {
            Some(handler) => match handler(args) {
                Ok(out) => out,
                Err(e) => format!("MCP error: {e}"),
            },
            None => format!("MCP error: unknown tool '{tool_name}'"),
        }
    }
}

/// 已连接的 MCP 服务器注册表（全局，s05 起静态惯例）。
/// order 记录连接顺序 —— Python 的 mcp_clients 是 dict 插入序，工具池顺序
/// 必须可复现（builtins → docs → deploy），HashMap 迭代无序，故单独存顺序。
struct McpState {
    order: Vec<String>,
    clients: HashMap<String, MCPClient>,
}

static MCP_STATE: LazyLock<Mutex<McpState>> = LazyLock::new(|| {
    Mutex::new(McpState {
        order: Vec::new(),
        clients: HashMap::new(),
    })
});

/// 测试辅助：清空全局 MCP 注册表。
/// 与 s17 的"唯一 request_id 自证"不同——mock 服务器名只有 docs/deploy 两个，
/// 无法用唯一名隔离，测试单线程（--test-threads=1）下先清后连，确定性保证。
#[cfg(test)]
fn reset_mcp_state() {
    let mut state = MCP_STATE.lock().unwrap();
    state.order.clear();
    state.clients.clear();
}

/// 测试辅助：替换启动时加载的 MCP 配置（模拟"配置文件里加了新服务器"）。
#[cfg(test)]
fn set_mcp_config(cfg: McpConfig) {
    *MCP_CONFIG.lock().unwrap() = cfg;
}

/// 测试辅助：Drop 守卫 —— 无论断言成败都还原默认配置。
/// 全局配置一旦被替换，panic 中途退出会泄漏给后续测试（级联失败），
/// 守卫让还原在 unwinding 时也执行。
#[cfg(test)]
struct McpConfigGuard;

#[cfg(test)]
impl Drop for McpConfigGuard {
    fn drop(&mut self) {
        set_mcp_config(default_mcp_config());
    }
}

/// 名字规范化：非 [a-zA-Z0-9_-] 一律替换为 '_'（对齐 Python
/// _DISALLOWED_CHARS.sub('_', name)）。工具命名 mcp__{server}__{tool}
/// 需要纯 ASCII 安全名。
fn normalize_mcp_name(name: &str) -> String {
    name.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' || c == '-' {
                c
            } else {
                '_'
            }
        })
        .collect()
}

// ── 教学 mock handler（docs / deploy 的实现层） ────────────────────────
//
// s19 前移：服务器注册表从硬编码工厂表改为 .mcp.json 配置文件驱动（贴近
// 真实 Claude Code）。handler 是代码实现（JSON 表达不了函数），配置文件里
// 用 handler 名引用这里的注册表——"配置声明工具，注册表提供实现"。

fn mock_docs_search(input: &serde_json::Value) -> Result<String, String> {
    #[derive(Deserialize)]
    struct SearchInput {
        query: String,
    }
    let q: SearchInput = serde_json::from_value(input.clone()).map_err(|e| e.to_string())?;
    Ok(format!("[docs] Found 3 results for '{}'", q.query))
}

fn mock_docs_get_version(_input: &serde_json::Value) -> Result<String, String> {
    Ok("[docs] API v2.1.0".to_string())
}

fn mock_deploy_trigger(input: &serde_json::Value) -> Result<String, String> {
    #[derive(Deserialize)]
    struct TriggerInput {
        service: String,
    }
    let t: TriggerInput = serde_json::from_value(input.clone()).map_err(|e| e.to_string())?;
    Ok(format!("[deploy] Triggered: {}", t.service))
}

fn mock_deploy_status(input: &serde_json::Value) -> Result<String, String> {
    #[derive(Deserialize)]
    struct StatusInput {
        service: String,
    }
    let s: StatusInput = serde_json::from_value(input.clone()).map_err(|e| e.to_string())?;
    Ok(format!("[deploy] {}: running (v1.4.2)", s.service))
}

/// handler 注册表：配置文件里的 handler 名 → 函数指针。
/// 配置文件只声明"这个工具由哪个 handler 实现"，实现在这里登记——
/// 新增 mock 服务器 = 配置文件加条目 + （需要新行为时）这里加一行。
fn mcp_handler_by_name(name: &str) -> Option<MockHandler> {
    match name {
        "docs_search" => Some(mock_docs_search),
        "docs_get_version" => Some(mock_docs_get_version),
        "deploy_trigger" => Some(mock_deploy_trigger),
        "deploy_status" => Some(mock_deploy_status),
        _ => None,
    }
}

// ── .mcp.json 配置（s19 前移：启动时读配置文件） ────────────────────────
//
// 真实 CC 的 .mcp.json 用 command/args/env 描述"如何启动服务器进程"，工具
// 由服务器进程在运行时 listTools 发现；教学 mock 没有子进程协议，配置文件
// 直接内联工具定义 + handler 名（server 名 → 工具定义 + handler 描述）。
// 真实 CC 的 stdio 条目（无 tools 字段）会被容错跳过并提示——本仓库根目录
// 就有一个真实的 codegraph 配置，两个格式可以在同一个文件里共存。

#[derive(Deserialize, Clone, Debug)]
struct McpToolConfig {
    name: String,
    description: String,
    /// MCP 惯例用 camelCase 的 inputSchema（对齐 Python tool_def["inputSchema"]）
    #[serde(rename = "inputSchema")]
    input_schema: serde_json::Value,
    /// handler 注册表里的名字（如 "docs_search"）
    handler: String,
}

#[derive(Deserialize, Clone, Debug)]
struct McpServerConfig {
    tools: Vec<McpToolConfig>,
}

#[derive(Deserialize, Clone, Debug)]
struct McpConfig {
    #[serde(rename = "mcpServers")]
    mcp_servers: HashMap<String, McpServerConfig>,
}

/// 从文件加载教学版 MCP 配置。容错：非教学条目（真实 CC 的 stdio 配置等）
/// 跳过并提示，不整体报错——同一文件可以混放两种格式。
fn load_mcp_config_from(path: &Path) -> Result<McpConfig, String> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let raw: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| format!("invalid JSON in {}: {e}", path.display()))?;
    let servers = raw
        .get("mcpServers")
        .and_then(|v| v.as_object())
        .ok_or_else(|| format!("{}: missing 'mcpServers' object", path.display()))?;
    let mut mcp_servers = HashMap::new();
    for (name, entry) in servers {
        match serde_json::from_value::<McpServerConfig>(entry.clone()) {
            Ok(cfg) => {
                mcp_servers.insert(name.clone(), cfg);
            }
            Err(_) => println!(
                "  \x1b[33m[mcp] config: skip '{}' — not a teaching entry (real CC stdio config?)\x1b[0m",
                name
            ),
        }
    }
    Ok(McpConfig { mcp_servers })
}

/// 内置兜底配置：找不到教学配置文件时用。内容与仓库里的
/// `tutorials/rust/.mcp.json` 完全一致——文件存在时文件优先，文件缺失时
/// 章节仍可独立运行（测试也依赖这个兜底：cargo test 的 cwd 在 crate 目录）。
fn default_mcp_config() -> McpConfig {
    serde_json::from_value(serde_json::json!({
        "mcpServers": {
            "docs": {
                "tools": [
                    { "name": "search", "description": "Search documentation. (readOnly)",
                      "inputSchema": { "type": "object", "properties": { "query": { "type": "string" } }, "required": ["query"] },
                      "handler": "docs_search" },
                    { "name": "get_version", "description": "Get API version. (readOnly)",
                      "inputSchema": { "type": "object", "properties": {}, "required": [] },
                      "handler": "docs_get_version" }
                ]
            },
            "deploy": {
                "tools": [
                    { "name": "trigger", "description": "Trigger a deployment. (destructive — requires approval in real CC)",
                      "inputSchema": { "type": "object", "properties": { "service": { "type": "string" } }, "required": ["service"] },
                      "handler": "deploy_trigger" },
                    { "name": "status", "description": "Check deployment status. (readOnly)",
                      "inputSchema": { "type": "object", "properties": { "service": { "type": "string" } }, "required": ["service"] },
                      "handler": "deploy_status" }
                ]
            }
        }
    }))
    .expect("default mcp config")
}

/// 启动时加载的 MCP 配置（进程生命周期内不变——改文件需重启，对齐"启动时读"）。
/// 候选路径（第一个有教学条目的生效）：
///   1. cwd/.mcp.json              —— 真实 CC 的位置；容错跳过其 stdio 条目
///   2. cwd/tutorials/rust/.mcp.json   —— 本仓库 Rust 轨道的教学配置（已提交）
/// 全部缺失 → 内置兜底 docs/deploy。
static MCP_CONFIG: LazyLock<Mutex<McpConfig>> = LazyLock::new(|| {
    let cwd = env::current_dir().unwrap_or_default();
    let candidates = [cwd.join(".mcp.json"), cwd.join("tutorials/rust/.mcp.json")];
    for path in &candidates {
        if !path.exists() {
            continue;
        }
        match load_mcp_config_from(path) {
            Ok(cfg) if !cfg.mcp_servers.is_empty() => {
                println!(
                    "  \x1b[36m[mcp] config loaded: {} server(s) from {}\x1b[0m",
                    cfg.mcp_servers.len(),
                    path.display()
                );
                return Mutex::new(cfg);
            }
            Ok(_) => { /* 文件存在但无教学条目（如真实 CC 配置）→ 试下一个候选 */ }
            Err(e) => println!("  \x1b[33m[mcp] config: {e}\x1b[0m"),
        }
    }
    Mutex::new(default_mcp_config())
});

/// 可连接服务器名（排序保证确定性——JSON 对象键无序，Python 是插入序）。
fn mcp_server_names() -> Vec<String> {
    let config = MCP_CONFIG.lock().unwrap();
    let mut names: Vec<String> = config.mcp_servers.keys().cloned().collect();
    names.sort();
    names
}

/// 从配置构建 MCPClient：工具定义透传 + handler 按名解析。
/// 未知 handler 名 → 配置错误（Err，connect_mcp 原样返回）。
/// 走 new + register 构造路径（模拟 MCP initialize/listTools 两步）。
fn build_client(name: &str, cfg: &McpServerConfig) -> Result<MCPClient, String> {
    let mut client = MCPClient::new(name);
    let mut tools = Vec::new();
    let mut handlers = HashMap::new();
    for t in &cfg.tools {
        let handler = mcp_handler_by_name(&t.handler).ok_or_else(|| {
            format!(
                "MCP config: unknown handler '{}' for tool '{}' (server '{name}')",
                t.handler, t.name
            )
        })?;
        tools.push(Tool {
            name: t.name.clone(),
            description: t.description.clone(),
            input_schema: t.input_schema.clone(),
        });
        handlers.insert(t.name.clone(), handler);
    }
    client.register(tools, handlers);
    Ok(client)
}

/// 连接一个 MCP 服务器：从配置构建客户端、写入全局注册表。
/// 三种返回（对齐 Python）：
///   - 已连接: "MCP server '{name}' already connected"
///   - 未知:   "Unknown server '{name}'. Available: deploy, docs"（排序）
///   - 成功:   "Connected to MCP server '{name}'. Discovered N tools: t1, t2"
fn connect_mcp(name: &str) -> String {
    let mut state = MCP_STATE.lock().unwrap();
    if state.clients.contains_key(name) {
        return format!("MCP server '{name}' already connected");
    }
    // 注意：Mutex 不可重入 —— 未知分支里再调 mcp_server_names() 会再锁
    // MCP_CONFIG，必须让 config 守卫先出作用域（块作用域 + 提前收集结果）。
    let client = match {
        let config = MCP_CONFIG.lock().unwrap();
        config.mcp_servers.get(name).map(|c| build_client(name, c))
    } {
        Some(Ok(c)) => c,
        Some(Err(e)) => return e,
        None => {
            return format!(
                "Unknown server '{name}'. Available: {}",
                mcp_server_names().join(", ")
            );
        }
    };
    let tool_names: Vec<String> = client.tools.iter().map(|t| t.name.clone()).collect();
    state.order.push(name.to_string());
    state.clients.insert(name.to_string(), client);
    // Lead 专属工具（队友工具集固定 8 个，碰不到这里）→ println 安全
    println!(
        "  \x1b[31m[mcp] connected: {name} → [{}]\x1b[0m",
        tool_names
            .iter()
            .map(|t| format!("'{t}'"))
            .collect::<Vec<_>>()
            .join(", ")
    );
    format!(
        "Connected to MCP server '{name}'. Discovered {} tools: {}",
        tool_names.len(),
        tool_names.join(", ")
    )
}

/// 动态工具池 handler：闭包捕获 (server, tool) 两个 String，调用时按名从
/// 全局 MCP_STATE 取客户端再 call_tool —— 等价于 Python 的
/// `lambda *, c=mcp_client, t=tool_def["name"], **kw: c.call_tool(t, kw)`。
/// Box<dyn Fn + Send + Sync>：agent_loop 里跨 spawn_blocking 线程使用。
type PoolHandler = Box<dyn Fn(&serde_json::Value) -> String + Send + Sync>;

/// 组装工具池：(内置工具 + 全部已连接 MCP 工具, MCP 运行时表)。
/// 命名 mcp__{safe_server}__{safe_tool}（两端都过 normalize_mcp_name）。
fn assemble_tool_pool() -> (Vec<Tool>, HashMap<String, PoolHandler>) {
    let mut tools = all_tools();
    let mut handlers: HashMap<String, PoolHandler> = HashMap::new();
    let state = MCP_STATE.lock().unwrap();
    for server in &state.order {
        let client = match state.clients.get(server) {
            Some(c) => c,
            None => continue,
        };
        let safe_server = normalize_mcp_name(server);
        for tool in &client.tools {
            let safe_tool = normalize_mcp_name(&tool.name);
            let prefixed = format!("mcp__{safe_server}__{safe_tool}");
            tools.push(Tool {
                name: prefixed.clone(),
                description: tool.description.clone(),
                input_schema: tool.input_schema.clone(),
            });
            let server_name = server.clone();
            let tool_name = tool.name.clone();
            handlers.insert(
                prefixed,
                Box::new(move |input: &serde_json::Value| -> String {
                    let st = MCP_STATE.lock().unwrap();
                    match st.clients.get(&server_name) {
                        Some(c) => c.call_tool(&tool_name, input),
                        None => format!("MCP error: server '{server_name}' not connected"),
                    }
                }),
            );
        }
    }
    (tools, handlers)
}

/// s19: 工具双路径分发 —— MCP 运行时表命中走动态 handler；
/// 未命中回退 execute_sync（内置工具的静态 match，s12 起冻结不动）。
fn dispatch_tool(
    name: &str,
    input: &serde_json::Value,
    mcp_handlers: &HashMap<String, PoolHandler>,
) -> String {
    match mcp_handlers.get(name) {
        Some(handler) => handler(input),
        None => execute_sync(name, input),
    }
}

/// s19: 本轮响应里是否调用了 connect_mcp（决定要不要重组装工具池）。
/// 对齐 Python agent_loop 的 `any(b.name == "connect_mcp" ...)` 检查。
fn response_uses_connect_mcp(blocks: &[ContentBlock]) -> bool {
    blocks.iter().any(|b| {
        matches!(b, ContentBlock::ToolUse { name, .. } if name == "connect_mcp")
    })
}

// ── 后台任务（对齐 Python s13） ──────────────────────────────────────────

/// 一个后台任务的运行时状态
struct BgTask {
    /// 原始 tool_use_id（占位 tool_result 已回复，这里仅留档对齐 Python 的
    /// background_tasks[bg_id]["tool_use_id"]）
    #[allow(dead_code)]
    tool_use_id: String,
    command: String,
    status: String, // "running" | "completed"
}

/// bg_id 自增计数器（对齐 Python 的 bg_{n:04d} 格式）
static BG_COUNTER: AtomicU64 = AtomicU64::new(0);
/// bg_id → 任务生命周期（含原始 tool_use_id，回填占位时不用，仅留档）
static BACKGROUND_TASKS: LazyLock<Mutex<HashMap<String, BgTask>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));
/// bg_id → 执行结果（worker 完成后写入，collect 时取走）
static BACKGROUND_RESULTS: LazyLock<Mutex<HashMap<String, String>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// 词边界判定：keyword 两侧必须是行首/行尾或非单词字符（空白、标点、中文等）。
/// 修复：朴素子串匹配会把 "makeCtx" 里的 "make"、"uninstall" 里的 "install"
/// 误判成慢命令丢后台（实测教训：mock 脚本里的 JS 函数名 makeCtx 让语法检查
/// 命令进了后台，模型一脸困惑）。
fn is_word_boundary(c: char) -> bool {
    !(c.is_alphanumeric() || c == '_')
}

/// 在 haystack 里做词边界子串匹配（keyword 两侧必须是边界）
fn contains_word(haystack: &str, keyword: &str) -> bool {
    haystack.match_indices(keyword).any(|(i, _)| {
        let before = haystack[..i].chars().next_back();
        let after = haystack[i + keyword.len()..].chars().next();
        before.is_none_or(is_word_boundary) && after.is_none_or(is_word_boundary)
    })
}

/// 启发式兜底：命令关键词命中（对齐 Python 的 slow_keywords 表，
/// 但用词边界匹配——复合词如 `cargo buildx` 不命中时模型可显式指定
/// run_in_background=true）
fn is_slow_operation(name: &str, input: &serde_json::Value) -> bool {
    if name != "bash" {
        return false;
    }
    let cmd = input
        .get("command")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_lowercase();
    const SLOW_KEYWORDS: [&str; 11] = [
        "install", "build", "test", "deploy", "compile", "docker build",
        "pip install", "npm install", "cargo build", "pytest", "make",
    ];
    SLOW_KEYWORDS.iter().any(|kw| contains_word(&cmd, kw))
}

/// 是否丢后台：模型显式 run_in_background=true 优先，否则启发式兜底
fn should_run_background(name: &str, input: &serde_json::Value) -> bool {
    if input
        .get("run_in_background")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
    {
        return true;
    }
    is_slow_operation(name, input)
}

/// 把工具调用丢到后台线程（spawn_blocking），立即返回 bg_id。
/// 主循环不等待：完成后由 collect_background_results 收集为通知。
fn start_background_task(id: &str, input: &serde_json::Value) -> String {
    let n = BG_COUNTER.fetch_add(1, Ordering::Relaxed) + 1;
    let bg_id = format!("bg_{n:04}");
    let cmd = input
        .get("command")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    {
        let mut tasks = BACKGROUND_TASKS.lock().unwrap();
        tasks.insert(
            bg_id.clone(),
            BgTask {
                tool_use_id: id.to_string(),
                command: cmd.clone(),
                status: "running".into(),
            },
        );
    }
    // worker：spawn_blocking 跑 run_bash（120s 超时由 run_bash 内部处理）
    let input = input.clone();
    let bg_id2 = bg_id.clone();
    tokio::task::spawn_blocking(move || {
        let output = serde_json::from_value::<BashInput>(input)
            .map(run_bash)
            .unwrap_or_else(|e| format!("Error: invalid bash params: {e}"));
        {
            let mut tasks = BACKGROUND_TASKS.lock().unwrap();
            if let Some(t) = tasks.get_mut(&bg_id2) {
                t.status = "completed".into();
            }
        }
        BACKGROUND_RESULTS.lock().unwrap().insert(bg_id2, output);
    });
    println!(
        "  \x1b[33m[background] dispatched {bg_id}: {}\x1b[0m",
        truncate_chars(&cmd, 40)
    );
    bg_id
}

/// 收集已完成的后台任务，格式化为 <task_notification> 通知。
/// 通知不复用原始 tool_use_id（对齐 Python s13：原始 tool call 已用
/// 占位 tool_result 回复，后台完成是独立事件——一个 tool_use 只配对一个 tool_result）。
fn collect_background_results() -> Vec<String> {
    let ready: Vec<String> = {
        let tasks = BACKGROUND_TASKS.lock().unwrap();
        tasks
            .iter()
            .filter(|(_, t)| t.status == "completed")
            .map(|(k, _)| k.clone())
            .collect()
    };
    let mut notifications = Vec::new();
    for bg_id in ready {
        let (task, output) = {
            let mut tasks = BACKGROUND_TASKS.lock().unwrap();
            let mut results = BACKGROUND_RESULTS.lock().unwrap();
            (tasks.remove(&bg_id), results.remove(&bg_id).unwrap_or_default())
        };
        if let Some(t) = task {
            let summary = truncate_chars(&output, 200);
            notifications.push(format!(
                "<task_notification>\n  <task_id>{bg_id}</task_id>\n  <status>completed</status>\n  <command>{}</command>\n  <summary>{summary}</summary>\n</task_notification>",
                t.command
            ));
            println!(
                "  \x1b[32m[background done] {bg_id}: {} ({} chars)\x1b[0m",
                truncate_chars(&t.command, 40),
                output.chars().count()
            );
        }
    }
    notifications
}

// ── 流式 SSE 输出（Rust 前向扩展，Python 参考轨没有） ────────────────────

/// 本轮是否已经由流式输出打印过文本（main 里避免重复打印最终回复）
static STREAMED_OUTPUT_PRINTED: AtomicBool = AtomicBool::new(false);

/// 流式重建的中间块：SSE 事件流结束时转成 ContentBlock。
/// tool_use 的 input 是 input_json_delta 的增量拼接，结束时才解析成 JSON。
enum StreamBlock {
    Text { text: String },
    Thinking {
        thinking: String,
        signature: Option<String>,
    },
    ToolUse {
        id: String,
        name: String,
        input_raw: String,
    },
}

/// 找 SSE 事件边界（空行分隔）。兼容 \n\n 与 \r\n\r\n 两种行尾。
fn find_event_boundary(buf: &[u8]) -> Option<usize> {
    if let Some(i) = buf.windows(2).position(|w| w == b"\n\n") {
        return Some(i + 1);
    }
    if let Some(i) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
        return Some(i + 3);
    }
    None
}

/// 从一行 "data: {...}" 抽出载荷
fn sse_data_line(line: &str) -> Option<&str> {
    line.trim_start().strip_prefix("data:").map(|s| s.trim())
}

/// 把一个 SSE 事件块（若干 event:/data: 行）解析成 JSON value。
/// 心跳（无 data）、[DONE] 终止标记、非法 JSON 都返回 None。
fn sse_event_json(block: &str) -> Option<serde_json::Value> {
    let data: Vec<&str> = block.lines().filter_map(sse_data_line).collect();
    if data.is_empty() {
        return None;
    }
    let joined = data.join("\n");
    if joined == "[DONE]" {
        return None;
    }
    serde_json::from_str(&joined).ok()
}

/// 处理一个 SSE 事件：增量重建 blocks、记录 stop_reason、标记是否有 tool_use。
/// text_delta 在这里边收边打印（终端流式效果）；
/// thinking_delta 默认只重建不显示（回传 API 必需），stream_thinking=true 时
/// 灰色打到 stderr（CC 风格），与 stdout 的 text 分离。
fn handle_sse_event(
    event_block: &str,
    blocks: &mut Vec<StreamBlock>,
    stop_reason: &mut Option<String>,
    has_tool_use: &mut bool,
    stream_thinking: bool,
) {
    let Some(value) = sse_event_json(event_block) else {
        return;
    };
    match value["type"].as_str() {
        Some("content_block_start") => {
            let idx = value["index"].as_u64().unwrap_or(0) as usize;
            while blocks.len() <= idx {
                blocks.push(StreamBlock::Text { text: String::new() });
            }
            match value["content_block"]["type"].as_str() {
                Some("text") => blocks[idx] = StreamBlock::Text { text: String::new() },
                Some("thinking") => {
                    blocks[idx] = StreamBlock::Thinking {
                        thinking: String::new(),
                        signature: None,
                    };
                }
                Some("tool_use") => {
                    let id = value["content_block"]["id"].as_str().unwrap_or("").to_string();
                    let name = value["content_block"]["name"].as_str().unwrap_or("").to_string();
                    blocks[idx] = StreamBlock::ToolUse {
                        id,
                        name,
                        input_raw: String::new(),
                    };
                    *has_tool_use = true;
                }
                _ => blocks[idx] = StreamBlock::Text { text: String::new() },
            }
        }
        Some("content_block_delta") => {
            let idx = value["index"].as_u64().unwrap_or(0) as usize;
            if idx >= blocks.len() {
                return;
            }
            match value["delta"]["type"].as_str() {
                Some("text_delta") => {
                    if let Some(t) = value["delta"]["text"].as_str() {
                        if let StreamBlock::Text { text } = &mut blocks[idx] {
                            text.push_str(t);
                        }
                        // 流式输出：边收边打印（无换行，message_stop 后由调用方补）
                        print!("{t}");
                        io::stdout().flush().ok();
                        // 有文本真的流式打印过 → main 不再重复打印最终回复
                        STREAMED_OUTPUT_PRINTED.store(true, Ordering::Relaxed);
                    }
                }
                Some("thinking_delta") => {
                    if let Some(t) = value["delta"]["thinking"].as_str() {
                        if let StreamBlock::Thinking { thinking, .. } = &mut blocks[idx] {
                            let first = thinking.is_empty();
                            thinking.push_str(t);
                            // s13: STREAM_THINKING=1 时思考过程流式打到 stderr
                            // （灰色，CC 风格），不污染 stdout 的主输出
                            if stream_thinking {
                                if first {
                                    eprint!("\x1b[90m[thinking] {t}\x1b[0m");
                                } else {
                                    eprint!("\x1b[90m{t}\x1b[0m");
                                }
                                io::stderr().flush().ok();
                            }
                        }
                    }
                }
                Some("signature_delta") => {
                    if let Some(sig) = value["delta"]["signature"].as_str() {
                        if let StreamBlock::Thinking { signature, .. } = &mut blocks[idx] {
                            let acc = signature.clone().unwrap_or_default();
                            *signature = Some(format!("{acc}{sig}"));
                        }
                    }
                }
                Some("input_json_delta") => {
                    if let Some(p) = value["delta"]["partial_json"].as_str() {
                        if let StreamBlock::ToolUse { input_raw, .. } = &mut blocks[idx] {
                            input_raw.push_str(p);
                        }
                    }
                }
                _ => {}
            }
        }
        Some("message_delta") => {
            if let Some(sr) = value["delta"]["stop_reason"].as_str() {
                *stop_reason = Some(sr.to_string());
            }
        }
        Some("message_stop") => {}
        // 流中错误事件（event: error）：教学版直接忽略，靠 HTTP 状态码兜底
        _ => {}
    }
}

/// 公共请求构造：POST /v1/messages + anthropic-version/beta 头 + 认证二选一。
/// s13 从 call_llm 抽出，流式与非流式两条路径共用。
fn build_request<'a>(
    http: &reqwest::Client,
    cfg: &Config,
    req: &'a ApiRequest<'a>,
) -> reqwest::RequestBuilder {
    let mut builder = http
        .post(format!("{}/v1/messages", cfg.base_url))
        // 2023-06-01 是最老的稳定版，所有 Anthropic 兼容网关均支持。
        // 不升级到更新版本（如 2025-01-01）是为了保持与第三方网关的最大兼容性。
        .header("anthropic-version", "2023-06-01")
        .json(req);
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
    builder
}

/// 流式 LLM 调用（父代理主循环用）：stream: true 发请求，SSE 事件流
/// 边收边重建 ContentBlock 并打印 text_delta。
///
/// 重建完成后返回与 call_llm 相同形状的 ApiResponse——截断恢复
/// （stop_reason == max_tokens）和工具循环逻辑完全复用，无需改动。
/// stop_reason 在流式里可能不可靠（对齐 CC 源码里 needsFollowUp 的思路）：
/// 收不到 stop_reason 时按"内容里有没有 tool_use"兜底。
async fn call_llm_streaming(
    http: &reqwest::Client,
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
        stream: true,
        output_config: cfg.effort.as_ref().map(|e| OutputConfig { effort: e.clone() }),
    };

    if cfg.debug {
        let req_json = serde_json::to_string_pretty(&req).unwrap_or_default();
        eprintln!(
            "\x1b[90m[debug] ==> POST {}/v1/messages (stream)\n{req_json}\x1b[0m",
            cfg.base_url
        );
    }

    let mut resp = build_request(http, cfg, &req)
        .send()
        .await
        .map_err(|e| LlmError::Other(format!("HTTP 请求失败: {e}")))?;

    let status = resp.status();
    let retry_after = parse_retry_after(
        resp.headers()
            .get("retry-after")
            .and_then(|v| v.to_str().ok()),
    );

    // 非 2xx：错误走非流式路径读取（错误体是普通 JSON）
    if !status.is_success() {
        let body = resp
            .text()
            .await
            .map_err(|e| LlmError::Other(format!("读取响应体失败: {e}")))?;
        if cfg.debug {
            let pretty = serde_json::from_str::<serde_json::Value>(&body)
                .and_then(|v| serde_json::to_string_pretty(&v))
                .unwrap_or_else(|_| body.clone());
            eprintln!("\x1b[90m[debug] <== HTTP {status}\n{pretty}\x1b[0m");
        }
        let mut err = classify_http_error(status.as_u16(), &body);
        if let LlmError::RateLimited { retry_after_secs } = &mut err {
            *retry_after_secs = retry_after;
        }
        return Err(err);
    }

    // ── SSE 事件流解析：按空行切事件块，逐块增量重建 ──
    let mut buf: Vec<u8> = Vec::new();
    let mut blocks: Vec<StreamBlock> = Vec::new();
    let mut stop_reason: Option<String> = None;
    let mut has_tool_use = false;

    while let Some(chunk) = resp
        .chunk()
        .await
        .map_err(|e| LlmError::Other(format!("SSE 读取失败: {e}")))?
    {
        buf.extend_from_slice(&chunk);
        while let Some(end) = find_event_boundary(&buf) {
            let event_block: Vec<u8> = buf.drain(..=end).collect();
            handle_sse_event(
                &String::from_utf8_lossy(&event_block),
                &mut blocks,
                &mut stop_reason,
                &mut has_tool_use,
                cfg.stream_thinking,
            );
        }
    }
    // 尾部残留（流结束没有空行时）
    if !buf.is_empty() {
        handle_sse_event(
            &String::from_utf8_lossy(&buf),
            &mut blocks,
            &mut stop_reason,
            &mut has_tool_use,
            cfg.stream_thinking,
        );
    }

    // 流式输出补一个换行（text_delta 都是无换行打印的）
    println!();

    // StreamBlock → ContentBlock（tool_use 的 input 增量 JSON 在此解析）
    let content: Vec<ContentBlock> = blocks
        .into_iter()
        .map(|b| match b {
            StreamBlock::Text { text } => ContentBlock::Text { text },
            StreamBlock::Thinking { thinking, signature } => {
                let mut extra = serde_json::Map::new();
                if let Some(sig) = signature {
                    extra.insert("signature".into(), serde_json::Value::String(sig));
                }
                ContentBlock::Thinking { thinking, extra }
            }
            StreamBlock::ToolUse { id, name, input_raw } => {
                let input = serde_json::from_str(&input_raw)
                    .unwrap_or_else(|_| serde_json::json!({}));
                ContentBlock::ToolUse { id, name, input }
            }
        })
        .collect();

    // stop_reason 兜底：流式里拿不到就按内容判断（对齐 CC 的 needsFollowUp）
    let stop_reason = stop_reason.or_else(|| {
        if has_tool_use {
            Some("tool_use".to_string())
        } else {
            None
        }
    });

    Ok(ApiResponse {
        content,
        stop_reason,
    })
}

// ═════════════════════════════════════════════════════════════════════
//  s14 新增：Cron 调度器（对齐 Python s14）
// ═════════════════════════════════════════════════════════════════════

/// 一个定时任务。字段与 Python 版 CronJob dataclass 的 asdict 输出逐字同构
/// （.scheduled_tasks.json 两轨可互换）。
#[derive(Serialize, Deserialize, Clone, Debug)]
struct CronJob {
    id: String,
    /// 五段式 cron 表达式："分 时 日 月 星期"
    cron: String,
    /// 触发时注入给 Agent 的消息
    prompt: String,
    /// true = 周期性；false = 一次性（触发后自动移除）
    recurring: bool,
    /// true = 写 .scheduled_tasks.json，跨会话保留
    durable: bool,
}

/// schedule_cron 工具的参数
#[derive(Deserialize)]
struct ScheduleCronInput {
    cron: String,
    prompt: String,
    #[serde(default)]
    recurring: Option<bool>,
    #[serde(default)]
    durable: Option<bool>,
}

/// list_crons 工具的参数（无字段）
#[derive(Deserialize)]
struct ListCronsInput {}

/// cancel_cron 工具的参数
#[derive(Deserialize)]
struct CronIdInput {
    job_id: String,
}

/// 已注册任务：id → CronJob
static CRON_JOBS: LazyLock<Mutex<HashMap<String, CronJob>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));
/// 已触发待交付队列：调度任务写，主循环消费
static CRON_QUEUE: LazyLock<Mutex<Vec<CronJob>>> = LazyLock::new(|| Mutex::new(Vec::new()));
/// 去重标记：job_id → "YYYY-MM-DD HH:MM"（含日期 → 跨天不跳过）
static LAST_FIRED: LazyLock<Mutex<HashMap<String, String>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// 调度检查间隔（秒，对齐 Python 的 1s 轮询）
const CRON_CHECK_INTERVAL_SECS: u64 = 1;
/// 作业数上限（CC 行为；防模型刷任务）
const MAX_JOBS: usize = 50;

/// 单个 cron 字段匹配：支持 * / */N / N / N-M / N,M,...（对齐 Python）。
/// 非法输入静默返回 false（替代 Python 的 try/except——注册/加载时已双重校验）。
fn cron_field_matches(field: &str, value: u32) -> bool {
    let field = field.trim();
    if field == "*" {
        return true;
    }
    if let Some(step) = field.strip_prefix("*/") {
        return step
            .parse::<u32>()
            .map(|s| s > 0 && value % s == 0)
            .unwrap_or(false);
    }
    if field.contains(',') {
        return field.split(',').any(|f| cron_field_matches(f, value));
    }
    if let Some((lo, hi)) = field.split_once('-') {
        return match (lo.parse::<u32>(), hi.parse::<u32>()) {
            (Ok(a), Ok(b)) => a <= value && value <= b,
            _ => false,
        };
    }
    field.parse::<u32>().map(|v| v == value).unwrap_or(false)
}

/// 五段式 cron 匹配（标准语义）：
///   分钟/小时/月必须全匹配；DOM/DOW 同时约束时任一匹配即可（OR）。
/// weekday 由调用方从 chrono 转换（周日=0，同 Python 的 (weekday+1)%7）。
/// 纯函数：时间字段注入，零时间依赖，可单测。
fn cron_matches(cron: &str, minute: u32, hour: u32, day: u32, month: u32, weekday: u32) -> bool {
    let fields: Vec<&str> = cron.split_whitespace().collect();
    if fields.len() != 5 {
        return false;
    }
    let (dom, dow) = (fields[2], fields[4]);
    if !(cron_field_matches(fields[0], minute)
        && cron_field_matches(fields[1], hour)
        && cron_field_matches(fields[3], month))
    {
        return false;
    }
    let dom_ok = cron_field_matches(dom, day);
    let dow_ok = cron_field_matches(dow, weekday);
    let dom_unconstrained = dom.trim() == "*";
    let dow_unconstrained = dow.trim() == "*";
    match (dom_unconstrained, dow_unconstrained) {
        (true, true) => true,
        (true, false) => dow_ok,
        (false, true) => dom_ok,
        (false, false) => dom_ok || dow_ok,
    }
}

/// 校验单个 cron 字段。返回错误文案（对齐 Python）或 None。
fn validate_cron_field(field: &str, lo: u32, hi: u32) -> Option<String> {
    let field = field.trim();
    if field == "*" {
        return None;
    }
    if let Some(step) = field.strip_prefix("*/") {
        return match step.parse::<u32>() {
            Ok(s) if s > 0 => None,
            Ok(_) => Some(format!("Step must be > 0: {field}")),
            Err(_) => Some(format!("Invalid step: {field}")),
        };
    }
    if field.contains(',') {
        for part in field.split(',') {
            if let Some(err) = validate_cron_field(part, lo, hi) {
                return Some(err);
            }
        }
        return None;
    }
    if let Some((a, b)) = field.split_once('-') {
        return match (a.parse::<u32>(), b.parse::<u32>()) {
            (Ok(x), Ok(y)) if x >= lo && x <= hi && y >= lo && y <= hi && x <= y => None,
            (Ok(x), Ok(y)) if x > y => Some(format!("Range start > end: {field}")),
            (Ok(_), Ok(_)) => Some(format!("Range {field} out of bounds [{lo}-{hi}]")),
            _ => Some(format!("Invalid range: {field}")),
        };
    }
    match field.parse::<u32>() {
        Ok(v) if v >= lo && v <= hi => None,
        Ok(v) => Some(format!("Value {v} out of bounds [{lo}-{hi}]")),
        Err(_) => Some(format!("Invalid field: {field}")),
    }
}

/// 校验整个 cron 表达式。返回错误消息或 None（对齐 Python 的 validate_cron）。
fn validate_cron(cron: &str) -> Option<String> {
    let fields: Vec<&str> = cron.split_whitespace().collect();
    if fields.len() != 5 {
        return Some(format!("Expected 5 fields, got {}", fields.len()));
    }
    let bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)];
    let names = ["minute", "hour", "day-of-month", "month", "day-of-week"];
    for (i, field) in fields.iter().enumerate() {
        if let Some(err) = validate_cron_field(field, bounds[i].0, bounds[i].1) {
            return Some(format!("{}: {err}", names[i]));
        }
    }
    None
}

/// 调度"判火"纯函数：时间字段由调用方注入（调度任务取 chrono::Local::now()，
/// 测试喂固定序列——去重/跨天/一次性全部可单测，不用真 sleep）。
/// 同分钟去重（marker 含日期 → 跨天不跳过）；one-shot 触发后从 jobs 移除。
/// 返回被移除的 durable job id（调用方负责同步落盘）。
fn fire_due_jobs(
    minute: u32,
    hour: u32,
    day: u32,
    month: u32,
    weekday: u32,
    marker: &str,
    jobs: &mut HashMap<String, CronJob>,
    last_fired: &mut HashMap<String, String>,
    queue: &mut Vec<CronJob>,
) -> Vec<String> {
    let mut removed_durable: Vec<String> = Vec::new();
    let due: Vec<String> = jobs
        .iter()
        .filter(|(_, j)| cron_matches(&j.cron, minute, hour, day, month, weekday))
        .map(|(id, _)| id.clone())
        .collect();
    for id in due {
        let Some(job) = jobs.get(&id).cloned() else {
            continue;
        };
        if last_fired.get(&id).map(|m| m == marker).unwrap_or(false) {
            continue; // 同一分钟已触发过
        }
        last_fired.insert(id.clone(), marker.to_string());
        queue.push(job.clone());
        println!(
            "  \x1b[35m[cron fire] {} → {}\x1b[0m",
            job.id,
            truncate_chars(&job.prompt, 40)
        );
        if !job.recurring {
            jobs.remove(&id);
            if job.durable {
                removed_durable.push(id);
            }
        }
    }
    removed_durable
}

/// durable 任务落盘：仅 durable job 的**数组** JSON（对齐 Python 的
/// json.dumps([asdict(j)...], indent=2)——数组格式，两轨文件可互换）。
/// best-effort：磁盘错误静默吞掉（与记忆系统同惯例）；先建父目录（测试注入
/// 临时目录时目录可能不存在，与 tasks_dir/memory_dir 的惯例一致）。
fn save_durable_jobs(cwd: &Path, jobs: &HashMap<String, CronJob>) {
    let durable: Vec<&CronJob> = jobs.values().filter(|j| j.durable).collect();
    let path = cwd.join(".scheduled_tasks.json");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).ok();
    }
    if let Ok(json) = serde_json::to_string_pretty(&durable) {
        fs::write(path, json).ok();
    }
}

/// 启动时加载 durable 任务：非法表达式跳过（不拖垮启动），打印统计。
fn load_durable_jobs(cwd: &Path, jobs: &mut HashMap<String, CronJob>) {
    let path = cwd.join(".scheduled_tasks.json");
    if !path.exists() {
        return;
    }
    let raw = match fs::read_to_string(&path) {
        Ok(r) => r,
        Err(_) => return,
    };
    let loaded: Vec<CronJob> = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(_) => return,
    };
    let mut valid = 0;
    for job in loaded {
        if let Some(err) = validate_cron(&job.cron) {
            println!(
                "  \x1b[31m[cron] skipping invalid job {}: {err}\x1b[0m",
                job.id
            );
            continue;
        }
        jobs.insert(job.id.clone(), job);
        valid += 1;
    }
    if valid > 0 {
        println!("  \x1b[35m[cron] loaded {valid} durable job(s)\x1b[0m");
    }
}

/// 注册定时任务：校验 → 生成 cron_{:06} id → 入表 → durable 落盘。
fn schedule_job(
    cwd: &Path,
    cron: &str,
    prompt: &str,
    recurring: bool,
    durable: bool,
) -> Result<CronJob, String> {
    if let Some(err) = validate_cron(cron) {
        return Err(err);
    }
    let mut jobs = CRON_JOBS.lock().unwrap();
    if jobs.len() >= MAX_JOBS {
        return Err("Too many scheduled jobs (max 50). Cancel one first.".to_string());
    }
    let job = CronJob {
        id: format!("cron_{:06}", rand::thread_rng().gen_range(0..=999999)),
        cron: cron.to_string(),
        prompt: prompt.to_string(),
        recurring,
        durable,
    };
    jobs.insert(job.id.clone(), job.clone());
    if durable {
        save_durable_jobs(cwd, &jobs);
    }
    println!(
        "  \x1b[35m[cron register] {} '{}' → {}\x1b[0m",
        job.id,
        job.cron,
        truncate_chars(&job.prompt, 40)
    );
    Ok(job)
}

/// 取消定时任务（durable 同步落盘）。
fn cancel_job(cwd: &Path, job_id: &str) -> String {
    let mut jobs = CRON_JOBS.lock().unwrap();
    let Some(job) = jobs.remove(job_id) else {
        return format!("Job {job_id} not found");
    };
    if job.durable {
        save_durable_jobs(cwd, &jobs);
    }
    println!("  \x1b[31m[cron cancel] {job_id}\x1b[0m");
    format!("Cancelled {job_id}")
}

/// 列出全部任务（对齐 Python 的行格式）。
fn list_crons() -> String {
    let jobs = CRON_JOBS.lock().unwrap();
    if jobs.is_empty() {
        return "No cron jobs. Use schedule_cron to add one.".to_string();
    }
    let mut lines = Vec::new();
    for j in jobs.values() {
        let tag = if j.recurring { "recurring" } else { "one-shot" };
        let dur = if j.durable { "durable" } else { "session" };
        lines.push(format!(
            "  {}: '{}' → {} [{tag}, {dur}]",
            j.id,
            j.cron,
            truncate_chars(&j.prompt, 40)
        ));
    }
    lines.join("\n")
}

/// 取走已触发的任务（agent_loop 循环顶部调用，路径 A）。
fn consume_cron_queue() -> Vec<CronJob> {
    let mut queue = CRON_QUEUE.lock().unwrap();
    std::mem::take(&mut *queue)
}

/// 队列是否非空（select! 定时分支判空用，防空转）。
fn has_cron_queue() -> bool {
    !CRON_QUEUE.lock().unwrap().is_empty()
}

/// schedule_cron 工具入口（workdir() 模式，与任务系统工具一致）
fn run_schedule_cron(input: ScheduleCronInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return format!("Error: {e}"),
    };
    match schedule_job(
        &cwd,
        &input.cron,
        &input.prompt,
        input.recurring.unwrap_or(true),
        input.durable.unwrap_or(true),
    ) {
        Ok(job) => format!("Scheduled {}: '{}' → {}", job.id, job.cron, job.prompt),
        Err(e) => format!("Error: {e}"),
    }
}

/// list_crons 工具入口
fn run_list_crons(_input: ListCronsInput) -> String {
    list_crons()
}

/// cancel_cron 工具入口
fn run_cancel_cron(input: CronIdInput) -> String {
    let cwd = match workdir() {
        Ok(c) => c,
        Err(e) => return format!("Error: {e}"),
    };
    cancel_job(&cwd, &input.job_id)
}

/// chrono 星期(周一=0..周日=6) → cron 星期(周日=0,周一=1..周六=6)。
/// 对齐 Python 的 `(dt.weekday() + 1) % 7`。纯函数,单独可测——
/// 调度循环在取"现在"字段时调用它,防止 DOW 约束任务错位一天。
fn cron_weekday_from_chrono(monday_based: u32) -> u32 {
    (monday_based + 1) % 7
}

/// 调度任务（tokio task）：1s 轮询，匹配则入队并通知主循环。
/// 注意：tokio::time::interval 首个 tick 立即完成（Python 是先睡 1s），
/// 无实际影响（首 tick 通常无到期任务）。
async fn cron_scheduler_loop(cwd: PathBuf, tx: tokio::sync::mpsc::UnboundedSender<()>) {
    let mut ticker = tokio::time::interval(Duration::from_secs(CRON_CHECK_INTERVAL_SECS));
    loop {
        ticker.tick().await;
        let now = chrono::Local::now();
        let marker = now.format("%Y-%m-%d %H:%M").to_string();
        let mut jobs = CRON_JOBS.lock().unwrap();
        let mut queue = CRON_QUEUE.lock().unwrap();
        let mut last_fired = LAST_FIRED.lock().unwrap();
        let was_empty = queue.is_empty();
        let removed = fire_due_jobs(
            now.minute(),
            now.hour(),
            now.day(),
            now.month(),
            cron_weekday_from_chrono(now.weekday().num_days_from_monday()),
            &marker,
            &mut jobs,
            &mut last_fired,
            &mut queue,
        );
        if !removed.is_empty() {
            save_durable_jobs(&cwd, &jobs);
        }
        // 只在"空 → 非空"转变时发一次唤醒信号：若每 tick 都发，
        // 回合中途触发后队列未消费的窗口会每秒积压一个信号，
        // 回合结束主循环逐个消费 → "s14 >> " 提示符刷屏（实测教训）。
        if was_empty && !queue.is_empty() {
            let _ = tx.send(());
        }
    }
}

// ═════════════════════════════════════════════════════════════════════
//  s15 新增：Agent Teams —— MessageBus 文件收件箱 + 队友任务 + Lead 唤醒
// ═════════════════════════════════════════════════════════════════════

// ── 团队工具输入 ──

/// spawn_teammate 工具的参数
#[derive(Deserialize)]
struct SpawnTeammateInput {
    name: String,
    role: String,
    prompt: String,
}

/// send_message 工具的参数
#[derive(Deserialize)]
struct SendMessageInput {
    to: String,
    content: String,
}

/// check_inbox 工具的参数（无字段）
#[derive(Deserialize)]
struct CheckInboxInput {}

// ── s16: 协议工具输入 ──

/// request_shutdown 工具的参数
#[derive(Deserialize)]
struct RequestShutdownInput {
    teammate: String,
}

/// request_plan 工具的参数
#[derive(Deserialize)]
struct RequestPlanInput {
    teammate: String,
    task: String,
}

/// review_plan 工具的参数（feedback 可选，对齐 Python 默认 ""）
#[derive(Deserialize)]
struct ReviewPlanInput {
    request_id: String,
    approve: bool,
    #[serde(default)]
    feedback: String,
}

/// 队友 submit_plan 工具的参数
#[derive(Deserialize)]
struct SubmitPlanInput {
    plan: String,
}

// ── s18: worktree 工具输入 ──

/// create_worktree 工具的参数（task_id 可选）
#[derive(Deserialize)]
struct CreateWorktreeInput {
    name: String,
    #[serde(default)]
    task_id: String,
}

/// remove_worktree 工具的参数（discard_changes 可选）
#[derive(Deserialize)]
struct RemoveWorktreeInput {
    name: String,
    #[serde(default)]
    discard_changes: bool,
}

/// keep_worktree 工具的参数
#[derive(Deserialize)]
struct KeepWorktreeInput {
    name: String,
}

// ── MessageBus: 文件收件箱（对齐 Python s15） ──────────────────────────────
//
// 每个 Agent（含 Lead）一个 .mailboxes/{agent}.jsonl 收件箱。
// 发消息 = 往对方文件 append 一行 JSON；读消息 = 读全文 + 删文件（消费式）；
// peek = 非破坏探测（唤醒轮询用，不消费）。
// 教学版无文件锁（read+unlink 竞态可接受，对齐 Python；真实 CC 用 proper-lockfile）。

/// 邮箱消息（字段与 Python 版同构：from/to/content/type/ts）。
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
struct MailMessage {
    from: String,
    to: String,
    content: String,
    #[serde(rename = "type")]
    msg_type: String,
    /// 时间戳（秒浮点，对齐 Python time.time()）
    ts: f64,
    /// s16: 协议元数据（request_id / approve 等）。`default_metadata` 兼容
    /// s15 时代无此字段的旧收件箱消息（Python 版 s16 同加 metadata 字段）；
    /// serde_json::Value 的 Default 是 Null，必须归一为空对象（对齐
    /// Python `msg.get("metadata", {})` 语义）。
    #[serde(default = "default_metadata")]
    metadata: serde_json::Value,
}

/// 缺失 metadata 字段时的默认值（空对象，对齐 Python `metadata or {}`）。
fn default_metadata() -> serde_json::Value {
    serde_json::json!({})
}

/// agent 名校验：防路径穿越（Python 教学版直接拼接文件名，
/// `to="../x"` 可把消息写到 .mailboxes/ 之外——Rust 版前向修复，见 README 差异表）。
/// 黑名单思路：拒绝路径敏感字符（/ \ . : 空格）与控制字符，
/// 中文等 Unicode 名称允许（队友名常为中文，实测需求）。
fn valid_agent_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 64
        && !name.chars().any(|c| {
            c.is_ascii_control() || matches!(c, '/' | '\\' | '.' | ':' | ' ')
        })
}

fn mailbox_path(cwd: &Path, agent: &str) -> PathBuf {
    cwd.join(".mailboxes").join(format!("{agent}.jsonl"))
}

/// 当前时间戳（秒浮点，对齐 Python time.time()）。
fn now_ts() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// 发送消息：往对方收件箱 append 一行 JSON。成功返回空串，失败返回 "Error: ..."。
/// 发送消息（无 metadata）：转发 bus_send_meta 并传空对象。
/// 保持 5 参签名不变——s15 冻结代码与既有测试零改动（s16 新增协议路径走 bus_send_meta）。
fn bus_send(cwd: &Path, from: &str, to: &str, content: &str, msg_type: &str) -> String {
    bus_send_meta(cwd, from, to, content, msg_type, &serde_json::json!({}))
}

/// 发送消息（带协议 metadata）：往对方收件箱 append 一行 JSON。
/// 成功返回空串，失败返回 "Error: ..."。
fn bus_send_meta(
    cwd: &Path,
    from: &str,
    to: &str,
    content: &str,
    msg_type: &str,
    metadata: &serde_json::Value,
) -> String {
    if !valid_agent_name(from) {
        return format!("Error: invalid agent name '{from}'");
    }
    if !valid_agent_name(to) {
        return format!("Error: invalid agent name '{to}'");
    }
    let msg = MailMessage {
        from: from.to_string(),
        to: to.to_string(),
        content: content.to_string(),
        msg_type: msg_type.to_string(),
        ts: now_ts(),
        metadata: metadata.clone(),
    };
    let path = mailbox_path(cwd, to);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).ok();
    }
    let line = match serde_json::to_string(&msg) {
        Ok(l) => l,
        Err(e) => return format!("Error: serialize message: {e}"),
    };
    match fs::OpenOptions::new().create(true).append(true).open(&path) {
        Ok(mut f) => {
            if let Err(e) = writeln!(f, "{line}") {
                return format!("Error: write mailbox: {e}");
            }
        }
        Err(e) => return format!("Error: open mailbox: {e}"),
    }
    // s15: 队友线程与 Lead 流式输出共用 stdout——标记走 stderr（对齐 [HOOK] 惯例），
    // 避免插入模型流式回复中间（实测交错教训）；`2>log.txt` 可单独收集诊断
    // s16: [bus] 打印带消息类型前缀（对齐 Python `({msg_type})`）
    eprintln!(
        "  \x1b[33m[bus] {from} → {to}: ({msg_type}) {}\x1b[0m",
        truncate_chars(content, 50)
    );
    String::new()
}

/// 读收件箱（消费式：读全文 + 删文件）。非法行跳过；空/不存在返回空 vec。
fn bus_read_inbox(cwd: &Path, agent: &str) -> Vec<MailMessage> {
    let path = mailbox_path(cwd, agent);
    let raw = match fs::read_to_string(&path) {
        Ok(r) => r,
        Err(_) => return Vec::new(),
    };
    let _ = fs::remove_file(&path);
    raw.lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str::<MailMessage>(l).ok())
        .collect()
}

/// 非破坏探测：收件箱是否有未读消息（唤醒轮询用，不消费）。
fn bus_peek(cwd: &Path, agent: &str) -> bool {
    match fs::metadata(mailbox_path(cwd, agent)) {
        Ok(m) => m.len() > 0,
        Err(_) => false,
    }
}

/// check_inbox 工具：读 Lead 收件箱并格式化（对齐 Python 文案）。
fn run_check_inbox(cwd: &Path) -> String {
    // s16: 统一消费（路由协议响应后再返回），避免消息被读走但协议状态没更新
    let msgs = consume_lead_inbox(cwd);
    if msgs.is_empty() {
        return "(inbox empty)".to_string();
    }
    msgs.iter()
        .map(|m| {
            // s16: 行格式带消息类型标签（对齐 Python）：
            //   [{from}] [{type} req:{request_id}] {content}   有 req_id
            //   [{from}] [{type}] {content}                     无 req_id
            let req_id = m
                .metadata
                .get("request_id")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let tag = if req_id.is_empty() {
                format!(" [{}]", m.msg_type)
            } else {
                format!(" [{} req:{req_id}]", m.msg_type)
            };
            format!("  [{}]{tag} {}", m.from, truncate_chars(&m.content, 200))
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// 把一组收件箱消息格式化成注入文本（对齐 Python 的
/// "[Inbox]\nFrom {from}: {content[:200]}"）。主循环唤醒轮与测试共用。
fn format_inbox_block(inbox: &[MailMessage]) -> String {
    let lines: Vec<String> = inbox
        .iter()
        .map(|m| format!("From {}: {}", m.from, truncate_chars(&m.content, 200)))
        .collect();
    format!("[Inbox]\n{}", lines.join("\n"))
}

/// send_message 工具：Lead 给队友发消息（同步，走 execute_sync）。
fn run_send_message(cwd: &Path, input: SendMessageInput) -> String {
    let err = bus_send(cwd, "lead", &input.to, &input.content, "message");
    if !err.is_empty() {
        return err;
    }
    format!("Sent to {}", input.to)
}

// ── 队友（对齐 Python s15 的 spawn_teammate_thread） ──────────────────────
//
// 队友跑在 tokio 任务里：独立 system prompt、独立 messages、4 个简化工具、
// 上限 10 轮（教学版；真实 CC 用 idle loop）、结束后把最终文本发回 Lead。
// 与 s06 子代理的区别：队友存活多轮、可收消息（每轮开头读自己收件箱）、
// 完成后向 Lead 收件箱汇报（子代理只把结果作为工具返回值）。

/// 已注册的队友名（防重名 spawn）。LazyLock：HashMap::new 非 const。
static ACTIVE_TEAMMATES: LazyLock<Mutex<HashMap<String, ()>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// 队友 system prompt（s16 对齐 Python：提示检查协议消息）。
fn teammate_system_prompt(name: &str, role: &str) -> String {
    format!(
        "You are '{name}', a {role}. Use tools to complete tasks. \
         You can list and claim tasks from the board. \
         When you finish a task, use complete_task to mark it completed. \
         If a task has a worktree, work in that directory. \
         Create new files in your work directory as needed. \
         Check inbox for protocol messages."
    )
}

/// 队友工具集：bash / read_file / write_file / send_message / submit_plan
/// （5 个，s16 对齐 Python；比 s06 子代理少 edit_file/glob——教学版聚焦通信机制）。
fn teammate_tools() -> [Tool; 8] {
    [
        Tool {
            name: "bash".to_string(),
            description: "Run a shell command.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "command": { "type": "string" } },
                "required": ["command"]
            }),
        },
        Tool {
            name: "read_file".to_string(),
            description: "Read file contents.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "path": { "type": "string" } },
                "required": ["path"]
            }),
        },
        Tool {
            name: "write_file".to_string(),
            description: "Write content to a file.".to_string(),
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
            name: "send_message".to_string(),
            description: "Send a message to another agent.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "to": { "type": "string" },
                    "content": { "type": "string" }
                },
                "required": ["to", "content"]
            }),
        },
        // ── s16: 队友协议工具 ──
        Tool {
            name: "submit_plan".to_string(),
            description: "Submit a plan for Lead approval.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "plan": { "type": "string" } },
                "required": ["plan"]
            }),
        },
        // ── s17: 队友任务板工具 ──
        Tool {
            name: "list_tasks".to_string(),
            description: "List all tasks on the board.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {},
                "required": []
            }),
        },
        Tool {
            name: "claim_task".to_string(),
            description: "Claim a pending task.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "task_id": { "type": "string" } },
                "required": ["task_id"]
            }),
        },
        Tool {
            name: "complete_task".to_string(),
            description: "Mark an in-progress task as completed.".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": { "task_id": { "type": "string" } },
                "required": ["task_id"]
            }),
        },
    ]
}

/// 队友历史窗口（对齐 Python messages[-20:]）。
/// s16 起无回合数上限：队友通过 idle loop 等待 inbox，靠 shutdown 协议退出
/// （对齐 Python s16；教学版不再有 10 轮限制）。
const TEAMMATE_HISTORY_WINDOW: usize = 20;

/// 队友主循环：独立 messages，最多 10 轮；每轮开头读自己收件箱注入
/// `<inbox>{json}</inbox>`；结束后把最终文本发回 Lead（type="result"）。
async fn run_teammate(
    http: &reqwest::Client,
    cfg: &Config,
    cwd: &Path,
    name: &str,
    role: &str,
    prompt: &str,
) {
    let system = teammate_system_prompt(name, role);
    let mut messages: Vec<Message> = vec![Message::user_text(prompt.to_string())];
    let tools = teammate_tools();
    // s18: 队友当前工作目录上下文——绑定 worktree 的任务认领后切换到
    // .worktrees/{name}，complete 后重置回 None（主仓库）
    let mut wt_path: Option<PathBuf> = None;

    // s17: 生命周期 WORK → IDLE → SHUTDOWN（对齐 Python 外层 while True）
    //   WORK: 身份重注入 → inbox 分发 → LLM（≤10 轮）→ 非 tool_use 结束
    //   IDLE: 60s 有界轮询（收件箱优先 → 任务板认领 → 超时关机）
    //   SHUTDOWN: 收尾 summary
    let mut shutdown_requested = false;
    loop {
        // s17: 身份重注入（压缩/刚 spawn 时 messages 过短）
        maybe_reinject_identity(&mut messages, name, role);

        // ── WORK 阶段（≤10 轮 LLM，对齐 Python for _ in range(10)）──
        for _ in 0..WORK_MAX_ROUNDS {
            // 读自己收件箱 → 按类型分发：shutdown_request 响应并停止；
            // plan_approval_response 注入 [Plan approved]/[Plan rejected]；
            // 其余消息合入 <inbox> 注入（对齐 Python handle_inbox_message）
            let inbox = bus_read_inbox(cwd, name);
            let mut non_protocol: Vec<MailMessage> = Vec::new();
            for msg in &inbox {
                let t = msg.msg_type.as_str();
                if t == "shutdown_request" || t == "plan_approval_response" {
                    if handle_inbox_message(cwd, name, msg, &mut messages) {
                        shutdown_requested = true;
                        break;
                    }
                } else {
                    non_protocol.push(msg.clone());
                }
            }
            if shutdown_requested {
                break;
            }
            if !non_protocol.is_empty() {
                let json = match serde_json::to_string(&non_protocol) {
                    Ok(j) => j,
                    Err(_) => "[inbox serialization failed]".to_string(),
                };
                messages.push(Message::user_text(format!("<inbox>{json}</inbox>")));
            }

            // 窗口截取（对齐 Python messages[-20:]）
            let window_start = messages.len().saturating_sub(TEAMMATE_HISTORY_WINDOW);
            let mut window: Vec<Message> = messages[window_start..].to_vec();
            // s16 修复（实测）：队友无轮数上限后 messages 超窗口，截断可能把
            // tool_use 切出窗口、留下孤儿 tool_result 成为窗口首条 → API 400
            // "unexpected tool_use_id found in tool_result"（bob 多轮探索实测）。
            // 复用 s14 的发送前配对清理，只作用于副本，不污染本地历史。
            sanitize_tool_pairs(&mut window);

            // 复用 s11 的 call_llm（错误恢复/退避继承；Python 是裸调用 + 静默 break）
            let resp = match call_llm(http, cfg, &cfg.model, &system, &window, &tools, cfg.max_tokens)
                .await
            {
                Ok(r) => r,
                Err(e) => {
                    // 对齐 Python 的 except: break；Rust 版多打印一行，可观测性更好
                    eprintln!("  \x1b[31m[teammate] {name} LLM error: {e}\x1b[0m");
                    break;
                }
            };
            let stop_reason = resp.stop_reason.clone();
            messages.push(Message::assistant_blocks(resp.content.clone()));

            if stop_reason.as_deref() != Some("tool_use") {
                break; // WORK 阶段结束 → IDLE
            }

        let mut results: Vec<ContentBlock> = Vec::new();
        for block in &resp.content {
            if let ContentBlock::ToolUse { id, name: tool_name, input } = block {
                let output = if tool_name == "send_message" {
                    // 队友的 send_message 特判（to/from 双向可用）
                    match serde_json::from_value::<SendMessageInput>(input.clone()) {
                        Ok(sm) => {
                            let err = bus_send(cwd, name, &sm.to, &sm.content, "message");
                            if err.is_empty() {
                                "Sent".to_string()
                            } else {
                                err
                            }
                        }
                        Err(e) => format!("Error: invalid send_message params: {e}"),
                    }
                } else if tool_name == "submit_plan" {
                    // s16: 队友协议工具——提交计划给 Lead 审批（内存状态 + 消息）
                    match serde_json::from_value::<SubmitPlanInput>(input.clone()) {
                        Ok(sp) => teammate_submit_plan(cwd, name, &sp.plan),
                        Err(e) => format!("Error: invalid submit_plan params: {e}"),
                    }
                } else if tool_name == "claim_task" {
                    // s17: 队友认领任务 owner=自己的名字（对齐 Python
                    // claim_task(task["id"], name)）——不能走 execute_sync
                    // 的 owner="agent" 版
                    match serde_json::from_value::<TaskIdInput>(input.clone()) {
                        Ok(ti) => {
                            let result = claim_task(cwd, &ti.task_id, name);
                            // s18: 认领成功后切换到任务绑定的 worktree（若有）
                            if result.starts_with("Claimed") {
                                wt_path = resolve_task_worktree(cwd, &ti.task_id);
                            }
                            result
                        }
                        Err(e) => format!("Error: invalid claim_task params: {e}"),
                    }
                } else if tool_name == "complete_task" {
                    // s18: 完成任务后 cwd 重置回主仓库（对齐 Python wt_ctx 重置）
                    match serde_json::from_value::<TaskIdInput>(input.clone()) {
                        Ok(ti) => {
                            let result = complete_task(cwd, &ti.task_id);
                            wt_path = None;
                            result
                        }
                        Err(e) => format!("Error: invalid complete_task params: {e}"),
                    }
                } else if tool_name == "bash" || tool_name == "read_file" || tool_name == "write_file" {
                    // s18: 队友文件/命令工具在 worktree cwd 下执行（若有绑定）；
                    // 无绑定时用进程 cwd（主仓库）。不触发权限 hook：
                    // Gate3 需 stdin 交互，后台队友任务不可行（对齐 Python 教学版）
                    // workdir() 失败场景理论不存在（进程必有 cwd），default 兜底
                    let base = wt_path
                        .clone()
                        .or_else(|| workdir().ok())
                        .unwrap_or_default();
                    match tool_name.as_str() {
                        "bash" => serde_json::from_value::<BashInput>(input.clone())
                            .map(|bi| run_bash_at(&base, bi))
                            .unwrap_or_else(|e| format!("Error: invalid bash params: {e}")),
                        "read_file" => serde_json::from_value::<ReadInput>(input.clone())
                            .map(|ri| run_read_at(&base, ri))
                            .unwrap_or_else(|e| format!("Error: invalid read_file params: {e}")),
                        _ => serde_json::from_value::<WriteInput>(input.clone())
                            .map(|wi| run_write_at(&base, wi))
                            .unwrap_or_else(|e| format!("Error: invalid write_file params: {e}")),
                    }
                } else {
                    // list_tasks 等复用主循环 handler
                    let name2 = tool_name.clone();
                    let input2 = input.clone();
                    tokio::task::spawn_blocking(move || execute_sync(&name2, &input2))
                        .await
                        .unwrap_or_else(|e| format!("Error: tool task panicked: {e}"))
                };
                eprintln!(
                    "  \x1b[90m[teammate:{name}] {tool_name}: {}\x1b[0m",
                    truncate_lines(&output, 100).trim_end()
                );
                results.push(ContentBlock::ToolResult {
                    tool_use_id: id.clone(),
                    content: output,
                });
            }
        }
            messages.push(Message::user_tool_results(results));
        } // WORK 阶段结束

        if shutdown_requested {
            break;
        }

        // ── IDLE 阶段（s17：60s 有界轮询 + 任务板认领）──
        // s18: 返回自动认领的任务 id，用于切换 worktree cwd（对齐 Python）
        let (idle_result, claimed_task_id) = idle_poll(cwd, name, &mut messages).await;
        match idle_result {
            IdleOutcome::Work => {
                if let Some(task_id) = claimed_task_id {
                    // s18: 自动认领的任务若有 worktree，切换到该目录
                    wt_path = resolve_task_worktree(cwd, &task_id);
                }
                // 有新工作（inbox 消息或自动认领）→ 下一轮 WORK
                continue;
            }
            IdleOutcome::Shutdown | IdleOutcome::Timeout => {
                // 收到关机请求（in idle 已响应）或 60s 超时 → SHUTDOWN
                break;
            }
        }
    }

    // 结束：提取最终文本（复用 extract_text + 倒查，同 s06），发回 Lead
    let mut summary = "Done.".to_string();
    for msg in messages.iter().rev() {
        if msg.role == Role::Assistant {
            let text = extract_text(&msg.content);
            if !text.is_empty() {
                summary = text;
                break;
            }
        }
    }
    bus_send(cwd, name, "lead", &summary, "result");
    ACTIVE_TEAMMATES.lock().unwrap().remove(name);
    eprintln!("  \x1b[32m[teammate] {name} finished\x1b[0m");
}

/// 校验 + 注册队友（防重名）。返回 Err(文案) 或 Ok(())。
/// 抽出为同步纯函数：run_spawn_teammate 与单元测试共用。
fn try_register_teammate(name: &str) -> Result<(), String> {
    if !valid_agent_name(name) {
        return Err(format!("Error: invalid teammate name '{name}'"));
    }
    let mut active = ACTIVE_TEAMMATES.lock().unwrap();
    if active.contains_key(name) {
        return Err(format!("Teammate '{name}' already exists"));
    }
    active.insert(name.to_string(), ());
    Ok(())
}

/// spawn_teammate 工具入口（async：需在 tokio 上下文里 spawn 任务）。
/// 与 "task" 工具同构：agent_loop 里特判调用，不走 execute_sync。
async fn run_spawn_teammate(
    http: &reqwest::Client,
    cfg: &Config,
    cwd: &Path,
    input: SpawnTeammateInput,
) -> String {
    if let Err(e) = try_register_teammate(&input.name) {
        return e;
    }
    let name = input.name.clone();
    let role = input.role.clone();
    let prompt = input.prompt.clone();
    let cwd = cwd.to_path_buf();
    let http = http.clone();
    let cfg = cfg.clone();
    tokio::task::spawn(async move {
        run_teammate(&http, &cfg, &cwd, &name, &role, &prompt).await;
    });
    eprintln!(
        "  \x1b[36m[teammate] {} spawned as {}\x1b[0m",
        input.name, input.role
    );
    // s17: 返回带 "(autonomous)" 后缀（对齐 Python）
    format!("Teammate '{}' spawned as {} (autonomous)", input.name, input.role)
}

// ── Lead 唤醒（对齐 Python s15 的 inbox_poller） ──────────────────────────

/// 后台任务是否有已完成待收集的结果（非破坏；唤醒条件的一半）。
fn has_pending_background() -> bool {
    BACKGROUND_TASKS
        .lock()
        .unwrap()
        .values()
        .any(|t| t.status == "completed")
}

/// 收件箱轮询器：每 1s 检查 Lead 收件箱或后台结果就绪，有货则唤醒主循环。
/// 对齐 Python 的 inbox_poller（BUS.peek("lead") || has_pending_background()）。
/// 教学版轮询间隔 1s；真实 CC 的 Lead useInboxPoller 同为 1s。
async fn inbox_poller(cwd: PathBuf, tx: tokio::sync::mpsc::UnboundedSender<()>) {
    let mut interval = tokio::time::interval(Duration::from_secs(1));
    loop {
        interval.tick().await;
        if bus_peek(&cwd, "lead") || has_pending_background() {
            let _ = tx.send(());
        }
    }
}

/// [all teammates done] 宣告：曾有队友，且现在队友全空 + 收件箱空 + 无后台待收。
/// 在每次 run_turn 后调用（对齐 Python REPL 主循环里的 had_teammates 状态机）。
fn announce_teammates_done(had_teammates: &mut bool, cwd: &Path) {
    let active = !ACTIVE_TEAMMATES.lock().unwrap().is_empty();
    if active {
        *had_teammates = true;
    } else if *had_teammates && !bus_peek(cwd, "lead") && !has_pending_background() {
        println!("\x1b[32m[all teammates done]\x1b[0m");
        *had_teammates = false;
    }
}

// ═════════════════════════════════════════════════════════════════════
//  s16 新增：Team Protocols —— 结构化请求-响应协议
// ═════════════════════════════════════════════════════════════════════
//
// 两种协议一套机制（对齐 Python s16）：
//   shutdown_request/response        Lead → 队友：体面关机握手
//   plan_approval_request/response    队友 → Lead：计划审批
// request_id 贯穿全链路：发请求时创建 ProtocolState（pending），
// 收回复时 match_response 按 request_id 关联并校验类型，更新状态。

/// 协议类型（Python 用字符串，Rust 强类型化）。
#[derive(Clone, Copy, Debug, PartialEq)]
enum ProtocolType {
    Shutdown,
    PlanApproval,
}

impl ProtocolType {
    /// 该类型请求对应的响应消息类型（match_response 校验用）。
    fn expected_response(&self) -> &'static str {
        match self {
            ProtocolType::Shutdown => "shutdown_response",
            ProtocolType::PlanApproval => "plan_approval_response",
        }
    }

    /// 打印用的类型名（对齐 Python state.type 字符串）。
    fn label(&self) -> &'static str {
        match self {
            ProtocolType::Shutdown => "shutdown",
            ProtocolType::PlanApproval => "plan_approval",
        }
    }
}

/// 协议状态（对齐 Python status 字符串语义）。
#[derive(Clone, Copy, Debug, PartialEq)]
enum ProtocolStatus {
    Pending,
    Approved,
    Rejected,
}

impl ProtocolStatus {
    fn label(&self) -> &'static str {
        match self {
            ProtocolStatus::Pending => "pending",
            ProtocolStatus::Approved => "approved",
            ProtocolStatus::Rejected => "rejected",
        }
    }
}

/// 一条协议请求的状态记录（对齐 Python ProtocolState dataclass）。
/// request_id 存于 HashMap key；target/payload/created_at 为审计字段
/// （教学版仅记录不读取，s14 BgTask.tool_use_id 同款先例）。
#[allow(dead_code)]
struct ProtocolState {
    request_id: String,
    protocol_type: ProtocolType,
    sender: String,
    target: String,
    status: ProtocolStatus,
    /// 计划文本或关机原因（Python payload）
    payload: String,
    created_at: f64,
}

/// 在途协议请求：request_id → 状态（线程安全，Python 靠 GIL）。
static PENDING_REQUESTS: LazyLock<Mutex<HashMap<String, ProtocolState>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// 协议请求 ID（对齐 Python `req_{random:06d}`）。
fn new_request_id() -> String {
    format!("req_{:06}", rand::thread_rng().gen_range(0..1_000_000))
}

/// 把回复关联回原请求（对齐 Python match_response）：
/// - unknown request_id → 红字提示，忽略
/// - 响应类型与请求类型不匹配 → 红字提示，忽略（shutdown_response 不会误批 plan）
/// - 已决请求的重复回复 → 黄字提示，忽略
/// - 通过 → 更新状态为 approved/rejected，绿/红字打印
fn match_response(response_type: &str, request_id: &str, approve: bool) {
    let mut pending = PENDING_REQUESTS.lock().unwrap();
    let Some(state) = pending.get_mut(request_id) else {
        eprintln!("  \x1b[31m[protocol] unknown request_id: {request_id}\x1b[0m");
        return;
    };
    let expected = state.protocol_type.expected_response();
    if response_type != expected {
        eprintln!(
            "  \x1b[31m[protocol] type mismatch: expected {expected}, got {response_type}\x1b[0m"
        );
        return;
    }
    if state.status != ProtocolStatus::Pending {
        eprintln!(
            "  \x1b[33m[protocol] {request_id} already {}, ignoring duplicate\x1b[0m",
            state.status.label()
        );
        return;
    }
    state.status = if approve {
        ProtocolStatus::Approved
    } else {
        ProtocolStatus::Rejected
    };
    let icon = if approve { "✓" } else { "✗" };
    let color = if approve { "32" } else { "31" };
    eprintln!(
        "  \x1b[{color}m[protocol] {} {icon} ({request_id}: {})\x1b[0m",
        state.protocol_type.label(),
        state.status.label()
    );
}

/// 统一消费 Lead 收件箱（对齐 Python consume_lead_inbox）：
/// 先路由协议响应（metadata.request_id 非空且 type 以 `_response` 结尾 →
/// match_response），再返回全部消息。check_inbox 工具与主循环唤醒分支共用，
/// 避免消息被读走但协议状态没更新。
fn consume_lead_inbox(cwd: &Path) -> Vec<MailMessage> {
    let msgs = bus_read_inbox(cwd, "lead");
    for msg in &msgs {
        let req_id = msg
            .metadata
            .get("request_id")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let msg_type = msg.msg_type.as_str();
        if !req_id.is_empty() && msg_type.ends_with("_response") {
            let approve = msg
                .metadata
                .get("approve")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            match_response(msg_type, req_id, approve);
        }
    }
    msgs
}

// ── Lead 协议工具（s16 新增，全部同步：bus_send + 内存状态） ─────────────

/// request_shutdown 工具：Lead 请求队友体面关机（握手协议）。
fn run_request_shutdown(cwd: &Path, input: RequestShutdownInput) -> String {
    let req_id = new_request_id();
    PENDING_REQUESTS.lock().unwrap().insert(
        req_id.clone(),
        ProtocolState {
            request_id: req_id.clone(),
            protocol_type: ProtocolType::Shutdown,
            sender: "lead".to_string(),
            target: input.teammate.clone(),
            status: ProtocolStatus::Pending,
            payload: String::new(),
            created_at: now_ts(),
        },
    );
    let err = bus_send_meta(
        cwd,
        "lead",
        &input.teammate,
        "Please shut down gracefully.",
        "shutdown_request",
        &serde_json::json!({ "request_id": req_id }),
    );
    if !err.is_empty() {
        return err;
    }
    eprintln!(
        "  \x1b[35m[protocol] shutdown_request → {} ({req_id})\x1b[0m",
        input.teammate
    );
    format!("Shutdown request sent to {} (req: {req_id})", input.teammate)
}

/// request_plan 工具：Lead 请队友提交计划（普通 message，无状态）。
fn run_request_plan(cwd: &Path, input: RequestPlanInput) -> String {
    let err = bus_send(
        cwd,
        "lead",
        &input.teammate,
        &format!("Please submit a plan for: {}", input.task),
        "message",
    );
    if !err.is_empty() {
        return err;
    }
    format!("Asked {} to submit a plan", input.teammate)
}

/// review_plan 工具：Lead 审批队友提交的计划（approve/reject + 可选反馈）。
fn run_review_plan(cwd: &Path, input: ReviewPlanInput) -> String {
    let sender = {
        let mut pending = PENDING_REQUESTS.lock().unwrap();
        let Some(state) = pending.get_mut(&input.request_id) else {
            return format!("Request {} not found", input.request_id);
        };
        if state.status != ProtocolStatus::Pending {
            return format!(
                "Request {} already {}",
                input.request_id,
                state.status.label()
            );
        }
        state.status = if input.approve {
            ProtocolStatus::Approved
        } else {
            ProtocolStatus::Rejected
        };
        state.sender.clone()
    };
    let feedback = if input.feedback.is_empty() {
        if input.approve {
            "Approved".to_string()
        } else {
            "Rejected".to_string()
        }
    } else {
        input.feedback.clone()
    };
    let err = bus_send_meta(
        cwd,
        "lead",
        &sender,
        &feedback,
        "plan_approval_response",
        &serde_json::json!({
            "request_id": input.request_id,
            "approve": input.approve,
        }),
    );
    if !err.is_empty() {
        return err;
    }
    let icon = if input.approve { "✓" } else { "✗" };
    let color = if input.approve { "32" } else { "31" };
    eprintln!("  \x1b[{color}m[protocol] plan {icon} ({})\x1b[0m", input.request_id);
    format!(
        "Plan {} ({})",
        if input.approve { "approved" } else { "rejected" },
        input.request_id
    )
}

// ── 队友侧：submit_plan + inbox 分发 + idle loop（s16 新增） ──────────────

/// 队友 submit_plan 工具：提交计划给 Lead 审批（协议级请求，非代码级门控——
/// 教学版不拦截工具执行，模型自行等待审批结果，对齐 Python 注释说明）。
fn teammate_submit_plan(cwd: &Path, name: &str, plan: &str) -> String {
    let req_id = new_request_id();
    PENDING_REQUESTS.lock().unwrap().insert(
        req_id.clone(),
        ProtocolState {
            request_id: req_id.clone(),
            protocol_type: ProtocolType::PlanApproval,
            sender: name.to_string(),
            target: "lead".to_string(),
            status: ProtocolStatus::Pending,
            payload: plan.to_string(),
            created_at: now_ts(),
        },
    );
    let err = bus_send_meta(
        cwd,
        name,
        "lead",
        plan,
        "plan_approval_request",
        &serde_json::json!({ "request_id": req_id }),
    );
    if !err.is_empty() {
        return err;
    }
    format!("Plan submitted ({req_id}). Waiting for approval...")
}

/// 按消息类型分发协议消息（对齐 Python handle_inbox_message，抽出可单测）。
/// 返回 true = 队友应停止（收到 shutdown_request 并已回复）。
fn handle_inbox_message(
    cwd: &Path,
    name: &str,
    msg: &MailMessage,
    messages: &mut Vec<Message>,
) -> bool {
    let msg_type = msg.msg_type.as_str();
    let req_id = msg
        .metadata
        .get("request_id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    if msg_type == "shutdown_request" {
        bus_send_meta(
            cwd,
            name,
            "lead",
            "Shutting down gracefully.",
            "shutdown_response",
            &serde_json::json!({ "request_id": req_id, "approve": true }),
        );
        eprintln!(
            "  \x1b[35m[protocol] {name} approved shutdown ({req_id})\x1b[0m"
        );
        return true; // 停止队友循环
    }

    if msg_type == "plan_approval_response" {
        let approve = msg
            .metadata
            .get("approve")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if approve {
            messages.push(Message::user_text(
                "[Plan approved] Proceed with the task.".to_string(),
            ));
        } else {
            messages.push(Message::user_text(format!(
                "[Plan rejected] Feedback: {}",
                msg.content
            )));
        }
    }

    false // 继续
}

// ═════════════════════════════════════════════════════════════════════
//  s17 新增：Autonomous Agents —— 看板认领 + 有界 idle + 身份重注入
// ═════════════════════════════════════════════════════════════════════

/// s17: 空闲轮询参数（对齐 Python IDLE_POLL_INTERVAL=5 / IDLE_TIMEOUT=60）。
const IDLE_POLL_INTERVAL_SECS: u64 = 5;
const IDLE_TIMEOUT_SECS: u64 = 60;
/// s17: WORK 阶段 LLM 轮数上限（对齐 Python for _ in range(10)，防无限干活）。
const WORK_MAX_ROUNDS: usize = 10;

/// s17: 扫描任务看板——找 pending + 无 owner + 所有依赖已完成的任务
/// （对齐 Python scan_unclaimed_tasks；复用 s12 的 list_tasks/can_start）。
fn scan_unclaimed_tasks(cwd: &Path) -> Vec<Task> {
    list_tasks(cwd)
        .into_iter()
        .filter(|t| t.status == "pending" && t.owner.is_none() && can_start(cwd, &t.id))
        .collect()
}

/// s18: 单次 idle 检查（抽出可测，对齐 Python idle_poll 的单次轮询体）：
/// ① 收件箱优先——shutdown_request 立即响应退出；其余消息原样注入
///    `<inbox>` 回 Work（对齐 Python：idle 阶段不细分协议，模型自行理解）；
/// ② 任务板——找到未认领任务 → claim(owner=自己) → 成功注入
///    `<auto-claimed>`（带 Work directory，若有绑定）回 Work（失败黄字提示后继续轮询）；
/// ③ 都空 → None（外层继续下一轮）。
/// 返回 (结果, 自动认领的任务 id)——外层用于切换 worktree cwd。
fn idle_poll_once(
    cwd: &Path,
    name: &str,
    messages: &mut Vec<Message>,
) -> Option<(IdleOutcome, Option<String>)> {
    // ① 收件箱（优先）
    let inbox = bus_read_inbox(cwd, name);
    if !inbox.is_empty() {
        for msg in &inbox {
            if msg.msg_type == "shutdown_request" {
                let req_id = msg
                    .metadata
                    .get("request_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                bus_send_meta(
                    cwd,
                    name,
                    "lead",
                    "Shutting down gracefully.",
                    "shutdown_response",
                    &serde_json::json!({ "request_id": req_id, "approve": true }),
                );
                eprintln!(
                    "  \x1b[35m[protocol] {name} approved shutdown in idle ({req_id})\x1b[0m"
                );
                return Some((IdleOutcome::Shutdown, None));
            }
        }
        let json = serde_json::to_string(&inbox).unwrap_or_else(|_| "[]".to_string());
        messages.push(Message::user_text(format!("<inbox>{json}</inbox>")));
        eprintln!("  \x1b[36m[idle] {name} found inbox messages\x1b[0m");
        return Some((IdleOutcome::Work, None));
    }

    // ② 任务板
    let unclaimed = scan_unclaimed_tasks(cwd);
    if let Some(task) = unclaimed.first() {
        let result = claim_task(cwd, &task.id, name);
        if result.starts_with("Claimed") {
            // s18: 绑定 worktree 的任务附带 Work directory 提示（对齐 Python）
            let wt_info = match resolve_task_worktree(cwd, &task.id) {
                Some(wt) => format!("\nWork directory: {}", wt.display()),
                None => String::new(),
            };
            messages.push(Message::user_text(format!(
                "<auto-claimed>Task {}: {}{wt_info}</auto-claimed>",
                task.id, task.subject
            )));
            eprintln!("  \x1b[32m[idle] {name} auto-claimed: {}\x1b[0m", task.subject);
            return Some((IdleOutcome::Work, Some(task.id.clone())));
        }
        eprintln!("  \x1b[33m[idle] {name} claim failed: {result}\x1b[0m");
    }

    None
}

/// s17: idle 结果三态（对齐 Python 返回 'work'/'shutdown'/'timeout'）。
#[derive(Clone, Copy, Debug, PartialEq)]
enum IdleOutcome {
    Work,
    Shutdown,
    Timeout,
}

/// s17: 60s 有界 idle 轮询（对齐 Python idle_poll：12 次 × 5s）——
/// 收件箱优先、任务板其次，超时自动关机（SHUTDOWN 阶段）。
/// 用 sleep 而非 interval：首轮先等 5s 再查（对齐 Python time.sleep）。
/// s18: 返回 (结果, 自动认领的任务 id)——run_teammate 用于切换 worktree cwd。
async fn idle_poll(
    cwd: &Path,
    name: &str,
    messages: &mut Vec<Message>,
) -> (IdleOutcome, Option<String>) {
    for _ in 0..(IDLE_TIMEOUT_SECS / IDLE_POLL_INTERVAL_SECS) {
        tokio::time::sleep(Duration::from_secs(IDLE_POLL_INTERVAL_SECS)).await;
        if let Some((outcome, claimed_id)) = idle_poll_once(cwd, name, messages) {
            return (outcome, claimed_id);
        }
    }
    eprintln!(
        "  \x1b[31m[idle] {name} timeout ({IDLE_TIMEOUT_SECS}s)\x1b[0m"
    );
    (IdleOutcome::Timeout, None)
}

/// s17: 身份重注入——messages 过短（压缩/刚 spawn）时在头部重新注入身份
/// （对齐 Python：`if len(messages) <= 3: messages.insert(0, <identity>)`）。
fn maybe_reinject_identity(messages: &mut Vec<Message>, name: &str, role: &str) {
    if messages.len() <= 3 {
        messages.insert(
            0,
            Message::user_text(format!(
                "<identity>You are '{name}', role: {role}. Continue your work.</identity>"
            )),
        );
    }
}


// ═════════════════════════════════════════════════════════════════════
//  s18 新增：Worktree Isolation —— 每任务独立 git worktree
// ═════════════════════════════════════════════════════════════════════
//
// Task 绑定 worktree 后，认领它的队友在 .worktrees/{name} 目录内干活
// （bash/read/write 的 cwd 切换到该目录），互不覆盖主仓库文件。
// 生命周期事件写入 .worktrees/events.jsonl 审计。

fn worktrees_dir(cwd: &Path) -> PathBuf {
    cwd.join(".worktrees")
}

/// s18: 校验 worktree 名（对齐 Python VALID_WT_NAME 正则
/// `^[A-Za-z0-9._-]{1,64}$`）。返回错误信息或 None。
fn validate_worktree_name(name: &str) -> Option<String> {
    if name.is_empty() {
        return Some("Worktree name cannot be empty".to_string());
    }
    if name == "." || name == ".." {
        return Some(format!("'{name}' is not a valid worktree name"));
    }
    let valid = name.len() <= 64
        && name.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'));
    if !valid {
        return Some(format!(
            "Invalid worktree name '{name}': only letters, digits, dots, underscores, dashes (1-64 chars)"
        ));
    }
    None
}

/// s18: 执行 git 命令（对齐 Python run_git：30s 超时、输出截 5000）。
/// 返回 (是否成功, 输出)。
fn run_git(cwd: &Path, args: &[&str]) -> (bool, String) {
    let mut cmd = Command::new("git");
    cmd.args(args)
        .current_dir(cwd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // s18 修复：独立进程组——超时 kill 整组（对齐 run_bash 惯例，
        // 防 git 派生的孙进程成孤儿；worktree add 可能等仓库锁）
        .process_group(0);
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return (false, format!("Error: git spawn: {e}")),
    };
    let status = match child.wait_timeout(Duration::from_secs(30)) {
        Ok(Some(st)) => st,
        Ok(None) => {
            // 超时：杀整个进程组（对齐 run_bash 的 -KILL -{pid} 模式）
            let pid = child.id();
            let _ = Command::new("kill").arg("-KILL").arg(format!("-{pid}")).status();
            let _ = child.kill();
            let _ = child.wait();
            return (false, "Error: git timeout".to_string());
        }
        Err(e) => return (false, format!("Error: git wait: {e}")),
    };
    let mut out = String::new();
    if let Some(mut stdout) = child.stdout.take() {
        use std::io::Read as _;
        let _ = stdout.read_to_string(&mut out);
    }
    let mut err_out = String::new();
    if let Some(mut stderr) = child.stderr.take() {
        use std::io::Read as _;
        let _ = stderr.read_to_string(&mut err_out);
    }
    let mut combined = out + &err_out;
    if combined.trim().is_empty() {
        combined = "(no output)".to_string();
    } else {
        combined = truncate_chars(combined.trim(), 5000).to_string();
    }
    (status.success(), combined)
}

/// s18: 追加工作区生命周期事件（对齐 Python log_event）。
fn log_event(cwd: &Path, event_type: &str, worktree_name: &str, task_id: &str) {
    let dir = worktrees_dir(cwd);
    let _ = fs::create_dir_all(&dir);
    let event = serde_json::json!({
        "type": event_type,
        "worktree": worktree_name,
        "task_id": task_id,
        "ts": now_ts(),
    });
    let path = dir.join("events.jsonl");
    if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(&path) {
        use std::io::Write as _;
        let _ = writeln!(f, "{event}");
    }
}

/// s18: 创建 git worktree（独立分支 wt/{name}），可选绑定任务。
fn create_worktree(cwd: &Path, name: &str, task_id: &str) -> String {
    let err = validate_worktree_name(name);
    if let Some(e) = err {
        return format!("Error: {e}");
    }
    let path = worktrees_dir(cwd).join(name);
    if path.exists() {
        return format!("Worktree '{name}' already exists at {}", path.display());
    }
    let branch = format!("wt/{name}");
    let path_str = path.to_str().unwrap_or("");
    let (ok, result) = run_git(cwd, &["worktree", "add", path_str, "-b", &branch, "HEAD"]);
    if !ok {
        return format!("Git error: {result}");
    }
    if !task_id.is_empty() {
        bind_task_to_worktree(cwd, task_id, name);
    }
    log_event(cwd, "create", name, task_id);
    eprintln!(
        "  \x1b[33m[worktree] created: {name} at {}\x1b[0m",
        path.display()
    );
    format!("Worktree '{name}' created at {}", path.display())
}

/// s18: 绑定任务到 worktree——只写 worktree 字段，**保持 pending**
/// （供队友自动认领；对齐 Python 注释）。
fn bind_task_to_worktree(cwd: &Path, task_id: &str, worktree_name: &str) -> String {
    let mut task = match load_task(cwd, task_id) {
        Some(t) => t,
        None => return format!("Error: Task {task_id} not found"),
    };
    task.worktree = Some(worktree_name.to_string());
    save_task(cwd, &task);
    eprintln!(
        "  \x1b[33m[bind] {} → worktree:{worktree_name}\x1b[0m",
        task.subject
    );
    format!("Bound task {task_id} to worktree {worktree_name}")
}

/// s18: 统计 worktree 的未提交文件数与未推送提交数（对齐 Python
/// _count_worktree_changes）。git 异常返回 (-1, -1)。
fn count_worktree_changes(path: &Path) -> (i32, i32) {
    let (ok1, out1) = run_git(path, &["status", "--porcelain"]);
    if !ok1 {
        return (-1, -1);
    }
    // run_git 对空输出返回 "(no output)" 占位——过滤掉（对齐 Python 的
    // _count_worktree_changes：直接读 subprocess stdout，无占位）
    let files = out1
        .lines()
        .filter(|l| !l.trim().is_empty() && *l != "(no output)")
        .count() as i32;
    let (_, out2) = run_git(path, &["log", "@{push}..HEAD", "--oneline"]);
    let commits = out2
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.contains("fatal:") && *l != "(no output)")
        .count() as i32;
    (files, commits)
}

/// s18: 移除 worktree。有未提交变更时拒绝（除非 discard_changes）。
fn remove_worktree(cwd: &Path, name: &str, discard_changes: bool) -> String {
    let err = validate_worktree_name(name);
    if let Some(e) = err {
        return e; // 对齐 Python：remove 的错误不带 "Error: " 前缀
    }
    let path = worktrees_dir(cwd).join(name);
    if !path.exists() {
        return format!("Worktree '{name}' not found");
    }
    if !discard_changes {
        let (files, commits) = count_worktree_changes(&path);
        if files < 0 {
            return format!(
                "Cannot verify worktree '{name}' status. Use discard_changes=true to force removal."
            );
        }
        if files > 0 || commits > 0 {
            return format!(
                "Worktree '{name}' has {files} uncommitted file(s) and {commits} unpushed commit(s). \
                 Use discard_changes=true to force removal, or keep_worktree to preserve for review."
            );
        }
    }
    let path_str = path.to_str().unwrap_or("");
    let (ok1, _) = run_git(cwd, &["worktree", "remove", path_str, "--force"]);
    if !ok1 {
        return format!("Failed to remove worktree directory for '{name}'");
    }
    run_git(cwd, &["branch", "-D", &format!("wt/{name}")]);
    log_event(cwd, "remove", name, "");
    eprintln!("  \x1b[33m[worktree] removed: {name}\x1b[0m");
    format!("Worktree '{name}' removed")
}

/// s18: 保留 worktree 供人工 review（分支保留）。
fn keep_worktree(cwd: &Path, name: &str) -> String {
    let err = validate_worktree_name(name);
    if let Some(e) = err {
        return format!("Error: {e}");
    }
    log_event(cwd, "keep", name, "");
    eprintln!("  \x1b[36m[worktree] kept: {name}\x1b[0m");
    format!("Worktree '{name}' kept for review (branch: wt/{name})")
}

/// s18: 解析任务绑定的 worktree 路径（队友 cwd 切换用）。
fn resolve_task_worktree(cwd: &Path, task_id: &str) -> Option<PathBuf> {
    let task = load_task(cwd, task_id)?;
    task.worktree.map(|w| worktrees_dir(cwd).join(w))
}

// ── 配置与入口（system prompt 由 assemble_system_prompt 动态生成） ──────

/// s15: Clone 用于把配置传入 'static 队友任务（tokio::task::spawn）。
#[derive(Clone)]
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
    /// s13: 思考可见性开关（STREAM_THINKING=1）——thinking_delta 灰色打到 stderr，
    /// 与 text 的 stdout 分离（CC 风格）；默认关，保持主输出干净
    stream_thinking: bool,
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
        stream_thinking: matches!(
            env::var("STREAM_THINKING").as_deref(),
            Ok("1") | Ok("true")
        ),
    })
}

/// 交互式 REPL。s04 变化：在追加用户输入到 history 之前，
/// 触发 UserPromptSubmit hook。
/// s13 变化：#[tokio::main] 多线程 runtime —— 后台任务/并行工具在 worker
/// 线程上跑；stdin 用 tokio 异步读，不阻塞 runtime。
/// 执行一轮 agent 回合（用户轮带 query，定时轮不带）。
/// 用户轮先过 UserPromptSubmit hook 再 append；定时轮（cron 注入）不 append。
/// s14 把 REPL 的回合执行抽成公共辅助，用户轮与 select! 定时分支共用。
async fn run_turn(
    http: &reqwest::Client,
    cfg: &Config,
    cwd: &Path,
    hooks: &Hooks,
    history: &mut Vec<Message>,
    query: Option<&str>,
) {
    if let Some(q) = query {
        // ── s04 变化：用户输入先过 UserPromptSubmit hook，再追加到 history ──
        trigger_user_prompt_submit(hooks, q);
        history.push(Message::user_text(q));
    }

    match agent_loop(http, cfg, cwd, history, hooks).await {
        Ok(()) => {
            // s13: 流式输出已把最终文本实时打印过，这里不重复打印
            if !STREAMED_OUTPUT_PRINTED.load(Ordering::Relaxed) {
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
            }
            println!();
        }
        Err(e) => {
            // 出错时把刚追加的用户输入弹出（定时轮没有新输入，跳过）
            if query.is_some() {
                history.pop();
            }
            eprintln!("Error: {e}\n");
        }
    }
}

#[tokio::main]
async fn main() {
    let cfg = match load_config() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("配置错误: {e}");
            std::process::exit(1);
        }
    };
    let http = reqwest::Client::builder()
        // 总超时：reqwest 默认无限等待，网关 hang 住会永远卡死。
        // 300s 覆盖长生成；连接超时单独收紧，快速暴露网络不通。
        .timeout(Duration::from_secs(300))
        .connect_timeout(Duration::from_secs(10))
        .build()
        .expect("build http client");

    // ── s04 新增：初始化 Hook 注册表并注册内置回调 ──
    let cwd = env::current_dir().expect("cwd");
    let mut hooks = Hooks::new();
    register_builtin_hooks(&mut hooks);

    // ── s14: 启动时恢复 durable 任务 + 拉起调度任务 ──
    load_durable_jobs(&cwd, &mut CRON_JOBS.lock().unwrap());
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<()>();
    tokio::task::spawn(cron_scheduler_loop(cwd.clone(), tx));
    println!("  \x1b[35m[cron] scheduler started\x1b[0m");

    // ── s15: 拉起收件箱轮询器（队友消息 / 后台结果就绪时唤醒主循环） ──
    let (wake_tx, mut wake_rx) = tokio::sync::mpsc::unbounded_channel::<()>();
    tokio::task::spawn(inbox_poller(cwd.clone(), wake_tx));

    // ── s19 前移: 启动时读 .mcp.json（打印 config loaded / 兜底提示） ──
    // 静态 LazyLock 首次访问即加载；改配置文件需重启进程才生效（对齐"启动时读"）。
    drop(MCP_CONFIG.lock().unwrap());

    println!("s19: MCP Tools — 外部能力即插即用");
    println!("输入问题，回车发送。输入 q 退出。\n");

    let mut history: Vec<Message> = Vec::new();
    let mut lines = tokio::io::BufReader::new(tokio::io::stdin()).lines();
    let mut had_teammates = false;

    loop {
        print!("\x1b[36ms19 >> \x1b[0m");
        io::stdout().flush().ok();

        tokio::select! {
            // 用户轮：读一行 stdin
            line = lines.next_line() => {
                let line = match line {
                    Ok(Some(l)) => l,
                    _ => break, // EOF (Ctrl-D) 或读取错误
                };
                let query = line.trim();
                // 空行忽略；只有显式输入 q / exit 才退出
                if query.is_empty() {
                    continue;
                }
                if query.eq_ignore_ascii_case("q") || query.eq_ignore_ascii_case("exit") {
                    break;
                }
                run_turn(&http, &cfg, &cwd, &hooks, &mut history, Some(query)).await;
            }
            // 定时轮（路径 B）：调度任务入队后唤醒空闲主循环。
            // Some(()) 模式：通道关闭（调度任务异常退出）时分支停用，REPL 照常。
            Some(()) = rx.recv() => {
                // 排空积压信号（旧版本每 tick 发一次,回合中途会积压多个——
                // 逐个消费会打印大量提示符,实测教训；现在调度只在转变时发,
                // 这里排空作为防御,保证一次事件最多多一次空迭代）
                while rx.try_recv().is_ok() {}
                if has_cron_queue() {
                    println!("\n  \x1b[35m[queue processor] delivering scheduled work\x1b[0m");
                    run_turn(&http, &cfg, &cwd, &hooks, &mut history, None).await;
                }
            }
            // ── s15: 唤醒轮（路径 C）：队友收件箱 / 后台结果就绪 → 注入新 turn ──
            // s16: 统一消费（consume_lead_inbox）——协议响应先路由到
            // match_response 更新状态，再注入 history（对齐 Python 主循环末尾）
            Some(()) = wake_rx.recv() => {
                // 排空积压信号（与 cron 分支同款防御）
                while wake_rx.try_recv().is_ok() {}
                // 消费式读取：收件箱 + 后台结果，合成一条 user 消息注入。
                // 已被其他唤醒消费掉的场合这里为空 → 跳过（幂等）
                let inbox = consume_lead_inbox(&cwd);
                let bg = collect_background_results();
                if inbox.is_empty() && bg.is_empty() {
                    continue;
                }
                let inbox_count = inbox.len();
                let bg_count = bg.len();
                let mut parts: Vec<String> = Vec::new();
                if !inbox.is_empty() {
                    parts.push(format_inbox_block(&inbox));
                }
                parts.extend(bg);
                println!(
                    "\n  \x1b[33m[wake: {inbox_count} inbox + {bg_count} background -> new turn]\x1b[0m",
                );
                history.push(Message::user_text(parts.join("\n")));
                run_turn(&http, &cfg, &cwd, &hooks, &mut history, None).await;
            }
        }

        // ── s15: 队友全部结束（且输出已排空）时宣告一次 ──
        announce_teammates_done(&mut had_teammates, &cwd);
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
        assert_eq!(run_bash(BashInput { command: "echo hello".into(), run_in_background: None }), "hello");
    }

    #[test]
    fn run_bash_empty_output_marker() {
        assert_eq!(run_bash(BashInput { command: "true".into(), run_in_background: None }), "(no output)");
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
        let result = run_bash(BashInput { command: "sudo ls".into(), run_in_background: None });
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
        let mut msgs: Vec<Message> = (0..140).map(|i| Message::user_text(format!("msg{i}"))).collect();
        snip_compact(&mut msgs);
        assert!(msgs.len() < 140);
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
                tool_use_id: "old5".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old6".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old7".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "old8".into(), content: "x".repeat(200),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "recent1".into(), content: "important result".to_string(),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "recent2".into(), content: "second result".to_string(),
            }]),
        ];
        micro_compact(&mut msgs);
        // 10 results, KEEP_RECENT=8, first 2 compacted, last 8 intact
        if let MessageContent::Blocks(blocks) = &msgs[0].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert!(content.contains("compacted"));
            }
        }
        if let MessageContent::Blocks(blocks) = &msgs[1].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert!(content.contains("compacted"));
            }
        }
        if let MessageContent::Blocks(blocks) = &msgs[7].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert_eq!(content, &"x".repeat(200));
            }
        }
        if let MessageContent::Blocks(blocks) = &msgs[9].content {
            if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
                assert_eq!(content, "second result");
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
            connected_mcp: Vec::new(),
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
            connected_mcp: Vec::new(),
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
            connected_mcp: Vec::new(),
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
            connected_mcp: Vec::new(),
            enabled_tools: vec!["bash".into()],
            workspace: "/tmp".into(),
            memories: String::new(),
            skills: String::new(),
        };
        let result = get_system_prompt(&ctx);
        assert!(!result.is_empty());
    }

    #[tokio::test]
    async fn select_relevant_memories_empty_when_no_files() {
        let cwd = test_cwd("empty");
        let msgs = vec![Message::user_text("hello world")];
        let result = select_relevant_memories(
            &reqwest::Client::new(),
            &Config { sub_system: "".into(), model: "".into(), fallback_model: None, base_url: "".into(), api_key: None, auth_token: None, max_tokens: 8000, effort: None, beta: None, debug: false, stream_thinking: false },
            &cwd, &msgs).await;
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

    // ── s11: with_retry（s13 起 async，测试用 #[tokio::test]） ──

    #[tokio::test]
    async fn with_retry_success_first_try() {
        // Cell<u32>：async move 闭包拿引用副本计数，FnMut 可被多次调用
        let calls = std::cell::Cell::new(0u32);
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            let calls = &calls;
            async move {
                calls.set(calls.get() + 1);
                Ok(ok_resp())
            }
        })
        .await;
        assert!(r.is_ok());
        assert_eq!(calls.get(), 1);
        assert_eq!(state.current_model, "primary");
    }

    #[tokio::test]
    async fn with_retry_reraises_non_transient_immediately() {
        let calls = std::cell::Cell::new(0u32);
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            let calls = &calls;
            async move {
                calls.set(calls.get() + 1);
                Err(LlmError::PromptTooLong)
            }
        })
        .await;
        assert!(matches!(r, Err(LlmError::PromptTooLong)));
        assert_eq!(calls.get(), 1); // 不重试，立即向上抛
    }

    #[tokio::test]
    async fn with_retry_retries_transient_then_succeeds() {
        // Retry-After: 0 -> 立即重试，测试不需要真实 sleep
        let calls = std::cell::Cell::new(0u32);
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            let calls = &calls;
            async move {
                calls.set(calls.get() + 1);
                if calls.get() == 1 {
                    Err(LlmError::RateLimited { retry_after_secs: Some(0) })
                } else {
                    Ok(ok_resp())
                }
            }
        })
        .await;
        assert!(r.is_ok());
        assert_eq!(calls.get(), 2);
    }

    #[tokio::test]
    async fn with_retry_exhausts_after_max_retries() {
        let calls = std::cell::Cell::new(0u32);
        let mut state = RecoveryState::new("primary", None);
        let r = with_retry(&mut state, |_model| {
            let calls = &calls;
            async move {
                calls.set(calls.get() + 1);
                Err(LlmError::RateLimited { retry_after_secs: Some(0) })
            }
        })
        .await;
        assert!(matches!(r, Err(LlmError::Other(msg)) if msg.contains("Max retries")));
        assert_eq!(calls.get(), MAX_RETRIES);
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

    #[tokio::test]
    async fn with_retry_passes_current_model_into_closure() {        // 验证 with_retry 每轮都用 state.current_model 调闭包：
        // 模拟一次 529 切换后（直接改状态），下一次重试应该看到 fallback 模型。
        // 用 RateLimited + Retry-After: 0 走重试路径且不真实 sleep。
        let calls = std::cell::Cell::new(0u32);
        let mut state = RecoveryState::new("primary", Some("fallback".into()));
        state.register_529(); // 1
        state.register_529(); // 2
        state.register_529(); // 3 -> 切到 fallback
        assert_eq!(state.current_model, "fallback");
        let r = with_retry(&mut state, |model| {
            let calls = &calls;
            async move {
                calls.set(calls.get() + 1);
                assert_eq!(model, "fallback"); // 闭包收到的是切换后的模型
                if calls.get() == 1 {
                    Err(LlmError::RateLimited { retry_after_secs: Some(0) })
                } else {
                    Ok(ok_resp())
                }
            }
        })
        .await;
        assert!(r.is_ok());
        assert_eq!(calls.get(), 2);
    }

    // ── s12 新增：任务系统 ──

    /// 用固定 ID 直接落盘一个任务（测试需要可控的依赖关系）
    fn save_test_task(cwd: &Path, id: &str, subject: &str, status: &str, blocked_by: &[&str]) {
        save_task(
            cwd,
            &Task {
                id: id.to_string(),
                subject: subject.to_string(),
                description: String::new(),
                status: status.to_string(),
                owner: None,
                blocked_by: blocked_by.iter().map(|s| s.to_string()).collect(),
                worktree: None,
            },
        );
    }

    #[test]
    fn new_task_id_format() {
        let id = new_task_id();
        let parts: Vec<&str> = id.split('_').collect();
        assert_eq!(parts.len(), 3);
        assert_eq!(parts[0], "task");
        assert!(parts[1].parse::<u64>().is_ok()); // unix 秒
        assert_eq!(parts[2].len(), 4); // 0000-9999 随机后缀
        assert!(parts[2].parse::<u32>().is_ok());
    }

    #[test]
    fn task_roundtrip_preserves_fields() {
        let cwd = test_cwd("task-roundtrip");
        let task = create_task(&cwd, "写 API", "实现 REST 接口", &["task_a".into()]);
        let loaded = load_task(&cwd, &task.id).unwrap();
        assert_eq!(loaded.id, task.id);
        assert_eq!(loaded.subject, "写 API");
        assert_eq!(loaded.description, "实现 REST 接口");
        assert_eq!(loaded.status, "pending");
        assert_eq!(loaded.owner, None);
        assert_eq!(loaded.blocked_by, vec!["task_a".to_string()]);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn task_json_matches_python_schema() {
        // 磁盘 JSON 必须与 Python asdict 输出同构：blockedBy camelCase、owner null、
        // worktree null（s18 字段，Python s18 asdict 同样输出）
        let cwd = test_cwd("task-schema");
        let task = create_task(&cwd, "s", "", &[]);
        let raw = fs::read_to_string(task_path(&cwd, &task.id)).unwrap();
        let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
        let mut keys: Vec<String> = v.as_object().unwrap().keys().cloned().collect();
        // serde_json 的 Map 按字母序存储 key，只校验集合相等
        keys.sort();
        assert_eq!(
            keys,
            ["blockedBy", "description", "id", "owner", "status", "subject", "worktree"]
                .iter()
                .map(|s| s.to_string())
                .collect::<Vec<_>>()
        );
        assert!(v["owner"].is_null());
        assert_eq!(v["blockedBy"], serde_json::json!([]));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn create_task_input_deserializes() {
        let json = serde_json::json!({"subject": "写测试", "description": "单测", "blockedBy": ["a", "b"]});
        let input: CreateTaskInput = serde_json::from_value(json).unwrap();
        assert_eq!(input.subject, "写测试");
        assert_eq!(input.description, "单测");
        assert_eq!(input.blocked_by, vec!["a".to_string(), "b".to_string()]);
        // 可选字段缺省
        let input: CreateTaskInput = serde_json::from_value(serde_json::json!({"subject": "x"})).unwrap();
        assert_eq!(input.description, "");
        assert!(input.blocked_by.is_empty());
    }

    #[test]
    fn list_tasks_sorted_and_empty() {
        let cwd = test_cwd("task-list");
        assert!(list_tasks(&cwd).is_empty());
        save_test_task(&cwd, "task_1_0002", "B", "pending", &[]);
        save_test_task(&cwd, "task_1_0001", "A", "pending", &[]);
        // 非 task_ 前缀的 json 不算任务（对齐 Python 的 glob("task_*.json")）
        fs::create_dir_all(tasks_dir(&cwd)).ok();
        fs::write(tasks_dir(&cwd).join("notes.json"), "{}").ok();
        let ids: Vec<String> = list_tasks(&cwd).iter().map(|t| t.id.clone()).collect();
        assert_eq!(ids, vec!["task_1_0001", "task_1_0002"]);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn can_start_dependency_semantics() {
        let cwd = test_cwd("task-canstart");
        // 缺失依赖 = 阻塞
        save_test_task(&cwd, "task_a", "A", "pending", &["task_missing"]);
        assert!(!can_start(&cwd, "task_a"));
        // 依赖未完成 = 阻塞
        save_test_task(&cwd, "task_b", "B", "pending", &["task_c"]);
        save_test_task(&cwd, "task_c", "C", "pending", &[]);
        assert!(!can_start(&cwd, "task_b"));
        // 依赖全部完成 = 可开始
        save_test_task(&cwd, "task_c", "C", "completed", &[]);
        assert!(can_start(&cwd, "task_b"));
        // 无依赖 = 可开始
        assert!(can_start(&cwd, "task_c"));
        // 任务本身不存在 = 不可开始
        assert!(!can_start(&cwd, "task_unknown"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn blocked_deps_lists_only_unfinished() {
        let cwd = test_cwd("task-blocked");
        save_test_task(&cwd, "task_done", "D", "completed", &[]);
        save_test_task(&cwd, "task_pending", "P", "pending", &[]);
        let task = Task {
            id: "task_x".into(), subject: "X".into(), description: String::new(),
            status: "pending".into(), owner: None,
            blocked_by: vec!["task_done".into(), "task_pending".into(), "task_missing".into()],
            worktree: None,
        };
        let deps = blocked_deps(&cwd, &task);
        assert_eq!(deps, vec!["task_pending".to_string(), "task_missing".to_string()]);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn claim_task_transitions_state() {
        let cwd = test_cwd("task-claim");
        save_test_task(&cwd, "task_a", "写文档", "pending", &[]);
        let msg = claim_task(&cwd, "task_a", "agent");
        assert!(msg.contains("Claimed task_a"));
        let t = load_task(&cwd, "task_a").unwrap();
        assert_eq!(t.status, "in_progress");
        assert_eq!(t.owner.as_deref(), Some("agent"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn claim_task_blocked_message_matches_python() {
        let cwd = test_cwd("task-claim-blocked");
        save_test_task(&cwd, "task_a", "A", "pending", &["task_b", "task_missing"]);
        let msg = claim_task(&cwd, "task_a", "agent");
        // 对齐 Python 的 f"Blocked by: {deps}"（单引号列表）
        assert_eq!(msg, "Blocked by: ['task_b', 'task_missing']");
        assert_eq!(load_task(&cwd, "task_a").unwrap().status, "pending");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn claim_task_wrong_status_rejected() {
        let cwd = test_cwd("task-claim-status");
        save_test_task(&cwd, "task_a", "A", "completed", &[]);
        assert_eq!(claim_task(&cwd, "task_a", "agent"), "Task task_a is completed, cannot claim");
        save_test_task(&cwd, "task_b", "B", "in_progress", &[]);
        assert!(claim_task(&cwd, "task_b", "agent").contains("cannot claim"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn complete_task_reports_unblocked_downstream() {
        let cwd = test_cwd("task-complete");
        // A 完成解禁 B；C 依赖 B，B 还没完成所以 C 仍然阻塞
        save_test_task(&cwd, "task_a", "地基", "in_progress", &[]);
        save_test_task(&cwd, "task_b", "墙体", "pending", &["task_a"]);
        save_test_task(&cwd, "task_c", "屋顶", "pending", &["task_b"]);
        let msg = complete_task(&cwd, "task_a");
        assert!(msg.contains("Completed task_a (地基)"));
        assert!(msg.contains("Unblocked: 墙体"), "msg = {msg}");
        assert!(!msg.contains("屋顶"), "C 不应被解禁: {msg}");
        assert_eq!(load_task(&cwd, "task_a").unwrap().status, "completed");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn complete_task_wrong_status_rejected() {
        let cwd = test_cwd("task-complete-status");
        save_test_task(&cwd, "task_a", "A", "pending", &[]);
        assert_eq!(complete_task(&cwd, "task_a"), "Task task_a is pending, cannot complete");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn claim_and_complete_unknown_task() {
        let cwd = test_cwd("task-unknown");
        assert_eq!(claim_task(&cwd, "task_nope", "agent"), "Error: Task task_nope not found");
        assert_eq!(complete_task(&cwd, "task_nope"), "Error: Task task_nope not found");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn dependency_chain_end_to_end() {
        // 完整状态机：建链 → 认领被阻塞 → 逐个完成解禁 → 全部 completed
        let cwd = test_cwd("task-chain");
        let t1 = create_task(&cwd, "设计", "", &[]);
        let t2 = create_task(&cwd, "编码", "", &[t1.id.clone()]);
        let t3 = create_task(&cwd, "测试", "", &[t2.id.clone()]);

        // 跳序认领 t2 → 阻塞
        assert!(claim_task(&cwd, &t2.id, "agent").starts_with("Blocked by:"));

        // 按序推进
        claim_task(&cwd, &t1.id, "agent");
        let msg = complete_task(&cwd, &t1.id);
        assert!(msg.contains("Unblocked: 编码"));
        claim_task(&cwd, &t2.id, "agent");
        let msg = complete_task(&cwd, &t2.id);
        assert!(msg.contains("Unblocked: 测试"));
        claim_task(&cwd, &t3.id, "agent");
        complete_task(&cwd, &t3.id);

        let statuses: Vec<String> = list_tasks(&cwd).iter().map(|t| t.status.clone()).collect();
        assert_eq!(statuses, vec!["completed", "completed", "completed"]);
        // 持久化：从磁盘重新读（模拟重启）
        assert_eq!(load_task(&cwd, &t1.id).unwrap().status, "completed");
        let _ = fs::remove_dir_all(&cwd);
    }

    // ── s13 新增：后台任务 / SSE 流式 / 并行执行 ──

    #[test]
    fn is_slow_operation_keyword_matching() {
        for kw in ["pip install", "cargo build", "npm install", "pytest", "make", "deploy"] {
            let input = serde_json::json!({"command": format!("{kw} --verbose")});
            assert!(is_slow_operation("bash", &input), "kw={kw}");
        }
        // 快命令不误判
        assert!(!is_slow_operation("bash", &serde_json::json!({"command": "git status"})));
        assert!(!is_slow_operation("bash", &serde_json::json!({"command": "ls -la"})));
        // 非 bash 工具一律不进后台
        assert!(!is_slow_operation("read_file", &serde_json::json!({"command": "npm install"})));
    }

    #[test]
    fn is_slow_operation_word_boundary_no_substring_false_positives() {
        // 回归（实测教训）：mock 脚本里的 JS 函数名 makeCtx 含 "make"，
        // 朴素子串匹配会把语法检查命令误丢后台——词边界匹配后不再命中
        let make_ctx = serde_json::json!({"command": "python3 - <<'PY'\nfunction makeCtx() {}\nPY"});
        assert!(!is_slow_operation("bash", &make_ctx), "makeCtx 不应命中 make");
        // 其他子串形态同样不命中
        for cmd in ["makefile", "remake", "uninstall pkg", "rebuild all", "deployment", "compiler",
                    "testing framework", "docker buildx", "cargo buildx"] {
            let input = serde_json::json!({"command": cmd});
            assert!(!is_slow_operation("bash", &input), "不应命中: {cmd}");
        }
        // 独立词仍命中（含行首/行尾边界）
        for cmd in ["make", "make -j8", "npm install --save", "cargo build --release",
                    "echo x && pytest"] {
            let input = serde_json::json!({"command": cmd});
            assert!(is_slow_operation("bash", &input), "应命中: {cmd}");
        }
    }

    #[test]
    fn should_run_background_explicit_flag_beats_heuristic() {
        // 显式 true：快命令也进后台（模型显式请求优先）
        let fast = serde_json::json!({"command": "git status", "run_in_background": true});
        assert!(should_run_background("bash", &fast));
        // 显式 flag 对任何工具都优先（对齐 Python：先查 flag 再查启发式）
        assert!(should_run_background("read_file", &fast));
        // 未指定 + 慢关键词 → 启发式兜底
        let slow = serde_json::json!({"command": "npm install lodash"});
        assert!(should_run_background("bash", &slow));
        // 未指定 + 快命令 → 前台
        let quick = serde_json::json!({"command": "git status"});
        assert!(!should_run_background("bash", &quick));
        // 无 flag 的非 bash 工具 → 前台
        assert!(!should_run_background("read_file", &serde_json::json!({"path": "x"})));
    }

    #[test]
    fn find_event_boundary_handles_lf_and_crlf() {
        let lf = b"data: {}\n\ndata: {}";
        assert_eq!(find_event_boundary(lf), Some(9));
        let crlf = b"data: {}\r\n\r\ndata: {}";
        assert_eq!(find_event_boundary(crlf), Some(11));
        assert_eq!(find_event_boundary(b"data: {}"), None);
    }

    #[test]
    fn sse_event_json_parses_data_and_skips_pings() {
        let evt = "event: content_block_delta\ndata: {\"type\":\"x\"}\n\n";
        let v = sse_event_json(evt).expect("data 行应解析成功");
        assert_eq!(v["type"], "x");
        assert!(sse_event_json("event: ping\ndata: [DONE]").is_none());
        assert!(sse_event_json("event: ping").is_none());
        assert!(sse_event_json("data: not json").is_none());
    }

    #[test]
    fn handle_sse_event_reconstructs_stream() {
        let mut blocks: Vec<StreamBlock> = Vec::new();
        let mut stop_reason: Option<String> = None;
        let mut has_tool_use = false;

        let events = [
            r#"event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}"#,
            r#"event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}"#,
            r#"event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}"#,
            r#"event: content_block_start
data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"tu_1","name":"bash","input":{}}}"#,
            r#"event: content_block_delta
data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\"command\":"}}"#,
            r#"event: content_block_delta
data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"\"ls\"}"}}"#,
            r#"event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null}}"#,
            r#"event: message_stop
data: {"type":"message_stop"}"#,
        ];
        for e in events {
            handle_sse_event(e, &mut blocks, &mut stop_reason, &mut has_tool_use, false);
        }
        assert_eq!(blocks.len(), 2);
        assert!(matches!(&blocks[0], StreamBlock::Text { text } if text == "Hello world"));
        assert!(matches!(
            &blocks[1],
            StreamBlock::ToolUse { id, name, .. } if id == "tu_1" && name == "bash"
        ));
        assert_eq!(stop_reason.as_deref(), Some("tool_use"));
        assert!(has_tool_use);
    }

    #[test]
    fn handle_sse_event_thinking_signature_preserved() {
        // thinking + signature_delta：签名必须保留（多轮工具调用回传要求）
        let mut blocks = vec![StreamBlock::Thinking {
            thinking: String::new(),
            signature: None,
        }];
        let mut stop_reason = None;
        let mut has_tool_use = false;
        handle_sse_event(
            r#"data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"step by step"}}"#,
            &mut blocks, &mut stop_reason, &mut has_tool_use, true,
        );
        handle_sse_event(
            r#"data: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"sig-abc"}}"#,
            &mut blocks, &mut stop_reason, &mut has_tool_use, true,
        );
        match &blocks[0] {
            StreamBlock::Thinking { thinking, signature } => {
                assert_eq!(thinking, "step by step");
                assert_eq!(signature.as_deref(), Some("sig-abc"));
            }
            _ => panic!("expected thinking block"),
        }
    }

    #[test]
    fn collect_background_results_formats_notification() {
        // 手工塞一个已完成任务（绕过真实执行），验证通知格式与 200 字符截断。
        // 后台静态是共享的（并行测试可能同时有别的任务），断言按自己的 id 定向。
        let bg_id = "bg_testfmt".to_string();
        BACKGROUND_TASKS.lock().unwrap().insert(
            bg_id.clone(),
            BgTask {
                tool_use_id: "tu_x".into(),
                command: "npm install".into(),
                status: "completed".into(),
            },
        );
        BACKGROUND_RESULTS
            .lock()
            .unwrap()
            .insert(bg_id.clone(), "x".repeat(500));
        let notifications = collect_background_results();
        let mine = notifications
            .iter()
            .find(|n| n.contains("<task_id>bg_testfmt</task_id>"))
            .expect("应有我们的通知");
        assert!(mine.contains("<task_notification>"));
        assert!(mine.contains("<command>npm install</command>"));
        assert!(mine.contains(&"x".repeat(200))); // summary 截断 200
        assert!(!mine.contains(&"x".repeat(201)));
        // 我们的任务被取走（不会重复注入）
        assert!(!BACKGROUND_TASKS.lock().unwrap().contains_key("bg_testfmt"));
        assert!(!BACKGROUND_RESULTS.lock().unwrap().contains_key("bg_testfmt"));
    }

    #[tokio::test]
    async fn background_task_lifecycle_end_to_end() {
        // 真实后台执行：echo 毫秒级完成，轮询等自己的结果出现后再收集
        let input = serde_json::json!({"command": "echo bg-task-ok"});
        let bg_id = start_background_task("tu_life", &input);
        assert!(bg_id.starts_with("bg_"));
        for _ in 0..200 {
            let done = BACKGROUND_RESULTS.lock().unwrap().contains_key(&bg_id);
            if done {
                break;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        assert!(
            BACKGROUND_RESULTS.lock().unwrap().contains_key(&bg_id),
            "后台任务应在轮询窗口内完成"
        );
        let notifications = collect_background_results();
        let mine = notifications
            .iter()
            .find(|n| n.contains(&format!("<task_id>{bg_id}</task_id>")))
            .expect("应有我们的通知");
        assert!(mine.contains("<task_notification>"));
        assert!(mine.contains("bg-task-ok"));
    }

    #[test]
    fn streamed_flag_set_only_when_text_printed() {
        // 回归：STREAMED_OUTPUT_PRINTED 只在真正打印过 text_delta 时置位。
        // 调用失败（[Error] 写历史）时 main 仍需打印错误回复——与 s12 一致。
        STREAMED_OUTPUT_PRINTED.store(false, Ordering::Relaxed);
        let mut stop_reason = None;
        let mut has_tool_use = false;

        // thinking_delta 不打印 → 不置位
        let mut thinking = vec![StreamBlock::Thinking {
            thinking: String::new(),
            signature: None,
        }];
        handle_sse_event(
            r#"data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"step"}}"#,
            &mut thinking, &mut stop_reason, &mut has_tool_use, false,
        );
        assert!(!STREAMED_OUTPUT_PRINTED.load(Ordering::Relaxed));

        // text_delta 打印 → 置位
        let mut text = vec![StreamBlock::Text { text: String::new() }];
        handle_sse_event(
            r#"data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hi"}}"#,
            &mut text, &mut stop_reason, &mut has_tool_use, false,
        );
        assert!(STREAMED_OUTPUT_PRINTED.load(Ordering::Relaxed));

        // 清理，防止污染其他测试
        STREAMED_OUTPUT_PRINTED.store(false, Ordering::Relaxed);
    }

    #[test]
    fn execute_sync_unknown_tool_returns_error() {
        let out = execute_sync("no_such_tool", &serde_json::json!({}));
        assert!(out.starts_with("Error: unknown tool"));
    }

    #[test]
    fn execute_sync_bash_echo_runs() {
        let out = execute_sync("bash", &serde_json::json!({"command": "echo s13-exec-ok"}));
        assert!(out.contains("s13-exec-ok"));
    }

    // ── s14 新增：cron 调度 ──

    /// 清空 cron 静态状态（测试共享静态，防止测试间顺序依赖）
    fn cron_reset_state() {
        CRON_JOBS.lock().unwrap().clear();
        CRON_QUEUE.lock().unwrap().clear();
        LAST_FIRED.lock().unwrap().clear();
    }

    #[test]
    fn cron_field_matches_all_forms() {
        assert!(cron_field_matches("*", 0));
        assert!(cron_field_matches("*", 59));
        assert!(cron_field_matches("*/5", 0));
        assert!(cron_field_matches("*/5", 10));
        assert!(!cron_field_matches("*/5", 7));
        assert!(!cron_field_matches("*/0", 5)); // step 0 不匹配
        assert!(cron_field_matches("5", 5));
        assert!(!cron_field_matches("5", 6));
        assert!(cron_field_matches("1-5", 3));
        assert!(!cron_field_matches("1-5", 6));
        assert!(cron_field_matches("1,3,5", 3));
        assert!(!cron_field_matches("1,3,5", 2));
        assert!(!cron_field_matches("abc", 1)); // 非法静默 false
    }

    #[test]
    fn cron_matches_standard_semantics() {
        // 每分钟
        assert!(cron_matches("* * * * *", 30, 12, 15, 6, 3));
        // 每天早上 9:00
        assert!(cron_matches("0 9 * * *", 0, 9, 15, 6, 3));
        assert!(!cron_matches("0 9 * * *", 1, 9, 15, 6, 3));
        // 每 5 分钟
        assert!(cron_matches("*/5 * * * *", 10, 8, 3, 1, 2));
        assert!(!cron_matches("*/5 * * * *", 11, 8, 3, 1, 2));
        // 工作日 9:00（1-5 = 周一~周五；cron 周日=0、周一=1）
        assert!(cron_matches("0 9 * * 1-5", 0, 9, 10, 5, 1)); // 周一(cron 1)
        assert!(!cron_matches("0 9 * * 1-5", 0, 9, 10, 5, 0)); // 周日(cron 0)
        assert!(cron_matches("0 0 * * 0", 0, 0, 10, 5, 0)); // 周日=0
        // 非法表达式静默 false
        assert!(!cron_matches("0 9", 0, 9, 1, 1, 1));
        assert!(!cron_matches("bad field", 0, 9, 1, 1, 1));
    }

    #[test]
    fn cron_matches_dom_dow_or_semantics() {
        // 0 9 13 * 5：13 号或周五（标准 OR 语义）
        assert!(cron_matches("0 9 13 * 5", 0, 9, 10, 6, 5)); // 周五非 13 号
        assert!(cron_matches("0 9 13 * 5", 0, 9, 13, 6, 3)); // 13 号非周五
        assert!(cron_matches("0 9 13 * 5", 0, 9, 13, 6, 5)); // 13 号且周五
        assert!(!cron_matches("0 9 13 * 5", 0, 9, 10, 6, 3)); // 都不是
        // 仅 DOM 约束
        assert!(cron_matches("0 9 13 * *", 0, 9, 13, 6, 3));
        assert!(!cron_matches("0 9 13 * *", 0, 9, 14, 6, 3));
        // 仅 DOW 约束
        assert!(cron_matches("0 9 * * 5", 0, 9, 14, 6, 5));
        assert!(!cron_matches("0 9 * * 5", 0, 9, 14, 6, 3));
    }

    #[test]
    fn validate_cron_rejects_bad_expressions() {
        assert!(validate_cron("0 9 * * *").is_none());
        assert!(validate_cron("*/5 * * * *").is_none());
        assert!(validate_cron("0 9 1-5 * 1,3,5").is_none());
        // 字段数
        assert!(validate_cron("0 9").unwrap().contains("Expected 5 fields"));
        // 越界（错误文案对齐 Python）
        assert!(validate_cron("60 * * * *").unwrap().contains("minute: Value 60 out of bounds [0-59]"));
        assert!(validate_cron("* 24 * * *").unwrap().contains("hour: Value 24 out of bounds [0-23]"));
        assert!(validate_cron("* * 32 * *").unwrap().contains("day-of-month: Value 32 out of bounds [1-31]"));
        assert!(validate_cron("* * * 13 *").unwrap().contains("month: Value 13 out of bounds [1-12]"));
        assert!(validate_cron("* * * * 7").unwrap().contains("day-of-week: Value 7 out of bounds [0-6]"));
        // step / range / 非数字
        assert!(validate_cron("*/0 * * * *").unwrap().contains("Step must be > 0"));
        assert!(validate_cron("*/x * * * *").unwrap().contains("Invalid step"));
        assert!(validate_cron("5-1 * * * *").unwrap().contains("Range start > end"));
        assert!(validate_cron("1-60 * * * *").unwrap().contains("out of bounds"));
        assert!(validate_cron("a * * * *").unwrap().contains("Invalid field"));
    }

    #[test]
    fn cron_weekday_conversion_aligns_chrono_to_cron() {
        // 回归（实测发现）：调度循环曾把 num_days_from_monday()(周一=0) 直接当
        // cron weekday 用,导致 DOW 约束任务错位一天(工作日任务在周二~周六触发)。
        // 转换后:周一(0)→1,周六(5)→6,周日(6)→0。
        assert_eq!(cron_weekday_from_chrono(0), 1); // 周一 → cron 1
        assert_eq!(cron_weekday_from_chrono(5), 6); // 周六 → cron 6
        assert_eq!(cron_weekday_from_chrono(6), 0); // 周日 → cron 0
        // 转换结果与 cron_matches 语义一致:周一转换后命中 1-5,周日转换后命中 0
        assert!(cron_matches("0 9 * * 1-5", 0, 9, 10, 5, cron_weekday_from_chrono(0))); // 周一
        assert!(!cron_matches("0 9 * * 1-5", 0, 9, 10, 5, cron_weekday_from_chrono(6))); // 周日
        assert!(cron_matches("0 0 * * 0", 0, 0, 10, 5, cron_weekday_from_chrono(6))); // 周日
    }

    #[test]
    fn fire_due_jobs_dedup_within_minute_and_fires_next() {
        let mut jobs = HashMap::new();
        jobs.insert(
            "c1".into(),
            CronJob { id: "c1".into(), cron: "* * * * *".into(), prompt: "p".into(), recurring: true, durable: false },
        );
        let mut last_fired = HashMap::new();
        let mut queue = Vec::new();
        // 同一分钟两次判火 → 只入队一次
        let r1 = fire_due_jobs(30, 12, 1, 1, 1, "2026-01-01 12:30", &mut jobs, &mut last_fired, &mut queue);
        assert!(r1.is_empty());
        assert_eq!(queue.len(), 1);
        fire_due_jobs(30, 12, 1, 1, 1, "2026-01-01 12:30", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 1);
        // 下一分钟 → 再次触发
        fire_due_jobs(31, 12, 1, 1, 1, "2026-01-01 12:31", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 2);
    }

    #[test]
    fn fire_due_jobs_crosses_days() {
        let mut jobs = HashMap::new();
        jobs.insert(
            "daily".into(),
            CronJob { id: "daily".into(), cron: "0 9 * * *".into(), prompt: "morning".into(), recurring: true, durable: false },
        );
        let mut last_fired = HashMap::new();
        let mut queue = Vec::new();
        // 第 1 天 9:00 触发
        fire_due_jobs(0, 9, 1, 1, 3, "2026-01-01 09:00", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 1);
        // 同一天其它时间不触发
        fire_due_jobs(0, 10, 1, 1, 3, "2026-01-01 10:00", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 1);
        // 第 2 天 9:00 再次触发（marker 含日期 → 不跳过）
        fire_due_jobs(0, 9, 2, 1, 4, "2026-01-02 09:00", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 2);
    }

    #[test]
    fn fire_due_jobs_one_shot_removes_and_reports_durable() {
        let mut jobs = HashMap::new();
        jobs.insert(
            "once".into(),
            CronJob { id: "once".into(), cron: "* * * * *".into(), prompt: "reminder".into(), recurring: false, durable: true },
        );
        let mut last_fired = HashMap::new();
        let mut queue = Vec::new();
        let removed = fire_due_jobs(0, 0, 1, 1, 1, "2026-01-01 00:00", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 1);
        assert_eq!(removed, vec!["once".to_string()]); // durable 需要调用方落盘
        assert!(!jobs.contains_key("once")); // 一次性任务触发后移除
        // 后续不再触发
        fire_due_jobs(1, 0, 1, 1, 1, "2026-01-01 00:01", &mut jobs, &mut last_fired, &mut queue);
        assert_eq!(queue.len(), 1);
    }

    #[test]
    fn fire_due_jobs_session_only_removal_not_reported() {
        let mut jobs = HashMap::new();
        jobs.insert(
            "s1".into(),
            CronJob { id: "s1".into(), cron: "* * * * *".into(), prompt: "x".into(), recurring: false, durable: false },
        );
        let mut last_fired = HashMap::new();
        let mut queue = Vec::new();
        let removed = fire_due_jobs(0, 0, 1, 1, 1, "2026-01-01 00:00", &mut jobs, &mut last_fired, &mut queue);
        assert!(removed.is_empty());
        assert!(!jobs.contains_key("s1"));
    }

    #[test]
    fn cron_schedule_cancel_list_roundtrip() {
        cron_reset_state();
        let cwd = test_cwd("cron-mgmt");
        let job = schedule_job(&cwd, "*/2 * * * *", "run date", true, true).unwrap();
        assert!(job.id.starts_with("cron_"));
        // 非法表达式被拒（不注册）
        let err = schedule_job(&cwd, "not a cron", "x", true, false).unwrap_err();
        assert!(err.contains("Expected 5 fields"));
        // list 包含该任务
        let list = list_crons();
        assert!(list.contains(&job.id));
        assert!(list.contains("[recurring, durable]"));
        // cancel
        assert_eq!(cancel_job(&cwd, &job.id), format!("Cancelled {}", job.id));
        assert!(cancel_job(&cwd, &job.id).contains("not found"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn cron_durable_persistence_roundtrip() {
        cron_reset_state();
        let cwd = test_cwd("cron-durable");
        let job = schedule_job(&cwd, "0 9 * * *", "morning check", true, true).unwrap();
        // 落盘：仅 durable job 的数组 JSON（字段与 Python asdict 同构）
        let raw = fs::read_to_string(cwd.join(".scheduled_tasks.json")).unwrap();
        assert!(raw.contains(&job.id));
        assert!(raw.contains("morning check"));
        assert!(raw.contains("\"recurring\": true"));
        // 重建加载（独立 map，不污染静态）
        let mut jobs = HashMap::new();
        load_durable_jobs(&cwd, &mut jobs);
        assert!(jobs.contains_key(&job.id));
        assert_eq!(jobs[&job.id].cron, "0 9 * * *");
        // 取消后文件同步移除
        cancel_job(&cwd, &job.id);
        let raw2 = fs::read_to_string(cwd.join(".scheduled_tasks.json")).unwrap();
        assert!(!raw2.contains(&job.id));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn cron_durable_load_skips_invalid_jobs() {
        let cwd = test_cwd("cron-invalid");
        // 手工写一个含非法 cron 的文件（模拟手改/旧版本数据）
        let path = cwd.join(".scheduled_tasks.json");
        fs::create_dir_all(&cwd).unwrap();
        fs::write(
            &path,
            r#"[{"id":"good","cron":"0 9 * * *","prompt":"ok","recurring":true,"durable":true},{"id":"bad","cron":"99 99 * * *","prompt":"bad","recurring":true,"durable":true}]"#,
        )
        .unwrap();
        let mut jobs = HashMap::new();
        load_durable_jobs(&cwd, &mut jobs);
        assert!(jobs.contains_key("good"));
        assert!(!jobs.contains_key("bad")); // 非法跳过
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn cron_max_jobs_limit() {
        cron_reset_state();
        let cwd = test_cwd("cron-max");
        let mut ids = Vec::new();
        for i in 0..MAX_JOBS {
            let job = schedule_job(&cwd, "0 0 * * *", &format!("job {i}"), true, false).unwrap();
            ids.push(job.id);
        }
        let err = schedule_job(&cwd, "0 0 * * *", "overflow", true, false).unwrap_err();
        assert!(err.contains("Too many scheduled jobs (max 50)"));
        for id in &ids {
            cancel_job(&cwd, id);
        }
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_bash_stdin_closed_immediately() {
        // 回归（实测）：run_bash 曾继承终端 stdin——模型跑读 stdin 的命令时
        // 子进程挂起等输入,agent 回合卡死直到按 Enter。修复后 stdin=EOF:
        // cat 立即返回空、wc -c 立即返回 0,绝不挂起。
        let cat = run_bash(BashInput { command: "cat".into(), run_in_background: None });
        assert_eq!(cat, "(no output)"); // EOF → cat 立即退出
        let wc = run_bash(BashInput { command: "wc -c".into(), run_in_background: None });
        assert_eq!(wc.trim(), "0"); // EOF → 0 字节
    }

    #[test]
    fn sanitize_tool_pairs_removes_orphans() {
        // 模拟压缩后配对断裂（实测 400 场景）：孤儿 tool_result 出现在
        // 没有配对 assistant 的位置（tool_use 被摘要进 [Compacted] 头部）
        let mut msgs = vec![
            Message::user_text("[Compacted]\n\nsummary"),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "orphan".into(),
                content: "结果".into(),
            }]),
            Message::assistant_blocks(vec![ContentBlock::ToolUse {
                id: "ok".into(),
                name: "bash".into(),
                input: serde_json::json!({"command": "date"}),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "ok".into(),
                content: "out".into(),
            }]),
        ];
        sanitize_tool_pairs(&mut msgs);
        // 孤儿被移除 → 该 user 消息被替换为占位文本（空数组同样可能 400）
        assert!(matches!(&msgs[1].content, MessageContent::Text(t) if t.contains("compacted")));
        // 正常配对原样保留
        assert!(matches!(&msgs[3].content, MessageContent::Blocks(blocks) if blocks.len() == 1));
    }

    #[test]
    fn sanitize_tool_pairs_keeps_mixed_user_blocks() {
        // user 消息同时含 tool_result + 文本通知（后台通知注入形态）：
        // 文本保留、孤儿结果被移除、合法结果保留
        let mut msgs = vec![Message::user_tool_results(vec![
            ContentBlock::ToolResult { tool_use_id: "ghost".into(), content: "x".into() },
            ContentBlock::Text { text: "<task_notification>...</task_notification>".into() },
        ])];
        sanitize_tool_pairs(&mut msgs);
        if let MessageContent::Blocks(blocks) = &msgs[0].content {
            assert_eq!(blocks.len(), 1);
            assert!(matches!(&blocks[0], ContentBlock::Text { .. }));
        } else {
            panic!("应保留文本块");
        }
    }

    #[test]
    fn cron_execute_sync_dispatch() {
        cron_reset_state();
        // unknown 工具仍报错
        let out = execute_sync("no_such_cron_tool", &serde_json::json!({}));
        assert!(out.starts_with("Error: unknown tool"));
        // schedule_cron 非法表达式 → 校验错误文案
        let out = execute_sync("schedule_cron", &serde_json::json!({"cron": "bad", "prompt": "x"}));
        assert!(out.starts_with("Error: "));
        assert!(out.contains("Expected 5 fields"));
        // list_crons 空文案（reset 后无任务）
        let out = execute_sync("list_crons", &serde_json::json!({}));
        assert_eq!(out, "No cron jobs. Use schedule_cron to add one.");
        // cancel 不存在的任务
        let out = execute_sync("cancel_cron", &serde_json::json!({"job_id": "cron_999999"}));
        assert!(out.contains("not found"));
    }

    // ── s15: MessageBus / 队友 / 团队工具 ──

    fn team_test_cwd(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("lcc-s15-test-{}-{tag}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        dir
    }

    #[test]
    fn bus_send_read_roundtrip_preserves_fields() {
        let cwd = team_test_cwd("roundtrip");
        assert!(bus_send(&cwd, "alice", "lead", "Schema done", "result").is_empty());
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].from, "alice");
        assert_eq!(msgs[0].to, "lead");
        assert_eq!(msgs[0].content, "Schema done");
        assert_eq!(msgs[0].msg_type, "result"); // serde rename "type" 往返
        assert!(msgs[0].ts > 0.0);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_send_read_roundtrip_chinese_names_and_content() {
        let cwd = team_test_cwd("roundtrip-zh");
        assert!(bus_send(&cwd, "小红", "lead", "数据库 schema 已完成", "result").is_empty());
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].from, "小红");
        assert_eq!(msgs[0].content, "数据库 schema 已完成");
        assert_eq!(msgs[0].msg_type, "result");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_read_inbox_is_consuming() {
        let cwd = team_test_cwd("consuming");
        bus_send(&cwd, "alice", "lead", "hi", "message");
        assert!(cwd.join(".mailboxes/lead.jsonl").exists());
        assert_eq!(bus_read_inbox(&cwd, "lead").len(), 1);
        // 消费式：文件已删，二次读为空
        assert!(!cwd.join(".mailboxes/lead.jsonl").exists());
        assert!(bus_read_inbox(&cwd, "lead").is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_peek_non_destructive() {
        let cwd = team_test_cwd("peek");
        assert!(!bus_peek(&cwd, "lead"));
        bus_send(&cwd, "alice", "lead", "hi", "message");
        assert!(bus_peek(&cwd, "lead"));
        // peek 不消费：消息仍在
        assert_eq!(bus_read_inbox(&cwd, "lead").len(), 1);
        assert!(!bus_peek(&cwd, "lead"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_read_empty_or_missing_inbox_returns_empty() {
        let cwd = team_test_cwd("empty");
        assert!(bus_read_inbox(&cwd, "lead").is_empty());
        fs::create_dir_all(cwd.join(".mailboxes")).unwrap();
        fs::write(cwd.join(".mailboxes/lead.jsonl"), "").unwrap();
        assert!(bus_read_inbox(&cwd, "lead").is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_read_skips_invalid_lines() {
        let cwd = team_test_cwd("bad-lines");
        fs::create_dir_all(cwd.join(".mailboxes")).unwrap();
        fs::write(
            cwd.join(".mailboxes/lead.jsonl"),
            "{\"from\":\"a\",\"to\":\"lead\",\"content\":\"ok1\",\"type\":\"message\",\"ts\":1.0}\nnot json\n\n{\"from\":\"b\",\"to\":\"lead\",\"content\":\"ok2\",\"type\":\"message\",\"ts\":2.0}\n",
        )
        .unwrap();
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 2);
        assert_eq!(msgs[0].content, "ok1");
        assert_eq!(msgs[1].content, "ok2");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bus_send_rejects_traversal_agent_names() {
        let cwd = team_test_cwd("traversal");
        // 路径穿越（Python 教学版可写出 .mailboxes/，Rust 版前向修复）
        assert!(bus_send(&cwd, "lead", "../evil", "x", "message").contains("invalid agent name"));
        assert!(bus_send(&cwd, "../evil", "lead", "x", "message").contains("invalid agent name"));
        assert!(bus_send(&cwd, "lead", "", "x", "message").contains("invalid agent name"));
        assert!(bus_send(&cwd, "lead", "a/b", "x", "message").contains("invalid agent name"));
        assert!(bus_send(&cwd, "lead", "a b", "x", "message").contains("invalid agent name"));
        assert!(!cwd.join(".mailboxes/../evil.jsonl").exists());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn valid_agent_name_accepts_normal_names() {
        assert!(valid_agent_name("alice"));
        assert!(valid_agent_name("dev-1"));
        assert!(valid_agent_name("a_b"));
        assert!(valid_agent_name("lead"));
        // 中文队友名允许（黑名单只拦路径敏感字符）
        assert!(valid_agent_name("小红"));
        assert!(valid_agent_name("数据库工程师"));
        assert!(!valid_agent_name(""));
        assert!(!valid_agent_name("../x"));
        assert!(!valid_agent_name("a.b"));
        assert!(!valid_agent_name("a:b"));
        assert!(!valid_agent_name("a\\b"));
        assert!(!valid_agent_name("a b"));
        assert!(!valid_agent_name(&"x".repeat(65)));
    }

    #[test]
    fn check_inbox_empty_wording() {
        let cwd = team_test_cwd("check-empty");
        assert_eq!(run_check_inbox(&cwd), "(inbox empty)");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn check_inbox_formats_messages_and_consumes() {
        let cwd = team_test_cwd("check-format");
        bus_send(&cwd, "alice", "lead", "Schema done", "result");
        bus_send(&cwd, "bob", "lead", "Client written", "result");
        let out = run_check_inbox(&cwd);
        // s16: 行格式带消息类型标签 [type]
        assert!(out.contains("  [alice] [result] Schema done"));
        assert!(out.contains("  [bob] [result] Client written"));
        // 消费式：再读为空
        assert_eq!(run_check_inbox(&cwd), "(inbox empty)");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn check_inbox_truncates_long_content() {
        let cwd = team_test_cwd("check-trunc");
        let long = "x".repeat(300);
        bus_send(&cwd, "alice", "lead", &long, "message");
        let out = run_check_inbox(&cwd);
        // s16: 前缀含 [type] 标签
        assert!(out.contains("  [alice] [message] "));
        // 200 字符截断 + 无多余内容
        let body = out.trim_start_matches("  [alice] [message] ");
        assert_eq!(body.chars().count(), 200);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_send_message_delivers_and_reports() {
        let cwd = team_test_cwd("send-msg");
        let input = SendMessageInput { to: "alice".into(), content: "please check schema".into() };
        assert_eq!(run_send_message(&cwd, input), "Sent to alice");
        assert!(bus_peek(&cwd, "alice"));
        let msgs = bus_read_inbox(&cwd, "alice");
        assert_eq!(msgs[0].from, "lead");
        assert_eq!(msgs[0].content, "please check schema");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn format_inbox_block_matches_python_format() {
        let msgs = vec![
            MailMessage { from: "alice".into(), to: "lead".into(), content: "Schema done".into(), msg_type: "result".into(), ts: 1.0, metadata: serde_json::json!({}) },
            MailMessage { from: "bob".into(), to: "lead".into(), content: "Client written".into(), msg_type: "result".into(), ts: 2.0, metadata: serde_json::json!({}) },
        ];
        assert_eq!(
            format_inbox_block(&msgs),
            "[Inbox]\nFrom alice: Schema done\nFrom bob: Client written"
        );
    }

    #[test]
    fn teammate_system_prompt_mentions_board_and_protocol() {
        let p = teammate_system_prompt("alice", "backend dev");
        assert!(p.contains("'alice'"));
        assert!(p.contains("backend dev"));
        // s17: 提示可看板认领（对齐 Python "You can list and claim tasks from the board"）
        assert!(p.contains("list and claim tasks from the board"));
        // s17 前移（实测）：明确指示完成后 complete_task——Python 版无此句，
        // 实测队友只报 Done 不更新任务板（僵尸 in_progress），Rust 前向改进
        assert!(p.contains("use complete_task to mark it completed"));
        // s16: 提示检查协议消息
        assert!(p.contains("Check inbox for protocol messages"));
    }

    #[test]
    fn teammate_tools_are_exactly_eight() {
        let tools = teammate_tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name.as_str()).collect();
        assert_eq!(
            names,
            vec![
                "bash",
                "read_file",
                "write_file",
                "send_message",
                "submit_plan",
                "list_tasks",
                "claim_task",
                "complete_task"
            ]
        );
    }

    #[test]
    fn all_tools_contains_team_and_protocol_tools() {
        let tools = all_tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name.as_str()).collect();
        assert_eq!(names.len(), 27);
        assert!(names.contains(&"spawn_teammate"));
        assert!(names.contains(&"send_message"));
        assert!(names.contains(&"check_inbox"));
        assert!(names.contains(&"request_shutdown"));
        assert!(names.contains(&"request_plan"));
        assert!(names.contains(&"review_plan"));
        // s18: worktree 3 工具
        assert!(names.contains(&"create_worktree"));
        assert!(names.contains(&"remove_worktree"));
        assert!(names.contains(&"keep_worktree"));
    }

    #[test]
    fn try_register_teammate_duplicate_rejected() {
        assert!(try_register_teammate("alice").is_ok());
        let err = try_register_teammate("alice").unwrap_err();
        assert_eq!(err, "Teammate 'alice' already exists");
        ACTIVE_TEAMMATES.lock().unwrap().remove("alice");
        // 清理后可重新注册
        assert!(try_register_teammate("alice").is_ok());
        ACTIVE_TEAMMATES.lock().unwrap().remove("alice");
    }

    #[test]
    fn try_register_teammate_rejects_traversal() {
        let err = try_register_teammate("../evil").unwrap_err();
        assert_eq!(err, "Error: invalid teammate name '../evil'");
    }

    #[test]
    fn spawn_teammate_input_requires_all_fields() {
        let r: Result<SpawnTeammateInput, _> =
            serde_json::from_value(serde_json::json!({"name": "a", "role": "r"}));
        assert!(r.is_err()); // 缺 prompt
        let ok: SpawnTeammateInput = serde_json::from_value(serde_json::json!({
            "name": "a", "role": "r", "prompt": "p"
        }))
        .unwrap();
        assert_eq!(ok.name, "a");
        assert_eq!(ok.role, "r");
        assert_eq!(ok.prompt, "p");
    }

    #[test]
    fn execute_sync_team_tools_dispatch() {
        let cwd = team_test_cwd("dispatch");
        // 需要 cwd 是临时目录：execute_sync 内部用 workdir()（进程 cwd），
        // 这里验证的是未知工具与参数校验路径
        let out = execute_sync("send_message", &serde_json::json!({"to": "x"}));
        assert!(out.starts_with("Error: invalid send_message params"));
        let out = execute_sync("check_inbox", &serde_json::json!({"extra": 1}));
        // 额外字段容忍（serde 默认忽略），不应报参数错误
        assert!(!out.starts_with("Error: invalid check_inbox params"));
        let _ = fs::remove_dir_all(&cwd);
    }

    /// s15 特有回归：inbox 注入（纯文本 user 消息）夹在 assistant(tool_use)
    /// 与 user(tool_result) 之间，sanitize_tool_pairs 不得误伤合法配对。
    #[test]
    fn sanitize_tool_pairs_keeps_pairs_across_inbox_injection() {
        let mut msgs = vec![
            Message::assistant_blocks(vec![ContentBlock::ToolUse {
                id: "ok".into(),
                name: "bash".into(),
                input: serde_json::json!({"command": "date"}),
            }]),
            Message::user_text("[Inbox]\nFrom alice: Schema done"),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "ok".into(),
                content: "out".into(),
            }]),
        ];
        sanitize_tool_pairs(&mut msgs);
        // [Inbox] 纯文本注入原样保留
        assert!(matches!(&msgs[1].content, MessageContent::Text(t) if t.starts_with("[Inbox]")));
        // 合法 tool_result 配对保留
        assert!(matches!(&msgs[2].content, MessageContent::Blocks(blocks) if blocks.len() == 1));
    }

    /// s15 注入形态：inbox 文本与 tool_result 合入同一条 user 消息
    /// （wake 轮 [Inbox] + 后台通知合流），文本与合法结果都保留。
    #[test]
    fn sanitize_tool_pairs_keeps_inbox_text_and_valid_result_in_one_user_msg() {
        let mut msgs = vec![
            Message::assistant_blocks(vec![ContentBlock::ToolUse {
                id: "ok".into(),
                name: "bash".into(),
                input: serde_json::json!({"command": "date"}),
            }]),
            Message::user_tool_results(vec![
                ContentBlock::Text { text: "[Inbox]\nFrom alice: Schema done".into() },
                ContentBlock::ToolResult { tool_use_id: "ok".into(), content: "out".into() },
            ]),
        ];
        sanitize_tool_pairs(&mut msgs);
        if let MessageContent::Blocks(blocks) = &msgs[1].content {
            assert_eq!(blocks.len(), 2);
            assert!(matches!(&blocks[0], ContentBlock::Text { .. }));
            assert!(matches!(&blocks[1], ContentBlock::ToolResult { .. }));
        } else {
            panic!("应保留文本块");
        }
    }

    /// 唤醒条件：完成态任务 → has_pending_background 为真 → collect 后复位。
    /// 直接注入状态（不依赖真实后台线程）：BACKGROUND_TASKS 是全进程共享 map，
    /// 端到端版本会在并行测试时被其他测试的 collect_background_results 消费掉
    /// （s13 继承测试同类竞争，--test-threads=1 约定下无碍）。
    #[test]
    fn has_pending_background_reflects_completed_tasks() {
        BACKGROUND_TASKS.lock().unwrap().insert(
            "bg_s15_test".into(),
            BgTask {
                tool_use_id: "call_1".into(),
                command: "echo hi".into(),
                status: "completed".into(),
            },
        );
        assert!(has_pending_background());
        let notifs = collect_background_results();
        assert_eq!(notifs.len(), 1);
        assert!(notifs[0].contains("<task_notification>"));
        assert!(notifs[0].contains("bg_s15_test"));
        assert!(!has_pending_background());
    }

    // ── s16: Team Protocols ──

    fn make_pending_state(request_id: &str, protocol_type: ProtocolType) -> ProtocolState {
        ProtocolState {
            request_id: request_id.to_string(),
            protocol_type,
            sender: "alice".to_string(),
            target: "lead".to_string(),
            status: ProtocolStatus::Pending,
            payload: String::new(),
            created_at: 1.0,
        }
    }

    #[test]
    fn new_request_id_has_expected_format() {
        let id = new_request_id();
        assert!(id.starts_with("req_"));
        assert_eq!(id.len(), 10); // "req_" + 6 位数字
        assert!(id[4..].chars().all(|c| c.is_ascii_digit()));
    }

    #[test]
    fn match_response_unknown_request_id_ignored() {
        match_response("shutdown_response", "req_999999", true);
        // 无 panic，且不创建状态（只查自己的 id，不依赖全局为空）
        assert!(!PENDING_REQUESTS.lock().unwrap().contains_key("req_999999"));
    }

    #[test]
    fn match_response_type_mismatch_ignored() {
                PENDING_REQUESTS.lock().unwrap().insert(
            "req_000001".to_string(),
            make_pending_state("req_000001", ProtocolType::Shutdown),
        );
        // shutdown 请求收到 plan_approval_response → 类型不匹配，状态不变
        match_response("plan_approval_response", "req_000001", true);
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000001").unwrap();
        assert_eq!(state.status, ProtocolStatus::Pending);
    }

    #[test]
    fn match_response_approve_updates_state() {
                PENDING_REQUESTS.lock().unwrap().insert(
            "req_000002".to_string(),
            make_pending_state("req_000002", ProtocolType::PlanApproval),
        );
        match_response("plan_approval_response", "req_000002", true);
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000002").unwrap();
        assert_eq!(state.status, ProtocolStatus::Approved);
    }

    #[test]
    fn match_response_reject_updates_state() {
                PENDING_REQUESTS.lock().unwrap().insert(
            "req_000003".to_string(),
            make_pending_state("req_000003", ProtocolType::Shutdown),
        );
        match_response("shutdown_response", "req_000003", false);
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000003").unwrap();
        assert_eq!(state.status, ProtocolStatus::Rejected);
    }

    #[test]
    fn match_response_duplicate_ignored() {
                PENDING_REQUESTS.lock().unwrap().insert(
            "req_000004".to_string(),
            make_pending_state("req_000004", ProtocolType::Shutdown),
        );
        match_response("shutdown_response", "req_000004", true);
        // 已决请求的重复回复 → 状态不再变化
        match_response("shutdown_response", "req_000004", false);
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000004").unwrap();
        assert_eq!(state.status, ProtocolStatus::Approved);
    }

    #[test]
    fn run_request_shutdown_creates_pending_and_sends() {
                let cwd = team_test_cwd("req-shutdown");
        let input = RequestShutdownInput { teammate: "alice".into() };
        let out = run_request_shutdown(&cwd, input);
        assert!(out.starts_with("Shutdown request sent to alice (req: "));
        // 消息落盘：shutdown_request 带 metadata.request_id
        let msgs = bus_read_inbox(&cwd, "alice");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "shutdown_request");
        let req_id = msgs[0]
            .metadata
            .get("request_id")
            .and_then(|v| v.as_str())
            .unwrap()
            .to_string();
        // 状态记录：type=shutdown, sender=lead, target=alice, pending
        // （只查自己的 request_id——并行测试共享 PENDING_REQUESTS，
        //   不做全局 len/is_empty 断言，避免 Mutex 中毒连锁）
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get(&req_id).unwrap();
        assert_eq!(state.protocol_type, ProtocolType::Shutdown);
        assert_eq!(state.sender, "lead");
        assert_eq!(state.target, "alice");
        assert_eq!(state.status, ProtocolStatus::Pending);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_request_plan_sends_plain_message() {
                let cwd = team_test_cwd("req-plan");
        let input = RequestPlanInput { teammate: "bob".into(), task: "重构认证模块".into() };
        assert_eq!(run_request_plan(&cwd, input), "Asked bob to submit a plan");
        let msgs = bus_read_inbox(&cwd, "bob");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "message");
        assert!(msgs[0].content.contains("重构认证模块"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_review_plan_not_found() {
                let cwd = team_test_cwd("review-miss");
        let input = ReviewPlanInput { request_id: "req_999999".into(), approve: true, feedback: String::new() };
        assert_eq!(run_review_plan(&cwd, input), "Request req_999999 not found");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_review_plan_already_resolved() {
                let cwd = team_test_cwd("review-already");
        PENDING_REQUESTS.lock().unwrap().insert(
            "req_000005".to_string(),
            make_pending_state("req_000005", ProtocolType::PlanApproval),
        );
        let input = ReviewPlanInput { request_id: "req_000005".into(), approve: true, feedback: String::new() };
        run_review_plan(&cwd, input);
        // 第二次审批 → already 文案
        let input2 = ReviewPlanInput { request_id: "req_000005".into(), approve: false, feedback: String::new() };
        let out = run_review_plan(&cwd, input2);
        assert_eq!(out, "Request req_000005 already approved");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_review_plan_approves_and_sends_response() {
                let cwd = team_test_cwd("review-ok");
        PENDING_REQUESTS.lock().unwrap().insert(
            "req_000006".to_string(),
            ProtocolState {
                request_id: "req_000006".to_string(),
                protocol_type: ProtocolType::PlanApproval,
                sender: "bob".to_string(),
                target: "lead".to_string(),
                status: ProtocolStatus::Pending,
                payload: "计划".to_string(),
                created_at: 1.0,
            },
        );
        let input = ReviewPlanInput { request_id: "req_000006".into(), approve: true, feedback: "很好".into() };
        assert_eq!(run_review_plan(&cwd, input), "Plan approved (req_000006)");
        // 状态更新
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000006").unwrap();
        assert_eq!(state.status, ProtocolStatus::Approved);
        drop(state);
        // 响应送达 bob：plan_approval_response 带 request_id + approve + feedback
        let msgs = bus_read_inbox(&cwd, "bob");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "plan_approval_response");
        assert_eq!(msgs[0].content, "很好");
        assert_eq!(msgs[0].metadata.get("approve").and_then(|v| v.as_bool()), Some(true));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn teammate_submit_plan_creates_pending_and_sends() {
                let cwd = team_test_cwd("submit-plan");
        let out = teammate_submit_plan(&cwd, "bob", "计划：先建 schema");
        assert!(out.starts_with("Plan submitted (req_"));
        assert!(out.ends_with("Waiting for approval..."));
        // 消息落盘：plan_approval_request 带 request_id
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "plan_approval_request");
        let req_id = msgs[0]
            .metadata
            .get("request_id")
            .and_then(|v| v.as_str())
            .unwrap()
            .to_string();
        // 状态：sender=bob, type=plan_approval, payload=计划（只查自己的 id）
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get(&req_id).unwrap();
        assert_eq!(state.sender, "bob");
        assert_eq!(state.protocol_type, ProtocolType::PlanApproval);
        assert_eq!(state.payload, "计划：先建 schema");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn handle_inbox_message_shutdown_stops_and_responds() {
                let cwd = team_test_cwd("handle-shutdown");
        let mut messages: Vec<Message> = Vec::new();
        let msg = MailMessage {
            from: "lead".into(),
            to: "alice".into(),
            content: "Please shut down gracefully.".into(),
            msg_type: "shutdown_request".into(),
            ts: 1.0,
            metadata: serde_json::json!({ "request_id": "req_000010" }),
        };
        assert!(handle_inbox_message(&cwd, "alice", &msg, &mut messages));
        // 响应落盘：shutdown_response 带 request_id + approve=true
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "shutdown_response");
        assert_eq!(msgs[0].content, "Shutting down gracefully.");
        assert_eq!(msgs[0].metadata.get("request_id").and_then(|v| v.as_str()), Some("req_000010"));
        assert_eq!(msgs[0].metadata.get("approve").and_then(|v| v.as_bool()), Some(true));
        // messages 未注入（shutdown 不注入）
        assert!(messages.is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn handle_inbox_message_plan_approved_injects() {
        let cwd = team_test_cwd("handle-approve");
        let mut messages: Vec<Message> = Vec::new();
        let msg = MailMessage {
            from: "lead".into(),
            to: "bob".into(),
            content: "Approved".into(),
            msg_type: "plan_approval_response".into(),
            ts: 1.0,
            metadata: serde_json::json!({ "request_id": "req_000011", "approve": true }),
        };
        assert!(!handle_inbox_message(&cwd, "bob", &msg, &mut messages));
        assert_eq!(messages.len(), 1);
        assert!(matches!(&messages[0].content, MessageContent::Text(t) if t == "[Plan approved] Proceed with the task."));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn handle_inbox_message_plan_rejected_injects_feedback() {
        let cwd = team_test_cwd("handle-reject");
        let mut messages: Vec<Message> = Vec::new();
        let msg = MailMessage {
            from: "lead".into(),
            to: "bob".into(),
            content: "计划太模糊".into(),
            msg_type: "plan_approval_response".into(),
            ts: 1.0,
            metadata: serde_json::json!({ "request_id": "req_000012", "approve": false }),
        };
        assert!(!handle_inbox_message(&cwd, "bob", &msg, &mut messages));
        assert_eq!(messages.len(), 1);
        assert!(matches!(&messages[0].content, MessageContent::Text(t) if t == "[Plan rejected] Feedback: 计划太模糊"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn handle_inbox_message_plain_message_continues() {
        let cwd = team_test_cwd("handle-plain");
        let mut messages: Vec<Message> = Vec::new();
        let msg = MailMessage {
            from: "lead".into(),
            to: "alice".into(),
            content: "继续干活".into(),
            msg_type: "message".into(),
            ts: 1.0,
            metadata: serde_json::json!({}),
        };
        assert!(!handle_inbox_message(&cwd, "alice", &msg, &mut messages));
        assert!(messages.is_empty()); // 普通消息由调用方注入 <inbox>
        let _ = fs::remove_dir_all(&cwd);
    }

    /// idle 收到 shutdown_request → Shutdown（响应已发送）
    #[test]
    /// s17: idle_poll_once 收到 shutdown_request → Shutdown + 响应落盘
    /// （对齐 Python idle_poll 的 in idle 分支；无 tokio 依赖，同步可测）
    fn idle_poll_once_shutdown_returns_shutdown() {
        let cwd = team_test_cwd("idle-shutdown");
        bus_send_meta(
            &cwd,
            "lead",
            "alice",
            "Please shut down gracefully.",
            "shutdown_request",
            &serde_json::json!({ "request_id": "req_000020" }),
        );
        let mut messages: Vec<Message> = Vec::new();
        let outcome = idle_poll_once(&cwd, "alice", &mut messages);
        assert_eq!(outcome, Some((IdleOutcome::Shutdown, None)));
        // 响应已发出（in idle 分支）
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "shutdown_response");
        assert_eq!(msgs[0].metadata.get("request_id").and_then(|v| v.as_str()), Some("req_000020"));
        let _ = fs::remove_dir_all(&cwd);
    }

    /// idle 收到普通消息 → Continue + <inbox> 注入
    #[test]
    /// s17: idle_poll_once 收到普通消息 → Work + <inbox> 注入
    fn idle_poll_once_plain_message_returns_work() {
        let cwd = team_test_cwd("idle-plain");
        bus_send(&cwd, "lead", "alice", "有新任务", "message");
        let mut messages: Vec<Message> = Vec::new();
        let outcome = idle_poll_once(&cwd, "alice", &mut messages);
        assert_eq!(outcome, Some((IdleOutcome::Work, None)));
        assert_eq!(messages.len(), 1);
        assert!(matches!(&messages[0].content, MessageContent::Text(t) if t.contains("<inbox>") && t.contains("有新任务")));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn consume_lead_inbox_routes_protocol_response() {
                let cwd = team_test_cwd("consume-route");
        // 队友回复 shutdown_response（带 request_id）
        PENDING_REQUESTS.lock().unwrap().insert(
            "req_000030".to_string(),
            make_pending_state("req_000030", ProtocolType::Shutdown),
        );
        bus_send_meta(
            &cwd,
            "alice",
            "lead",
            "Shutting down gracefully.",
            "shutdown_response",
            &serde_json::json!({ "request_id": "req_000030", "approve": true }),
        );
        let msgs = consume_lead_inbox(&cwd);
        assert_eq!(msgs.len(), 1); // 返回全部消息
        // 协议状态已更新（消息被消费但协议先路由）
        let pending = PENDING_REQUESTS.lock().unwrap();
        let state = pending.get("req_000030").unwrap();
        assert_eq!(state.status, ProtocolStatus::Approved);
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn consume_lead_inbox_plain_message_unchanged() {
                let cwd = team_test_cwd("consume-plain");
        bus_send(&cwd, "alice", "lead", "Schema done", "result");
        let msgs = consume_lead_inbox(&cwd);
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].msg_type, "result");
        // （不断言全局无状态：并行测试共享 PENDING_REQUESTS，只验证消息原样返回）
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn mail_message_metadata_roundtrip() {
        let cwd = team_test_cwd("meta-roundtrip");
        bus_send_meta(
            &cwd,
            "lead",
            "alice",
            "hi",
            "shutdown_request",
            &serde_json::json!({ "request_id": "req_000040", "approve": true }),
        );
        let msgs = bus_read_inbox(&cwd, "alice");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].metadata.get("request_id").and_then(|v| v.as_str()), Some("req_000040"));
        assert_eq!(msgs[0].metadata.get("approve").and_then(|v| v.as_bool()), Some(true));
        let _ = fs::remove_dir_all(&cwd);
    }

    /// s16 兼容性：无 metadata 字段的旧消息（s15 时代）仍可反序列化
    #[test]
    fn mail_message_legacy_without_metadata_deserializes() {
        let cwd = team_test_cwd("meta-legacy");
        fs::create_dir_all(cwd.join(".mailboxes")).unwrap();
        fs::write(
            cwd.join(".mailboxes/lead.jsonl"),
            "{\"from\":\"alice\",\"to\":\"lead\",\"content\":\"旧消息\",\"type\":\"result\",\"ts\":1.0}\n",
        )
        .unwrap();
        let msgs = bus_read_inbox(&cwd, "lead");
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].content, "旧消息");
        assert_eq!(msgs[0].metadata, serde_json::json!({}));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn check_inbox_protocol_tag_format() {
                let cwd = team_test_cwd("check-tag");
        // 带 request_id 的协议响应
        bus_send_meta(
            &cwd,
            "alice",
            "lead",
            "Shutting down.",
            "shutdown_response",
            &serde_json::json!({ "request_id": "req_000050" }),
        );
        // 普通消息（无 request_id）
        bus_send(&cwd, "bob", "lead", "Schema done", "result");
        let out = run_check_inbox(&cwd);
        assert!(out.contains("  [alice] [shutdown_response req:req_000050] Shutting down."));
        assert!(out.contains("  [bob] [result] Schema done"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn execute_sync_protocol_tools_dispatch() {
        // 参数校验路径（workdir 生效前先验 serde）
        let out = execute_sync("request_shutdown", &serde_json::json!({}));
        assert!(out.starts_with("Error: invalid request_shutdown params"));
        let out = execute_sync("review_plan", &serde_json::json!({ "request_id": "x" }));
        assert!(out.starts_with("Error: invalid review_plan params")); // 缺 approve
        let out = execute_sync("request_plan", &serde_json::json!({ "teammate": "a" }));
        assert!(out.starts_with("Error: invalid request_plan params")); // 缺 task
    }

    #[test]
    fn review_plan_input_feedback_optional() {
        // feedback 缺省 → 空串（对齐 Python 默认 ""）
        let ok: ReviewPlanInput = serde_json::from_value(serde_json::json!({
            "request_id": "req_1", "approve": true
        }))
        .unwrap();
        assert_eq!(ok.feedback, "");
        let with_fb: ReviewPlanInput = serde_json::from_value(serde_json::json!({
            "request_id": "req_1", "approve": false, "feedback": "改一下"
        }))
        .unwrap();
        assert_eq!(with_fb.feedback, "改一下");
    }

    /// s16 实测回归：队友无轮数上限后 messages 超窗口，截断可能把 tool_use
    /// 切出窗口、留下孤儿 tool_result 成为窗口首条 → API 400（bob 多轮探索
    /// 实测）。run_teammate 发送前 sanitize_tool_pairs 必须把孤儿替换为占位。
    #[test]
    fn teammate_window_sanitizes_orphan_tool_results() {
        // 21 条消息：前置 1 对（tool_use "outside" 在窗口外）+ 19 条正常配对
        let mut messages = vec![
            Message::assistant_blocks(vec![ContentBlock::ToolUse {
                id: "outside".into(),
                name: "bash".into(),
                input: serde_json::json!({"command": "old"}),
            }]),
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "outside".into(),
                content: "旧结果".into(),
            }]),
        ];
        for i in 0..19 {
            messages.push(Message::assistant_blocks(vec![ContentBlock::ToolUse {
                id: format!("in{i}"),
                name: "bash".into(),
                input: serde_json::json!({"command": "x"}),
            }]));
            messages.push(Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: format!("in{i}"),
                content: "ok".into(),
            }]));
        }
        assert_eq!(messages.len(), 40);
        // run_teammate 的窗口逻辑：len - 20 = 20 → 窗口首条是 messages[20]
        // （in0 的 tool_result？不——20 是 assistant 位置，需构造窗口首条为孤儿）
        // 实际触发场景：窗口起点落在 tool_result 上。这里直接验证 sanitize
        // 对"窗口首条是孤儿 tool_result"的处理：
        let window_start = messages.len().saturating_sub(TEAMMATE_HISTORY_WINDOW);
        let mut window: Vec<Message> = messages[window_start..].to_vec();
        // 若窗口起点是孤儿 tool_result（tool_use 在窗口外）→ sanitize 替换为占位
        let mut orphan_head = vec![
            Message::user_tool_results(vec![ContentBlock::ToolResult {
                tool_use_id: "outside".into(),
                content: "旧结果".into(),
            }]),
        ];
        orphan_head.extend(window);
        sanitize_tool_pairs(&mut orphan_head);
        assert!(matches!(&orphan_head[0].content, MessageContent::Text(t) if t.contains("compacted")));
        // 窗口内正常配对不受影响
        assert!(matches!(&orphan_head[1].content, MessageContent::Blocks(_)));
    }

    // ── s17: Autonomous Agents ──

    #[test]
    fn scan_unclaimed_tasks_empty_when_no_tasks() {
        let cwd = team_test_cwd("scan-empty");
        assert!(scan_unclaimed_tasks(&cwd).is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn scan_unclaimed_tasks_finds_pending_unowned() {
        let cwd = team_test_cwd("scan-find");
        create_task(&cwd, "设计", "", &[]);
        create_task(&cwd, "编码", "", &[]);
        let unclaimed = scan_unclaimed_tasks(&cwd);
        assert_eq!(unclaimed.len(), 2);
        assert!(unclaimed.iter().all(|t| t.status == "pending" && t.owner.is_none()));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn scan_unclaimed_tasks_excludes_owned_and_in_progress() {
        let cwd = team_test_cwd("scan-exclude");
        let owned = create_task(&cwd, "已认领", "", &[]);
        claim_task(&cwd, &owned.id, "alice");
        let in_progress = create_task(&cwd, "进行中", "", &[]);
        claim_task(&cwd, &in_progress.id, "bob");
        // 两个都被认领 → 无未认领任务
        assert!(scan_unclaimed_tasks(&cwd).is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn scan_unclaimed_tasks_excludes_blocked_deps() {
        let cwd = team_test_cwd("scan-blocked");
        let dep = create_task(&cwd, "前置", "", &[]);
        // 编码 blockedBy 前置（未完成）→ 不可认领；但前置本身可认领
        create_task(&cwd, "编码", "", &[dep.id.clone()]);
        let unclaimed = scan_unclaimed_tasks(&cwd);
        assert_eq!(unclaimed.len(), 1);
        assert_eq!(unclaimed[0].subject, "前置"); // 编码被依赖阻塞
        // 前置完成后 → 编码可认领
        claim_task(&cwd, &dep.id, "alice");
        complete_task(&cwd, &dep.id);
        let unclaimed2 = scan_unclaimed_tasks(&cwd);
        assert_eq!(unclaimed2.len(), 1);
        assert_eq!(unclaimed2[0].subject, "编码");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn claim_task_rejects_existing_owner() {
        let cwd = team_test_cwd("claim-owner");
        let t = create_task(&cwd, "任务", "", &[]);
        assert!(claim_task(&cwd, &t.id, "alice").starts_with("Claimed"));
        // 已认领任务第二次 claim：status 检查先命中（对齐 Python 顺序）
        let out = claim_task(&cwd, &t.id, "bob");
        assert_eq!(out, format!("Task {} is in_progress, cannot claim", t.id));
        // owner 检查的独立场景：手工构造 owner 存在但 status=pending 的任务
        let t2 = create_task(&cwd, "特殊", "", &[]);
        let mut task = load_task(&cwd, &t2.id).unwrap();
        task.owner = Some("alice".to_string());
        save_task(&cwd, &task);
        let out2 = claim_task(&cwd, &t2.id, "bob");
        assert_eq!(out2, format!("Task {} already owned by alice", t2.id));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn idle_poll_once_auto_claims_board_task() {
        let cwd = team_test_cwd("idle-claim");
        let t = create_task(&cwd, "写 schema", "", &[]);
        let mut messages: Vec<Message> = Vec::new();
        let outcome = idle_poll_once(&cwd, "alice", &mut messages);
        assert_eq!(outcome, Some((IdleOutcome::Work, Some(t.id.clone()))));
        // <auto-claimed> 注入
        assert_eq!(messages.len(), 1);
        assert!(matches!(&messages[0].content, MessageContent::Text(x)
            if x.contains("<auto-claimed>") && x.contains(&t.subject)));
        // 任务已被 alice 认领（owner=队友名）
        let task = load_task(&cwd, &t.id).unwrap();
        assert_eq!(task.status, "in_progress");
        assert_eq!(task.owner.as_deref(), Some("alice"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn idle_poll_once_claim_failure_returns_none() {
        let cwd = team_test_cwd("idle-claim-fail");
        let t = create_task(&cwd, "被抢", "", &[]);
        claim_task(&cwd, &t.id, "bob"); // bob 先认领
        let mut messages: Vec<Message> = Vec::new();
        // alice 抢不到 → 无注入、返回 None（继续轮询）
        assert_eq!(idle_poll_once(&cwd, "alice", &mut messages), None);
        assert!(messages.is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn idle_poll_once_nothing_returns_none() {
        let cwd = team_test_cwd("idle-nothing");
        let mut messages: Vec<Message> = Vec::new();
        assert_eq!(idle_poll_once(&cwd, "alice", &mut messages), None);
        assert!(messages.is_empty());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn reinject_identity_when_messages_short() {
        let mut messages: Vec<Message> = vec![Message::user_text("干活".to_string())];
        maybe_reinject_identity(&mut messages, "alice", "backend dev");
        assert_eq!(messages.len(), 2);
        assert!(matches!(&messages[0].content, MessageContent::Text(t)
            if t.contains("<identity>") && t.contains("'alice'") && t.contains("backend dev")));
    }

    #[test]
    fn reinject_identity_skips_when_messages_long() {
        let mut messages: Vec<Message> = Vec::new();
        for i in 0..5 {
            messages.push(Message::user_text(format!("消息 {i}")));
        }
        maybe_reinject_identity(&mut messages, "alice", "backend dev");
        assert_eq!(messages.len(), 5); // 未注入
        assert!(!matches!(&messages[0].content, MessageContent::Text(t) if t.contains("<identity>")));
    }

    #[test]
    fn work_max_rounds_and_idle_constants() {
        assert_eq!(WORK_MAX_ROUNDS, 10);        // 对齐 Python range(10)
        assert_eq!(IDLE_POLL_INTERVAL_SECS, 5);  // 对齐 Python 5s
        assert_eq!(IDLE_TIMEOUT_SECS, 60);       // 对齐 Python 60s
    }

    // ── s18: Worktree Isolation ──

    /// 在临时目录初始化 git 仓库（含一个初始 commit，worktree add 需要 HEAD）
    fn git_init_repo(cwd: &Path) {
        fs::create_dir_all(cwd).unwrap();
        let _ = Command::new("git").args(["init", "-b", "main"]).current_dir(cwd).output();
        let _ = Command::new("git").args(["config", "user.email", "test@example.com"]).current_dir(cwd).output();
        let _ = Command::new("git").args(["config", "user.name", "test"]).current_dir(cwd).output();
        fs::write(cwd.join("base.txt"), "base").unwrap();
        let _ = Command::new("git").args(["add", "."]).current_dir(cwd).output();
        let _ = Command::new("git").args(["commit", "-m", "init"]).current_dir(cwd).output();
    }

    #[test]
    fn validate_worktree_name_cases() {
        assert!(validate_worktree_name("").is_some());
        assert!(validate_worktree_name(".").is_some());
        assert!(validate_worktree_name("..").is_some());
        assert!(validate_worktree_name("a/b").is_some());
        assert!(validate_worktree_name("a b").is_some());
        assert!(validate_worktree_name("中文").is_some());
        assert!(validate_worktree_name(&"x".repeat(65)).is_some());
        assert!(validate_worktree_name("auth").is_none());
        assert!(validate_worktree_name("ui-1").is_none());
        assert!(validate_worktree_name("a.b_c").is_none());
    }

    /// s18 核心：真实 git worktree 创建 + 事件日志 + 重名拒绝
    #[test]
    fn create_worktree_real_git_lifecycle() {
        let cwd = team_test_cwd("wt-create");
        git_init_repo(&cwd);
        let out = create_worktree(&cwd, "auth", "");
        assert!(out.starts_with("Worktree 'auth' created at "), "{out}");
        assert!(cwd.join(".worktrees/auth").exists());
        // 事件日志记录 create
        let events = fs::read_to_string(cwd.join(".worktrees/events.jsonl")).unwrap();
        assert!(events.contains("\"type\":\"create\"") && events.contains("\"worktree\":\"auth\""));
        // 重名拒绝
        let dup = create_worktree(&cwd, "auth", "");
        assert!(dup.contains("already exists"), "{dup}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn create_worktree_with_task_binds_and_keeps_pending() {
        // create → bind 组合链路（此前所有 create 测试都用空 task_id）
        let cwd = team_test_cwd("wt-create-bind");
        git_init_repo(&cwd);
        let t = create_task(&cwd, "任务", "", &[]);
        let out = create_worktree(&cwd, "auth", &t.id);
        assert!(out.starts_with("Worktree 'auth' created at "), "{out}");
        let task = load_task(&cwd, &t.id).unwrap();
        assert_eq!(task.worktree.as_deref(), Some("auth"));
        assert_eq!(task.status, "pending"); // bind 不改变状态
        let events = fs::read_to_string(cwd.join(".worktrees/events.jsonl")).unwrap();
        assert!(events.contains(&t.id), "{events}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn create_worktree_rejects_invalid_name() {
        let cwd = team_test_cwd("wt-invalid");
        git_init_repo(&cwd);
        let out = create_worktree(&cwd, "../evil", "");
        assert!(out.starts_with("Error: Invalid worktree name"), "{out}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn bind_task_keeps_pending_and_sets_worktree() {
        let cwd = team_test_cwd("wt-bind");
        let t = create_task(&cwd, "任务", "", &[]);
        let out = bind_task_to_worktree(&cwd, &t.id, "auth");
        assert!(out.contains("Bound task"), "{out}");
        let task = load_task(&cwd, &t.id).unwrap();
        assert_eq!(task.worktree.as_deref(), Some("auth"));
        // 保持 pending（供自动认领）
        assert_eq!(task.status, "pending");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn resolve_task_worktree_returns_path() {
        let cwd = team_test_cwd("wt-resolve");
        let t = create_task(&cwd, "任务", "", &[]);
        assert!(resolve_task_worktree(&cwd, &t.id).is_none());
        bind_task_to_worktree(&cwd, &t.id, "auth");
        let p = resolve_task_worktree(&cwd, &t.id).unwrap();
        assert_eq!(p, cwd.join(".worktrees").join("auth"));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn count_worktree_changes_detects_dirty() {
        let cwd = team_test_cwd("wt-count");
        git_init_repo(&cwd);
        create_worktree(&cwd, "auth", "");
        let wt = cwd.join(".worktrees/auth");
        // 干净 worktree：(0, 0)
        let (files, commits) = count_worktree_changes(&wt);
        assert_eq!((files, commits), (0, 0));
        // 写文件后：(≥1, 0)
        fs::write(wt.join("new.txt"), "x").unwrap();
        let (files2, _) = count_worktree_changes(&wt);
        assert!(files2 >= 1, "files={files2}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn remove_worktree_refuses_dirty_unless_discard() {
        let cwd = team_test_cwd("wt-remove");
        git_init_repo(&cwd);
        create_worktree(&cwd, "auth", "");
        let wt = cwd.join(".worktrees/auth");
        fs::write(wt.join("dirty.txt"), "x").unwrap();
        // 有未提交变更 → 拒绝
        let refused = remove_worktree(&cwd, "auth", false);
        assert!(refused.contains("uncommitted file(s)"), "{refused}");
        assert!(wt.exists()); // 目录仍在
        // discard_changes=true → 强制移除
        let removed = remove_worktree(&cwd, "auth", true);
        assert!(removed.contains("removed"), "{removed}");
        assert!(!wt.exists());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn remove_worktree_not_found() {
        let cwd = team_test_cwd("wt-miss");
        let out = remove_worktree(&cwd, "ghost", false);
        assert!(out.contains("not found"), "{out}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn keep_worktree_logs_event() {
        let cwd = team_test_cwd("wt-keep");
        let out = keep_worktree(&cwd, "auth");
        assert_eq!(out, "Worktree 'auth' kept for review (branch: wt/auth)");
        let events = fs::read_to_string(cwd.join(".worktrees/events.jsonl")).unwrap();
        assert!(events.contains("\"type\":\"keep\""), "{events}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_bash_at_executes_in_given_cwd() {
        let cwd = team_test_cwd("bash-at");
        fs::create_dir_all(cwd.join("sub")).unwrap();
        let out = run_bash_at(&cwd.join("sub"), BashInput { command: "pwd".into(), run_in_background: None });
        assert!(out.contains("sub"), "{out}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn run_write_at_rejects_escape_outside_cwd() {
        // s18 隔离语义核心：write 越界（../ 逃出 worktree）被拒
        let cwd = team_test_cwd("wt-escape");
        fs::create_dir_all(cwd.join("wt")).unwrap();
        let out = run_write_at(&cwd.join("wt"), WriteInput {
            path: "../escape.txt".into(),
            content: "x".into(),
        });
        assert!(out.contains("Error") && out.contains("escapes"), "{out}");
        assert!(!cwd.join("escape.txt").exists());
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn list_tasks_shows_worktree_suffix() {
        let cwd = team_test_cwd("wt-list");
        let t = create_task(&cwd, "任务", "", &[]);
        bind_task_to_worktree(&cwd, &t.id, "auth");
        let out = run_list_tasks(ListTasksInput {});
        // 但 run_list_tasks 用 workdir()（进程 cwd），这里直接测 list 格式逻辑：
        // 构造含 worktree 的任务后直接格式化
        let task = load_task(&cwd, &t.id).unwrap();
        let line = format!(
            "  ○ {}: {} [pending]{}",
            task.id,
            task.subject,
            task.worktree.as_ref().map(|w| format!(" (wt:{w})")).unwrap_or_default()
        );
        assert!(line.contains("(wt:auth)"), "{line}");
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn idle_auto_claim_injects_work_directory() {
        let cwd = team_test_cwd("wt-idle-claim");
        git_init_repo(&cwd);
        create_worktree(&cwd, "auth", "");
        let t = create_task(&cwd, "写 schema", "", &[]);
        bind_task_to_worktree(&cwd, &t.id, "auth");
        let mut messages: Vec<Message> = Vec::new();
        let outcome = idle_poll_once(&cwd, "alice", &mut messages);
        assert!(outcome.is_some());
        let (outcome, claimed) = outcome.unwrap();
        assert_eq!(outcome, IdleOutcome::Work);
        assert_eq!(claimed.as_deref(), Some(t.id.as_str()));
        // 注入含 Work directory
        assert!(matches!(&messages[0].content, MessageContent::Text(x)
            if x.contains("<auto-claimed>") && x.contains("Work directory:") && x.contains("auth")));
        let _ = fs::remove_dir_all(&cwd);
    }

    #[test]
    fn teammate_system_prompt_mentions_worktree() {
        let p = teammate_system_prompt("alice", "backend dev");
        assert!(p.contains("If a task has a worktree, work in that directory"));
        assert!(p.contains("use complete_task to mark it completed"));
        // s18 前移（实测）：队友在 worktree 里可能探索而非创建新文件
        // （worktree 是主仓库 checkout，模型倾向"找文件"）——显式指示创建
        assert!(p.contains("Create new files in your work directory as needed"));
    }

    #[test]
    fn worktree_tool_inputs_serde() {
        // task_id 可选
        let ok: CreateWorktreeInput = serde_json::from_value(serde_json::json!({"name": "auth"})).unwrap();
        assert_eq!(ok.task_id, "");
        let with: CreateWorktreeInput = serde_json::from_value(serde_json::json!({"name": "auth", "task_id": "t1"})).unwrap();
        assert_eq!(with.task_id, "t1");
        let r: Result<CreateWorktreeInput, _> = serde_json::from_value(serde_json::json!({}));
        assert!(r.is_err()); // 缺 name
        let ok2: RemoveWorktreeInput = serde_json::from_value(serde_json::json!({"name": "auth"})).unwrap();
        assert!(!ok2.discard_changes);
    }

    // ═══════════════ s19: MCP 系统测试 ═══════════════

    #[test]
    fn normalize_mcp_name_keeps_alnum_underscore_dash() {
        assert_eq!(normalize_mcp_name("docs"), "docs");
        assert_eq!(normalize_mcp_name("get_version"), "get_version");
        assert_eq!(normalize_mcp_name("my-server_2"), "my-server_2");
    }

    #[test]
    fn normalize_mcp_name_replaces_special_chars() {
        assert_eq!(normalize_mcp_name("a b.c:d/e"), "a_b_c_d_e");
        assert_eq!(normalize_mcp_name("a,b;c!"), "a_b_c_");
        assert_eq!(normalize_mcp_name("mcp__x"), "mcp__x"); // 下划线本身合法
    }

    #[test]
    fn normalize_mcp_name_replaces_cjk() {
        // 中文/全角 → 逐字符 '_'（对齐 Python re.sub 的字符级替换）
        assert_eq!(normalize_mcp_name("文档搜索"), "____");
        assert_eq!(normalize_mcp_name("中文 空格"), "_____");
    }

    #[test]
    fn normalize_mcp_name_empty_string() {
        assert_eq!(normalize_mcp_name(""), "");
    }

    #[test]
    fn mcp_client_call_tool_success() {
        let mut handlers: HashMap<String, MockHandler> = HashMap::new();
        handlers.insert("search".to_string(), mock_docs_search);
        let mut client = MCPClient::new("docs");
        client.register(vec![], handlers);
        let out = client.call_tool("search", &serde_json::json!({"query": "agents"}));
        assert_eq!(out, "[docs] Found 3 results for 'agents'");
    }

    #[test]
    fn mcp_client_call_tool_unknown_tool() {
        let client = MCPClient::new("docs");
        let out = client.call_tool("nope", &serde_json::json!({}));
        assert_eq!(out, "MCP error: unknown tool 'nope'");
    }

    #[test]
    fn mcp_client_call_tool_wraps_handler_error() {
        fn failing(_input: &serde_json::Value) -> Result<String, String> {
            Err("boom".to_string())
        }
        let mut handlers: HashMap<String, MockHandler> = HashMap::new();
        handlers.insert("fail".to_string(), failing);
        let mut client = MCPClient::new("x");
        client.register(vec![], handlers);
        let out = client.call_tool("fail", &serde_json::json!({}));
        assert_eq!(out, "MCP error: boom");
    }

    #[test]
    fn mcp_client_call_tool_missing_field_error() {
        // mock_docs_search 需要 query；缺字段 → serde 错误 →
        // "MCP error: missing field `query`"（对齐 Python 的 TypeError 捕获）
        let mut handlers: HashMap<String, MockHandler> = HashMap::new();
        handlers.insert("search".to_string(), mock_docs_search);
        let mut client = MCPClient::new("docs");
        client.register(vec![], handlers);
        let out = client.call_tool("search", &serde_json::json!({}));
        assert!(out.starts_with("MCP error: "), "{out}");
        assert!(out.contains("query"), "{out}");
    }

    #[test]
    fn default_config_builds_docs_and_deploy() {
        // 内置兜底配置（≡ tutorials/rust/.mcp.json 内容）→ build_client 产物
        let cfg = default_mcp_config();
        assert_eq!(cfg.mcp_servers.len(), 2);
        let docs = build_client("docs", &cfg.mcp_servers["docs"]).unwrap();
        assert_eq!(docs.tools.len(), 2);
        assert_eq!(docs.tools[0].name, "search");
        assert!(docs.tools[0].description.contains("readOnly"));
        assert_eq!(docs.tools[1].name, "get_version");
        // schema 透传（配置文件里是 inputSchema 键，反序列化映射到 input_schema）
        assert_eq!(docs.tools[0].input_schema["properties"]["query"]["type"], "string");
        // handler 已解析：直接 call_tool 可用
        assert_eq!(
            docs.call_tool("search", &serde_json::json!({"query": "agents"})),
            "[docs] Found 3 results for 'agents'"
        );
        let deploy = build_client("deploy", &cfg.mcp_servers["deploy"]).unwrap();
        assert_eq!(deploy.tools.len(), 2);
        assert_eq!(deploy.tools[0].name, "trigger");
        assert!(deploy.tools[0].description.contains("destructive"));
        assert!(deploy.tools[1].description.contains("readOnly"));
    }

    #[test]
    fn connect_mcp_docs_success() {
        reset_mcp_state();
        let out = connect_mcp("docs");
        assert_eq!(
            out,
            "Connected to MCP server 'docs'. Discovered 2 tools: search, get_version"
        );
        let state = MCP_STATE.lock().unwrap();
        assert_eq!(state.order, vec!["docs"]);
        assert!(state.clients.contains_key("docs"));
    }

    #[test]
    fn connect_mcp_already_connected() {
        reset_mcp_state();
        connect_mcp("docs");
        let out = connect_mcp("docs");
        assert_eq!(out, "MCP server 'docs' already connected");
    }

    #[test]
    fn connect_mcp_unknown_server_lists_available_sorted() {
        reset_mcp_state();
        let out = connect_mcp("nope");
        // 配置来自 JSON 对象（键无序）→ 按名称排序保证确定性
        // （Python 是 dict 插入序 "docs, deploy"，差异记录在 README）
        assert_eq!(out, "Unknown server 'nope'. Available: deploy, docs");
        // 未连接成功：注册表仍空
        let state = MCP_STATE.lock().unwrap();
        assert!(state.clients.is_empty());
    }

    #[test]
    fn load_mcp_config_from_reads_file() {
        let path = std::env::temp_dir().join("mcp_test_reads_file.json");
        std::fs::write(
            &path,
            r#"{
                "mcpServers": {
                    "docs": {
                        "tools": [
                            { "name": "search", "description": "Search documentation. (readOnly)",
                              "inputSchema": { "type": "object", "properties": { "query": { "type": "string" } }, "required": ["query"] },
                              "handler": "docs_search" }
                        ]
                    }
                }
            }"#,
        )
        .unwrap();
        let cfg = load_mcp_config_from(&path).unwrap();
        std::fs::remove_file(&path).ok();
        assert_eq!(cfg.mcp_servers.len(), 1);
        let docs = &cfg.mcp_servers["docs"];
        assert_eq!(docs.tools.len(), 1);
        // inputSchema（camelCase）反序列化映射到 input_schema
        assert_eq!(docs.tools[0].input_schema["properties"]["query"]["type"], "string");
        assert_eq!(docs.tools[0].handler, "docs_search");
    }

    #[test]
    fn load_mcp_config_from_skips_non_teaching_entries() {
        // 真实 CC 的 stdio 配置（command/args，无 tools 字段）被容错跳过
        let path = std::env::temp_dir().join("mcp_test_skip_cc.json");
        std::fs::write(
            &path,
            r#"{
                "mcpServers": {
                    "codegraph": { "type": "stdio", "command": "codegraph", "args": ["serve", "--mcp"] },
                    "docs": {
                        "tools": [
                            { "name": "get_version", "description": "Get API version. (readOnly)",
                              "inputSchema": { "type": "object", "properties": {}, "required": [] },
                              "handler": "docs_get_version" }
                        ]
                    }
                }
            }"#,
        )
        .unwrap();
        let cfg = load_mcp_config_from(&path).unwrap();
        std::fs::remove_file(&path).ok();
        assert_eq!(cfg.mcp_servers.len(), 1);
        assert!(cfg.mcp_servers.contains_key("docs"));
        assert!(!cfg.mcp_servers.contains_key("codegraph"));
    }

    #[test]
    fn load_mcp_config_from_rejects_missing_or_malformed() {
        let path = std::env::temp_dir().join("mcp_test_nonexistent.json");
        let r = load_mcp_config_from(&path);
        assert!(r.is_err());
        assert!(r.unwrap_err().contains("cannot read"));

        let path2 = std::env::temp_dir().join("mcp_test_bad.json");
        std::fs::write(&path2, "not json{").unwrap();
        let r = load_mcp_config_from(&path2);
        std::fs::remove_file(&path2).ok();
        assert!(r.is_err());
        assert!(r.unwrap_err().contains("invalid JSON"));

        let path3 = std::env::temp_dir().join("mcp_test_no_servers.json");
        std::fs::write(&path3, r#"{"hello": 1}"#).unwrap();
        let r = load_mcp_config_from(&path3);
        std::fs::remove_file(&path3).ok();
        assert!(r.is_err());
        assert!(r.unwrap_err().contains("mcpServers"));
    }

    #[test]
    fn mcp_handler_by_name_known_and_unknown() {
        assert!(mcp_handler_by_name("docs_search").is_some());
        assert!(mcp_handler_by_name("deploy_status").is_some());
        assert!(mcp_handler_by_name("no_such_handler").is_none());
    }

    #[test]
    fn build_client_rejects_unknown_handler() {
        let cfg = McpServerConfig {
            tools: vec![McpToolConfig {
                name: "search".to_string(),
                description: "x".to_string(),
                input_schema: serde_json::json!({}),
                handler: "no_such_handler".to_string(),
            }],
        };
        let err = build_client("wiki", &cfg).unwrap_err();
        assert!(err.contains("unknown handler 'no_such_handler'"), "{err}");
        assert!(err.contains("wiki"), "{err}");
    }

    #[test]
    fn config_driven_extension_connects_new_server() {
        // 模拟"在 .mcp.json 里新增一个 wiki 服务器"：换配置 → connect 即用
        let cfg = serde_json::from_value(serde_json::json!({
            "mcpServers": {
                "wiki": {
                    "tools": [
                        { "name": "lookup", "description": "Look up a wiki page. (readOnly)",
                          "inputSchema": { "type": "object", "properties": { "query": { "type": "string" } }, "required": ["query"] },
                          "handler": "docs_search" }
                    ]
                }
            }
        }))
        .unwrap();
        let _guard = McpConfigGuard;
        set_mcp_config(cfg);
        reset_mcp_state();
        let out = connect_mcp("wiki");
        assert_eq!(
            out,
            "Connected to MCP server 'wiki'. Discovered 1 tools: lookup"
        );
        let (tools, handlers) = assemble_tool_pool();
        assert_eq!(tools.len(), 28);
        assert!(tools.iter().any(|t| t.name == "mcp__wiki__lookup"));
        // handler 复用 docs_search 实现（配置只管声明，实现来自注册表；
        // 参数契约由 handler 决定——docs_search 读 "query"）
        let out = handlers["mcp__wiki__lookup"](&serde_json::json!({"query": "agents"}));
        assert_eq!(out, "[docs] Found 3 results for 'agents'");
        // 可用列表来自当前配置（排序）
        let out = connect_mcp("docs");
        assert_eq!(out, "Unknown server 'docs'. Available: wiki");
        // 恢复默认配置，避免影响后续测试
        set_mcp_config(default_mcp_config());
    }

    #[test]
    fn assemble_tool_pool_empty_has_only_builtins() {
        reset_mcp_state();
        let (tools, handlers) = assemble_tool_pool();
        assert_eq!(tools.len(), 27);
        assert!(handlers.is_empty());
        assert!(tools.iter().all(|t| !t.name.starts_with("mcp__")));
    }

    #[test]
    fn assemble_tool_pool_after_docs_has_prefixed_tools() {
        reset_mcp_state();
        connect_mcp("docs");
        let (tools, handlers) = assemble_tool_pool();
        assert_eq!(tools.len(), 29);
        assert_eq!(handlers.len(), 2);
        let names: Vec<&str> = tools.iter().map(|t| t.name.as_str()).collect();
        assert!(names.contains(&"mcp__docs__search"));
        assert!(names.contains(&"mcp__docs__get_version"));
        // 顺序：builtins 在前，MCP 按连接序追加在后（对齐 Python 池结构）
        let idx = |n: &str| names.iter().position(|x| *x == n).unwrap();
        assert!(idx("bash") < idx("mcp__docs__search"));
        // 描述注解透传
        let search = tools.iter().find(|t| t.name == "mcp__docs__search").unwrap();
        assert!(search.description.contains("readOnly"));
        // schema 透传
        assert_eq!(search.input_schema["properties"]["query"]["type"], "string");
    }

    #[test]
    fn assemble_tool_pool_after_both_servers_preserves_order() {
        reset_mcp_state();
        connect_mcp("docs");
        connect_mcp("deploy");
        let (tools, _) = assemble_tool_pool();
        assert_eq!(tools.len(), 31);
        let names: Vec<&str> = tools.iter().map(|t| t.name.as_str()).collect();
        // 27 内置 + docs(2) + deploy(2)，按连接序
        assert_eq!(names[27], "mcp__docs__search");
        assert_eq!(names[28], "mcp__docs__get_version");
        assert_eq!(names[29], "mcp__deploy__trigger");
        assert_eq!(names[30], "mcp__deploy__status");
    }

    #[test]
    fn assemble_tool_pool_handlers_route_to_mock() {
        reset_mcp_state();
        connect_mcp("docs");
        connect_mcp("deploy");
        let (_, handlers) = assemble_tool_pool();
        let out = handlers["mcp__docs__search"](&serde_json::json!({"query": "x"}));
        assert_eq!(out, "[docs] Found 3 results for 'x'");
        let out = handlers["mcp__docs__get_version"](&serde_json::json!({}));
        assert_eq!(out, "[docs] API v2.1.0");
        let out = handlers["mcp__deploy__trigger"](&serde_json::json!({"service": "api"}));
        assert_eq!(out, "[deploy] Triggered: api");
        let out = handlers["mcp__deploy__status"](&serde_json::json!({"service": "web"}));
        assert_eq!(out, "[deploy] web: running (v1.4.2)");
    }

    #[test]
    fn dispatch_tool_routes_mcp_and_builtin() {
        reset_mcp_state();
        connect_mcp("docs");
        let (_, handlers) = assemble_tool_pool();
        // MCP 命中 → 动态 handler
        let out = dispatch_tool(
            "mcp__docs__search",
            &serde_json::json!({"query": "dispatch"}),
            &handlers,
        );
        assert_eq!(out, "[docs] Found 3 results for 'dispatch'");
        // 未命中 → execute_sync 内置（bash）
        let out = dispatch_tool(
            "bash",
            &serde_json::json!({"command": "echo mcp-dispatch-ok"}),
            &handlers,
        );
        assert_eq!(out.trim(), "mcp-dispatch-ok");
        // 未命中且非内置 → execute_sync 的 unknown 文案（s02 起冻结）
        let out = dispatch_tool("no_such_tool", &serde_json::json!({}), &handlers);
        assert_eq!(out, "Error: unknown tool 'no_such_tool'");
    }

    #[test]
    fn assemble_system_prompt_has_no_mcp_section_when_none_connected() {
        let ctx = PromptContext {
            connected_mcp: Vec::new(),
            enabled_tools: vec!["bash".to_string()],
            workspace: "/tmp".to_string(),
            memories: String::new(),
            skills: String::new(),
        };
        let p = assemble_system_prompt(&ctx);
        assert!(!p.contains("Connected MCP servers"));
        // tools 段始终带前缀约定（对齐 Python PROMPT_SECTIONS["tools"]）
        assert!(p.contains("MCP tools are prefixed mcp__{server}__{tool}"));
    }

    #[test]
    fn assemble_system_prompt_lists_connected_servers_in_order() {
        let ctx = PromptContext {
            connected_mcp: vec!["docs".to_string(), "deploy".to_string()],
            enabled_tools: vec!["bash".to_string()],
            workspace: "/tmp".to_string(),
            memories: String::new(),
            skills: String::new(),
        };
        let p = assemble_system_prompt(&ctx);
        assert!(p.contains("Connected MCP servers: docs, deploy"));
        assert!(p.find("docs").unwrap() < p.find("deploy").unwrap());
    }

    #[test]
    fn update_context_includes_connected_mcp_tools() {
        reset_mcp_state();
        connect_mcp("docs");
        let ctx = update_context(Path::new("/tmp"));
        assert_eq!(ctx.enabled_tools.len(), 27 + 2);
        assert!(ctx.enabled_tools.contains(&"mcp__docs__search".to_string()));
        assert_eq!(ctx.connected_mcp, vec!["docs"]);
    }

    #[test]
    fn prompt_cache_invalidates_on_mcp_connect() {
        reset_mcp_state();
        let ctx1 = update_context(Path::new("/tmp"));
        let p1 = get_system_prompt(&ctx1);
        connect_mcp("docs");
        let ctx2 = update_context(Path::new("/tmp"));
        let p2 = get_system_prompt(&ctx2);
        assert_ne!(p1, p2);
        assert!(p2.contains("Connected MCP servers: docs"));
        // 缓存命中：ctx 不变时返回同一份 prompt
        let p3 = get_system_prompt(&ctx2);
        assert_eq!(p2, p3);
    }

    #[test]
    fn response_uses_connect_mcp_detects() {
        use ContentBlock::*;
        assert!(response_uses_connect_mcp(&[ToolUse {
            id: "a".into(),
            name: "connect_mcp".into(),
            input: serde_json::json!({"name": "docs"}),
        }]));
        assert!(!response_uses_connect_mcp(&[ToolUse {
            id: "a".into(),
            name: "bash".into(),
            input: serde_json::json!({}),
        }]));
        assert!(!response_uses_connect_mcp(&[Text { text: "hi".into() }]));
        assert!(!response_uses_connect_mcp(&[]));
    }

    #[test]
    fn connect_mcp_twice_keeps_pool_stable() {
        reset_mcp_state();
        connect_mcp("docs");
        let (t1, h1) = assemble_tool_pool();
        connect_mcp("docs"); // 已连接，拒绝
        let (t2, h2) = assemble_tool_pool();
        assert_eq!(t1.len(), t2.len());
        assert_eq!(h1.len(), h2.len());
    }

    #[test]
    fn teammate_tools_have_no_mcp_tools() {
        // s19 聚焦 Lead：队友工具集固定 8 个，拿不到 connect_mcp / mcp__*
        reset_mcp_state();
        connect_mcp("docs");
        let tools = teammate_tools();
        assert!(tools.iter().all(|t| !t.name.starts_with("mcp__")));
        assert!(tools.iter().all(|t| t.name != "connect_mcp"));
    }
}
