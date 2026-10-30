"""本文件模块职责：DeepAgents Runtime 构建工厂模块。

本模块根据 调用方提交的 AgentSnapshot 组装模型、Prompt、Skill、MCP Tool、Sandbox Tool、Workspace、SubAgent 和摘要中间件，并返回需要由执行器统一关闭的资源句柄。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepagents import CompiledSubAgent, FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend, StateBackend
from deepagents.middleware.async_subagents import AsyncSubAgent
from deepagents.middleware.rubric import RubricMiddleware
from deepagents.middleware.summarization import create_summarization_middleware
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from data_agent_runtime.clients.factory import create_sandbox_provider
from data_agent_runtime.clients.provider import SandboxProvider
from data_agent_runtime.clients.sandbox import SandboxRunContext
from data_agent_runtime.config import Settings
from data_agent_runtime.prompts.analysis import build_analysis_prompt
from data_agent_runtime.runtime.model_providers import (
    normalize_provider,
    provider_adapter,
)
from data_agent_runtime.runtime.skill_artifacts import (
    MaterializedSkills,
    SkillArtifactError,
    SkillArtifactManager,
)
from data_agent_runtime.schemas import (
    AgentRuntimeConfig,
    AgentSnapshot,
    ModelConfig,
    SandboxConfig,
    SubAgentSnapshot,
)
from data_agent_runtime.tools.mcp import load_mcp_tools
from data_agent_runtime.tools.sandbox import create_sandbox_tools

logger = logging.getLogger(__name__)

_MAX_SUBAGENT_DEPTH = 5
_SANDBOX_TOOL_NAMES = frozenset(
    {
        "sandbox_write_file",
        "sandbox_run",
        "sandbox_read_file",
        "sandbox_collect_artifact",
    }
)


@dataclass
class AgentRuntimeHandle:
    """一次已构建 Agent Run 所拥有的 MCP、Sandbox 和 SubAgent 资源。

    Worker 在成功、失败、取消和重试路径都必须关闭句柄中的全部资源，不能只释放根 Agent。
    """

    mcp_client: Any | None = None
    sandbox_provider: SandboxProvider | None = None
    run_context: SandboxRunContext | None = None
    # SubAgent 拥有独立的 MCP/Sandbox 资源；全部资源都放入 Run Handle，
    # 这样重试、失败、取消和正常完成都能清理，而不是只清理根 Agent。
    mcp_clients: list[Any] = field(default_factory=list)
    sandbox_providers: list[SandboxProvider] = field(default_factory=list)

    @property
    def sandbox_client(self) -> SandboxProvider | None:
        """返回历史集成所使用的 ``sandbox_client`` 兼容别名。

        新代码应优先使用 ``sandbox_provider``；该属性仅保持旧调用方平滑迁移，
        不会创建新的 Provider，也不会复制底层 Sandbox 资源。
        """
        return self.sandbox_provider

    async def aclose(self) -> None:
        """关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。"""
        providers: list[SandboxProvider] = []
        if self.sandbox_provider is not None:
            providers.append(self.sandbox_provider)
        providers.extend(self.sandbox_providers)
        seen: set[int] = set()
        for provider in reversed(providers):
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            await provider.aclose()

        clients: list[Any] = []
        if self.mcp_client is not None:
            clients.append(self.mcp_client)
        clients.extend(self.mcp_clients)
        seen.clear()
        for client in reversed(clients):
            if id(client) in seen:
                continue
            seen.add(id(client))
            close = getattr(client, "aclose", None) or getattr(client, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result


def _without_sandbox_tools(tools: Sequence[Any]) -> list[Any]:
    """在构建 SubAgent 前移除绑定父级资源的 Sandbox 工具。

    父 Agent 的工具闭包持有自己的 Run Context 和 Provider，不能直接注入子 Agent；
    子 Agent 必须依据自身 Snapshot 创建独立资源，并通过能力边界校验后再加载工具。
    """
    return [tool for tool in tools if _tool_name(tool) not in _SANDBOX_TOOL_NAMES]


def _validate_subagent_sandbox(
    parent: SandboxConfig,
    child: SandboxConfig,
    path: str,
) -> None:
    """将父级 Sandbox 约束作为 SubAgent 的能力和资源上限进行校验。

    子 Agent 不得启用父级未启用的 Sandbox，也不得放宽网络、超时、输出、进程、
    CPU、内存或磁盘限制；违反约束时立即失败，防止子 Agent 越权获得更多执行能力。
    """
    if not parent.enabled:
        raise SkillArtifactError(
            f"SubAgent {path!r} enables Sandbox but its parent Sandbox is disabled; "
            "set the parent Sandbox enabled and use tool_allowlist to hide root tools"
        )

    network_rank = {"none": 0, "restricted": 1, "full": 2}
    if network_rank[child.network_mode] > network_rank[parent.network_mode]:
        raise SkillArtifactError(
            f"SubAgent {path!r} Sandbox network_mode cannot be less restrictive "
            f"than its parent ({parent.network_mode!r} -> {child.network_mode!r})"
        )

    for field_name in (
        "timeout_seconds",
        "max_output_bytes",
        "max_processes",
        "cpu_limit",
        "memory_limit_mb",
        "disk_limit_mb",
    ):
        parent_value = getattr(parent, field_name)
        child_value = getattr(child, field_name)
        if parent_value is not None and (
            child_value is None or child_value > parent_value
        ):
            raise SkillArtifactError(
                f"SubAgent {path!r} Sandbox {field_name} must not exceed "
                f"the parent limit ({parent_value!r})"
            )

    if parent.image and child.image != parent.image:
        raise SkillArtifactError(
            f"SubAgent {path!r} Sandbox must use the parent image {parent.image!r}"
        )
    if parent.image_digest and child.image_digest != parent.image_digest:
        raise SkillArtifactError(
            f"SubAgent {path!r} Sandbox must use the parent image digest"
        )
    if parent.allow_commands and not set(child.allow_commands).issubset(
        parent.allow_commands
    ):
        raise SkillArtifactError(
            f"SubAgent {path!r} Sandbox allow_commands must be a subset of the parent"
        )



def _tool_name(tool: Any) -> str | None:
    """执行“_tool_name”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if isinstance(tool, BaseTool):
        return tool.name
    if isinstance(tool, dict):
        function = tool.get("function")
        return tool.get("name") or (
            function.get("name") if isinstance(function, dict) else None
        )
    return getattr(tool, "name", None)


