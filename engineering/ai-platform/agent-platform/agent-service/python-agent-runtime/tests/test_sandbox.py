"""本文件模块职责：HTTP Sandbox Provider 和 Sandbox Tool 的契约测试。

测试覆盖 HTTP 请求、鉴权、创建会话、文件读写、命令执行、产物收集、超时、错误转换和资源关闭。
"""

import asyncio
import base64
import json

import httpx
import pytest

from data_agent_runtime.clients.factory import (
    SandboxProviderConfigurationError,
    create_sandbox_provider,
)
from data_agent_runtime.clients.sandbox import (
    HttpSandboxProvider,
    SandboxClient,
    SandboxGatewayError,
    SandboxRunContext,
)
from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.signing import content_sha256, verify_signature
from data_agent_runtime.schemas import SandboxConfig
from data_agent_runtime.tools.sandbox import create_sandbox_tools


def make_client(handler):
    """
    中文说明：
        实现 tests/test_sandbox 的“make_client”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - handler: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://gateway.test")
    settings = Settings(
        app_env="test",
        sandbox_gateway_access_key="runtime-sandbox",
        sandbox_gateway_secret_key="sandbox-secret",
        sandbox_gateway_base_url="http://gateway.test",
        sandbox_read_timeout_seconds=10,
    )
    client = SandboxClient(
        settings,
        SandboxConfig(
            enabled=True,
            image="data-analysis-python",
            image_digest="sha256:abc",
            allow_commands=["python3"],
        ),
        SandboxRunContext(
            run_id="run-1",
            tenant_id="tenant-1",
            session_id="session-1",
            user_id="user-1",
        ),
        http_client=http,
    )
    return client, http


def test_sandbox_session_is_lazy_and_command_is_structured():
    """
    中文说明：
        验证 tests/test_sandbox 中“sandbox_session_is_lazy_and_command_is_structured”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

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
        calls = []

        async def handler(request: httpx.Request) -> httpx.Response:
            """
            中文说明：
                实现 tests/test_sandbox 的“handler”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - request: httpx.Request：由调用方传入，用于完成本函数的核心处理。

            返回：
                httpx.Response。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            calls.append(request)
            body = request.content
            assert request.headers["X-Access-Key"] == "runtime-sandbox"
            assert request.headers["X-Content-SHA256"] == content_sha256(body)
            assert verify_signature(
                signature=request.headers["X-Signature"],
                secret_key="sandbox-secret",
                access_key=request.headers["X-Access-Key"],
                timestamp=request.headers["X-Timestamp"],
                nonce=request.headers["X-Nonce"],
                method=request.method,
                path=request.url.path,
                query=request.url.query,
                body=body,
            )
            if request.method == "POST" and request.url.path == "/v1/sandboxes":
                body = json.loads(request.content)
                assert body["image_digest"] == "sha256:abc"
                assert body["network_mode"] == "none"
                return httpx.Response(200, json={"sandbox_id": "sb-1", "status": "READY"})
            if request.method == "POST" and request.url.path.endswith("/commands"):
                body = json.loads(request.content)
                assert body == {
                    "executable": "python3",
                    "args": ["/workspace/a.py"],
                    "timeout_seconds": 60,
                    "max_output_bytes": 1048576,
                }
                return httpx.Response(
                    200,
                    json={
                        "status": "COMPLETED",
                        "exit_code": 0,
                        "stdout": "ok",
                        "stderr": "",
                        "truncated": False,
                        "duration_ms": 10,
                    },
                )
            if request.method == "DELETE":
                return httpx.Response(204)
            raise AssertionError(f"unexpected request: {request.method} {request.url}")

        client, http = make_client(handler)
        assert client.is_created is False
        result = await client.run("python3", ["/workspace/a.py"])
        assert result.exit_code == 0
        assert result.stdout == "ok"
        assert client.is_created is True
        assert len([call for call in calls if call.url.path == "/v1/sandboxes"]) == 1
        assert calls[0].headers["X-Signature-Version"] == "DATA_AGENT-HMAC-SHA256"
        assert calls[0].headers["X-Access-Key"] == "runtime-sandbox"
        await client.aclose()
        await http.aclose()

    asyncio.run(run())


def test_sandbox_rejects_unsafe_paths_and_unapproved_commands():
    """
    中文说明：
        验证 tests/test_sandbox 中“sandbox_rejects_unsafe_paths_and_unapproved_commands”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

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
        async def handler(request: httpx.Request) -> httpx.Response:
            """
            中文说明：
                实现 tests/test_sandbox 的“handler”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - request: httpx.Request：由调用方传入，用于完成本函数的核心处理。

            返回：
                httpx.Response。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            if request.url.path == "/v1/sandboxes":
                return httpx.Response(200, json={"sandbox_id": "sb-1", "status": "READY"})
            if request.method == "DELETE":
                return httpx.Response(204)
            raise AssertionError("the rejected operations must not reach the gateway")

        client, http = make_client(handler)
        with pytest.raises(SandboxGatewayError, match="unsafe path"):
            await client.write_file("/workspace/../secret", b"no")
        with pytest.raises(SandboxGatewayError, match="not allowed"):
            await client.run("bash", [])
        await client.aclose()
        await http.aclose()

    asyncio.run(run())


def test_file_round_trip_and_artifact():
    """
    中文说明：
        验证 tests/test_sandbox 中“file_round_trip_and_artifact”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

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
        async def handler(request: httpx.Request) -> httpx.Response:
            """
            中文说明：
                实现 tests/test_sandbox 的“handler”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - request: httpx.Request：由调用方传入，用于完成本函数的核心处理。

            返回：
                httpx.Response。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            if request.url.path == "/v1/sandboxes":
                return httpx.Response(200, json={"sandbox_id": "sb-1", "status": "READY"})
            if request.url.path.endswith("/files"):
                body = json.loads(request.content)
                assert base64.b64decode(body["content_base64"]) == b"hello"
                return httpx.Response(200, json={"path": body["path"], "size_bytes": 5})
            if request.url.path.endswith("/files:read"):
                return httpx.Response(
                    200,
                    json={
                        "path": "/workspace/out.txt",
                        "content_base64": base64.b64encode(b"hello").decode(),
                    },
                )
            if request.url.path.endswith("/artifacts"):
                return httpx.Response(
                    200,
                    json={
                        "artifact_id": "artifact-1",
                        "file_name": "out.txt",
                        "size_bytes": 5,
                        "sha256": "abc",
                    },
                )
            if request.method == "DELETE":
                return httpx.Response(204)
            raise AssertionError(f"unexpected request: {request.url}")

        client, http = make_client(handler)
        written = await client.write_file("/workspace/out.txt", b"hello")
        assert written.size_bytes == 5
        assert await client.read_file("/workspace/out.txt") == b"hello"
        artifact = await client.collect_artifact("/workspace/out.txt")
        assert artifact.artifact_id == "artifact-1"
        await client.aclose()
        await http.aclose()

    asyncio.run(run())


def test_sandbox_tools_expose_only_restricted_operations():
    """
    中文说明：
        验证 tests/test_sandbox 中“sandbox_tools_expose_only_restricted_operations”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

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
        async def handler(request: httpx.Request) -> httpx.Response:
            """
            中文说明：
                实现 tests/test_sandbox 的“handler”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - request: httpx.Request：由调用方传入，用于完成本函数的核心处理。

            返回：
                httpx.Response。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            if request.url.path == "/v1/sandboxes":
                return httpx.Response(200, json={"sandbox_id": "sb-1", "status": "READY"})
            if request.url.path.endswith("/commands"):
                return httpx.Response(200, json={"status": "COMPLETED", "exit_code": 0})
            if request.method == "DELETE":
                return httpx.Response(204)
            raise AssertionError(f"unexpected request: {request.url}")

        client, http = make_client(handler)
        tools = create_sandbox_tools(client)
        assert [tool.name for tool in tools] == [
            "sandbox_write_file",
            "sandbox_run",
            "sandbox_read_file",
            "sandbox_collect_artifact",
        ]
        result = await tools[1].ainvoke(
            {"executable": "python3", "args": ["/workspace/a.py"]}
        )
        assert json.loads(result)["status"] == "COMPLETED"
        await client.aclose()
        await http.aclose()

    asyncio.run(run())


def test_sandbox_provider_factory_is_not_java_specific():
    """
    中文说明：
        验证 tests/test_sandbox 中“sandbox_provider_factory_is_not_java_specific”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    settings = Settings(
        app_env="test",
        sandbox_provider="http",
        sandbox_gateway_base_url="http://sandbox-sidecar.test",
    )
    provider = create_sandbox_provider(
        settings,
        SandboxConfig(enabled=True),
        SandboxRunContext(run_id="run-1", tenant_id="tenant-1", session_id="session-1"),
    )
    assert isinstance(provider, HttpSandboxProvider)


