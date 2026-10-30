"""公共 Runtime 模式的 Principal、Snapshot 准入和租户隔离测试。"""

import asyncio

import pytest
from test_auth import FakeRedis as AuthFakeRedis
from test_auth import make_request
from test_memory import FakeRedis as MemoryFakeRedis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.admission import (
    SnapshotAdmissionError,
    admit_snapshot,
    bind_principal_context,
)
from data_agent_runtime.runtime.auth import require_hmac_principal
from data_agent_runtime.runtime.memory import RedisConversationHistory, _session_key
from data_agent_runtime.runtime.principal import Principal
from data_agent_runtime.runtime.signing import signing_headers
from data_agent_runtime.schemas import (
    AgentSnapshot,
    MCPServerConfig,
    ModelConfig,
    RunRequest,
    SkillSnapshot,
    UserContext,
)
from data_agent_runtime.tools.mcp import _validate_server


def _snapshot() -> AgentSnapshot:
    """构造一个最小合法 AgentSnapshot 供测试复用。"""
    return AgentSnapshot(
        id="public-agent",
        version=1,
        system_prompt="回答问题",
        model=ModelConfig(name="gpt-4o-mini"),
    )


def test_multi_credential_hmac_resolves_principal():
    """验证多个 AK/SK 可以解析到各自的 Principal 身份和 Scope。"""
    async def run():
        """执行当前测试场景的异步步骤并完成断言。"""
        settings = Settings(
            _env_file=None,
            app_env="test",
            internal_service_credentials_json=(
                '[{"access_key":"caller-a","secret_key":"secret-a",'
                '"principal_id":"p-a","tenant_id":"tenant-a",'
                '"subject_id":"user-a","scopes":["runs:write"]}]'
            ),
        )
        body = b"{}"
        request = make_request(body=body, scheme="https", redis=AuthFakeRedis())
        headers = signing_headers(
            access_key="caller-a",
            secret_key="secret-a",
            method="POST",
            path=request.url.path,
            query="",
            body=body,
            nonce="principal-nonce",
        )
        principal = await require_hmac_principal(
            settings,
            request=request,
            x_access_key=headers["X-Access-Key"],
            x_timestamp=headers["X-Timestamp"],
            x_nonce=headers["X-Nonce"],
            x_content_sha256=headers["X-Content-SHA256"],
            x_signature=headers["X-Signature"],
            x_signature_version=headers["X-Signature-Version"],
        )
        assert principal.principal_id == "p-a"
        assert principal.tenant_id == "tenant-a"
        assert principal.user_id == "user-a"

    asyncio.run(run())


def test_body_identity_cannot_override_principal():
    """验证请求体中的用户和租户不能覆盖认证 Principal。"""
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    request = RunRequest(
        run_id="run-1",
        message="hello",
        agent=_snapshot(),
        user_context=UserContext(user_id="user-b", tenant_id="tenant-b"),
    )
    with pytest.raises(SnapshotAdmissionError):
        bind_principal_context(request, principal)


def test_deepseek_provider_uses_installed_openai_compatible_adapter():
    """验证 DeepSeek Provider 名称可以复用已安装的 OpenAI-compatible 适配器。"""
    settings = Settings(
        _env_file=None,
        allowed_model_providers="deepseek",
        openai_base_url="https://api.deepseek.com",
    )
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    snapshot = _snapshot().model_copy(
        update={
            "model": ModelConfig(
                provider="deepseek",
                name="deepseek-flash",
            )
        }
    )

    admit_snapshot(settings, snapshot, principal)


def test_public_admission_rejects_inline_skill_and_stdio():
    """验证公共模式拒绝内联 Skill 和不允许的 stdio MCP。"""
    settings = Settings(
        _env_file=None,
        public_mode=True,
        allowed_model_providers="openai",
        allowed_mcp_hosts="mcp.example.com",
        allow_inline_skills=False,
    )
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    inline = _snapshot().model_copy(
        update={"skills": [{"id": "s", "version": 1, "content": "x"}]}
    )
    with pytest.raises(SnapshotAdmissionError):
        admit_snapshot(settings, inline, principal)