def _filter_tools(tools: Sequence[Any], allowlist: list[str]) -> list[Any]:
    """执行“_filter_tools”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if not allowlist:
        return list(tools)
    allowed = set(allowlist)
    return [tool for tool in tools if _tool_name(tool) in allowed]


def _runtime_directives(agent: AgentRuntimeConfig) -> str:
    """执行“_runtime_directives”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    directives: list[str] = []
    if agent.plan.enabled:
        approval = "需要持有 runs:approve Scope 的调用方审批后再继续" if agent.plan.require_approval else "无需额外审批"
        directives.append(
            "# 执行计划\n"
            f"本次运行必须先形成最多 {agent.plan.max_steps} 步的分析计划，"
            f"{approval}；允许重新规划={agent.plan.allow_replan}。"
        )
    if agent.rag.enabled:
        directives.append(
            "# 知识检索\n"
            "需要业务口径、指标定义或数据字典时，优先使用已配置的知识检索工具，"
            "不得凭空编造口径。"
        )
    if agent.workspace.enabled:
        mode = "只读" if agent.workspace.read_only else "可写"
        directives.append(f"# 工作区\n当前运行工作区为{mode}模式，只能使用运行时提供的文件工具。")
    if agent.sandbox.enabled:
        directives.append(
            "# 沙箱\n脚本或命令只能通过受控沙箱执行，不得尝试访问宿主机或绕过工具权限。"
        )
    directives.append(f"# 运行预算\n本 Agent 最多执行 {agent.max_steps} 步。")
    return "\n\n".join(directives)


def _filesystem_permissions(agent: AgentRuntimeConfig) -> list[FilesystemPermission] | None:
    """执行“_filesystem_permissions”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if not agent.workspace.enabled:
        return None

    if agent.workspace.read_only:
        return [FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")]

    if not agent.workspace.allowed_paths:
        return None

    allowed = [
        path if path.startswith("/") else f"/{path}"
        for path in agent.workspace.allowed_paths
    ]
    allowed = [
        path if path.endswith("/**") else f"{path.rstrip('/')}/**"
        for path in allowed
    ]
    return [
        FilesystemPermission(operations=["write"], paths=allowed, mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]


def _safe_subagent_dir(name: str) -> str:
    """执行“_safe_subagent_dir”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return value[:96] or "subagent"


