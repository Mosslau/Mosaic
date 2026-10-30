"""公共 Runtime API 的入队、身份绑定和 HTTP 契约测试。"""

import asyncio

import pytest
from fastapi import HTTPException

from data_agent_runtime import api
from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.principal import Principal
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    RunResumeRequest,
    UserContext,
)


def _snapshot() -> AgentSnapshot:
    """构造一个最小合法 AgentSnapshot 供测试复用。"""
    return AgentSnapshot(
        id="agent-api-test",
        version=1,
        system_prompt="回答问题",
        model=ModelConfig(name="gpt-4o-mini"),
    )


class _Queue:
    """API 测试使用的最小任务队列替身。"""
    def __init__(self, result: tuple[bool, str] = (True, "1-0")) -> None:
        """初始化测试替身及其调用记录。"""
        self.requests: list[RunRequest] = []
        self.result = result

    async def enqueue(self, request: RunRequest) -> tuple[bool, str]:
        """记录任务入队并返回测试预设结果。"""
        self.requests.append(request)
        return self.result


def _principal() -> Principal:
    """构造测试使用的认证 Principal。"""
    return Principal(
        principal_id="principal-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
        scopes=frozenset({"runs:write"}),
    )


def test_runtime_api_does_not_register_internal_alias_routes():
    """验证 Runtime API 不再注册已移除的 internal 兼容路由。"""
    assert not any(route.path.startswith("/internal/") for route in api.app.routes)


def test_run_routes_return_accepted_status_code():
    """验证 Run 提交接口返回异步受理语义和正确状态码。"""
    routes = {
        route.path: route
        for route in api.app.routes
        if route.path == "/v1/runs"
        and "POST" in getattr(route, "methods", set())
    }
    assert routes["/v1/runs"].status_code == 202


def test_submit_run_binds_principal_and_uses_queue_contract(monkeypatch):
    """验证提交 Run 会绑定 Principal 并调用任务队列契约。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        settings = Settings(_env_file=None, allowed_model_providers="openai")
        queue = _Queue()
        monkeypatch.setattr(api, "settings", settings)
        monkeypatch.setattr(api.app.state, "queue", queue, raising=False)

        request = RunRequest(
            run_id="run-api-test",
            message="hello",
            agent=_snapshot(),
            internal_token="must-not-enter-queue",
        )
        accepted = await api.submit_run(request, _principal())

        assert accepted.run_id == "run-api-test"
        assert request.user_context is not None
        assert request.user_context.tenant_id == "tenant-a"
        assert request.user_context.user_id == "user-a"
        assert queue.requests[0].internal_token is None

    asyncio.run(run())


def test_submit_run_rejects_body_identity_mismatch(monkeypatch):
    """验证提交请求中的身份与 Principal 不一致时被拒绝。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api,
            "settings",
            Settings(_env_file=None, allowed_model_providers="openai"),
        )
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)
        request = RunRequest(
            run_id="run-api-forbidden",
            message="hello",
            agent=_snapshot(),
            user_context=UserContext(user_id="user-b", tenant_id="tenant-b"),
        )
        with pytest.raises(HTTPException) as error:
            await api.submit_run(request, _principal())
        assert error.value.status_code == 403

    asyncio.run(run())


class _ApprovalQueue:
    """审批流程测试使用的队列替身，覆盖批准、重复和失败结果。"""
    def __init__(self, result: tuple[str, str | None]) -> None:
        """初始化测试替身及其调用记录。"""
        self.result = result

    async def approve(self, run_id: str) -> tuple[str, str | None]:
        """模拟审批队列中的原子批准转换。"""
        return self.result


class _RunState:
    """API 测试使用的内存 Run 状态替身。"""
    def __init__(
        self,
        state: dict[str, object] | None,
        *,
        create_result: bool = True,
        create_error: Exception | None = None,
    ) -> None:
        """初始化测试替身及其调用记录。"""
        self.state = state
        self.create_result = create_result
        self.create_error = create_error
        self.created: list[RunRequest] = []

    async def get(self, run_id: str) -> dict[str, object] | None:
        """读取测试替身保存的 Run 状态。"""
        return self.state

    async def create_pending_approval(self, request: RunRequest) -> bool:
        """测试辅助函数：执行 create_pending_approval 的测试准备或断言逻辑。"""
        if self.create_error is not None:
            raise self.create_error
        self.created.append(request)
        return self.create_result


