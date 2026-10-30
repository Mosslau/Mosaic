"""Token 计量的单元测试。

覆盖：不同来源的用量字段归一化、单次 Run 的用量汇总（含按模型拆分）、
终态事件与状态投影携带用量、以及 token 指标写入。
"""

import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from test_memory import FakeRedis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.executor import (
    RunExecutor,
    _merge_usage,
    _normalise_usage,
    _stream_chunks,
    _usage_from_event,
)
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.runtime.metrics import RuntimeMetrics
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    UserContext,
)


def test_normalise_usage_supports_both_field_sets():
    """验证 usage_metadata 与 token_usage 两种字段命名都能归一化。"""
    assert _normalise_usage(
        {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    ) == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert _normalise_usage({"prompt_tokens": 7, "completion_tokens": 3}) == {
        "input_tokens": 7,
        "output_tokens": 3,
        "total_tokens": 10,
    }
    assert _normalise_usage({}) is None
    assert _normalise_usage(None) is None


def test_usage_from_event_reads_ai_message_usage():
    """验证从 on_chat_model_end 事件提取模型名与用量。"""
    message = AIMessage(
        content="hi",
        usage_metadata={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        response_metadata={"model_name": "gpt-4o-mini"},
    )
    event = {"event": "on_chat_model_end", "data": {"output": message}}
    model_name, usage = _usage_from_event(event)
    assert model_name == "gpt-4o-mini"
    assert usage == {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16}


def test_usage_from_event_returns_none_without_usage():
    """验证没有用量信息的事件返回 None，不会写入零值。"""
    event = {"event": "on_chat_model_end", "data": {"output": SimpleNamespace()}}
    assert _usage_from_event(event) is None


def test_merge_usage_accumulates_total_and_by_model():
    """验证多次模型调用的用量累加与按模型拆分。"""
    usage: dict = {}
    _merge_usage(usage, "model-a", {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7})
    _merge_usage(usage, "model-a", {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
    _merge_usage(usage, "model-b", {"input_tokens": 3, "output_tokens": 0, "total_tokens": 3})
    assert usage["input_tokens"] == 9
    assert usage["output_tokens"] == 3
    assert usage["total_tokens"] == 12
    assert usage["by_model"]["model-a"]["total_tokens"] == 9
    assert usage["by_model"]["model-b"]["input_tokens"] == 3


class _Events:
    """记录事件的发布器替身。"""

    def __init__(self) -> None:
        """初始化事件列表。"""
        self.values: list[tuple[str, str, dict]] = []

    async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
        """记录一次发布。"""
        self.values.append((run_id, event_type, payload))


class _Agent:
    """产生一次带用量的模型调用并正常结束的 Agent 替身。"""

    async def astream_events(self, payload, config, version):
        """先产出模型调用，再产出终态。"""
        yield {
            "event": "on_chat_model_end",
            "data": {
                "output": AIMessage(
                    content="答案",
                    usage_metadata={
                        "input_tokens": 21,
                        "output_tokens": 9,
                        "total_tokens": 30,
                    },
                    response_metadata={"model_name": "gpt-4o-mini"},
                )
            },
        }
        yield {
            "event": "on_chain_end",
            "data": {"output": {"messages": [{"role": "assistant", "content": "答案"}]}},
        }

    async def aget_state(self, config):
        """返回没有中断的状态。"""
        return SimpleNamespace(values={}, interrupts=())


def test_run_completion_carries_usage_and_metrics():
    """验证终态事件、状态投影与指标都带上本次 Run 的 token 用量。"""

    async def run() -> None:
        """执行一次 Run 并检查用量落点。"""

        async def fake_build_agent(*args, **kwargs):
            """返回替身 Agent。"""
            return _Agent(), None

        import data_agent_runtime.runtime.executor as executor_module

        original = executor_module.build_agent
        executor_module.build_agent = fake_build_agent
        try:
            reader = InMemoryMetricReader()
            provider = MeterProvider(metric_readers=[reader])
            metrics = RuntimeMetrics(meter=provider.get_meter("usage-test"))

            settings = Settings(_env_file=None)
            redis = FakeRedis()
            events = _Events()
            executor = RunExecutor(
                settings,
                events,
                RedisConversationHistory(redis, settings),
                RedisLongTermMemory(redis, settings),
                InMemorySaver(),
                None,
                metrics=metrics,
            )
            request = RunRequest(
                run_id="run-usage",
                message="你好",
                agent=AgentSnapshot(
                    id="agent-usage",
                    version=1,
                    system_prompt="你是数据分析助手",
                    model=ModelConfig(name="gpt-4o-mini"),
                ),
                user_context=UserContext(user_id="u-1", tenant_id="t-1"),
            )
            await executor.execute_queued(request, worker_id="w-1", attempt=0)

            completed = [
                payload
                for _, event, payload in events.values
                if event == "run_completed"
            ][-1]
            assert completed["usage"]["total_tokens"] == 30
            assert completed["usage"]["by_model"]["gpt-4o-mini"]["input_tokens"] == 21

            data = reader.get_metrics_data()
            metrics_by_name = {
                metric.name: metric
                for scope in data.resource_metrics[0].scope_metrics
                for metric in scope.metrics
            }
            points = metrics_by_name["runtime.llm.tokens"].data.data_points
            recorded = {
                (dict(point.attributes).get("token.type"), dict(point.attributes).get("model")): point.value
                for point in points
            }
            assert recorded[("input", None)] == 21
            assert recorded[("output", None)] == 9
            assert recorded[("input", "gpt-4o-mini")] == 21
        finally:
            executor_module.build_agent = original

    asyncio.run(run())


def test_stream_chunks_split_reasoning_and_text():
    """验证推理块与文本块被分流成不同 kind，思考内容不会混进答案。"""
    event = {
        "data": {
            "chunk": {
                "content": [
                    {"type": "reasoning", "reasoning": "先查元数据"},
                    {"type": "text", "text": "共 128 台"},
                ]
            }
        }
    }
    assert _stream_chunks(event) == [("reasoning", "先查元数据"), ("text", "共 128 台")]


def test_stream_chunks_reads_deepseek_reasoning_content():
    """验证仅带 additional_kwargs.reasoning_content 的网关也能取到思考内容。"""
    event = {"data": {"chunk": {"content": "", "additional_kwargs": {"reasoning_content": "思考中"}}}}
    assert _stream_chunks(event) == [("reasoning", "思考中")]


def test_stream_chunks_ignores_unrelated_blocks():
    """验证无法识别的块不会产生任何增量。"""
    event = {"data": {"chunk": {"content": [{"type": "image_url", "image_url": {"url": "x"}}]}}}
    assert _stream_chunks(event) == []


def test_usage_records_reasoning_tokens():
    """验证 output_token_details.reasoning 被单独归一化并计入指标。"""
    _, usage = _usage_from_event(
        {
            "data": {
                "output": AIMessage(
                    content="答",
                    usage_metadata={
                        "input_tokens": 5,
                        "output_tokens": 9,
                        "total_tokens": 14,
                        "output_token_details": {"reasoning": 4},
                    },
                    response_metadata={"model_name": "deepseek-reasoner"},
                )
            }
        }
    )
    assert usage["reasoning_tokens"] == 4
    merged: dict = {}
    _merge_usage(merged, "deepseek-reasoner", usage)
    assert merged["reasoning_tokens"] == 4
    assert merged["by_model"]["deepseek-reasoner"]["reasoning_tokens"] == 4