def _model_config(
    spec: AgentRuntimeConfig, inherited: ModelConfig, settings: Settings
) -> ModelConfig:
    """执行“_model_config”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    model = spec.model
    # 兼容旧版 SubAgentSnapshot.model_name 平铺字段。
    model_name = getattr(spec, "model_name", None)
    if model is None and model_name:
        model = ModelConfig(provider=settings.model_provider, name=model_name)
    return model or inherited or ModelConfig(
        provider=settings.model_provider,
        name=settings.model_name,
    )


def _chat_model(config: ModelConfig, settings: Settings) -> ChatOpenAI:
    """根据部署注册的 Provider 构造模型客户端。

    当前依赖只提供 OpenAI 协议适配器，因此 ``openai``、``deepseek`` 和
    ``openai-compatible`` 都通过 ``OPENAI_BASE_URL`` 接入对应网关；不支持的
    Provider 必须显式失败，不能静默把一个合法的 Snapshot 路由到错误的模型后端。
    """
    provider = normalize_provider(config.provider, settings.model_provider)
    adapter = provider_adapter(provider)
    if adapter is None:
        raise ValueError(
            f"unsupported model provider {provider!r}; configure a provider adapter "
            "or use an installed OpenAI-compatible provider"
        )
    if adapter == "openai-compatible" and not settings.openai_base_url:
        raise ValueError(
            "OPENAI_BASE_URL is required for the configured OpenAI-compatible provider"
        )
    return ChatOpenAI(
        model=config.name or settings.model_name,
        temperature=(
            settings.model_temperature
            if config.temperature is None
            else config.temperature
        ),
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def _check_rag_tools(agent: AgentRuntimeConfig, tools: Sequence[Any]) -> None:
    """执行“_check_rag_tools”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if not agent.rag.enabled or not agent.rag.tool_allowlist:
        return
    available = {_tool_name(tool) for tool in tools}
    missing = sorted(set(agent.rag.tool_allowlist) - available)
    if missing:
        raise SkillArtifactError(
            f"configured RAG tools are not available in this run: {missing}"
        )