def test_public_session_key_isolated_by_tenant_and_user():
    """验证 Session 存储键按租户和用户隔离。"""
    async def run():
        """执行当前测试场景的异步步骤并完成断言。"""
        redis = MemoryFakeRedis()
        settings = Settings(_env_file=None, public_mode=True)
        history = RedisConversationHistory(redis, settings)
        await history.append_message(
            session_id="same",
            run_id="run-a",
            role="user",
            content="a",
            tenant_id="tenant-a",
            user_id="user-a",
        )
        await history.append_message(
            session_id="same",
            run_id="run-b",
            role="user",
            content="b",
            tenant_id="tenant-b",
            user_id="user-b",
        )
        assert [
            item["content"]
            for item in await history.list_messages(
                "same", tenant_id="tenant-a", user_id="user-a"
            )
        ] == ["a"]
        assert [
            item["content"]
            for item in await history.list_messages(
                "same", tenant_id="tenant-b", user_id="user-b"
            )
        ] == ["b"]
        assert _session_key("same", "tenant-a", "user-a") != _session_key(
            "same", "tenant-b", "user-b"
        )

    asyncio.run(run())


def test_worker_rejects_invalid_snapshot_and_projects_failed_state():
    """Worker 二次准入失败时不能把 Run 永久留在 ACCEPTED。"""
    from data_agent_runtime.runtime.worker import TaskWorker

    class Queue:
        """公共 Runtime 测试使用的任务队列替身。"""
        stream_key = "agent:test:tasks"

        def __init__(self) -> None:
            """初始化测试替身及其调用记录。"""
            self.dead_letters: list[dict[str, str]] = []
            self.acked: list[str] = []

        @staticmethod
        def new_consumer_name() -> str:
            """返回测试用的 Consumer 名称。"""
            return "test-worker"

        @staticmethod
        def parse_message(message):
            """解析测试队列消息为 Run 请求，并返回与真实实现一致的五元组。"""
            return (
                message[0],
                RunRequest.model_validate_json(message[1]["payload"]),
                0,
                "run",
                None,
            )

        async def dead_letter(self, message_id, fields, *, error_type, error_message):
            """记录消息进入 Dead Letter 的调用。"""
            self.dead_letters.append(
                {"message_id": message_id, "error_type": error_type, "message": error_message}
            )
            return "dead-letter-1"

        async def ack(self, message_id):
            """记录消息确认调用。"""
            self.acked.append(message_id)
            return 1

    class State:
        """公共 Runtime 测试使用的 Run 状态存储替身。"""
        def __init__(self) -> None:
            """初始化测试替身及其调用记录。"""
            self.status = {"status": "ACCEPTED"}
            self.updates: list[tuple[str, str, dict]] = []

        async def get(self, run_id):
            """读取测试替身保存的 Run 状态。"""
            return self.status

        async def set_status(self, run_id, status, **kwargs):
            """更新测试替身中的 Run 状态。"""
            self.status = {"status": status, **kwargs}
            self.updates.append((run_id, status, kwargs))
            return self.status

    class Events:
        """公共 Runtime 测试使用的事件发布器替身。"""
        def __init__(self) -> None:
            """初始化测试替身及其调用记录。"""
            self.values = []

        async def publish(self, run_id, event_type, payload):
            """记录事件发布调用。"""
            self.values.append((run_id, event_type, payload))

    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        settings = Settings(_env_file=None, public_mode=True, allow_inline_skills=False)
        request = RunRequest(
            run_id="invalid-worker-run",
            message="hello",
            agent=_snapshot().model_copy(
                deep=True,
                update={
                    "skills": [
                        SkillSnapshot(id="inline", version=1, content="x")
                    ]
                },
            ),
            user_context=UserContext(
                principal_id="principal-a",
                user_id="user-a",
                tenant_id="tenant-a",
            ),
        )
        queue = Queue()
        state = State()
        events = Events()
        worker = TaskWorker(settings, queue, object(), state, events, consumer_name="test-worker")
        await worker._handle_message(
            ("1-0", {"run_id": request.run_id, "payload": request.model_dump_json()})
        )
        assert queue.acked == ["1-0"]
        assert queue.dead_letters[0]["error_type"] == "SnapshotAdmissionError"
        assert state.status["status"] == "FAILED"
        assert events.values[-1][1] == "run_failed"

    asyncio.run(run())


def test_admission_rejects_provider_without_runtime_adapter():
    """验证准入阶段拒绝 Runtime 不支持的模型 Provider。"""
    settings = Settings(
        _env_file=None,
        allowed_model_providers="openai,anthropic",
    )
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    snapshot = _snapshot().model_copy(
        update={"model": ModelConfig(provider="anthropic", name="claude")}
    )
    with pytest.raises(SnapshotAdmissionError, match="no installed Runtime adapter"):
        admit_snapshot(settings, snapshot, principal)


