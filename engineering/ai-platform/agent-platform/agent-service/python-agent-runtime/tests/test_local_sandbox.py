"""本文件模块职责：Docker/Kubernetes 本地控制面辅助函数和 Provider 行为测试。

测试验证结构化命令、路径安全、超时、容器/Pod 生命周期和文件传输逻辑，避免 Runtime 退化为宿主机命令执行。
"""

import asyncio

from data_agent_runtime.clients.docker import DockerSandboxProvider
from data_agent_runtime.clients.factory import create_sandbox_provider
from data_agent_runtime.clients.kubernetes import KubernetesSandboxProvider
from data_agent_runtime.clients.local import ProcessResult, tar_single_file
from data_agent_runtime.clients.sandbox import SandboxRunContext
from data_agent_runtime.config import Settings
from data_agent_runtime.schemas import SandboxConfig


def _context() -> SandboxRunContext:
    """
    中文说明：
        实现 tests/test_local_sandbox 的内部辅助步骤“_context”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        SandboxRunContext。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return SandboxRunContext(
        run_id="run-local-provider",
        tenant_id="tenant-1",
        session_id="session-1",
    )


def test_factory_selects_docker_and_kubernetes_providers():
    """
    中文说明：
        验证 tests/test_local_sandbox 中“factory_selects_docker_and_kubernetes_providers”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    docker = create_sandbox_provider(
        Settings(sandbox_provider="docker"),
        SandboxConfig(enabled=True),
        _context(),
    )
    kubernetes = create_sandbox_provider(
        Settings(sandbox_provider="kubernetes"),
        SandboxConfig(enabled=True),
        _context(),
    )
    assert isinstance(docker, DockerSandboxProvider)
    assert isinstance(kubernetes, KubernetesSandboxProvider)


def test_docker_provider_lifecycle_and_structured_commands(monkeypatch):
    """
    中文说明：
        验证 tests/test_local_sandbox 中“docker_provider_lifecycle_and_structured_commands”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。

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
        calls: list[list[str]] = []
        archive = tar_single_file("/workspace/result.txt", b"hello")

        async def fake_runner(argv, *, input_bytes=None, timeout_seconds):
            """
            中文说明：
                实现 tests/test_local_sandbox 的“fake_runner”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - argv: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - input_bytes: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - timeout_seconds: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            calls.append(list(argv))
            if "create" in argv:
                return ProcessResult(0, b"container-1\n", b"")
            if "start" in argv:
                return ProcessResult(0, b"container-1\n", b"")
            if "exec" in argv and "tar" in argv and "-x" in argv:
                assert input_bytes
                return ProcessResult(0, b"", b"")
            if "exec" in argv and "tar" in argv and "-c" in argv:
                return ProcessResult(0, archive, b"")
            if "exec" in argv:
                return ProcessResult(0, b"ok", b"")
            if "rm" in argv:
                return ProcessResult(0, b"", b"")
            raise AssertionError(argv)

        monkeypatch.setattr("data_agent_runtime.clients.docker.run_control_command", fake_runner)
        provider = DockerSandboxProvider(
            Settings(
                sandbox_provider="docker",
                docker_default_image="analysis:latest",
            ),
            SandboxConfig(enabled=True, allow_commands=["python3"]),
            _context(),
        )
        await provider.write_file("/workspace/result.txt", b"hello")
        assert await provider.read_file("/workspace/result.txt") == b"hello"
        result = await provider.run("python3", ["/workspace/a.py"])
        assert result.status == "COMPLETED"
        artifact = await provider.collect_artifact("/workspace/result.txt")
        assert artifact.size_bytes == 5
        await provider.aclose()
        assert any("--network" in call and "none" in call for call in calls)
        assert any("--cap-drop" in call for call in calls)
        assert any("--security-opt" in call for call in calls)

    asyncio.run(run())


def test_kubernetes_provider_lifecycle_and_network_policy(monkeypatch):
    """
    中文说明：
        验证 tests/test_local_sandbox 中“kubernetes_provider_lifecycle_and_network_policy”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。

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
        calls: list[list[str]] = []
        archive = tar_single_file("/workspace/result.txt", b"hello")

        async def fake_runner(argv, *, input_bytes=None, timeout_seconds):
            """
            中文说明：
                实现 tests/test_local_sandbox 的“fake_runner”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - argv: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - input_bytes: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - timeout_seconds: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            calls.append(list(argv))
            if "apply" in argv:
                assert input_bytes
                assert b"NetworkPolicy" in input_bytes
                return ProcessResult(0, b"applied", b"")
            if "wait" in argv:
                return ProcessResult(0, b"condition met", b"")
            if "exec" in argv and "-x" in argv:
                assert input_bytes
                return ProcessResult(0, b"", b"")
            if "exec" in argv and "-c" in argv and "tar" in argv:
                return ProcessResult(0, archive, b"")
            if "exec" in argv:
                return ProcessResult(0, b"ok", b"")
            if "delete" in argv:
                return ProcessResult(0, b"deleted", b"")
            raise AssertionError(argv)

        monkeypatch.setattr(
            "data_agent_runtime.clients.kubernetes.run_control_command", fake_runner
        )
        provider = KubernetesSandboxProvider(
            Settings(
                sandbox_provider="kubernetes",
                kubernetes_namespace="data-agent-test",
            ),
            SandboxConfig(enabled=True, allow_commands=["python3"]),
            _context(),
        )
        await provider.write_file("/workspace/result.txt", b"hello")
        assert await provider.read_file("/workspace/result.txt") == b"hello"
        result = await provider.run("python3", ["/workspace/a.py"])
        assert result.status == "COMPLETED"
        await provider.aclose()
        assert any("apply" in call for call in calls)
        assert any("--for=condition=Ready" in call for call in calls)
        assert any("delete" in call and "pod" in call for call in calls)

    asyncio.run(run())


def test_docker_provider_reuses_one_container_for_concurrent_tools(monkeypatch):
    """
    中文说明：
        验证 tests/test_local_sandbox 中“docker_provider_reuses_one_container_for_concurrent_tools”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - monkeypatch: 未声明类型：由调用方传入，用于完成本函数的核心处理。

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
        calls: list[list[str]] = []

        async def fake_runner(argv, *, input_bytes=None, timeout_seconds):
            """
            中文说明：
                实现 tests/test_local_sandbox 的“fake_runner”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - argv: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - input_bytes: 未声明类型：由调用方传入，用于完成本函数的核心处理。
                - timeout_seconds: 未声明类型：由调用方传入，用于完成本函数的核心处理。

            返回：
                根据具体分支返回结果或抛出异常。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            calls.append(list(argv))
            if "create" in argv:
                await asyncio.sleep(0.01)
                return ProcessResult(0, b"container-concurrent\n", b"")
            if "start" in argv:
                return ProcessResult(0, b"container-concurrent\n", b"")
            if "rm" in argv:
                return ProcessResult(0, b"", b"")
            raise AssertionError(argv)

        monkeypatch.setattr("data_agent_runtime.clients.docker.run_control_command", fake_runner)
        provider = DockerSandboxProvider(
            Settings(sandbox_provider="docker"),
            SandboxConfig(enabled=True),
            _context(),
        )
        responses = await asyncio.gather(
            provider.ensure_created(),
            provider.ensure_created(),
            provider.ensure_created(),
        )
        assert {response.sandbox_id for response in responses} == {"container-concurrent"}
        assert sum("create" in call for call in calls) == 1
        await provider.aclose()

    asyncio.run(run())