def _check_skill_tools(
    skill_ids: Sequence[str],
    all_skills: dict[str, Any],
    tools: Sequence[Any],
    owner: str,
) -> None:
    """执行“_check_skill_tools”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    required_tools = {
        required
        for skill_id in skill_ids
        for required in all_skills[skill_id].required_tools
    }
    available = {_tool_name(tool) for tool in tools}
    missing = sorted(required_tools - available)
    if missing:
        raise SkillArtifactError(
            f"required Skill tools are not available for {owner}: {missing}"
        )


async def _build_compiled_subagent(
    spec: SubAgentSnapshot,
    *,
    settings: Settings,
    inherited_model: ModelConfig,
    inherited_tools: list[Any],
    all_skills: dict[str, Any],
    skill_paths: dict[str, str],
    parent_workspace: Path,
    depth: int,
    subagent_path: tuple[str, ...],
    resources: AgentRuntimeHandle,
    parent_sandbox: SandboxConfig,
) -> CompiledSubAgent:
    """执行“_build_compiled_subagent”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if depth > _MAX_SUBAGENT_DEPTH:
        raise SkillArtifactError(
            f"SubAgent nesting exceeds the maximum depth {_MAX_SUBAGENT_DEPTH}"
        )
    if spec.mode == "fork":
        raise SkillArtifactError(
            f"SubAgent {spec.name!r} uses mode=fork, which is not supported for "
            "compiled full-runtime SubAgents"
        )

    # Sandbox 绑定到单个 Agent/SubAgent 执行上下文；不能让子 Agent 意外复用父 Agent 的 Sandbox Tool。
    # 如果子 Agent 声明 Sandbox，下面会为它创建独立 Provider 和 Tool 闭包。
    inherited_tools_without_sandbox = _without_sandbox_tools(inherited_tools)
    parent_tool_names = {
        tool_name
        for tool in inherited_tools_without_sandbox
        if (tool_name := _tool_name(tool))
    }
    child_tools = list(inherited_tools_without_sandbox)
    if spec.mcp_servers:
        child_mcp_client, declared_tools = await load_mcp_tools(spec.mcp_servers, settings)
        resources.mcp_clients.append(child_mcp_client)
        # 子 Agent 可以收窄父 Agent 的 Tool 范围，但不能声明父 Agent 无权使用的新 MCP Server 或 Tool。
        child_tools = [
            tool for tool in declared_tools if _tool_name(tool) in parent_tool_names
        ]
    child_tools = _filter_tools(child_tools, spec.tool_allowlist)

    if spec.sandbox.enabled:
        _validate_subagent_sandbox(
            parent_sandbox,
            spec.sandbox,
            "/".join(subagent_path),
        )
        if resources.run_context is None:
            raise RuntimeError("SubAgent Sandbox requires a run context")
        scope = "/".join(("subagent", *subagent_path))
        sandbox_provider = create_sandbox_provider(
            settings,
            spec.sandbox,
            SandboxRunContext(
                run_id=resources.run_context.run_id,
                tenant_id=resources.run_context.tenant_id,
                session_id=resources.run_context.session_id,
                user_id=resources.run_context.user_id,
                trace_id=resources.run_context.trace_id,
                sandbox_scope=scope,
            ),
        )
        resources.sandbox_providers.append(sandbox_provider)
        sandbox_tools = create_sandbox_tools(sandbox_provider)
        # 子 Agent 的显式 Tool 白名单可以进一步收窄 Sandbox Tool 范围。
        # 与收窄 MCP Tool 的规则一致。
        child_tools.extend(_filter_tools(sandbox_tools, spec.tool_allowlist))

    _check_rag_tools(spec, child_tools)
    _check_skill_tools(spec.skill_ids, all_skills, child_tools, spec.name)

    model_config = _model_config(spec, inherited_model, settings)
    model = _chat_model(model_config, settings)
    selected_skills = [skill_paths[skill_id] for skill_id in spec.skill_ids]

    workspace_root = parent_workspace
    if spec.workspace.enabled:
        workspace_root = parent_workspace / "subagents" / _safe_subagent_dir(spec.name)
        workspace_root.mkdir(parents=True, exist_ok=True)
    backend = FilesystemBackend(root_dir=str(workspace_root))

    nested = [
        await _build_compiled_subagent(
            child,
            settings=settings,
            inherited_model=model_config,
            inherited_tools=child_tools,
            all_skills=all_skills,
            skill_paths=skill_paths,
            parent_workspace=workspace_root,
            depth=depth + 1,
            subagent_path=(*subagent_path, child.name),
            resources=resources,
            parent_sandbox=spec.sandbox,
        )
        for child in spec.subagents
    ]

    prompt = spec.system_prompt or f"你是 {spec.name}，负责完成被委派的子任务。"
    directives = _runtime_directives(spec)
    if directives:
        prompt = f"{prompt}\n\n{directives}"

    middleware = []
    if spec.compression.enabled:
        middleware.append(
            create_summarization_middleware(
                model,
                backend,
                trim_tokens_to_summarize=spec.compression.trigger_tokens,
            )
        )

    runnable = create_deep_agent(
        model=model,
        tools=child_tools,
        system_prompt=prompt,
        subagents=nested or None,
        skills=selected_skills or None,
        backend=backend,
        permissions=_filesystem_permissions(spec),
        middleware=middleware,
        # 可选能力：调用方未声明时不传，deepagents 的默认装配链保持不变。
        interrupt_on=spec.interrupt_on,
        response_format=spec.response_format,
        memory=spec.memory_sources,
        name=spec.name,
    )
    return {
        "name": spec.name,
        "description": spec.description,
        "runnable": runnable,
    }