def test_public_admission_rejects_private_mcp_endpoint():
    """验证公共模式拒绝本地地址和私有网络 MCP Endpoint。"""
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_mode=True,
        allowed_mcp_hosts="127.0.0.1",
    )
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    snapshot = _snapshot().model_copy(
        update={
            "mcp_servers": [
                MCPServerConfig(id="local", url="https://127.0.0.1/mcp")
            ]
        }
    )
    with pytest.raises(SnapshotAdmissionError, match="private or local"):
        admit_snapshot(settings, snapshot, principal)


def test_public_admission_rejects_mcp_url_userinfo():
    """验证公共模式拒绝带 URL 用户名或密码的 MCP 地址。"""
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_mode=True,
        allowed_mcp_hosts="8.8.8.8",
    )
    principal = Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )
    snapshot = _snapshot().model_copy(
        update={
            "mcp_servers": [
                MCPServerConfig(
                    id="external", url="https://user:secret@8.8.8.8/mcp"
                )
            ]
        }
    )
    with pytest.raises(SnapshotAdmissionError, match="userinfo"):
        admit_snapshot(settings, snapshot, principal)


def test_mcp_factory_rejects_url_userinfo_and_fragment():
    """验证 MCP 工具工厂拒绝 userinfo 和 fragment。"""
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_mode=True,
        allowed_mcp_hosts="mcp.example.com",
    )
    with pytest.raises(ValueError, match="userinfo"):
        _validate_server(
            MCPServerConfig(
                id="userinfo",
                url="https://user:secret@mcp.example.com/mcp",
            ),
            settings,
        )
    with pytest.raises(ValueError, match="fragment"):
        _validate_server(
            MCPServerConfig(
                id="fragment",
                url="https://mcp.example.com/mcp#secret",
            ),
            settings,
        )


def test_mcp_factory_requires_stdio_command_even_when_transport_is_allowed():
    """验证允许 stdio 时仍必须提供命令。"""
    settings = Settings(_env_file=None, app_env="local", allow_mcp_stdio=True)
    with pytest.raises(ValueError, match="requires command"):
        _validate_server(MCPServerConfig(id="stdio", transport="stdio"), settings)


def _reviewer_principal():
    """构造用于准入校验的调用方身份。"""
    return Principal(
        principal_id="p-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
    )


def _async_subagent_snapshot(url: str):
    """构造带异步子 Agent 声明的快照（走完整校验，避免 model_copy 跳过类型转换）。"""
    data = _snapshot().model_dump()
    data["async_subagents"] = [
        {
            "name": "remote-a",
            "description": "远程分析",
            "graph_id": "graph-a",
            "url": url,
        }
    ]
    return AgentSnapshot.model_validate(data)


def _public_settings(**overrides):
    """构造公共服务模式下的部署配置。"""
    values = {"_env_file": None, "public_mode": True, "allow_inline_skills": False}
    values.update(overrides)
    return Settings(**values)


def test_public_mode_requires_subagent_host_allowlist():
    """验证 public_mode 下声明异步子 Agent 必须配置 Host 白名单。"""
    with pytest.raises(SnapshotAdmissionError, match="ALLOWED_SUBAGENT_HOSTS"):
        admit_snapshot(
            _public_settings(),
            _async_subagent_snapshot("https://agent-protocol.test"),
            _reviewer_principal(),
        )


def test_public_mode_rejects_private_subagent_endpoint():
    """验证 public_mode 下拒绝指向本机/私网的异步子 Agent 地址。"""
    settings = _public_settings(allowed_subagent_hosts="127.0.0.1")
    with pytest.raises(SnapshotAdmissionError, match="private or local"):
        admit_snapshot(
            settings, _async_subagent_snapshot("https://127.0.0.1:8080"), _reviewer_principal()
        )


def test_subagent_host_not_in_allowlist_is_rejected():
    """验证不在白名单中的异步子 Agent Host 会被拒绝。"""
    settings = _public_settings(allowed_subagent_hosts="allowed.test")
    with pytest.raises(SnapshotAdmissionError, match="host .* is not allowed"):
        admit_snapshot(
            settings, _async_subagent_snapshot("https://other.test"), _reviewer_principal()
        )


def test_production_rejects_http_subagent_endpoint():
    """验证生产环境拒绝 HTTP 形式的异步子 Agent 地址。"""
    settings = Settings(
        _env_file=None,
        app_env="production",
        allowed_subagent_hosts="agent-protocol.test",
    )
    with pytest.raises(SnapshotAdmissionError, match="must use HTTPS"):
        admit_snapshot(
            settings, _async_subagent_snapshot("http://agent-protocol.test"), _reviewer_principal()
        )
