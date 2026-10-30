"""工具级人工确认与恢复执行（HITL / resume）的单元测试。

本模块验证三件事：中断被识别并暂停、恢复通过 ``Command(resume=...)`` 继续、
队列消息能区分普通运行与恢复投递。测试不连接模型、Redis 或外部服务。
"""

import asyncio
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from test_memory import FakeRedis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.executor import RunExecutor
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.runtime.queue import RunTaskQueue
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    UserContext,
)


class _Events:
    """记录 Executor 发布的事件。"""

    def __init__(self) -> None:
        """初始化事件记录容器。"""
        self.values: list[tuple[str, str, dict]] = []

    async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
        """记录一次事件发布。"""
        self.values.append((run_id, event_type, payload))


class _State:
    """记录 Run 状态写入的最小状态替身。"""

    def __init__(self) -> None:
        """初始化状态记录。"""
        self.status: str | None = None
        self.calls: list[tuple[str, dict]] = []

    async def set_status(self, run_id: str, status: str, **kwargs) -> dict:
        """记录通用状态写入。"""
        self.status = status
        self.calls.append((status, kwargs))
        return {"run_id": run_id, "status": status}

    async def mark_waiting_confirmation(self, run_id: str, *, interrupt_count: int):
        """记录等待人工确认状态。"""
        self.status = "WAITING_CONFIRMATION"
        self.calls.append(
            ("WAITING_CONFIRMATION", {"interrupt_count": interrupt_count})
        )


class _Agent:
    """按预设中断返回状态的 Agent 替身。"""

    def __init__(self, interrupts=()) -> None:
        """保存中断列表并初始化调用记录。"""
        self.interrupts = tuple(interrupts)
        self.payloads: list[object] = []

    async def astream_events(self, payload, config, version):
        """记录收到的输入载荷，不产生任何流式事件。"""
        self.payloads.append(payload)
        if False:  # pragma: no cover - 保持异步生成器语义
            yield {}

    async def aget_state(self, config):
        """返回带（或空）中断列表的状态快照。"""
        return SimpleNamespace(values={}, interrupts=self.interrupts)


def _request(run_id: str = "run-hitl") -> RunRequest:
    """构造一次最小合法 Run 请求。"""
    return RunRequest(
        run_id=run_id,
        session_id="session-1",
        message="执行危险操作前请确认",
        agent=AgentSnapshot(
            id="agent-hitl",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="gpt-4o-mini"),
            interrupt_on={"sandbox_run": True},
        ),
        user_context=UserContext(user_id="user-1", tenant_id="tenant-1"),
    )


def _executor(monkeypatch, agent: _Agent) -> tuple[RunExecutor, _Events, _State]:
    """构造一个使用内存 Redis、内存 Checkpoint 与替身 Agent 的 Executor。"""

    async def fake_build_agent(*args, **kwargs):
        """返回替身 Agent，不构建真实 DeepAgents 图。"""
        return agent, None

    monkeypatch.setattr(
        "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
    )
    settings = Settings(_env_file=None)
    redis = FakeRedis()
    events = _Events()
    state = _State()
    executor = RunExecutor(
        settings,
        events,
        RedisConversationHistory(redis, settings),
        RedisLongTermMemory(redis, settings),
        InMemorySaver(),
        state,
    )
    return executor, events, state


def test_interrupt_pauses_run_and_publishes_permission_request(monkeypatch):
    """验证工具级中断会暂停 Run、写入等待状态并发布确认请求事件。"""

    async def run() -> None:
        """执行中断场景并完成断言。"""
        agent = _Agent(
            interrupts=[
                SimpleNamespace(
                    id="int-1",
                    value={
                        "action_requests": [
                            {"name": "sandbox_run", "arguments": {}}
                        ],
                        "review_configs": [
                            {"allowed_decisions": ["approve", "reject"]}
                        ],
                    },
                )
            ]
        )
        executor, events, state = _executor(monkeypatch, agent)

        outcome = await executor.execute_queued(
            _request(), worker_id="w-1", attempt=0
        )

        assert outcome == "interrupted"
        assert state.status == "WAITING_CONFIRMATION"
        assert state.calls[-1] == ("WAITING_CONFIRMATION", {"interrupt_count": 1})
        event_type = events.values[-1][1]
        payload = events.values[-1][2]
        assert event_type == "tool_permission_request"
        assert payload["interrupts"][0]["interrupt_id"] == "int-1"
        assert payload["resume_endpoint"] == "/v1/runs/run-hitl/resume"
        # 中断不是失败，也不应发布完成事件
        assert all(
            event not in {"run_failed", "run_completed"}
            for _, event, _ in events.values
        )

    asyncio.run(run())


def test_resume_uses_command_and_completes(monkeypatch):
    """验证恢复执行使用 ``Command(resume=...)`` 且不重复写入用户消息。"""

    async def run() -> None:
        """执行恢复场景并完成断言。"""
        agent = _Agent()
        executor, events, state = _executor(monkeypatch, agent)
        decisions = [{"type": "approve"}]

        outcome = await executor.execute_resume(_request(), decisions)

        assert outcome == "completed"
        assert state.status == "COMPLETED"
        assert isinstance(agent.payloads[0], Command)
        assert agent.payloads[0].resume == {"decisions": decisions}
        assert events.values[-1][1] == "run_completed"
        # 恢复路径不应把用户消息再追加一次
        messages = await executor.history.list_messages(
            "session-1", tenant_id="tenant-1", user_id="user-1"
        )
        assert [item["role"] for item in messages].count("user") == 0

    asyncio.run(run())