async def _build_full_subagents(
    specs: list[SubAgentSnapshot],
    *,
    settings: Settings,
    inherited_model: ModelConfig,
    inherited_tools: list[Any],
    all_skills: dict[str, Any],
    skill_paths: dict[str, str],
    parent_workspace: Path,
    resources: AgentRuntimeHandle,
    parent_sandbox: SandboxConfig,
) -> list[CompiledSubAgent]:
    """执行“_build_full_subagents”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return [
        await _build_compiled_subagent(
            spec,
            settings=settings,
            inherited_model=inherited_model,
            inherited_tools=inherited_tools,
            all_skills=all_skills,
            skill_paths=skill_paths,
            parent_workspace=parent_workspace,
            depth=1,
            subagent_path=(spec.name,),
            resources=resources,
            parent_sandbox=parent_sandbox,
        )
        for spec in specs
    ]


async def build_agent(
    agent: AgentSnapshot,
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    store: Any | None = None,
    memories: list[dict[str, str]] | None = None,
    run_id: str = "local-run",
    session_id: str = "local-session",
    tenant_id: str = "local-tenant",
):
    """根据不可变的 AgentSnapshot 构建一次完整的 DeepAgents Runtime。

    构建过程会物化 Skill、组装 Prompt、初始化模型、加载 MCP 工具、创建根 Agent
    和 SubAgent，并按 Snapshot 与部署配置创建独立的 Sandbox、Workspace 及资源句柄。
    返回结果由执行器负责在成功、失败、取消和异常路径统一释放。
    """
    artifact_manager = SkillArtifactManager(settings)
    materialized: MaterializedSkills = await artifact_manager.materialize(
        agent.skills,
        tenant_id=tenant_id,
        session_id=session_id,
        run_id=run_id,
        workspace_enabled=agent.workspace.enabled,
        workspace_id=agent.workspace.workspace_id,
    )

    system_prompt = build_analysis_prompt(agent.system_prompt, [], memories)
    runtime_directives = _runtime_directives(agent)
    if runtime_directives:
        system_prompt = f"{system_prompt}\n\n{runtime_directives}"

    model_config = agent.model
    model = _chat_model(model_config, settings)
    if agent.interrupt_on and settings.checkpoint_backend != "postgres":
        # 中断恢复依赖 Checkpoint：内存模式只在同一 Worker 进程内有效，
        # 多副本或进程重启后恢复会找不到会话状态。
        logger.warning(
            "interrupt_on requires a durable checkpointer; "
            "CHECKPOINT_BACKEND=%s may lose paused runs across workers or restarts",
            settings.checkpoint_backend,
        )

    _mcp_client, loaded_tools = await load_mcp_tools(agent.mcp_servers, settings)
    run_context = SandboxRunContext(
        run_id=run_id,
        tenant_id=tenant_id,
        session_id=session_id,
    )
    resources = AgentRuntimeHandle(mcp_client=_mcp_client, run_context=run_context)
    try:
        tools = list(loaded_tools)
        if agent.sandbox.enabled:
            sandbox_provider = create_sandbox_provider(
                settings,
                agent.sandbox,
                run_context,
            )
            resources.sandbox_provider = sandbox_provider
            resources.sandbox_providers.append(sandbox_provider)
            # Session 在第一次 Sandbox Tool 调用时惰性创建。
            tools.extend(create_sandbox_tools(sandbox_provider))
        tools = _filter_tools(tools, agent.tool_allowlist)
        _check_rag_tools(agent, tools)
        all_skills = {skill.id: skill for skill in agent.skills}
        _check_skill_tools(all_skills.keys(), all_skills, tools, agent.id)

        backend = (
            FilesystemBackend(root_dir=str(materialized.workspace_root))
            if materialized.skill_sources or agent.workspace.enabled
            else StateBackend()
        )
        async_specs: list[AsyncSubAgent] = [
            AsyncSubAgent(
                name=spec.name,
                description=spec.description,
                graph_id=spec.graph_id,
                url=spec.url,
                update_strategy=spec.update_strategy,
            )
            for spec in (agent.async_subagents or [])
        ]
        subagents = await _build_full_subagents(
            agent.subagents,
            settings=settings,
            inherited_model=model_config,
            inherited_tools=tools,
            all_skills=all_skills,
            skill_paths=materialized.skill_paths,
            parent_workspace=materialized.workspace_root,
            resources=resources,
            parent_sandbox=agent.sandbox,
        )

        middleware = []
        if agent.compression.enabled:
            middleware.append(
                create_summarization_middleware(
                    model,
                    backend,
                    trim_tokens_to_summarize=agent.compression.trigger_tokens,
                )
            )
        if agent.plan.todo_tool:
            # 把"先列计划"从 Prompt 要求升级为可观测的工具调用（write_todos）。
            middleware.append(TodoListMiddleware())
        if agent.rubric:
            # RubricMiddleware 只在调用状态里带 rubric 时激活；声明了自评标准才装配，
            # 避免为没有 rubric 的 Agent 额外创建评分模型实例。
            middleware.append(RubricMiddleware(model=model))

        runtime_agent = create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            subagents=[*subagents, *async_specs] or None,
            skills=materialized.skill_sources or None,
            backend=backend,
            permissions=_filesystem_permissions(agent),
            middleware=middleware,
            checkpointer=checkpointer,
            # 可选能力：工具级确认、结构化输出、AGENTS.md 记忆。
            interrupt_on=agent.interrupt_on,
            response_format=agent.response_format,
            memory=agent.memory_sources,
            store=store,
            name=agent.id,
        )
        return runtime_agent, resources
    except BaseException:
        # 后续子 Agent 校验失败前可能已经创建 Provider/MCP Client；build_agent 无法返回 Run Handle 时必须清理这些资源。
        await resources.aclose()
        raise
