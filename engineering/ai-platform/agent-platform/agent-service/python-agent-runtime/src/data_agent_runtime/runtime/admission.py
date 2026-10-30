"""本文件模块职责：AgentSnapshot 入站准入、资源边界和供应链策略校验。

Pydantic 只负责结构合法性；本模块负责把任意结构合法的 Snapshot 限制在部署、
调用方和公共服务安全策略允许的范围内。任何请求都必须在入队前通过本模块。
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlparse

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.model_providers import (
    normalize_provider,
    provider_adapter,
)
from data_agent_runtime.runtime.network_policy import is_private_or_local_host
from data_agent_runtime.runtime.principal import Principal, QuotaPolicy
from data_agent_runtime.schemas import (
    AgentRuntimeConfig,
    AgentSnapshot,
    RunRequest,
    UserContext,
)


class SnapshotAdmissionError(ValueError):
    """Snapshot 不满足 Runtime 部署安全策略。"""


def _csv(value: str) -> set[str]:
    """把逗号分隔的部署配置解析为去空白的非空字符串集合。"""
    return {item.strip() for item in value.split(",") if item.strip()}


def _validate_credential_ref(settings: Settings, credential_ref: str) -> None:
    """只校验部署侧 MCP 凭证引用存在，不把解析后的 Secret 带入 Snapshot。"""
    if not settings.mcp_credentials_json:
        raise SnapshotAdmissionError(
            f"MCP credential_ref {credential_ref!r} is not available"
        )
    try:
        registry = json.loads(settings.mcp_credentials_json)
    except json.JSONDecodeError as exc:
        raise SnapshotAdmissionError("MCP_CREDENTIALS_JSON is invalid") from exc
    if not isinstance(registry, dict) or not isinstance(
        registry.get(credential_ref), dict
    ):
        raise SnapshotAdmissionError(
            f"MCP credential_ref {credential_ref!r} is not registered"
        )
    value = registry[credential_ref]
    headers = value.get("headers", value)
    if not isinstance(headers, dict) or not headers:
        raise SnapshotAdmissionError(
            f"MCP credential_ref {credential_ref!r} has no headers"
        )


def _min_limit(*values: int | None) -> int | None:
    """计算 Snapshot 请求值、Principal 配额和部署上限中的最小有效值。

    该函数把调用方可请求的资源限制收敛到最严格边界；缺失或非法配额不会放大部署上限。"""
    present = [value for value in values if value is not None]
    return min(present) if present else None


def _depth(config: AgentRuntimeConfig, current: int = 0) -> int:
    """递归计算 SubAgent 树的最大深度，用于执行准入前的嵌套限制校验。"""
    if not config.subagents:
        return current
    return max(_depth(item, current + 1) for item in config.subagents)


def _walk(config: AgentRuntimeConfig):
    """遍历根 Agent 及其全部 SubAgent，收集统一的运行时配置节点。"""
    yield config
    for child in config.subagents:
        yield from _walk(child)


def _validate_mcp(settings: Settings, snapshot: AgentSnapshot) -> None:
    """校验快照内所有 MCP 声明是否符合部署级网络和凭证策略。

    公共模式拒绝不安全 URL、私有或本地地址、未白名单 Host、内联 Header 和未允许的 stdio。"""
    allowed_hosts = {host.lower() for host in _csv(settings.allowed_mcp_hosts)}
    for config in (item for node in _walk(snapshot) for item in node.mcp_servers):
        if config.transport == "stdio":
            if settings.public_mode or not settings.allow_mcp_stdio:
                raise SnapshotAdmissionError(
                    "stdio MCP transport is disabled by Runtime policy"
                )
            if not config.command or not config.command.strip():
                raise SnapshotAdmissionError(
                    f"stdio MCP server {config.id!r} requires command"
                )
            continue
        if not config.url:
            raise SnapshotAdmissionError(f"MCP server {config.id!r} requires url")
        parsed = urlparse(config.url)
        if parsed.username or parsed.password:
            raise SnapshotAdmissionError(
                f"MCP server {config.id!r} URL must not contain userinfo"
            )
        host = parsed.hostname
        if not host:
            raise SnapshotAdmissionError(
                f"MCP server {config.id!r} has invalid url"
            )
        if parsed.fragment:
            raise SnapshotAdmissionError(
                f"MCP server {config.id!r} URL must not contain a fragment"
            )
        if settings.public_mode and not allowed_hosts:
            raise SnapshotAdmissionError(
                "ALLOWED_MCP_HOSTS must be configured in public mode"
            )
        if allowed_hosts and host.lower() not in allowed_hosts:
            raise SnapshotAdmissionError(f"MCP host {host!r} is not allowed")
        if parsed.scheme not in {"https"} and not (
            not settings.public_mode
            and settings.app_env.lower() in {"local", "dev", "development"}
            and parsed.scheme == "http"
        ):
            raise SnapshotAdmissionError("MCP HTTP endpoints must use HTTPS")
        if settings.public_mode and is_private_or_local_host(host):
            raise SnapshotAdmissionError(
                "MCP endpoint resolves to a private or local address"
            )
        if config.headers and settings.public_mode:
            raise SnapshotAdmissionError(
                f"MCP server {config.id!r} must use a server-side credential_ref instead of inline headers"
            )
        if config.credential_ref:
            _validate_credential_ref(settings, config.credential_ref)


def admit_snapshot(
    settings: Settings, snapshot: AgentSnapshot, principal: Principal
) -> AgentSnapshot:
    """校验 Snapshot，并返回可安全入队的原对象。"""
    if len(snapshot.system_prompt) > settings.max_prompt_chars:
        raise SnapshotAdmissionError("agent system_prompt exceeds deployment limit")
    if len(snapshot.skills) > settings.max_snapshot_skills:
        raise SnapshotAdmissionError("AgentSnapshot contains too many Skills")
    if (
        sum(len(node.mcp_servers) for node in _walk(snapshot))
        > settings.max_snapshot_mcp_servers
    ):
        raise SnapshotAdmissionError("AgentSnapshot contains too many MCP servers")
    if _depth(snapshot) > settings.max_snapshot_subagent_depth:
        raise SnapshotAdmissionError("AgentSnapshot exceeds maximum SubAgent depth")
    if (
        sum(len(node.tool_allowlist) for node in _walk(snapshot))
        > settings.max_snapshot_tool_count
    ):
        raise SnapshotAdmissionError("AgentSnapshot contains too many tools")

    providers = _csv(settings.allowed_model_providers)
    names = _csv(settings.allowed_model_names)
    for node in _walk(snapshot):
        model = node.model
        if model is None:
            continue
        provider = normalize_provider(model.provider)
        if provider_adapter(provider) is None:
            raise SnapshotAdmissionError(
                f"model provider {provider!r} has no installed Runtime adapter"
            )
        if providers and provider not in {item.lower() for item in providers}:
            raise SnapshotAdmissionError(
                f"model provider {model.provider!r} is not allowed"
            )
        if names and model.name not in names:
            raise SnapshotAdmissionError(f"model {model.name!r} is not allowed")
        effective_steps = _min_limit(
            node.max_steps, settings.max_steps, principal.quotas.max_steps
        )
        if effective_steps is None or node.max_steps > effective_steps:
            raise SnapshotAdmissionError(
                f"agent {getattr(node, 'name', snapshot.id)!r} max_steps exceeds Runtime policy"
            )
    allowed_images = _csv(settings.allowed_sandbox_images)
    for node in _walk(snapshot):
        sandbox = node.sandbox
        if not sandbox.enabled:
            continue
        if sandbox.timeout_seconds > settings.max_sandbox_timeout_seconds:
            raise SnapshotAdmissionError("Sandbox timeout exceeds deployment limit")
        if sandbox.max_output_bytes > settings.max_sandbox_output_bytes:
            raise SnapshotAdmissionError(
                "Sandbox output limit exceeds deployment limit"
            )
        if sandbox.max_processes > settings.max_sandbox_processes:
            raise SnapshotAdmissionError(
                "Sandbox process limit exceeds deployment limit"
            )
        if (
            sandbox.cpu_limit is not None
            and sandbox.cpu_limit > settings.max_sandbox_cpu_limit
        ):
            raise SnapshotAdmissionError("Sandbox CPU limit exceeds deployment limit")
        if (
            sandbox.memory_limit_mb is not None
            and sandbox.memory_limit_mb > settings.max_sandbox_memory_mb
        ):
            raise SnapshotAdmissionError(
                "Sandbox memory limit exceeds deployment limit"
            )
        if (
            sandbox.disk_limit_mb is not None
            and sandbox.disk_limit_mb > settings.max_sandbox_disk_mb
        ):
            raise SnapshotAdmissionError("Sandbox disk limit exceeds deployment limit")
        if settings.public_mode and sandbox.network_mode == "full":
            raise SnapshotAdmissionError(
                "full Sandbox network is disabled in public mode"
            )
        if allowed_images and sandbox.image and sandbox.image not in allowed_images:
            raise SnapshotAdmissionError(
                f"Sandbox image {sandbox.image!r} is not allowed"
            )

    for node in _walk(snapshot):
        if node.interrupt_on and len(node.interrupt_on) > settings.max_snapshot_tool_count:
            raise SnapshotAdmissionError(
                "agent interrupt_on exceeds deployment tool count limit"
            )
        if node.memory_sources and len(node.memory_sources) > 20:
            raise SnapshotAdmissionError(
                "agent memory_sources exceeds deployment limit"
            )
        if node.rubric is not None and len(node.rubric) > settings.max_prompt_chars:
            raise SnapshotAdmissionError(
                "agent rubric exceeds deployment prompt size limit"
            )
        if node.response_format is not None:
            import json as _json

            encoded = _json.dumps(node.response_format, ensure_ascii=False)
            if len(encoded) > settings.max_prompt_chars:
                raise SnapshotAdmissionError(
                    "agent response_format schema exceeds deployment size limit"
                )

    subagent_hosts = {host.lower() for host in _csv(settings.allowed_subagent_hosts)}
    for node in _walk(snapshot):
        if not node.async_subagents:
            continue
        if settings.public_mode and not subagent_hosts:
            raise SnapshotAdmissionError(
                "ALLOWED_SUBAGENT_HOSTS must be configured in public mode"
            )
        for spec in node.async_subagents:
            parsed = urlparse(spec.url)
            if parsed.username or parsed.password:
                raise SnapshotAdmissionError(
                    f"async subagent {spec.name!r} url must not contain userinfo"
                )
            host = parsed.hostname
            if not host:
                raise SnapshotAdmissionError(
                    f"async subagent {spec.name!r} has invalid url"
                )
            if parsed.scheme != "https" and not (
                not settings.public_mode
                and settings.app_env.lower() in {"local", "dev", "development", "test"}
                and parsed.scheme == "http"
            ):
                raise SnapshotAdmissionError(
                    "async subagent endpoints must use HTTPS"
                )
            if subagent_hosts and host.lower() not in subagent_hosts:
                raise SnapshotAdmissionError(
                    f"async subagent host {host!r} is not allowed"
                )
            if settings.public_mode and is_private_or_local_host(host):
                raise SnapshotAdmissionError(
                    "async subagent endpoint resolves to a private or local address"
                )

    for skill in snapshot.skills:
        if (settings.public_mode or not settings.allow_inline_skills) and getattr(
            skill, "content", None
        ):
            raise SnapshotAdmissionError(
                "inline Skill content is disabled by Runtime policy"
            )
        if settings.public_mode and (
            not getattr(skill, "bundle_url", None) or not getattr(skill, "sha256", None)
        ):
            raise SnapshotAdmissionError(
                "public Skills require immutable bundle_url and sha256"
            )
    _validate_mcp(settings, snapshot)
    return snapshot


async def admit_snapshot_async(
    settings: Settings, snapshot: AgentSnapshot, principal: Principal
) -> AgentSnapshot:
    """异步准入：把可能包含 DNS 解析的校验放到线程池，避免阻塞事件循环。"""
    return await asyncio.to_thread(admit_snapshot, settings, snapshot, principal)


async def validate_bound_request_async(
    settings: Settings, request: RunRequest
) -> RunRequest:
    """异步版本的消费侧准入，供 Worker 在事件循环中调用。"""
    return await asyncio.to_thread(validate_bound_request, settings, request)


def validate_attachments(settings: Settings, request: RunRequest) -> None:
    """校验附件数量与图片输入的模型能力。

    图片需要模型支持视觉；部署通过 ``ALLOWED_VISION_MODELS`` 显式声明哪些模型可用，
    未配置时直接拒绝图片，避免把图片发给纯文本模型后在运行中期失败。
    """
    attachments = request.attachments
    if not attachments:
        return
    if len(attachments) > settings.max_attachments:
        raise SnapshotAdmissionError("too many attachments for a single run")
    vision_models = _csv(settings.allowed_vision_models)
    for item in attachments:
        if (item.media_type or "").lower().startswith("image/"):
            if not vision_models:
                raise SnapshotAdmissionError(
                    "image attachments are disabled; configure ALLOWED_VISION_MODELS"
                )
            if request.agent.model.name not in vision_models:
                raise SnapshotAdmissionError(
                    f"model {request.agent.model.name!r} does not support image input"
                )


def validate_bound_request(settings: Settings, request: RunRequest) -> RunRequest:
    """在 Worker 消费侧再次校验已绑定的 Run 请求。

    HTTP API 是首个准入边界，但 Redis Stream 也可能被重试、迁移脚本或其他
    内部生产者写入。Worker 不重新信任 Snapshot 中的资源参数，而是对入队后的
    请求执行同一套部署级策略校验，避免绕过 HTTP 入口直接获得更高能力。
    """
    context = request.user_context
    if context is None:
        raise SnapshotAdmissionError("RunRequest must contain a bound user_context")
    principal = Principal(
        principal_id=context.principal_id or f"{context.tenant_id}:{context.user_id}",
        access_key="worker-bound-context",
        tenant_id=context.tenant_id,
        subject_id=context.user_id,
        roles=frozenset(context.roles),
        scopes=frozenset(context.scopes),
        quotas=QuotaPolicy(
            max_steps=context.max_steps,
            run_timeout_seconds=context.run_timeout_seconds,
            max_concurrent_runs=context.max_concurrent_runs,
        ),
    )
    admit_snapshot(settings, request.agent, principal)
    validate_attachments(settings, request)
    if request.internal_token is not None:
        raise SnapshotAdmissionError("internal_token must not be present in task payload")
    return request


def bind_principal_context(request: RunRequest, principal: Principal) -> RunRequest:
    """把 Principal 身份绑定到 RunRequest，拒绝 Body 伪造租户或用户。"""
    supplied = request.user_context
    if supplied is not None and (
        supplied.tenant_id != principal.tenant_id
        or (
            principal.subject_id is not None
            and supplied.user_id != principal.subject_id
        )
    ):
        raise SnapshotAdmissionError(
            "user_context does not match authenticated Principal"
        )
    context = UserContext(
        principal_id=principal.principal_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        roles=sorted(principal.roles),
        scopes=sorted(principal.scopes),
        max_steps=principal.quotas.max_steps,
        run_timeout_seconds=principal.quotas.run_timeout_seconds,
        max_concurrent_runs=principal.quotas.max_concurrent_runs,
    )
    request.user_context = context
    # 旧字段只为反序列化兼容保留，绝不把调用方提交的 Token 写入任务队列。
    request.internal_token = None
    return request