def test_parse_message_distinguishes_run_and_resume():
    """验证队列消息解析能区分普通运行与恢复投递。"""
    request = _request()
    message_id, parsed, attempt, kind, decisions = RunTaskQueue.parse_message(
        ("1-0", {"kind": "run", "payload": request.model_dump_json(), "attempt": "2"})
    )
    assert (message_id, attempt, kind, decisions) == ("1-0", 2, "run", None)
    assert parsed is not None and parsed.run_id == "run-hitl"

    message_id, parsed, attempt, kind, decisions = RunTaskQueue.parse_message(
        ("2-0", {"kind": "resume", "payload": '{"decisions": [{"type": "reject"}]}'})
    )
    assert parsed is None
    assert (message_id, attempt, kind) == ("2-0", 0, "resume")
    assert decisions == [{"type": "reject"}]


def test_parse_resume_message_requires_decisions():
    """验证缺少决策的恢复消息会被拒绝，而不是静默恢复。"""
    with pytest.raises(ValueError, match="no decisions"):
        RunTaskQueue.parse_message(("3-0", {"kind": "resume", "payload": "{}"}))


def test_enqueue_resume_writes_resume_kind():
    """验证恢复投递写入 kind=resume 并携带决策载荷。"""

    async def run() -> None:
        """执行入队场景并完成断言。"""
        added: list[dict] = []

        class _Redis:
            """记录 XADD 调用的最小 Redis 替身。"""

            def register_script(self, script):
                """返回一个不会被调用的脚本占位。"""
                return

            async def xadd(self, key, fields, **kwargs):
                """记录任务流写入并返回消息 ID。"""
                added.append(fields)
                return "9-0"

        queue = RunTaskQueue(_Redis(), Settings(_env_file=None), SimpleNamespace())
        message_id = await queue.enqueue_resume("run-hitl", [{"type": "approve"}])

        assert message_id == "9-0"
        assert added[0]["kind"] == "resume"
        assert added[0]["run_id"] == "run-hitl"
        assert '"type": "approve"' in added[0]["payload"]

    asyncio.run(run())


def test_structured_response_becomes_canonical_answer(monkeypatch):
    """验证声明 response_format 后，结构化结果作为权威答案写入事件与状态。"""

    async def run() -> None:
        """执行结构化输出场景并完成断言。"""
        agent = _Agent()
        agent.structured = {"answer": "128 台", "source": "vehicle_table"}

        async def astream_events(payload, config, version):
            """返回带结构化输出的终态。"""
            agent.payloads.append(payload)
            yield {
                "event": "on_chain_end",
                "data": {"output": {"structured_response": agent.structured}},
            }

        agent.astream_events = astream_events
        executor, events, _state = _executor(monkeypatch, agent)

        outcome = await executor.execute_resume(_request(), [{"type": "approve"}])

        assert outcome == "completed"
        completed = [payload for _, event, payload in events.values if event == "run_completed"]
        assert completed[-1]["answer"] == '{"answer": "128 台", "source": "vehicle_table"}'
        assert completed[-1]["structured"] == agent.structured

    asyncio.run(run())


def test_rubric_is_injected_into_invocation_state(monkeypatch):
    """验证声明 rubric 后，评分标准随调用状态传给 RubricMiddleware。"""

    async def run() -> None:
        """执行带 rubric 的运行并断言载荷内容。"""
        agent = _Agent()
        executor, _events, _state = _executor(monkeypatch, agent)
        request = _request()
        request.agent.rubric = "必须给出数据来源"

        await executor.execute_queued(request, worker_id="w-1", attempt=0)

        payload = agent.payloads[0]
        assert payload["rubric"] == "必须给出数据来源"
        assert payload["messages"][-1]["content"] == request.message

    asyncio.run(run())


def test_todos_and_async_tasks_are_surfaced(monkeypatch):
    """验证计划与异步任务状态随终态事件透出，供前端展示进度。"""

    async def run() -> None:
        """执行带计划与异步任务的运行并断言载荷。"""
        agent = _Agent()

        async def astream_events(payload, config, version):
            """返回带 todos 与 async_tasks 的终态。"""
            agent.payloads.append(payload)
            yield {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "messages": [{"role": "assistant", "content": "完成"}],
                        "todos": [{"content": "查询元数据", "status": "completed"}],
                        "async_tasks": {"task-1": {"status": "pending"}},
                    }
                },
            }

        agent.astream_events = astream_events
        executor, events, _state = _executor(monkeypatch, agent)

        await executor.execute_queued(_request(), worker_id="w-1", attempt=0)

        completed = [
            payload for _, event, payload in events.values if event == "run_completed"
        ]
        assert completed[-1]["todos"][0]["content"] == "查询元数据"
        assert completed[-1]["async_tasks"]["task-1"]["status"] == "pending"

    asyncio.run(run())
