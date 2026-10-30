"""本文件模块职责：Python Runtime 的统一可观测性基础设施。

本模块同时提供三类能力：

1. 将标准库 ``logging`` 输出为可被 Loki、ELK、Splunk 等平台直接采集的 JSON 日志；
2. 对日志消息、异常、Header、连接串和嵌套结构执行统一敏感信息脱敏；
3. 以 OpenTelemetry 为可选实现建立 HTTP、Redis Stream、Worker、Agent Run 和下游
   Sandbox/MCP 调用之间的 W3C Trace Context 传播链路。

OpenTelemetry 未启用或依赖未安装时，本模块必须安全降级为零配置模式：日志仍然可用，
Trace API 返回 No-op 实现，不应因为本地没有 Collector 而影响 Agent 业务。
"""

from __future__ import annotations

import contextvars
import inspect
import json
import logging
import os
import re
import socket
import traceback
import uuid
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from data_agent_runtime.config import Settings

# 请求/任务级上下文使用 ContextVar，能够在 asyncio Task 之间隔离，同时让所有模块的
# logger 自动拿到同一组 run_id、request_id 和用户/租户关联字段。
_LOG_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "data_agent_log_context", default=None
)

# 对 URL、Bearer、API Key 等高风险字符串执行二次兜底脱敏。结构化字段会先走 key
# 判断，再走文本规则，避免调用方通过 message 参数绕过脱敏。
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(basic\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\b(?:sk|rk)-)[A-Za-z0-9_-]{8,}"), r"\1[REDACTED]"),
    (
        # 同时覆盖 redis://user:password@、redis://:password@ 和无用户名场景。
        re.compile(r"(?i)((?:rediss?|postgres(?:ql)?):\/\/(?:[^/@\s]*:)?)[^@\s/?]+(@)"),
        r"\1[REDACTED]\2",
    ),
    (
        # 兜底处理 Query String 中的 password/token/api_key 等凭证。
        re.compile(r"(?i)([?&](?:password|passwd|token|api[_-]?key|secret)=)[^&\s]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)((?:authorization)\s*[:=]\s*)[^\s,;]+"
        ),
        r"\1[REDACTED]",
    ),
)

_SECRET_KEYS = {
    "authorization",
    "proxy_authorization",
    "cookie",
    "set_cookie",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "openai_api_key",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "redis_url",
    "postgres_dsn",
    "otel_exporter_otlp_headers",
}

# logging.LogRecord 中这些属性是框架元数据，不应重复写入 extra，避免 JSON 结构膨胀。
_STANDARD_LOG_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

try:  # OpenTelemetry 是可选依赖，便于没有 Collector 的本地开发环境运行。
    from opentelemetry import context as otel_context
    from opentelemetry import propagate, trace
    from opentelemetry.trace import Span, SpanKind, Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - 由无 OTel 依赖的最小安装触发
    otel_context = None  # type: ignore[assignment]
    propagate = None  # type: ignore[assignment]
    trace = None  # type: ignore[assignment]
    Span = Any  # type: ignore[misc,assignment]
    SpanKind = Any  # type: ignore[misc,assignment]
    Status = Any  # type: ignore[misc,assignment]
    StatusCode = Any  # type: ignore[misc,assignment]
    _OTEL_AVAILABLE = False


class JsonLogFormatter(logging.Formatter):
    """将标准 LogRecord 转换为统一 JSON 对象，并在最终输出前进行脱敏。"""

    def __init__(self, settings: Settings, *, role: str):
        """初始化 JSON Formatter，并保存服务级日志标签。"""
        super().__init__()
        self.settings = settings
        self.role = role

    # 函数说明：将 LogRecord 转换为结构化 JSON 字符串并附加当前异步上下文。
    # 参数说明：record: logging.LogRecord。
    # 返回说明：str；始终返回一行合法 JSON，便于日志采集器按行解析。
    def format(self, record: logging.LogRecord) -> str:
        """生成结构化日志；消息、异常和 extra 字段均经过敏感信息脱敏。"""
        context = dict(_LOG_CONTEXT.get() or {})
        trace_values = current_trace_identifiers()
        context.update({key: value for key, value in trace_values.items() if value})

        try:
            message = record.getMessage()
        except (AttributeError, TypeError, ValueError):  # pragma: no cover
            message = "<log message formatting failed>"

        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_value(message) if self.settings.log_redaction_enabled else message,
            "service": self.settings.app_name,
            "environment": self.settings.app_env,
            "role": self.role,
            "process_id": os.getpid(),
            "thread_name": record.threadName,
            "source": {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            },
            **context,
        }
        if record.exc_info:
            exception_text = "".join(traceback.format_exception(*record.exc_info)).strip()
            payload["exception"] = (
                redact_value(exception_text)
                if self.settings.log_redaction_enabled
                else exception_text
            )
        if record.stack_info:
            payload["stack"] = (
                redact_value(record.stack_info)
                if self.settings.log_redaction_enabled
                else record.stack_info
            )

        # 允许 logger.info(..., extra={"event": ..., "duration_ms": ...}) 增加低敏结构化字段。
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_KEYS or key.startswith("_"):
                continue
            if key in {"message", "asctime", "exc_text"}:
                continue
            payload[key] = (
                redact_value(value, key=key)
                if self.settings.log_redaction_enabled
                else value
            )
        output = redact_mapping(payload) if self.settings.log_redaction_enabled else payload
        return json.dumps(output, ensure_ascii=False, default=str)


