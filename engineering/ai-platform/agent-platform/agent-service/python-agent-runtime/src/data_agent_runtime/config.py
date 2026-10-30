"""本文件模块职责：Python Runtime 的部署级配置模块。

本模块从环境变量和 .env 文件加载服务、Redis、PostgreSQL、模型、Skill、队列、Worker、Sandbox 和安全参数，并通过 Pydantic 完成类型转换与默认值管理；Agent Snapshot 负责单次 Run 配置，不能覆盖部署安全边界。
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime 的部署级配置集合。

    配置来自环境变量或本地 ``.env`` 文件，包含 API、Redis、模型、MCP、Skill、Sandbox、
    Checkpointer、队列和安全策略。这里定义的是服务级边界；调用方提交的 AgentSnapshot
    只能请求更小的能力，不能提升这些上限或替换认证凭证。
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "data-agent-runtime"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    # 是否输出 JSON 结构化日志；生产环境建议保持 true，便于日志平台检索和聚合。
    log_json: bool = True
    # 是否对日志消息、异常、Header、连接串和结构化 extra 字段执行脱敏。
    log_redaction_enabled: bool = True
    # OpenTelemetry 资源中的实例标识；未指定时由部署系统或主机名补充。
    service_instance_id: str = ""

    # 外部调用方的 HMAC 凭证注册表。每个调用方必须独立配置 AK/SK、Principal、
    # Tenant 和 Scope；Secret 仅通过部署 Secret 注入，Runtime 不提供单 AK/SK fallback。
    internal_service_credentials_json: str | None = None
    # 公共服务模式会强制启用资源归属、Snapshot Admission 和供应链安全策略。
    public_mode: bool = False
    redis_url: str = "redis://localhost:6379/0"
    # Redis 客户端韧性：超时、重试与连接池上限。缺少这些设置时，一次网络抖动就可能让
    # API 或 Worker 永久阻塞在读写上（没有自愈能力）。
    redis_socket_timeout_seconds: float = 5.0
    redis_socket_connect_timeout_seconds: float = 5.0
    redis_retry_attempts: int = 3
    redis_retry_backoff_base_seconds: float = 0.05
    redis_retry_backoff_cap_seconds: float = 1.0
    redis_health_check_interval_seconds: int = 30
    redis_max_connections: int = 50
    # 优雅停机：收到 SIGTERM 后等待当前 Run 完成的最长时间，超时则取消并留给重投递。
    shutdown_timeout_seconds: float = 60.0
    # 入口限流：每个调用方每分钟允许提交的 Run 数；0 表示关闭限流。
    rate_limit_runs_per_minute: int = 60
    # 背压：任务流长度超过该水位时拒绝新提交（低于 TASK_STREAM_MAXLEN 以预留缓冲）。
    task_max_queue_depth: int = 80_000

    # Sandbox Provider 的默认 HTTP 契约与实现方解耦：http 表示任意实现该契约的网关。
    # Python Runtime 不在宿主机直接执行调用方命令。
    sandbox_provider: str = "http"
    sandbox_gateway_base_url: str | None = None
    sandbox_gateway_access_key: str | None = None
    sandbox_gateway_secret_key: str | None = None
    sandbox_connect_timeout_seconds: float = 5.0
    sandbox_read_timeout_seconds: float = 90.0
    # 本地 APP_ENV=local 时允许 HTTP 联调；生产环境必须保持 true，否则安全失败。
    hmac_require_https: bool = True
    hmac_clock_skew_seconds: int = 300
    hmac_nonce_ttl_seconds: int = 300
    # Snapshot 的部署级硬上限；最终生效值取 Snapshot、Principal 配额和部署上限的最小值。
    max_prompt_chars: int = 200_000
    max_snapshot_skills: int = 100
    max_snapshot_mcp_servers: int = 50
    max_snapshot_subagent_depth: int = 5
    max_snapshot_tool_count: int = 200
    allowed_model_names: str = ""
    allowed_model_providers: str = "openai,openai-compatible"
    allowed_mcp_hosts: str = ""
    # 异步子 Agent（远程 Agent Protocol 服务）的 Host 白名单；public_mode 下必填。
    allowed_subagent_hosts: str = ""
    # 附件上传：单文件大小、保留时长、单次 Run 附件数与注入模型的文本上限。
    max_upload_bytes: int = 10 * 1024 * 1024
    upload_ttl_seconds: int = 3600
    max_attachments: int = 5
    attachment_max_chars: int = 20_000
    attachment_preview_rows: int = 20
    # 允许图片输入的模型名白名单（逗号分隔）；为空表示不接受图片附件。
    allowed_vision_models: str = ""
    # MCP 服务端凭证注册表；Snapshot 仅携带 credential_ref，不携带 Secret。
    # 生产环境应由 Secret 管理系统注入 JSON，禁止写入代码仓库。
    mcp_credentials_json: str | None = None
    allow_mcp_stdio: bool = False
    allow_inline_skills: bool = True
    max_concurrent_runs_per_principal: int = 20
    max_sandbox_timeout_seconds: int = 3600
    max_sandbox_output_bytes: int = 50_000_000
    max_sandbox_processes: int = 10_000
    max_sandbox_cpu_limit: float = 64.0
    max_sandbox_memory_mb: int = 262_144
    max_sandbox_disk_mb: int = 1_048_576
    allowed_sandbox_images: str = ""
    # 本地 Provider 的控制面可执行文件只负责管理隔离容器或 Pod，绝不作为 Agent 命令 Shell。
    docker_binary: str = "docker"
    docker_default_image: str = "python:3.12-slim"
    docker_control_timeout_seconds: float = 30.0
    kubectl_binary: str = "kubectl"
    kubernetes_namespace: str = "data-agent"
    kubernetes_kubeconfig: str | None = None
    kubernetes_context: str | None = None
    kubernetes_default_image: str = "python:3.12-slim"
    kubernetes_control_timeout_seconds: float = 120.0
    event_stream_maxlen: int = 10_000
    # 本地开发浏览器允许的来源；生产环境必须显式收紧为可信前端域名。
    cors_allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    conversation_history_max_messages: int = 100
    long_term_memory_max_items: int = 50
    checkpoint_backend: Literal["memory", "postgres"] = "memory"
    postgres_dsn: str | None = None
    # Agent 的跨会话键值存储（LangGraph BaseStore）：none / memory / postgres。
    # 用于跨会话记忆与工具产物等需要跨 Run 读取的数据；postgres 时复用 POSTGRES_DSN。
    agent_store_backend: Literal["none", "memory", "postgres"] = "memory"

    # OpenAI 及 OpenAI 兼容模型网关配置。
    model_provider: str = "openai"
    model_name: str = Field(default="gpt-4o-mini", alias="MODEL_NAME")
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    model_temperature: float = 0.1

    # Runtime 执行安全上限。
    max_steps: int = 20
    run_timeout_seconds: int = 300
    run_state_ttl_seconds: int = 7 * 24 * 60 * 60

    # 持久化 Agent 任务队列；API 负责入队，独立 Worker 负责消费和执行。
    task_stream_key: str = "agent:tasks"
    task_consumer_group: str = "data-agent-workers"
    task_consumer_name: str | None = None
    task_stream_maxlen: int = 100_000
    task_dead_letter_stream_key: str = "agent:tasks:dead-letter"
    task_block_ms: int = 5_000
    task_visibility_timeout_seconds: int = 900
    task_max_attempts: int = 3
    task_retry_delay_seconds: int = 5
    worker_heartbeat_interval_seconds: int = 10
    runtime_mode: Literal["api", "worker", "all"] = "api"

    # OpenTelemetry Trace 配置。关闭时业务仍运行，Trace API 使用 No-op 实现。
    otel_enabled: bool = False
    otel_service_name: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    otel_trace_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    otel_exporter_timeout_seconds: float = Field(default=10.0, gt=0.0, le=300.0)
    otel_insecure: bool = False

    # Skill Artifact 和单次 Run 工作区控制。
    skill_cache_dir: str = "/tmp/data-agent-runtime/skill-cache"
    workspace_root: str = "/tmp/data-agent-runtime/workspaces"
    skill_download_timeout_seconds: float = 30.0
    # 可选的 Skill Artifact 下载 AK/SK。两者同时配置时，Runtime 使用
    # DATA_AGENT-HMAC-SHA256 请求签名访问对象存储或 Artifact Gateway；均未配置时直接拉取公开或预签名 URL。
    skill_artifact_access_key: str | None = None
    skill_artifact_secret_key: str | None = None
    skill_max_bundle_bytes: int = 50 * 1024 * 1024
    skill_max_extracted_bytes: int = 200 * 1024 * 1024
    skill_max_files: int = 2_000
    # 逗号分隔的对象存储 Host 白名单；非本地环境必须配置，避免 bundle_url 变成 SSRF 通道。
    skill_allowed_hosts: str = ""
    skill_allow_http_local: bool = True


@lru_cache
def get_settings() -> Settings:
    """读取并缓存当前进程配置。

    默认加载 ``.env``、``.env.local`` 和进程环境变量；设置
    ``DATA_AGENT_ENV_FILE`` 时改为加载指定环境文件，便于 API 和 Worker 显式
    选择 ``.env.prod`` 等部署配置，避免配置文件名称看似生效但实际没有被读取。
    """
    env_file = os.getenv("DATA_AGENT_ENV_FILE")
    return Settings(_env_file=env_file) if env_file else Settings()