class _Events:
    """API 测试使用的事件发布替身。"""
    def __init__(self) -> None:
        """初始化测试替身及其调用记录。"""
        self.values: list[tuple[str, str, dict[str, object]]] = []

    async def publish(self, run_id: str, event_type: str, payload: dict[str, object]) -> None:
        """记录事件发布调用。"""
        self.values.append((run_id, event_type, payload))


def _approval_principal() -> Principal:
    """构造具备审批 Scope 的测试 Principal。"""
    return Principal(
        principal_id="principal-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
        scopes=frozenset({"runs:approve"}),
    )


def test_approve_run_is_idempotent_after_atomic_queue_transition(monkeypatch):
    """验证审批队列原子转换后重复审批保持幂等。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState(
                {
                    "run_id": "run-approval",
                    "status": "PENDING_APPROVAL",
                    "tenant_id": "tenant-a",
                    "user_id": "user-a",
                }
            ),
            raising=False,
        )
        events = _Events()
        monkeypatch.setattr(api.app.state, "events", events, raising=False)
        monkeypatch.setattr(
            api.app.state,
            "queue",
            _ApprovalQueue(("ACCEPTED", "42-0")),
            raising=False,
        )

        result = await api.approve_run("run-approval", _approval_principal())

        assert result == {"run_id": "run-approval", "status": "ACCEPTED"}
        assert events.values[-1][1] == "run_approved"
        assert events.values[-1][2] == {"message_id": "42-0"}

    asyncio.run(run())


def test_approve_run_requires_approval_scope(monkeypatch):
    """验证审批接口要求独立的审批 Scope。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState({"tenant_id": "tenant-a", "user_id": "user-a"}),
            raising=False,
        )
        principal = Principal(
            principal_id="principal-a",
            access_key="caller-a",
            tenant_id="tenant-a",
            subject_id="user-a",
        )
        with pytest.raises(HTTPException) as error:
            await api.approve_run("run-approval-forbidden", principal)
        assert error.value.status_code == 403

    asyncio.run(run())


def _approval_request() -> RunRequest:
    """构造审批流程所需的 RunRequest。"""
    snapshot = _snapshot()
    snapshot.plan.enabled = True
    snapshot.plan.require_approval = True
    return RunRequest(run_id="run-pending", message="hello", agent=snapshot)


def test_submit_run_persists_pending_approval_before_emitting_event(monkeypatch):
    """验证待审批 Run 先持久化状态再发布事件。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        settings = Settings(_env_file=None, allowed_model_providers="openai")
        state = _RunState(None)
        events = _Events()
        monkeypatch.setattr(api, "settings", settings)
        monkeypatch.setattr(api.app.state, "run_state", state, raising=False)
        monkeypatch.setattr(api.app.state, "events", events, raising=False)
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)

        principal = _principal()
        request = _approval_request()
        result = await api.submit_run(request, principal)

        assert result.status == "PENDING_APPROVAL"
        assert [item.run_id for item in state.created] == ["run-pending"]
        assert events.values[-1][1] == "run_pending_approval"

    asyncio.run(run())


def test_submit_run_rejects_duplicate_pending_approval(monkeypatch):
    """验证重复提交相同待审批 Run 不会覆盖已有状态。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api,
            "settings",
            Settings(_env_file=None, allowed_model_providers="openai"),
        )
        monkeypatch.setattr(
            api.app.state, "run_state", _RunState(None, create_result=False), raising=False
        )
        monkeypatch.setattr(api.app.state, "events", _Events(), raising=False)
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)

        with pytest.raises(HTTPException) as error:
            await api.submit_run(_approval_request(), _principal())
        assert error.value.status_code == 409

    asyncio.run(run())