class _PlainLogFormatter(logging.Formatter):
    """本地关闭 JSON 时使用的兼容文本格式 Formatter。"""

    def __init__(self, settings: Settings, *, role: str):
        """初始化文本 Formatter。"""
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self.settings = settings
        self.role = role

    # 函数说明：格式化传统文本日志并执行同一套脱敏规则。
    # 参数说明：record: logging.LogRecord。
    # 返回说明：str。
    def format(self, record: logging.LogRecord) -> str:
        """输出便于本地阅读但不泄漏敏感信息的文本日志。"""
        return redact_value(super().format(record))


def _normalise_key(key: Any) -> str:
    """将字段名标准化为小写下划线/短横线形式，便于匹配敏感字段。"""
    return str(key).strip().lower().replace("-", "_")


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """递归脱敏字符串、Mapping、列表和元组；不改变原始业务对象。"""
    if key and _normalise_key(key) in _SECRET_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        result = value
        for pattern, replacement in _SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, set):
        return [redact_value(item) for item in value]
    return value


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """对结构化映射执行递归脱敏并返回普通 dict。"""
    result = redact_value(value)
    return result if isinstance(result, dict) else {"value": result}


def bind_log_context(**values: Any) -> contextvars.Token[dict[str, Any]]:
    """合并当前 asyncio 上下文并绑定关联字段，返回可用于 reset 的 Token。"""
    current = dict(_LOG_CONTEXT.get() or {})
    current.update({key: value for key, value in values.items() if value is not None})
    return _LOG_CONTEXT.set(current)


def reset_log_context(token: contextvars.Token[dict[str, Any]]) -> None:
    """恢复 bind_log_context 之前的上下文，避免请求/任务字段泄漏到后续请求。"""
    _LOG_CONTEXT.reset(token)


def get_log_context() -> dict[str, Any]:
    """返回当前上下文的副本，供队列、Span 和测试读取。"""
    return dict(_LOG_CONTEXT.get() or {})


def _span_id_hex(span: Any) -> str | None:
    """安全读取 OTel SpanContext 的 trace/span id，No-op 时返回 None。"""
    try:
        context = span.get_span_context()
        if context and context.is_valid:
            return f"{context.span_id:016x}"
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def current_trace_identifiers() -> dict[str, str]:
    """返回当前 Span 的 trace_id/span_id，供日志 Formatter 关联。"""
    if not _OTEL_AVAILABLE or trace is None:
        return {}
    try:
        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return {}
        return {
            "trace_id": f"{context.trace_id:032x}",
            "span_id": f"{context.span_id:016x}",
        }
    except (AttributeError, TypeError, ValueError):
        return {}


def current_traceparent() -> str | None:
    """将当前 Span 注入标准 W3C ``traceparent``，用于 Redis/HTTP 跨进程传播。"""
    if not _OTEL_AVAILABLE or propagate is None:
        return None
    carrier: dict[str, str] = {}
    try:
        propagate.inject(carrier)
    except (AttributeError, RuntimeError, TypeError, ValueError):  # pragma: no cover
        return None
    value = carrier.get("traceparent")
    return value if isinstance(value, str) and value else None


def current_tracestate() -> str | None:
    """返回当前 W3C ``tracestate``，没有供应商状态时返回 None。"""
    if not _OTEL_AVAILABLE or propagate is None:
        return None
    carrier: dict[str, str] = {}
    try:
        propagate.inject(carrier)
    except (AttributeError, RuntimeError, TypeError, ValueError):  # pragma: no cover
        return None
    value = carrier.get("tracestate")
    return value if isinstance(value, str) and value else None


def extract_trace_context(carrier: Mapping[str, str]) -> Any:
    """从 HTTP Header 或 Redis 字段提取 OTel Context；无效输入自动返回 None。"""
    if not _OTEL_AVAILABLE or propagate is None:
        return None
    try:
        # HTTP Header 大小写不敏感，而 Redis Stream 字段通常是小写；统一转换后
        # 可以避免不同客户端的大小写差异导致 Trace 链路断裂。
        normalised = {str(key).lower(): str(value) for key, value in carrier.items()}
        return propagate.extract(carrier=normalised)
    except (AttributeError, RuntimeError, TypeError, ValueError):  # pragma: no cover
        return None


def configure_observability(settings: Settings, *, role: str) -> None:
    """初始化结构化日志、脱敏 Formatter 和 OpenTelemetry Provider。"""
    configure_logging(settings, role=role)
    configure_tracing(settings, role=role)