def test_sandbox_provider_factory_rejects_unknown_provider():
    """
    中文说明：
        验证 tests/test_sandbox 中“sandbox_provider_factory_rejects_unknown_provider”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    settings = Settings(
        app_env="test",
        sandbox_provider="unknown",
        sandbox_gateway_base_url="http://sandbox.test",
    )
    with pytest.raises(SandboxProviderConfigurationError, match="unsupported"):
        create_sandbox_provider(
            settings,
            SandboxConfig(enabled=True),
            SandboxRunContext(run_id="run-1", tenant_id="tenant-1", session_id="session-1"),
        )


def test_subagent_scope_is_forwarded_and_separates_idempotency_keys():
    """
    中文说明：
        验证 tests/test_sandbox 中“subagent_scope_is_forwarded_and_separates_idempotency_keys”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

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
        calls = []

        async def handler(request: httpx.Request) -> httpx.Response:
            """
            中文说明：
                实现 tests/test_sandbox 的“handler”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

            参数：
                - request: httpx.Request：由调用方传入，用于完成本函数的核心处理。

            返回：
                httpx.Response。

            异常与边界：
                外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
            """
            calls.append(request)
            if request.url.path == "/v1/sandboxes":
                body = json.loads(request.content)
                assert body["sandbox_scope"] == "subagent/python-analysis"
                assert request.headers["X-Sandbox-Scope"] == "subagent/python-analysis"
                assert "subagent/python-analysis" in request.headers["Idempotency-Key"]
                return httpx.Response(200, json={"sandbox_id": "sb-child", "status": "READY"})
            if request.method == "DELETE":
                assert "subagent/python-analysis" in request.headers["Idempotency-Key"]
                return httpx.Response(204)
            raise AssertionError(f"unexpected request: {request.url}")

        settings = Settings(
            app_env="test",
            sandbox_gateway_access_key="runtime-sandbox",
            sandbox_gateway_secret_key="sandbox-secret",
            sandbox_gateway_base_url="http://gateway.test",
        )
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://gateway.test"
        )
        client = HttpSandboxProvider(
            settings,
            SandboxConfig(enabled=True),
            SandboxRunContext(
                run_id="run-1",
                tenant_id="tenant-1",
                session_id="session-1",
                sandbox_scope="subagent/python-analysis",
            ),
            http_client=http,
        )
        await client.ensure_created()
        await client.aclose()
        await http.aclose()
        assert len(calls) == 2

    asyncio.run(run())


