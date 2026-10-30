"""Runtime 对外协议和 AgentSnapshot 数据模型。

本模块使用 Pydantic 定义调用方提交的快照、运行请求、Sandbox 响应、会话消息和记忆对象。
模型负责字段类型、范围和跨字段关系校验；认证身份、租户归属和部署级安全策略由 API、Principal
和 Admission 层负责，不能通过请求体模型绕过。
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    """模型提供商和模型调用参数。

    调用方可以在 AgentSnapshot 中声明模型名称和温度；允许的 Provider、模型名称以及凭证
    仍由 Runtime 部署配置和准入策略决定。
    """

    provider: str = "openai"
    name: str
    # 省略时使用 Runtime 的 MODEL_TEMPERATURE；调用方显式传值时覆盖部署默认值。
    temperature: float | None = Field(default=None, ge=0, le=2)


class SkillSnapshot(BaseModel):
    """Agent 使用的 Skill 来源声明。

    生产调用方应提供不可变的 ``bundle_url`` 和 ``sha256``，Runtime 下载后校验摘要并加载。
    ``content`` 仅作为本地开发兼容方式保留，是否允许由 ``ALLOW_INLINE_SKILLS`` 决定；模型
    不保存任何凭证或可绕过供应链校验的隐藏字段。
    """

    id: str
    version: str | int
    bundle_url: str | None = None
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=1)
    entry_path: str | None = None
    required_tools: list[str] = Field(default_factory=list)
    content: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "SkillSnapshot":
        """确保 Skill 恰好声明一种来源，并拒绝空的内联内容或 URL。"""
        has_bundle = bool(self.bundle_url and self.bundle_url.strip())
        has_content = bool(self.content and self.content.strip())
        if has_bundle == has_content:
            raise ValueError(
                "SkillSnapshot must provide exactly one of bundle_url or content"
            )
        if self.bundle_url and not self.bundle_url.strip():
            self.bundle_url = None
        return self


class MCPServerConfig(BaseModel):
    """Agent 使用的 MCP 服务声明。

    ``credential_ref`` 只引用 Runtime 部署侧的凭证注册表，不能把 Secret 直接放入快照。
    URL、传输协议、Header 和工具白名单还要经过 MCP 网络准入校验。
    """

    id: str
    transport: Literal["streamable_http", "sse", "stdio"] = "streamable_http"
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    credential_ref: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)


class AsyncSubAgentSnapshot(BaseModel):
    """远程异步子 Agent 的声明。

    运行时只负责按要求把任务提交到 Agent Protocol 服务并轮询结果；远端 Agent 的
    模型、工具与权限由该服务自己负责。URL 必须通过部署级 Host 白名单校验。
    """

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    graph_id: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    update_strategy: Literal["interrupt", "enqueue"] = "interrupt"


class PlanConfig(BaseModel):
    """Agent 计划执行策略。

    该模型只表达单次快照请求的计划偏好；审批、步骤上限和实际执行状态由 Runtime 生命周期控制。
    """

    enabled: bool = False
    require_approval: bool = False
    max_steps: int = Field(default=10, ge=1, le=1000)
    allow_replan: bool = True
    # 是否启用 write_todos 工具：开启后计划从"Prompt 要求"变成"可观测的结构化状态"。
    todo_tool: bool = False


class CompressionConfig(BaseModel):
    """会话上下文压缩策略。"""

    enabled: bool = True
    trigger_tokens: int = Field(default=24_000, ge=1_000)
    keep_recent_messages: int = Field(default=12, ge=1)
    summary_max_tokens: int = Field(default=3_000, ge=256)
    persist_summary: bool = True


class RAGConfig(BaseModel):
    """RAG 能力开关及允许使用的检索工具。"""

    enabled: bool = False
    tool_allowlist: list[str] = Field(default_factory=list)


class WorkspaceConfig(BaseModel):
    """Agent 工作区的声明式访问策略。

    ``workspace_id`` 和路径列表只表达请求意图，最终路径隔离和读写权限由 Sandbox Provider 执行。
    """

    enabled: bool = False
    workspace_id: str | None = None
    read_only: bool = True
    allowed_paths: list[str] = Field(default_factory=list)


class SandboxConfig(BaseModel):
    """一次 Agent Run 请求的隔离 Sandbox 策略。

    字段是调用方请求的上限，不是对外部 Sandbox Gateway 平台策略的覆盖。Provider 必须采用
    更严格的租户、资源、命令、网络和输出限制；公共模式下尤其不能通过快照开启宿主机执行。
    """

    enabled: bool = False
    image: str | None = None
    image_digest: str | None = None
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    cpu_limit: float | None = Field(default=None, gt=0, le=64)
    memory_limit_mb: int | None = Field(default=None, ge=128, le=262_144)
    disk_limit_mb: int | None = Field(default=None, ge=128, le=1_048_576)
    max_output_bytes: int = Field(default=1_048_576, ge=1024, le=50_000_000)
    max_processes: int = Field(default=64, ge=1, le=10_000)
    network_mode: Literal["none", "restricted", "full"] = "none"
    allow_commands: list[str] = Field(default_factory=list)


class SandboxCreateResponse(BaseModel):
    """Sandbox 创建接口返回的会话标识和生命周期信息。"""

    sandbox_id: str
    status: Literal["CREATING", "READY", "RUNNING", "EXPIRED", "DESTROYED"] = "READY"
    workspace_path: str = "/workspace"
    expires_at: datetime | None = None


class SandboxFileResponse(BaseModel):
    """Sandbox 文件读取接口的内容和完整性信息。"""

    path: str
    content_base64: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None


class SandboxCommandResult(BaseModel):
    """Sandbox 结构化命令执行结果。

    Runtime 通过该模型区分正常退出、超时、失败和被杀死，并保留截断标记，避免调用方把
    不完整的标准输出误认为完整结果。
    """

    status: Literal["RUNNING", "COMPLETED", "TIMED_OUT", "FAILED", "KILLED"]
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    duration_ms: int | None = Field(default=None, ge=0)


class SandboxArtifact(BaseModel):
    """Sandbox 产物的受控下载信息和摘要。"""

    artifact_id: str
    file_name: str
    size_bytes: int = Field(ge=0)
    download_url: str | None = None
    sha256: str | None = None


class AgentRuntimeConfig(BaseModel):
    """Root Agent 和 SubAgent 共享的执行配置。

    这里描述模型、Skill 引用、MCP、工具、计划、工作区、Sandbox 和步骤上限。它不是认证
    或租户策略，部署级上限会在 Admission 阶段再次覆盖和校验。
    """

    system_prompt: str | None = None
    model: ModelConfig | None = None
    skill_ids: list[str] = Field(default_factory=list)
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    tool_allowlist: list[str] = Field(default_factory=list)
    subagents: list["SubAgentSnapshot"] = Field(default_factory=list)
    plan: PlanConfig = Field(default_factory=PlanConfig)
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    max_steps: int = Field(default=20, ge=1, le=1000)
    # 工具级人工确认：工具名 → 是否在执行前中断等待人工决策。None/空表示不启用。
    interrupt_on: dict[str, bool] | None = None
    # 结构化输出：JSON Schema（根节点必须是 object）。None 表示自由文本答案。
    response_format: dict[str, Any] | None = None
    # AGENTS.md 记忆文件路径（相对 Agent 工作区根）。None 表示不加载记忆文件。
    memory_sources: list[str] | None = None
    # 自评标准（"什么样算完成"）。声明后由 RubricMiddleware 迭代评分，未达标会继续改进。
    rubric: str | None = Field(default=None, max_length=8000)
    # 远程异步子 Agent（Agent Protocol 服务）；数量与 Host 受部署策略限制。
    async_subagents: list["AsyncSubAgentSnapshot"] | None = None

    @model_validator(mode="after")
    def validate_optional_capabilities(self) -> "AgentRuntimeConfig":
        """校验工具级确认、结构化输出与记忆路径的形态与规模上限。

        这些字段属于"可选能力开关"：缺省时行为与旧版本完全一致；一旦提供，必须在准入前
        拒绝明显越界或无法执行的配置，避免把错误推迟到 Worker 侧构建阶段。
        """
        if self.interrupt_on is not None:
            if len(self.interrupt_on) > 50:
                raise ValueError("interrupt_on supports at most 50 tools")
            for tool_name in self.interrupt_on:
                if not tool_name.strip():
                    raise ValueError("interrupt_on tool name must not be empty")
        if (
            self.response_format is not None
            and self.response_format.get("type") != "object"
        ):
            raise ValueError("response_format root schema type must be 'object'")
        if self.rubric is not None and not self.rubric.strip():
            raise ValueError("rubric must not be blank when provided")
        if self.async_subagents is not None:
            if len(self.async_subagents) > 10:
                raise ValueError("async_subagents supports at most 10 entries")
            names = [item.name for item in self.async_subagents]
            if len(names) != len(set(names)):
                raise ValueError("async_subagents names must be unique")
            for item in self.async_subagents:
                if not item.url.lower().startswith(("https://", "http://")):
                    raise ValueError(
                        f"async subagent {item.name!r} url must be absolute HTTP(S)"
                    )
        if self.memory_sources is not None:
            if len(self.memory_sources) > 20:
                raise ValueError("memory_sources supports at most 20 files")
            for path in self.memory_sources:
                if not path.startswith("/") or ".." in path or "\\" in path:
                    raise ValueError(
                        f"memory_sources path must be an absolute workspace path: {path!r}"
                    )
        return self


class SubAgentSnapshot(AgentRuntimeConfig):
    """DeepAgents SubAgent 的完整执行快照。

    ``mode`` 决定 SubAgent 是隔离构建还是 Fork 父上下文；每个 SubAgent 可以声明自己的
    模型、工具和 Sandbox。``model_name`` 仅用于兼容旧快照，新调用方应使用 ``model``。
    """

    name: str
    description: str
    mode: Literal["isolated", "fork"] = "isolated"
    model_name: str | None = None

    @model_validator(mode="after")
    def normalize_legacy_model(self) -> "SubAgentSnapshot":
        """把旧版 ``model_name`` 迁移为统一的 ``ModelConfig``，并校验 Fork 限制。"""
        if self.model is None and self.model_name:
            self.model = ModelConfig(name=self.model_name)
        if self.mode == "fork" and self.skill_ids:
            raise ValueError("fork SubAgents cannot declare skill_ids")
        return self


class AgentSnapshot(AgentRuntimeConfig):
    """一次可构建、可执行的 Agent 完整快照。

    快照是 Runtime 的核心输入，包含 Agent 身份、系统提示词、模型、Skill、MCP、Sandbox、
    SubAgent 和执行限制。它可以来自 Java 控制面、Web、Python 或其他合法调用方；Runtime
    只要求通过 HMAC 认证、Scope 鉴权和公共准入策略，不依赖特定上游系统。
    """

    id: str
    version: int
    name: str = "Data Analysis Agent"
    system_prompt: str
    model: ModelConfig
    skills: list[SkillSnapshot] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "AgentSnapshot":
        """校验 Skill 与 SubAgent 引用，阻止重复 ID、重复名称和悬空引用。"""
        skill_ids = [skill.id for skill in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("AgentSnapshot contains duplicate Skill ids")

        known_skills = set(skill_ids)
        seen_names: set[str] = set()

        def validate_subagents(
            specs: list[SubAgentSnapshot], parent_path: str = ""
        ) -> None:
            """递归校验 SubAgent 名称唯一性和 Skill 引用完整性。"""
            for spec in specs:
                path = f"{parent_path}/{spec.name}" if parent_path else spec.name
                if spec.name in seen_names:
                    raise ValueError(
                        f"AgentSnapshot contains duplicate SubAgent name: {spec.name!r}"
                    )
                seen_names.add(spec.name)
                missing = sorted(set(spec.skill_ids) - known_skills)
                if missing:
                    raise ValueError(
                        f"SubAgent {path!r} references unavailable Skills: {missing}"
                    )
                validate_subagents(spec.subagents, path)

        validate_subagents(self.subagents)
        return self


class UserContext(BaseModel):
    """绑定到 Run 的调用方上下文。

    API 在 HMAC 认证后由 Principal 注入这些字段；请求体提供的同名身份不能覆盖认证结果。
    配额字段仅用于把认证方的有效部署策略传递给 Worker。
    """

    principal_id: str | None = None
    user_id: str
    tenant_id: str
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    max_steps: int | None = Field(default=None, ge=1)
    run_timeout_seconds: int | None = Field(default=None, ge=1)
    max_concurrent_runs: int | None = Field(default=None, ge=1)


class FileAttachment(BaseModel):
    """一次 Run 引用的上传文件。

    ``file_id`` 由 ``POST /v1/files`` 返回；``media_type`` 用于判断是表格、PDF 还是图片。
    文件内容本身不进入请求体，避免把二进制塞进任务流。
    """

    file_id: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=255)
    media_type: str | None = Field(default=None, max_length=200)


class RunRequest(BaseModel):
    """提交给 Runtime 的一次 Agent Run 请求。

    API 负责认证、快照准入、身份绑定和 Redis 入队，Worker 负责真正构建并执行 Agent。
    ``internal_token`` 仅为历史反序列化兼容字段，正常请求和任务负载都不得携带它。
    """

    run_id: str
    message: str = Field(min_length=1)
    stream: bool = False
    agent: AgentSnapshot
    user_context: UserContext | None = None
    internal_token: str | None = None
    session_id: str | None = None
    # 可选附件：运行时在构建 Agent 前读取并注入（表格/PDF 转文本，图片走多模态）。
    attachments: list[FileAttachment] | None = None


class RunResumeRequest(BaseModel):
    """恢复一次等待人工确认的 Run。

    ``decisions`` 与中断里的 ``action_requests`` 按位置一一对应；每项至少包含
    ``type``（approve / edit / reject / respond），具体字段由被中断的工具决定。
    """

    decisions: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_decisions(self) -> "RunResumeRequest":
        """校验决策类型合法，避免把无法识别的动作透传给执行引擎。"""
        allowed = {"approve", "edit", "reject", "respond"}
        for decision in self.decisions:
            if decision.get("type") not in allowed:
                raise ValueError(
                    f"decision type must be one of {sorted(allowed)}"
                )
        return self


class ConversationMessage(BaseModel):
    """Session 历史中的一条用户或 Agent 消息。"""

    message_id: str
    session_id: str
    run_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class MemoryItem(BaseModel):
    """Runtime 长期记忆中的一条租户和用户隔离记录。"""

    memory_id: str
    tenant_id: str
    user_id: str
    memory_type: Literal["preference", "fact", "summary"] = "fact"
    key: str
    content: str
    source_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryUpsertRequest(BaseModel):
    """创建或更新长期记忆的请求体。

    路径中的租户、用户和记忆 ID 必须与请求体一致，并由 API 对照 Principal 校验归属。
    """

    memory_id: str
    tenant_id: str
    user_id: str
    memory_type: Literal["preference", "fact", "summary"] = "fact"
    key: str
    content: str = Field(min_length=1)
    source_run_id: str | None = None


class RunAccepted(BaseModel):
    """Run 入队成功后的异步受理响应。"""

    run_id: str
    status: Literal["ACCEPTED", "PENDING_APPROVAL"] = "ACCEPTED"


class RunEvent(BaseModel):
    """Redis Event Stream 中对外暴露的运行事件。

    ``sequence`` 用于同一 Run 内排序；API 转换为 SSE 时会把 Redis Stream ID 作为 SSE ``id``，
    事件类型作为 ``event``，整个对象作为 JSON ``data``。
    """

    run_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