def configure_logging(settings: Settings, *, role: str) -> None:
    """幂等配置进程根 logger；不会重复添加 Handler。"""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    marker = f"data-agent-runtime:{role}"
    for handler in root.handlers:
        if getattr(handler, "_data_agent_marker", None) == marker:
            return
    handler = logging.StreamHandler()
    handler._data_agent_marker = marker  # type: ignore[attr-defined]
    handler.setFormatter(
        JsonLogFormatter(settings, role=role)
        if settings.log_json
        else _PlainLogFormatter(settings, role=role)
    )
    root.addHandler(handler)


def configure_tracing(settings: Settings, *, role: str) -> None:
    """按配置初始化 OTel TracerProvider、采样器和 OTLP HTTP Exporter。"""
    if not settings.otel_enabled or not _OTEL_AVAILABLE or trace is None:
        return
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        provider = trace.get_tracer_provider()
        # 避免 API 模块 reload 或测试 fixture 重复覆盖全局 Provider。
        if provider.__class__.__module__.startswith("opentelemetry.sdk"):
            return
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name or settings.app_name,
                "service.instance.id": settings.service_instance_id
                or f"{socket.gethostname()}-{os.getpid()}",
                "deployment.environment.name": settings.app_env,
                "service.role": role,
                "host.name": socket.gethostname(),
                "process.pid": os.getpid(),
            }
        )
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(settings.otel_trace_sample_ratio),
        )
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            headers: dict[str, str] = {}
            if settings.otel_exporter_otlp_headers:
                for item in settings.otel_exporter_otlp_headers.split(","):
                    if "=" in item:
                        name, value = item.split("=", 1)
                        headers[name.strip()] = value.strip()
            endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
            if not endpoint.endswith("/v1/traces"):
                endpoint += "/v1/traces"
            exporter_kwargs: dict[str, Any] = {
                "endpoint": endpoint,
                "headers": headers,
                "timeout": settings.otel_exporter_timeout_seconds,
            }
            # OTLP HTTP Exporter 通过 endpoint 的 http/https scheme 控制 TLS，
            # 不同版本对 insecure 参数支持不一致；仅在当前版本明确暴露该参数
            # 时传入，避免因配置项导致 API/Worker 启动失败。
            if "insecure" in inspect.signature(OTLPSpanExporter).parameters:
                exporter_kwargs["insecure"] = settings.otel_insecure
            exporter = OTLPSpanExporter(**exporter_kwargs)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    except Exception:
        # 可观测性故障不能阻塞 API/Worker 启动；错误本身仍通过原始 logging 输出。
        logging.getLogger(__name__).exception("OpenTelemetry initialization failed")


def get_tracer(name: str = "data-agent-runtime") -> Any:
    """返回 Tracer；无 OTel 依赖时返回 No-op Tracer。"""
    if not _OTEL_AVAILABLE or trace is None:
        return None
    return trace.get_tracer(name)


@contextmanager
def start_span(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
    kind: Any = None,
    parent_context: Any = None,
) -> Iterable[Any]:
    """创建并激活一个可选 Span，自动记录异常并设置 error 状态。"""
    tracer = get_tracer()
    if tracer is None:
        yield _NoopSpan()
        return
    span_kind = kind if kind is not None and _OTEL_AVAILABLE else SpanKind.INTERNAL
    kwargs: dict[str, Any] = {"kind": span_kind}
    if parent_context is not None:
        kwargs["context"] = parent_context
    with tracer.start_as_current_span(name, **kwargs) as span:
        if attributes:
            safe_attributes = {
                key: value
                for key, value in redact_mapping(dict(attributes)).items()
                if isinstance(value, (str, bool, int, float))
            }
            span.set_attributes(safe_attributes)
        try:
            yield span
        except BaseException as exc:
            try:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, redact_value(str(exc))))
            except (AttributeError, RuntimeError, TypeError, ValueError):  # pragma: no cover
                logging.getLogger(__name__).debug(
                    "OpenTelemetry span error recording failed", exc_info=True
                )
            raise


class _NoopSpan:
    """在 OTel 未启用时维持 Span API 的最小兼容对象。"""

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
        """忽略属性设置。"""

    def set_attributes(self, *_args: Any, **_kwargs: Any) -> None:
        """忽略属性设置。"""

    def add_event(self, *_args: Any, **_kwargs: Any) -> None:
        """忽略 Span Event。"""

    def record_exception(self, *_args: Any, **_kwargs: Any) -> None:
        """忽略异常记录。"""

    def get_span_context(self) -> Any:
        """返回无效 SpanContext。"""
        return None


def new_request_id(value: str | None = None) -> str:
    """校验/复用调用方 Request ID；缺失或过长时生成新的不可预测 ID。"""
    candidate = (value or "").strip()
    if candidate and len(candidate) <= 128 and re.fullmatch(r"[A-Za-z0-9._:-]+", candidate):
        return candidate
    return uuid.uuid4().hex


def current_log_value(name: str) -> Any:
    """读取当前日志上下文的单个值。"""
    return (_LOG_CONTEXT.get() or {}).get(name)
