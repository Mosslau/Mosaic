"""运行指标模块的单元测试。

使用 OpenTelemetry 的内存 MetricReader 断言计数、时延直方图与队列深度仪表，
不依赖 Collector；同时验证 Executor 会在终态写入完成指标。
"""

import asyncio
from types import SimpleNamespace

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from data_agent_runtime.runtime.metrics import RuntimeMetrics


def _metrics() -> tuple[RuntimeMetrics, InMemoryMetricReader]:
    """构造带内存读取器的指标实例。"""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return RuntimeMetrics(meter=provider.get_meter("test-meter")), reader


def _values(reader: InMemoryMetricReader) -> dict[str, list[tuple[dict, float]]]:
    """把读取结果整理成 {指标名: [(属性, 值)]}。"""
    data = reader.get_metrics_data()
    result: dict[str, list[tuple[dict, float]]] = {}
    if data is None:
        return result
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                points = []
                for point in metric.data.data_points:
                    attributes = dict(point.attributes)
                    value = getattr(
                        point, "value", getattr(point, "sum", getattr(point, "count", 0))
                    )
                    points.append((attributes, float(value)))
                result[metric.name] = points
    return result


def test_counters_record_expected_attributes():
    """验证受理、终态、重试、死信与工具调用计数都能被采集。"""
    metrics, reader = _metrics()

    metrics.run_accepted(tenant_id="t-1", agent_id="agent-a")
    metrics.run_finished(status="completed", duration_seconds=1.5)
    metrics.queue_retry(run_id="run-1")
    metrics.queue_dead_letter(run_id="run-2")
    metrics.tool_call(tool_name="sandbox_run", status="completed")

    values = _values(reader)
    assert values["runtime.run.accepted"][0][0] == {
        "tenant.id": "t-1",
        "agent.id": "agent-a",
    }
    assert values["runtime.run.finished"][0][0] == {"status": "completed"}
    assert values["runtime.queue.retry"][0][1] == 1.0
    assert values["runtime.queue.dead_letter"][0][1] == 1.0
    assert values["runtime.tool.calls"][0][0] == {
        "tool.name": "sandbox_run",
        "status": "completed",
    }


def test_duration_histogram_records_seconds():
    """验证 Run 时延以秒为单位写入直方图。"""
    metrics, reader = _metrics()

    metrics.run_finished(status="interrupted", duration_seconds=2.25)

    data = reader.get_metrics_data()
    metrics_by_name = {
        metric.name: metric
        for scope in data.resource_metrics[0].scope_metrics
        for metric in scope.metrics
    }
    point = metrics_by_name["runtime.run.duration"].data.data_points[0]
    assert dict(point.attributes) == {"status": "interrupted"}
    assert point.sum == 2.25
    assert point.count == 1


def test_queue_depth_gauge_reads_last_value():
    """验证队列深度仪表返回最近一次记录的值，并做负数保护。"""
    metrics, reader = _metrics()

    metrics.record_queue_depth(7)
    _values(reader)
    metrics.record_queue_depth(-3)

    points = _values(reader)["runtime.queue.depth"]
    assert points[0][1] == 0.0


def test_executor_records_finished_metric(monkeypatch, tmp_path):
    """验证 Executor 在 Run 结束时写入完成指标（状态与时长）。"""
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

    class _Agent:
        """产生一次正常完成的最小 Agent 替身。"""

        async def astream_events(self, payload, config, version):
            """产出一个完整答案。"""
            yield {
                "event": "on_chain_end",
                "data": {"output": {"messages": [{"role": "assistant", "content": "ok"}]}},
            }

        async def aget_state(self, config):
            """返回没有中断的状态。"""
            return SimpleNamespace(values={}, interrupts=())

    class _Events:
        """忽略事件的最小发布器。"""

        async def publish(self, run_id, event_type, payload):
            """丢弃事件。"""
            return

    async def fake_build_agent(*args, **kwargs):
        """返回替身 Agent。"""
        return _Agent(), None

    async def run() -> None:
        """执行一次 Run 并检查指标。"""
        monkeypatch.setattr(
            "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
        )
        metrics, reader = _metrics()
        settings = Settings(_env_file=None)
        redis = FakeRedis()
        executor = RunExecutor(
            settings,
            _Events(),
            RedisConversationHistory(redis, settings),
            RedisLongTermMemory(redis, settings),
            InMemorySaver(),
            None,
            metrics=metrics,
        )
        request = RunRequest(
            run_id="run-metrics",
            message="你好",
            agent=AgentSnapshot(
                id="agent-metrics",
                version=1,
                system_prompt="你是数据分析助手",
                model=ModelConfig(name="gpt-4o-mini"),
            ),
            user_context=UserContext(user_id="u-1", tenant_id="t-1"),
        )
        await executor.execute_queued(request, worker_id="w-1", attempt=0)

        finished = _values(reader)["runtime.run.finished"]
        assert finished[0][0] == {"status": "completed"}

    asyncio.run(run())
