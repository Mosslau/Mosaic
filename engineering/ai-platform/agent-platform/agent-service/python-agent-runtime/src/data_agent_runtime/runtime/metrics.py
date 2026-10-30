"""Runtime 运行指标（OpenTelemetry Metrics）。

本模块把"能不能验证高可用"所需的核心指标收敛到一处：Run 受理/终态/时延、队列深度、
重试与死信、工具调用结果。没有配置 OTel Provider 时，OpenTelemetry 的 API 会自动退化为
no-op 实现，因此调用方不需要关心指标是否启用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentelemetry import metrics as otel_metrics
from opentelemetry.metrics import Meter

_METER_NAME = "data-agent-runtime"


@dataclass
class RuntimeMetrics:
    """一次进程生命周期内共享的指标句柄集合。

    指标是"可被采集"的事实来源：业务代码只负责记录，导出与采样由 OTel Provider 决定。
    """

    meter: Meter | None = None

    def __post_init__(self) -> None:
        """按需创建各指标仪器；重复创建同名仪器是幂等的。"""
        meter = self.meter or otel_metrics.get_meter(_METER_NAME)
        self._accepted = meter.create_counter(
            "runtime.run.accepted",
            unit="{run}",
            description="已受理的 Agent Run 数量",
        )
        self._finished = meter.create_counter(
            "runtime.run.finished",
            unit="{run}",
            description="进入终态的 Agent Run 数量（按状态区分）",
        )
        self._duration = meter.create_histogram(
            "runtime.run.duration",
            unit="s",
            description="Agent Run 端到端执行时长",
        )
        self._retry = meter.create_counter(
            "runtime.queue.retry",
            unit="{task}",
            description="任务重试投递次数",
        )
        self._dead_letter = meter.create_counter(
            "runtime.queue.dead_letter",
            unit="{task}",
            description="进入死信流的任务数量",
        )
        self._tool_calls = meter.create_counter(
            "runtime.tool.calls",
            unit="{call}",
            description="工具调用次数（按工具与结果区分）",
        )
        self._llm_tokens = meter.create_counter(
            "runtime.llm.tokens",
            unit="{token}",
            description="模型调用消耗的 token 数量（按输入/输出与模型区分）",
        )
        self._queue_depth = 0
        meter.create_observable_gauge(
            "runtime.queue.depth",
            callbacks=[self._observe_queue_depth],
            unit="{task}",
            description="任务流中待处理的消息数量",
        )

    def run_accepted(self, *, tenant_id: str | None, agent_id: str | None) -> None:
        """记录一次 Run 被受理（入队或进入等待审批）。"""
        self._accepted.add(
            1,
            {
                "tenant.id": tenant_id or "unknown",
                "agent.id": agent_id or "unknown",
            },
        )

    def run_finished(self, *, status: str, duration_seconds: float) -> None:
        """记录一次 Run 进入终态及其端到端时延。"""
        self._finished.add(1, {"status": status})
        self._duration.record(max(duration_seconds, 0.0), {"status": status})

    def queue_retry(self, *, run_id: str | None = None) -> None:
        """记录一次重试投递。"""
        self._retry.add(1, {"run.id": run_id or ""})

    def queue_dead_letter(self, *, run_id: str | None = None) -> None:
        """记录一条任务进入死信流。"""
        self._dead_letter.add(1, {"run.id": run_id or ""})

    def tool_call(self, *, tool_name: str, status: str) -> None:
        """记录一次工具调用结果（completed / failed）。"""
        self._tool_calls.add(1, {"tool.name": tool_name, "status": status})

    def llm_tokens(self, *, usage: dict[str, Any]) -> None:
        """记录一次 Run 的 token 用量（总计 + 按模型拆分）。

        ``usage`` 形如 ``{"input_tokens": n, "output_tokens": n, "total_tokens": n,
        "by_model": {model: {...}}}``；总计与按模型两条序列都会写入，避免下游只能二选一。
        """
        self._llm_tokens.add(
            int(usage.get("input_tokens", 0)), {"token.type": "input"}
        )
        self._llm_tokens.add(
            int(usage.get("output_tokens", 0)), {"token.type": "output"}
        )
        if usage.get("reasoning_tokens"):
            self._llm_tokens.add(
                int(usage["reasoning_tokens"]), {"token.type": "reasoning"}
            )
        for model_name, bucket in (usage.get("by_model") or {}).items():
            self._llm_tokens.add(
                int(bucket.get("input_tokens", 0)),
                {"token.type": "input", "model": str(model_name)},
            )
            self._llm_tokens.add(
                int(bucket.get("output_tokens", 0)),
                {"token.type": "output", "model": str(model_name)},
            )
            if bucket.get("reasoning_tokens"):
                self._llm_tokens.add(
                    int(bucket["reasoning_tokens"]),
                    {"token.type": "reasoning", "model": str(model_name)},
                )

    def record_queue_depth(self, depth: int) -> None:
        """更新队列深度（由采集回调异步读取）。"""
        self._queue_depth = max(depth, 0)

    def _observe_queue_depth(self, options: Any = None):
        """返回最近一次记录的队列深度。"""
        from opentelemetry.metrics import Observation

        return [Observation(self._queue_depth)]


def configure_metrics(settings: Any) -> None:
    """按部署配置初始化 OTel Meter Provider。

    ``OTEL_ENABLED=false`` 时不注册 Provider，指标调用退化为 no-op，不影响业务与延迟。
    """
    if not getattr(settings, "otel_enabled", False):
        return
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    endpoint = getattr(settings, "otel_exporter_otlp_endpoint", None)
    if not endpoint:
        return
    base = endpoint.rstrip("/")
    if not base.endswith("/v1/metrics"):
        base = f"{base}/v1/metrics"
    headers = None
    raw_headers = getattr(settings, "otel_exporter_otlp_headers", None)
    if raw_headers:
        headers = dict(
            item.split("=", 1) for item in raw_headers.split(",") if "=" in item
        )
    exporter = OTLPMetricExporter(
        endpoint=base,
        headers=headers,
        timeout=int(getattr(settings, "otel_exporter_timeout_seconds", 10)),
    )
    provider = MeterProvider(
        resource=Resource.create(
            {
                "service.name": getattr(settings, "otel_service_name", None)
                or getattr(settings, "app_name", "data-agent-runtime"),
            }
        ),
        metric_readers=[
            PeriodicExportingMetricReader(exporter, export_interval_millis=15000)
        ],
    )
    otel_metrics.set_meter_provider(provider)


_default_metrics: RuntimeMetrics | None = None


def get_metrics() -> RuntimeMetrics:
    """返回进程内共享的指标实例，避免每个组件重复创建仪器。"""
    global _default_metrics
    if _default_metrics is None:
        _default_metrics = RuntimeMetrics()
    return _default_metrics
