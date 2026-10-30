"""本文件模块职责：验证 Runtime 的结构化日志、敏感信息脱敏和 Trace 基础能力。

测试不依赖外部 Collector、Redis 或 Java 服务，确保在本地最小环境中也能验证：

- JSON 日志具备固定的服务、角色、来源和关联字段；
- 消息、结构化 extra 和异常文本不会泄漏 Token、密码或连接串凭证；
- ContextVar 不会把一个请求的 run_id 泄漏到另一个异步任务；
- OpenTelemetry SDK 未安装或未启用时，Trace API 仍然安全降级。
"""

from __future__ import annotations

import asyncio
import json
import logging

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.observability import (
    JsonLogFormatter,
    bind_log_context,
    current_log_value,
    current_trace_identifiers,
    extract_trace_context,
    get_log_context,
    new_request_id,
    redact_mapping,
    redact_value,
    reset_log_context,
    start_span,
)


def _settings(**overrides: object) -> Settings:
    """创建不读取本地真实 ``.env`` 的测试配置，避免测试受开发机状态影响。"""
    return Settings(_env_file=None, **overrides)


def test_json_formatter_contains_structured_fields_and_context() -> None:
    """验证 JSON 日志具备稳定字段，并正确关联 request/run 上下文。"""
    formatter = JsonLogFormatter(_settings(), role="worker")
    token = bind_log_context(
        request_id="request-123",
        run_id="run-456",
        tenant_id="tenant-1",
    )
    try:
        record = logging.makeLogRecord(
            {
                "name": "tests.observability",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "agent task accepted",
                "args": (),
                "funcName": "test_json_formatter_contains_structured_fields_and_context",
                "lineno": 42,
            }
        )
        record.event = "run_accepted"
        record.duration_ms = 12
        payload = json.loads(formatter.format(record))
    finally:
        reset_log_context(token)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.observability"
    assert payload["service"] == "data-agent-runtime"
    assert payload["role"] == "worker"
    assert payload["request_id"] == "request-123"
    assert payload["run_id"] == "run-456"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["event"] == "run_accepted"
    assert payload["duration_ms"] == 12
    assert payload["source"]["line"] == 42
    assert payload["process_id"] > 0
    assert payload["timestamp"].endswith("Z")


def test_redaction_covers_messages_urls_headers_and_nested_values() -> None:
    """验证常见 Bearer、OpenAI、Redis、PostgreSQL 和嵌套字段均会脱敏。"""
    value = {
        "authorization": "Bearer top-secret",
        "redis_url": "redis://:root@127.0.0.1:6379/0",
        "postgres_dsn": "postgresql://postgres:root@127.0.0.1:5432/postgres",
        "nested": [
            "Bearer another-secret",
            "https://example.test/api?token=query-secret&x=1",
            {"password": "db-password"},
        ],
        "message": "sk-1234567890abcdef and x-internal-service-token=secret-token",
    }

    redacted = redact_mapping(value)
    serialized = json.dumps(redacted, ensure_ascii=False)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["redis_url"] == "[REDACTED]"
    assert redacted["postgres_dsn"] == "[REDACTED]"
    assert redacted["nested"][2]["password"] == "[REDACTED]"
    assert "top-secret" not in serialized
    assert "root@" not in serialized
    assert "db-password" not in serialized
    assert "query-secret" not in serialized
    assert "1234567890abcdef" not in serialized
    assert "[REDACTED]" in serialized


def test_json_formatter_redacts_exception_and_extra_fields() -> None:
    """验证异常堆栈和 extra 字段也经过最终输出层脱敏。"""
    formatter = JsonLogFormatter(_settings(), role="api")
    try:
        raise RuntimeError("request failed: Bearer exception-secret")
    except RuntimeError:
        record = logging.makeLogRecord(
            {
                "name": "tests.observability",
                "levelno": logging.ERROR,
                "levelname": "ERROR",
                "msg": "call failed",
                "args": (),
                "exc_info": __import__("sys").exc_info(),
            }
        )
        record.headers = {"Authorization": "Bearer header-secret"}
        payload = json.loads(formatter.format(record))

    output = json.dumps(payload, ensure_ascii=False)
    assert "exception-secret" not in output
    assert "header-secret" not in output
    assert "[REDACTED]" in output


async def _read_context_in_task(run_id: str) -> str | None:
    """在独立 asyncio Task 中读取日志上下文，用于验证任务隔离。"""
    await asyncio.sleep(0)
    return current_log_value("run_id")


def test_contextvar_isolated_between_async_tasks() -> None:
    """验证不同异步任务的关联字段不会相互污染。"""

    async def run() -> tuple[str | None, str | None, dict[str, object]]:
        """执行当前测试场景的异步步骤并完成断言。"""
        first_token = bind_log_context(run_id="run-parent")
        try:
            first = asyncio.create_task(_read_context_in_task("run-child-1"))
            second_token = bind_log_context(run_id="run-child-2")
            try:
                second = asyncio.create_task(_read_context_in_task("run-child-2"))
            finally:
                reset_log_context(second_token)
            values = await asyncio.gather(first, second)
        finally:
            reset_log_context(first_token)
        return values[0], values[1], get_log_context()

    first, second, restored = asyncio.run(run())
    assert first == "run-parent"
    assert second == "run-child-2"
    assert restored == {}


def test_trace_helpers_fail_open_without_collector_or_sdk() -> None:
    """验证没有配置 Collector 时 Trace 辅助函数不阻断业务。"""
    assert new_request_id("request-abc_123") == "request-abc_123"
    generated = new_request_id("contains spaces")
    assert generated and generated != "contains spaces"
    # 无 SDK 时可能返回 None；关键要求是非法输入不抛异常。
    extract_trace_context({"TRACEPARENT": "invalid"})
    assert isinstance(current_trace_identifiers(), dict)

    with start_span("test.noop", attributes={"secret": "Bearer hidden"}) as span:
        span.set_attribute("test", "ok")
        span.add_event("test.event")


def test_redact_value_can_be_used_for_plain_text() -> None:
    """验证纯文本日志也能使用同一脱敏策略。"""
    result = redact_value(
        "redis://user:password@localhost:6379/0 Bearer token-value"
    )
    assert "password@" not in result
    assert "token-value" not in result