def test_submit_run_returns_503_when_approval_persistence_fails(monkeypatch):
    """验证待审批状态持久化失败时接口返回 503。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api,
            "settings",
            Settings(_env_file=None, allowed_model_providers="openai"),
        )
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState(None, create_error=RuntimeError("redis down")),
            raising=False,
        )
        monkeypatch.setattr(api.app.state, "events", _Events(), raising=False)
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)

        with pytest.raises(HTTPException) as error:
            await api.submit_run(_approval_request(), _principal())
        assert error.value.status_code == 503

    asyncio.run(run())


def test_approve_run_handles_cancelled_and_missing_payload(monkeypatch):
    """验证审批接口正确处理已取消 Run 和缺少任务负载。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        for result, expected_status, expected_http in [
            (("CANCELLED", None), "CANCELLED", None),
            (("FAILED", None), None, 500),
        ]:
            monkeypatch.setattr(
                api.app.state,
                "run_state",
                _RunState(
                    {
                        "run_id": "run-approval",
                        "status": "PENDING_APPROVAL",
                        "tenant_id": "tenant-a",
                        "user_id": "user-a",
                    }
                ),
                raising=False,
            )
            monkeypatch.setattr(api.app.state, "events", _Events(), raising=False)
            monkeypatch.setattr(
                api.app.state, "queue", _ApprovalQueue(result), raising=False
            )
            if expected_http is None:
                assert await api.approve_run("run-approval", _approval_principal()) == {
                    "run_id": "run-approval",
                    "status": expected_status,
                }
            else:
                with pytest.raises(HTTPException) as error:
                    await api.approve_run("run-approval", _approval_principal())
                assert error.value.status_code == expected_http

    asyncio.run(run())


def test_approve_run_returns_503_when_queue_is_unavailable(monkeypatch):
    """验证审批队列不可用时接口返回 503。"""
    class _FailingApprovalQueue:
        """始终模拟 Redis 故障的审批队列替身。"""
        async def approve(self, run_id: str) -> tuple[str, str | None]:
            """模拟审批队列中的原子批准转换。"""
            raise RuntimeError("redis down")

    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState(
                {
                    "run_id": "run-approval",
                    "status": "PENDING_APPROVAL",
                    "tenant_id": "tenant-a",
                    "user_id": "user-a",
                }
            ),
            raising=False,
        )
        monkeypatch.setattr(api.app.state, "queue", _FailingApprovalQueue(), raising=False)
        with pytest.raises(HTTPException) as error:
            await api.approve_run("run-approval", _approval_principal())
        assert error.value.status_code == 503

    asyncio.run(run())

class _SseRedis:
    """按预设批次返回 Event Stream 数据的 Redis 测试替身。"""
    def __init__(self, responses: list[object]) -> None:
        """初始化测试替身及其调用记录。"""
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def xread(self, streams, *, count, block):
        """按预设结果模拟 Redis Event Stream 读取。"""
        self.calls.append({"streams": streams, "count": count, "block": block})
        return self.responses.pop(0)


def _sse_principal() -> Principal:
    """构造具备 runs:read 权限的 SSE Principal。"""
    return Principal(
        principal_id="principal-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
        scopes=frozenset({"runs:read"}),
    )