def test_java_gateway_config_name_is_no_longer_accepted():
    """
    中文说明：
        验证历史配置名 `java_gateway` 已被彻底移除：Provider 选择只看通用契约名，
        Runtime 不再内置任何以具体控制面命名的取值，误配置时应当直接失败而不是静默回退。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        None。

    异常与边界：
        配置非法时抛出 SandboxProviderConfigurationError，避免把部署错误推迟到运行期。
    """
    settings = Settings(
        app_env="test",
        sandbox_provider="java_gateway",
        sandbox_gateway_base_url="http://sandbox.test",
    )
    with pytest.raises(SandboxProviderConfigurationError, match="unsupported"):
        create_sandbox_provider(
            settings,
            SandboxConfig(enabled=True),
            SandboxRunContext(run_id="r", tenant_id="t", session_id="s"),
        )


def test_default_sandbox_provider_is_neutral_http():
    """
    中文说明：
        验证默认 Sandbox Provider 是中性名称 `http`，且与 `http_gateway` 等价，
        确保公共 Runtime 的默认配置不指向任何具体实现方。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        None。

    异常与边界：
        本次断言只比较类型与默认值，不建立任何网络连接。
    """
    context = SandboxRunContext(run_id="r", tenant_id="t", session_id="s")
    # 关闭 .env 加载，验证的是代码默认值本身，避免被本地配置干扰。
    default_settings = Settings(
        _env_file=None, app_env="test", sandbox_gateway_base_url="http://sandbox.test"
    )
    assert default_settings.sandbox_provider == "http"
    assert isinstance(
        create_sandbox_provider(default_settings, SandboxConfig(enabled=True), context),
        HttpSandboxProvider,
    )
    alias_settings = Settings(
        app_env="test",
        sandbox_provider="http_gateway",
        sandbox_gateway_base_url="http://sandbox.test",
    )
    assert isinstance(
        create_sandbox_provider(alias_settings, SandboxConfig(enabled=True), context),
        HttpSandboxProvider,
    )
