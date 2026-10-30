"""本文件模块职责：DeepAgents Runtime Factory 单元测试。

测试验证 Snapshot 到模型、Skill、MCP、Sandbox、Workspace 和 SubAgent 的组装，以及父子 Agent Sandbox 能力边界校验。
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from data_agent_runtime.clients.sandbox import SandboxRunContext
from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.factory import (
    AgentRuntimeHandle,
    _build_compiled_subagent,
    build_agent,
)
from data_agent_runtime.runtime.skill_artifacts import SkillArtifactError
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    SandboxConfig,
    SubAgentSnapshot,
)


class FakeProvider:
    """Runtime Factory 测试使用的 Sandbox Provider 替身。"""
    def __init__(self, context):
        """
        中文说明：
            初始化 FakeProvider，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - context: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.context = context
        self.closed = False

    @property
    def is_created(self):
        """
        中文说明：
            实现 FakeProvider 的“is_created”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        return False

    async def ensure_created(self):
        """
        中文说明：
            按需创建并返回隔离 Sandbox；重复调用时复用已经创建的会话。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        raise AssertionError("not needed for build test")

    async def write_file(self, path, content, *, encoding="utf-8"):
        """
        中文说明：
            在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。

        参数：
            - path: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - content: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - encoding: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        raise AssertionError("not needed for build test")

    async def read_file(self, path):
        """
        中文说明：
            从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。

        参数：
            - path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        raise AssertionError("not needed for build test")

    async def run(self, executable, args, *, timeout_seconds=None, max_output_bytes=None):
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - executable: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - args: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - timeout_seconds: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - max_output_bytes: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        raise AssertionError("not needed for build test")

    async def collect_artifact(self, path, *, name=None):
        """
        中文说明：
            将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。

        参数：
            - path: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - name: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        raise AssertionError("not needed for build test")

    async def destroy(self):
        """
        中文说明：
            销毁底层 Sandbox 资源并使后续操作失效，确保容器、Pod 或远程会话不会泄漏。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.closed = True

    async def aclose(self):
        """
        中文说明：
            关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.closed = True


def test_subagent_sandbox_gets_its_own_tools_and_scope(monkeypatch, tmp_path):
    """
    中文说明：
        验证 tests/test_runtime_factory 中“subagent_sandbox_gets_its_own_tools_and_scope”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run():
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        providers = []
        built = []

        def fake_provider(settings, sandbox, context):
            """
            中文说明：
                实现 tests/test_runtime_factory 的“fake_provider”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - settings: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - sandbox: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - context: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            provider = FakeProvider(context)
            providers.append(provider)
            return provider

        def fake_agent(**kwargs):
            """
            中文说明：
                实现 tests/test_runtime_factory 的“fake_agent”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - **kwargs: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            built.append(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_sandbox_provider",
            fake_provider,
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent",
            fake_agent,
        )

        spec = SubAgentSnapshot(
            name="python-analysis",
            description="run isolated analysis",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
            sandbox=SandboxConfig(enabled=True, allow_commands=["python3"]),
            subagents=[
                SubAgentSnapshot(
                    name="nested-analysis",
                    description="nested isolated analysis",
                    sandbox=SandboxConfig(enabled=True, allow_commands=["python3"]),
                    compression={"enabled": False},
                )
            ],
        )
        context = SandboxRunContext(
            run_id="run-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        resources = AgentRuntimeHandle(run_context=context)

        await _build_compiled_subagent(
            spec,
            settings=Settings(sandbox_provider="docker"),
            inherited_model=ModelConfig(name="parent-model"),
            inherited_tools=[],
            all_skills={},
            skill_paths={},
            parent_workspace=Path(tmp_path),
            depth=1,
            subagent_path=(spec.name,),
            resources=resources,
            parent_sandbox=spec.sandbox,
        )

        assert len(providers) == 2
        assert providers[0].context.sandbox_scope == "subagent/python-analysis"
        assert (
            providers[1].context.sandbox_scope
            == "subagent/python-analysis/nested-analysis"
        )
        assert providers[0].context.run_id == providers[1].context.run_id == "run-1"
        assert [tool.name for tool in built[0]["tools"]] == [
            "sandbox_write_file",
            "sandbox_run",
            "sandbox_read_file",
            "sandbox_collect_artifact",
        ]
        assert [tool.name for tool in built[1]["tools"]] == [
            "sandbox_write_file",
            "sandbox_run",
            "sandbox_read_file",
            "sandbox_collect_artifact",
        ]

        await resources.aclose()
        assert all(provider.closed for provider in providers)

    asyncio.run(run())


def test_subagent_does_not_inherit_parent_sandbox_tools(monkeypatch, tmp_path):
    """
    中文说明：
        验证 tests/test_runtime_factory 中“subagent_does_not_inherit_parent_sandbox_tools”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run():
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        captured = {}

        def fake_agent(**kwargs):
            """
            中文说明：
                实现 tests/test_runtime_factory 的“fake_agent”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - **kwargs: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            captured.update(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent",
            fake_agent,
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )

        class ParentSandboxTool:
            """模拟父 Agent Sandbox 工具，验证子 Agent 资源隔离。"""
            name = "sandbox_run"

        spec = SubAgentSnapshot(
            name="metadata-agent",
            description="metadata only",
            compression={"enabled": False},
            sandbox=SandboxConfig(enabled=False),
        )
        resources = AgentRuntimeHandle(
            run_context=SandboxRunContext(
                run_id="run-1",
                tenant_id="tenant-1",
                session_id="session-1",
            )
        )
        await _build_compiled_subagent(
            spec,
            settings=Settings(sandbox_provider="docker"),
            inherited_model=ModelConfig(name="parent-model"),
            inherited_tools=[ParentSandboxTool()],
            all_skills={},
            skill_paths={},
            parent_workspace=Path(tmp_path),
            depth=1,
            subagent_path=(spec.name,),
            resources=resources,
            parent_sandbox=SandboxConfig(enabled=True),
        )
        assert captured["tools"] == []

    asyncio.run(run())


def test_subagent_sandbox_cannot_expand_parent_policy(monkeypatch, tmp_path):
    """
    中文说明：
        验证 tests/test_runtime_factory 中“subagent_sandbox_cannot_expand_parent_policy”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run():
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent",
            lambda **kwargs: SimpleNamespace(name=kwargs["name"]),
        )

        spec = SubAgentSnapshot(
            name="unsafe-child",
            description="must be rejected",
            sandbox=SandboxConfig(
                enabled=True,
                network_mode="full",
                memory_limit_mb=2048,
                allow_commands=["python3", "bash"],
            ),
            compression={"enabled": False},
        )
        resources = AgentRuntimeHandle(
            run_context=SandboxRunContext(
                run_id="run-1",
                tenant_id="tenant-1",
                session_id="session-1",
            )
        )
        parent = SandboxConfig(
            enabled=True,
            network_mode="none",
            memory_limit_mb=512,
            allow_commands=["python3"],
        )
        try:
            try:
                await _build_compiled_subagent(
                    spec,
                    settings=Settings(sandbox_provider="docker"),
                    inherited_model=ModelConfig(name="parent-model"),
                    inherited_tools=[],
                    all_skills={},
                    skill_paths={},
                    parent_workspace=Path(tmp_path),
                    depth=1,
                    subagent_path=(spec.name,),
                    resources=resources,
                    parent_sandbox=parent,
                )
            except SkillArtifactError as exc:
                assert "network_mode" in str(exc)
            else:
                raise AssertionError("a child Sandbox must not expand its parent policy")
        finally:
            await resources.aclose()

    asyncio.run(run())


def test_model_temperature_uses_runtime_default_when_snapshot_omits_it():
    """验证 Snapshot 未传温度时使用部署级 MODEL_TEMPERATURE。"""
    from data_agent_runtime.runtime.factory import _chat_model

    settings = Settings(
        _env_file=None,
        model_temperature=0.7,
        openai_api_key="test-key",
        openai_base_url="https://model.example.com/v1",
    )
    model = _chat_model(
        ModelConfig(provider="deepseek", name="deepseek-chat"),
        settings,
    )

    assert model.temperature == 0.7


def test_root_agent_passes_optional_capabilities(monkeypatch, tmp_path):
    """
    中文说明：
        验证根 Agent 构建时把 interrupt_on、response_format、memory_sources 透传给
        create_deep_agent，确保这三个可选能力真正接线而不是只停留在 Snapshot 字段。

    参数：
        - monkeypatch: 未声明类型：用于替换模型与 Agent 构建函数。
        - tmp_path: 未声明类型：用于提供隔离的工作区目录。

    返回：
        None。

    异常与边界：
        测试不连接模型、MCP 或 Redis，只捕获构建参数。
    """

    async def run():
        """
        中文说明：
            执行一次 build_agent 并返回 create_deep_agent 收到的关键字参数。

        参数：
            - 无：函数使用闭包变量完成工作。

        返回：
            None。

        异常与边界：
            构建失败时异常向上抛出，由 pytest 记录。
        """
        built = []

        def fake_agent(**kwargs):
            """
            中文说明：
                记录 create_deep_agent 的调用参数并返回最小替身。

            参数：
                - **kwargs: 未声明类型：构建参数。

            返回：
                带 name 属性的 SimpleNamespace。

            异常与边界：
                无外部依赖。
            """
            built.append(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent", fake_agent
        )
        snapshot = AgentSnapshot(
            id="agent-optional",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
            interrupt_on={"sandbox_run": True},
            response_format={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
            },
            memory_sources=["/AGENTS.md"],
        )
        settings = Settings(
            workspace_root=str(tmp_path),
            skill_cache_dir=str(tmp_path / "skill-cache"),
        )
        agent, resources = await build_agent(
            snapshot,
            settings,
            run_id="run-1",
            session_id="session-1",
            tenant_id="tenant-1",
        )
        await resources.aclose()
        assert agent is not None
        assert built[0]["interrupt_on"] == {"sandbox_run": True}
        assert built[0]["response_format"]["type"] == "object"
        assert built[0]["memory"] == ["/AGENTS.md"]

    asyncio.run(run())


def test_optional_capabilities_default_to_none(monkeypatch, tmp_path):
    """
    中文说明：
        验证未声明可选能力时不传任何开关，保证 deepagents 的默认装配链与旧版本完全一致。

    参数：
        - monkeypatch: 未声明类型：用于替换模型与 Agent 构建函数。
        - tmp_path: 未声明类型：用于提供隔离的工作区目录。

    返回：
        None。

    异常与边界：
        测试不连接外部依赖。
    """

    async def run():
        """
        中文说明：
            执行一次 build_agent 并检查三个可选参数均为 None。

        参数：
            - 无：函数使用闭包变量完成工作。

        返回：
            None。

        异常与边界：
            构建失败时异常向上抛出。
        """
        built = []

        def fake_agent(**kwargs):
            """
            中文说明：
                记录构建参数并返回最小替身。

            参数：
                - **kwargs: 未声明类型：构建参数。

            返回：
                带 name 属性的 SimpleNamespace。

            异常与边界：
                无外部依赖。
            """
            built.append(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent", fake_agent
        )
        snapshot = AgentSnapshot(
            id="agent-default",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
        )
        settings = Settings(
            workspace_root=str(tmp_path),
            skill_cache_dir=str(tmp_path / "skill-cache"),
        )
        _, resources = await build_agent(
            snapshot,
            settings,
            run_id="run-2",
            session_id="session-2",
            tenant_id="tenant-1",
        )
        await resources.aclose()
        assert built[0]["interrupt_on"] is None
        assert built[0]["response_format"] is None
        assert built[0]["memory"] is None

    asyncio.run(run())


def test_root_agent_passes_store_and_rubric(monkeypatch, tmp_path):
    """
    中文说明：
        验证跨会话 Store 被透传到 create_deep_agent，且声明 rubric 时才装配
        RubricMiddleware，避免无自评需求的 Agent 额外创建评分模型。

    参数：
        - monkeypatch: 未声明类型：用于替换模型与 Agent 构建函数。
        - tmp_path: 未声明类型：用于提供隔离的工作区目录。

    返回：
        None。

    异常与边界：
        测试不连接模型、Store 或 Redis。
    """

    async def run():
        """
        中文说明：
            分别构建带 rubric 与不带 rubric 的 Agent，并检查构建参数。

        参数：
            - 无：函数使用闭包变量完成工作。

        返回：
            None。

        异常与边界：
            构建失败时异常向上抛出。
        """
        from deepagents.middleware.rubric import RubricMiddleware

        built = []

        def fake_agent(**kwargs):
            """
            中文说明：
                记录构建参数并返回最小替身。

            参数：
                - **kwargs: 未声明类型：构建参数。

            返回：
                带 name 属性的 SimpleNamespace。

            异常与边界：
                无外部依赖。
            """
            built.append(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent", fake_agent
        )
        settings = Settings(
            _env_file=None,
            workspace_root=str(tmp_path),
            skill_cache_dir=str(tmp_path / "skill-cache"),
        )
        store = object()
        snapshot = AgentSnapshot(
            id="agent-rubric",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
            rubric="回答必须给出数据来源与筛选条件",
        )
        _, resources = await build_agent(
            snapshot,
            settings,
            store=store,
            run_id="run-3",
            session_id="session-3",
            tenant_id="tenant-1",
        )
        await resources.aclose()
        assert built[0]["store"] is store
        assert any(
            isinstance(item, RubricMiddleware) for item in built[0]["middleware"]
        )

        plain = AgentSnapshot(
            id="agent-plain",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
        )
        _, resources = await build_agent(
            plain,
            settings,
            run_id="run-4",
            session_id="session-4",
            tenant_id="tenant-1",
        )
        await resources.aclose()
        assert built[1]["store"] is None
        assert not any(
            isinstance(item, RubricMiddleware) for item in built[1]["middleware"]
        )

    asyncio.run(run())


def test_todo_tool_and_async_subagents_are_wired(monkeypatch, tmp_path):
    """
    中文说明：
        验证 plan.todo_tool 会装配 TodoListMiddleware，异步子 Agent 声明会以
        AsyncSubAgent 形式进入 subagents 列表。

    参数：
        - monkeypatch: 未声明类型：用于替换模型与 Agent 构建函数。
        - tmp_path: 未声明类型：用于提供隔离的工作区目录。

    返回：
        None。

    异常与边界：
        测试不连接远端 Agent Protocol 服务。
    """

    async def run():
        """
        中文说明：
            构建带 Todo 与异步子 Agent 的 Agent，并检查构建参数。

        参数：
            - 无：函数使用闭包变量完成工作。

        返回：
            None。

        异常与边界：
            构建失败时异常向上抛出。
        """
        from langchain.agents.middleware import TodoListMiddleware

        built = []

        def fake_agent(**kwargs):
            """
            中文说明：
                记录构建参数并返回最小替身。

            参数：
                - **kwargs: 未声明类型：构建参数。

            返回：
                带 name 属性的 SimpleNamespace。

            异常与边界：
                无外部依赖。
            """
            built.append(kwargs)
            return SimpleNamespace(name=kwargs["name"])

        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory._chat_model",
            lambda config, settings: object(),
        )
        monkeypatch.setattr(
            "data_agent_runtime.runtime.factory.create_deep_agent", fake_agent
        )
        settings = Settings(
            _env_file=None,
            workspace_root=str(tmp_path),
            skill_cache_dir=str(tmp_path / "skill-cache"),
        )
        snapshot = AgentSnapshot(
            id="agent-todo",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
            compression={"enabled": False},
            plan={"enabled": True, "todo_tool": True},
            async_subagents=[
                {
                    "name": "long-analysis",
                    "description": "长时间分析任务",
                    "graph_id": "analysis-graph",
                    "url": "https://agent-protocol.test",
                }
            ],
        )
        _, resources = await build_agent(
            snapshot,
            settings,
            run_id="run-5",
            session_id="session-5",
            tenant_id="tenant-1",
        )
        await resources.aclose()

        assert any(
            isinstance(item, TodoListMiddleware) for item in built[0]["middleware"]
        )
        async_specs = [item for item in built[0]["subagents"] if isinstance(item, dict)]
        assert async_specs[0]["name"] == "long-analysis"
        assert async_specs[0]["graph_id"] == "analysis-graph"
        assert async_specs[0]["url"] == "https://agent-protocol.test"

    asyncio.run(run())