def test_run_events_emit_sse_id_and_close_on_terminal_event(monkeypatch):
    """验证 SSE 输出包含 id 字段，并在读取终态事件后关闭。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        run_id = "run-sse-terminal-event"
        redis = _SseRedis(
            [
                [
                    (
                        f"agent:run:{run_id}:events",
                        [
                            (
                                "1761466200000-0",
                                {
                                    "event": '{"event_type":"run_completed","payload":{"answer":"done"}}'
                                },
                            )
                        ],
                    )
                ]
            ]
        )
        monkeypatch.setattr(api.app.state, "redis", redis, raising=False)
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState(
                {
                    "run_id": run_id,
                    "status": "RUNNING",
                    "tenant_id": "tenant-a",
                    "user_id": "user-a",
                }
            ),
            raising=False,
        )

        response = await api.stream_run_events(run_id, _sse_principal())
        chunks = [chunk async for chunk in response.body_iterator]

        assert chunks == [
            'id: 1761466200000-0\nevent: run_completed\ndata: {"event_type": "run_completed", "payload": {"answer": "done"}}\n\n'
        ]
        assert len(redis.calls) == 1

    asyncio.run(run())


def test_run_events_close_when_terminal_state_has_no_remaining_events(monkeypatch):
    """验证 Run 已终态且没有剩余事件时 SSE 自动关闭。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        run_id = "run-sse-terminal-state"
        redis = _SseRedis([[]])
        monkeypatch.setattr(api.app.state, "redis", redis, raising=False)
        monkeypatch.setattr(
            api.app.state,
            "run_state",
            _RunState(
                {
                    "run_id": run_id,
                    "status": "COMPLETED",
                    "tenant_id": "tenant-a",
                    "user_id": "user-a",
                }
            ),
            raising=False,
        )

        response = await api.stream_run_events(
            run_id,
            _sse_principal(),
            last_event_id="1761466200000-0",
        )
        chunks = [chunk async for chunk in response.body_iterator]

        assert chunks == []
        assert len(redis.calls) == 1

    asyncio.run(run())


class _ResumeQueue:
    """只实现恢复投递的队列替身。"""

    def __init__(self) -> None:
        """初始化调用记录。"""
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    async def enqueue_resume(self, run_id: str, decisions: list[dict[str, object]]) -> str:
        """记录恢复投递并返回消息 ID。"""
        self.calls.append((run_id, decisions))
        return "77-0"


def _waiting_state() -> dict[str, object]:
    """构造一个等待人工确认的 Run 状态。"""
    return {
        "run_id": "run-hitl",
        "status": "WAITING_CONFIRMATION",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "session_id": "session-a",
    }


def test_resume_run_enqueues_decisions(monkeypatch):
    """验证恢复接口在合法状态下投递决策并发布事件。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        queue = _ResumeQueue()
        events = _Events()
        monkeypatch.setattr(
            api.app.state, "run_state", _RunState(_waiting_state()), raising=False
        )
        monkeypatch.setattr(api.app.state, "queue", queue, raising=False)
        monkeypatch.setattr(api.app.state, "events", events, raising=False)

        result = await api.resume_run(
            "run-hitl",
            RunResumeRequest(decisions=[{"type": "approve"}]),
            _approval_principal(),
        )

        assert result == {"run_id": "run-hitl", "status": "RESUMING"}
        assert queue.calls == [("run-hitl", [{"type": "approve"}])]
        assert events.values[-1][1] == "run_resumed"

    asyncio.run(run())


def test_resume_run_requires_approval_scope():
    """验证恢复接口要求 runs:approve Scope。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        with pytest.raises(HTTPException) as excinfo:
            await api.resume_run(
                "run-hitl",
                RunResumeRequest(decisions=[{"type": "approve"}]),
                _principal(),
            )
        assert excinfo.value.status_code == 403

    asyncio.run(run())


def test_resume_run_rejects_run_not_waiting(monkeypatch):
    """验证非等待确认状态的 Run 不能被恢复。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        state = _waiting_state()
        state["status"] = "RUNNING"
        monkeypatch.setattr(api.app.state, "run_state", _RunState(state), raising=False)

        with pytest.raises(HTTPException) as excinfo:
            await api.resume_run(
                "run-hitl",
                RunResumeRequest(decisions=[{"type": "approve"}]),
                _approval_principal(),
            )
        assert excinfo.value.status_code == 409

    asyncio.run(run())


def test_resume_run_rejects_resource_outside_principal(monkeypatch):
    """验证不能恢复其他租户/用户的 Run。"""
    async def run() -> None:
        """执行当前测试场景的异步步骤并完成断言。"""
        state = _waiting_state()
        state["user_id"] = "someone-else"
        monkeypatch.setattr(api.app.state, "run_state", _RunState(state), raising=False)

        with pytest.raises(HTTPException) as excinfo:
            await api.resume_run(
                "run-hitl",
                RunResumeRequest(decisions=[{"type": "approve"}]),
                _approval_principal(),
            )
        assert excinfo.value.status_code == 403

    asyncio.run(run())
