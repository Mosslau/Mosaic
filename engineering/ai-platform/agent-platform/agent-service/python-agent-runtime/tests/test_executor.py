"""本文件模块职责：RunExecutor 的执行流程单元测试。

测试覆盖运行状态、历史上下文、Token 流式事件、非流式模式、最终答案、失败和取消等路径，不依赖真实模型服务。
"""

import asyncio
from types import SimpleNamespace
from typing import ClassVar

from langgraph.checkpoint.memory import InMemorySaver
from test_memory import FakeRedis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.executor import RunExecutor
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    UserContext,
)


class FakeEvents:
    """记录 Executor 发布的事件，供测试断言事件顺序和负载。"""
    def __init__(self):
        """
        中文说明：
            初始化 FakeEvents，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.events = []

    async def publish(self, run_id, event_type, payload):
        """
        中文说明：
            为运行事件分配全局递增序号并写入对应 Run 的 Redis Event Stream。

        参数：
            - run_id: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - event_type: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - payload: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.events.append((run_id, event_type, payload))


class FakeAgent:
    """模拟 DeepAgents Agent，按预设结果验证执行器的调用契约。"""
    calls: ClassVar[list] = []
    states: ClassVar[dict] = {}

    async def aget_state(self, config):
        """
        中文说明：
            实现 FakeAgent 的“aget_state”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - config: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        return SimpleNamespace(
            values=self.states.get(config["configurable"]["thread_id"], {})
        )

    async def ainvoke(self, payload, config):
        """
        中文说明：
            实现 FakeAgent 的“ainvoke”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - payload: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - config: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        thread_id = config["configurable"]["thread_id"]
        messages = list(payload["messages"])
        self.calls.append(messages)
        answer = {"role": "assistant", "content": f"已处理：{messages[-1]['content']}"}
        self.states[thread_id] = {"messages": messages + [answer]}
        return {"messages": messages + [answer]}

    async def astream_events(self, payload, config, version):
        """
        中文说明：
            实现 FakeAgent 的“astream_events”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - payload: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - config: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - version: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        thread_id = config["configurable"]["thread_id"]
        messages = list(payload["messages"])
        self.calls.append(messages)
        answer_text = f"已处理：{messages[-1]['content']}"
        answer = {"role": "assistant", "content": answer_text}
        self.states[thread_id] = {"messages": messages + [answer]}
        yield {
            "event": "on_tool_start",
            "name": "query_metadata",
            "run_id": "tool-run-1",
        }
        yield {
            "event": "on_tool_end",
            "name": "query_metadata",
            "run_id": "tool-run-1",
        }
        for delta in ("已处理：", messages[-1]["content"]):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": {"content": delta}},
            }


async def fake_build_agent(
    agent,
    settings,
    *,
    checkpointer=None,
    store=None,
    memories=None,
    run_id="local-run",
    session_id="local-session",
    tenant_id="local-tenant",
):
    """
    中文说明：
        实现 tests/test_executor 的“fake_build_agent”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - agent: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - settings: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - checkpointer: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - memories: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - run_id: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - session_id: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - tenant_id: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return FakeAgent(), None


def make_request(run_id, message, *, stream=False):
    """
    中文说明：
        实现 tests/test_executor 的“make_request”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - run_id: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - message: 未声明类型：由调用方传入，用于完成本函数的核心处理。
        - stream: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return RunRequest(
        run_id=run_id,
        session_id="session-1",
        message=message,
        stream=stream,
        agent=AgentSnapshot(
            id="analysis",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
        ),
        user_context=UserContext(user_id="user-1", tenant_id="tenant-1"),
    )


def test_same_session_reuses_context(monkeypatch):
    """
    中文说明：
        验证 tests/test_executor 中“same_session_reuses_context”这一行为，确保协议、状态变化和异常边界符合预期。

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
        FakeAgent.calls = []
        FakeAgent.states = {}
        monkeypatch.setattr(
            "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
        )
        redis = FakeRedis()
        history = RedisConversationHistory(redis, Settings())
        memories = RedisLongTermMemory(redis, Settings())
        executor = RunExecutor(
            Settings(), FakeEvents(), history, memories, InMemorySaver()
        )

        await executor._run(make_request("run-1", "第一轮"))
        await executor._run(make_request("run-2", "第二轮"))

        assert FakeAgent.calls[0] == [{"role": "user", "content": "第一轮"}]
        assert FakeAgent.calls[1] == [{"role": "user", "content": "第二轮"}]
        messages = await history.list_messages("session-1")
        assert [message["role"] for message in messages] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]

    asyncio.run(run())


def test_streaming_publishes_token_deltas(monkeypatch):
    """
    中文说明：
        验证 tests/test_executor 中“streaming_publishes_token_deltas”这一行为，确保协议、状态变化和异常边界符合预期。

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
        FakeAgent.calls = []
        FakeAgent.states = {}
        monkeypatch.setattr(
            "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
        )
        redis = FakeRedis()
        history = RedisConversationHistory(redis, Settings())
        memories = RedisLongTermMemory(redis, Settings())
        events = FakeEvents()
        executor = RunExecutor(Settings(), events, history, memories, InMemorySaver())

        await executor._run(make_request("run-stream", "流式测试", stream=True))

        deltas = [
            payload["delta"]
            for _, event_type, payload in events.events
            if event_type == "agent_message_delta"
        ]
        assert deltas == ["已处理：", "流式测试"]
        assert [
            event_type
            for _, event_type, _ in events.events
            if event_type.startswith("tool_")
        ] == ["tool_started", "tool_completed"]
        assert any(
            event_type == "run_completed" for _, event_type, _ in events.events
        )

    asyncio.run(run())


def test_non_streaming_publishes_only_final_answer(monkeypatch):
    """
    中文说明：
        验证 tests/test_executor 中“non_streaming_publishes_only_final_answer”这一行为，确保协议、状态变化和异常边界符合预期。

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
        FakeAgent.calls = []
        FakeAgent.states = {}
        monkeypatch.setattr(
            "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
        )
        redis = FakeRedis()
        history = RedisConversationHistory(redis, Settings())
        memories = RedisLongTermMemory(redis, Settings())
        events = FakeEvents()
        executor = RunExecutor(Settings(), events, history, memories, InMemorySaver())

        await executor._run(make_request("run-sync", "非流式测试"))

        event_types = [event_type for _, event_type, _ in events.events]
        assert "agent_message_delta" not in event_types
        completed = next(
            payload
            for _, event_type, payload in events.events
            if event_type == "run_completed"
        )
        assert completed["answer"] == "已处理：非流式测试"

    asyncio.run(run())


def test_non_streaming_keeps_tool_events_but_suppresses_token_deltas(monkeypatch):
    """
    中文说明：
        验证 tests/test_executor 中“non_streaming_keeps_tool_events_but_suppresses_token_deltas”这一行为，确保协议、状态变化和异常边界符合预期。

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
        FakeAgent.calls = []
        FakeAgent.states = {}
        monkeypatch.setattr(
            "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
        )
        redis = FakeRedis()
        history = RedisConversationHistory(redis, Settings())
        memories = RedisLongTermMemory(redis, Settings())
        events = FakeEvents()
        executor = RunExecutor(Settings(), events, history, memories, InMemorySaver())

        await executor._run(make_request("run-sync-tools", "非流式工具测试"))

        event_types = [event_type for _, event_type, _ in events.events]
        assert "agent_message_delta" not in event_types
        assert event_types.count("tool_started") == 1
        assert event_types.count("tool_completed") == 1

    asyncio.run(run())
