"""本文件模块职责：基于 Redis Stream 的持久化 Agent 任务队列模块。

本模块提供 Consumer Group、run_id 幂等、任务入队、重试投递、Pending 接管、ACK 和死信流能力，确保 API 进程重启不会直接丢失已接受的任务。

Durable Redis Stream task queue for Agent Runs.

The HTTP API only enqueues a serialized RunRequest.  Agent execution is owned
by a separate worker process and therefore survives API process restarts.  The
queue uses a consumer group for delivery/ACK and keeps the initial idempotency
claim in the same Redis Lua transaction as XADD.

"""

from __future__ import annotations

import json
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.observability import (
    current_log_value,
    current_traceparent,
    current_tracestate,
    start_span,
)
from data_agent_runtime.runtime.state import RedisRunState
from data_agent_runtime.schemas import RunRequest

_INITIAL_ENQUEUE_SCRIPT = """
local claimed = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
if not claimed then
  return {0, ''}
end
redis.call('HSET', KEYS[2],
  'run_id', ARGV[1],
  'status', 'ACCEPTED',
  'session_id', ARGV[3],
  'agent_id', ARGV[4],
  'tenant_id', ARGV[5],
  'user_id', ARGV[6],
  'principal_id', ARGV[7],
  'stream', ARGV[8],
  'attempt', '0',
  'updated_at', ARGV[9])
redis.call('EXPIRE', KEYS[2], ARGV[2])
redis.call('SET', KEYS[4], ARGV[11], 'EX', ARGV[2])
local message_id = redis.call('XADD', KEYS[3], 'MAXLEN', '~', ARGV[10], '*',
  'run_id', ARGV[1], 'payload', ARGV[11], 'attempt', '0',
  'traceparent', ARGV[12], 'tracestate', ARGV[13], 'request_id', ARGV[14])
return {1, message_id}
"""

_APPROVE_ENQUEUE_SCRIPT = """
local status = redis.call('HGET', KEYS[1], 'status')
if status ~= 'PENDING_APPROVAL' then
  return {0, status or ''}
end
local payload = redis.call('GET', KEYS[2])
if not payload then
  redis.call('HSET', KEYS[1], 'status', 'FAILED', 'updated_at', ARGV[1],
    'error', '{"type":"APPROVAL_PAYLOAD_MISSING","retryable":false}')
  return {-1, 'MISSING_PAYLOAD'}
end
if redis.call('HGET', KEYS[1], 'cancel_requested') == 'true' then
  redis.call('HSET', KEYS[1], 'status', 'CANCELLED', 'updated_at', ARGV[1])
  redis.call('DEL', KEYS[2])
  return {-2, 'CANCELLED'}
end
local message_id = redis.call('XADD', KEYS[3], 'MAXLEN', '~', ARGV[2], '*',
  'run_id', ARGV[3], 'payload', payload, 'attempt', '0',
  'traceparent', ARGV[4], 'tracestate', ARGV[5], 'request_id', ARGV[6])
redis.call('HSET', KEYS[1], 'status', 'ACCEPTED', 'updated_at', ARGV[1])
redis.call('DEL', KEYS[2])
return {1, message_id}
"""


class RunTaskQueue:
    """连接 API Producer 与 Agent Worker 的 Redis Stream 任务队列。

    API 使用 Consumer Group 约定入队，Worker 通过阻塞读取和 Pending reclaim 消费；投递语义
    是 At-least-once，必须结合 run_id 幂等和有限重试使用。
    """

    def __init__(self, redis: Redis, settings: Settings, run_state: RedisRunState):
        """初始化 RunTaskQueue，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.redis = redis
        self.settings = settings
        self.run_state = run_state
        self._enqueue_script = redis.register_script(_INITIAL_ENQUEUE_SCRIPT)
        self._approve_enqueue_script = redis.register_script(_APPROVE_ENQUEUE_SCRIPT)

    @property
    def stream_key(self) -> str:
        """处理“stream_key”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return self.settings.task_stream_key

    @property
    def group_name(self) -> str:
        """处理“group_name”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return self.settings.task_consumer_group

    async def ensure_group(self) -> None:
        """处理“ensure_group”业务步骤，完成输入校验、依赖调用和结果返回。"""
        try:
            await self.redis.xgroup_create(
                self.stream_key,
                self.group_name,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, request: RunRequest) -> tuple[bool, str | None]:
        """以 Redis 原子脚本抢占 run_id 幂等键，并追加首次任务投递。

        新任务返回 ``(True, stream_id)``；相同 run_id 的重复提交返回
        ``(False, None)``，不会再次写入任务流，从而保证提交幂等性。
        """
        session_id = request.session_id or request.run_id
        now = self.run_state.now()
        traceparent = current_traceparent() or ""
        tracestate = current_tracestate() or ""
        request_id = str(current_log_value("request_id") or "")
        with start_span(
            "redis.task.enqueue",
            attributes={
                "messaging.system": "redis",
                "messaging.destination": self.stream_key,
                "run.id": request.run_id,
                "session.id": session_id,
                "agent.id": request.agent.id,
            },
        ) as span:
            result = await self._enqueue_script(
                keys=[
                    self.run_state.claim_key(request.run_id),
                    self.run_state.state_key(request.run_id),
                    self.stream_key,
                    self.run_state.request_payload_key(request.run_id),
                ],
                args=[
                    request.run_id,
                    str(self.settings.run_state_ttl_seconds),
                    session_id,
                    request.agent.id,
                    request.user_context.tenant_id,
                    request.user_context.user_id,
                    request.user_context.principal_id
                    or f"{request.user_context.tenant_id}:{request.user_context.user_id}",
                    str(request.stream).lower(),
                    now,
                    str(self.settings.task_stream_maxlen),
                    request.model_dump_json(),
                    traceparent,
                    tracestate,
                    request_id,
                ],
            )
            accepted = bool(int(result[0]))
            stream_id = result[1] or None
            span.set_attribute("messaging.operation", "publish")
            span.set_attribute("run.accepted", accepted)
            if stream_id:
                span.set_attribute("messaging.message.id", stream_id)
        return accepted, stream_id

    async def approve(self, run_id: str) -> tuple[str, str | None]:
        """审批并原子地把 Pending Run 投递到任务 Stream。

        状态更新、载荷读取和 XADD 在同一个 Redis Lua 脚本中完成，避免审批成功
        但 API 进程在投递前崩溃而丢失任务。重复审批会返回当前状态，不会重复投递。
        """
        traceparent = current_traceparent() or ""
        tracestate = current_tracestate() or ""
        request_id = str(current_log_value("request_id") or "")
        result = await self._approve_enqueue_script(
            keys=[
                self.run_state.state_key(run_id),
                self.run_state.approval_payload_key(run_id),
                self.stream_key,
            ],
            args=[
                self.run_state.now(),
                str(self.settings.task_stream_maxlen),
                run_id,
                traceparent,
                tracestate,
                request_id,
            ],
        )
        code = int(result[0])
        value = result[1] or None
        if code == 1:
            return "ACCEPTED", value
        if code == -1:
            return "FAILED", None
        if code == -2:
            return "CANCELLED", None
        return str(value or "UNKNOWN"), None

    async def dead_letter(
        self,
        message_id: str,
        fields: dict[str, str],
        *,
        error_type: str,
        error_message: str,
    ) -> str:
        """处理“dead_letter”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return await self.redis.xadd(
            self.settings.task_dead_letter_stream_key,
            {
                "source_message_id": message_id,
                "run_id": fields.get("run_id", ""),
                "payload": fields.get("payload", ""),
                "attempt": fields.get("attempt", "0"),
                "error_type": error_type,
                "error_message": error_message,
            },
            maxlen=self.settings.task_stream_maxlen,
            approximate=True,
        )

    async def enqueue_retry(self, request: RunRequest, attempt: int) -> str:
        """为已成功占用的 Run 追加一次重试投递。

        重试复用原始请求载荷并递增 attempt，由 Worker 负责决定何时调用本方法以及
        何时达到最大重试次数后进入死信流。
        """
        fields = {
            "run_id": request.run_id,
            "payload": request.model_dump_json(),
            "attempt": str(attempt),
            # 重试必须沿用首个 API 请求的 Trace Context；若当前上下文已经被
            # Worker Span 替换，则优先读取消息中的原始传播字段。
            "traceparent": str(current_log_value("traceparent") or current_traceparent() or ""),
            "tracestate": str(current_log_value("tracestate") or current_tracestate() or ""),
            "request_id": str(current_log_value("request_id") or ""),
        }
        with start_span(
            "redis.task.retry",
            attributes={
                "messaging.system": "redis",
                "messaging.destination": self.stream_key,
                "run.id": request.run_id,
                "messaging.retry.attempt": attempt,
            },
        ) as span:
            message_id = await self.redis.xadd(
                self.stream_key,
                fields,
                maxlen=self.settings.task_stream_maxlen,
                approximate=True,
            )
            span.set_attribute("messaging.message.id", message_id)
            return message_id

    async def enqueue_resume(
        self, run_id: str, decisions: list[dict[str, object]]
    ) -> str:
        """为一次等待人工确认的 Run 投递恢复任务。

        恢复任务携带人工决策，Worker 会用 ``Command(resume=...)`` 让 LangGraph 从
        checkpoint 继续执行，而不是重跑整个 Agent。
        """
        payload = {"decisions": decisions}
        with start_span(
            "redis.task.resume",
            attributes={
                "messaging.system": "redis",
                "messaging.destination": self.stream_key,
                "run.id": run_id,
            },
        ) as span:
            message_id = await self.redis.xadd(
                self.stream_key,
                {
                    "kind": "resume",
                    "run_id": run_id,
                    "payload": json.dumps(payload, ensure_ascii=False),
                    "attempt": "0",
                    "traceparent": current_traceparent() or "",
                    "tracestate": current_tracestate() or "",
                    "request_id": str(current_log_value("request_id") or ""),
                },
                maxlen=self.settings.task_stream_maxlen,
                approximate=True,
            )
            span.set_attribute("messaging.message.id", message_id)
            return message_id

    async def read(self, consumer_name: str) -> list[tuple[str, dict[str, str]]]:
        """处理“read”业务步骤，完成输入校验、依赖调用和结果返回。"""
        records = await self.redis.xreadgroup(
            self.group_name,
            consumer_name,
            {self.stream_key: ">"},
            count=1,
            block=self.settings.task_block_ms,
        )
        if not records:
            return []
        return [record for _, entries in records for record in entries]

    async def reclaim(self, consumer_name: str) -> list[tuple[str, dict[str, str]]]:
        """接管因 Worker 崩溃或失联而长期处于 Pending 的任务投递。

        Redis 可见性超时后由其他 Consumer 将消息转移到当前 Consumer；调用方仍需
        依靠 run lease、session lease 和幂等状态防止同一 Run 被并发执行。
        """
        result = await self.redis.xautoclaim(
            self.stream_key,
            self.group_name,
            consumer_name,
            min_idle_time=self.settings.task_visibility_timeout_seconds * 1000,
            start_id="0-0",
            count=10,
        )
        if not result or len(result) < 2:
            return []
        return list(result[1])

    async def depth(self) -> int:
        """返回任务流当前的近似长度，用于队列深度指标。"""
        try:
            return int(await self.redis.xlen(self.stream_key))
        except (RedisError, OSError):  # 指标采集失败不应影响消费主流程。
            return 0

    async def ack(self, message_id: str) -> int:
        """处理“ack”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return await self.redis.xack(self.stream_key, self.group_name, message_id)

    async def renew_delivery(self, consumer_name: str, message_id: str) -> None:
        # min_idle_time=0 的 XCLAIM 可以在模型或 Tool 调用运行时保持当前 Consumer 的 Pending 投递存活。
        """处理“renew_delivery”业务步骤，完成输入校验、依赖调用和结果返回。"""
        await self.redis.xclaim(
            self.stream_key,
            self.group_name,
            consumer_name,
            min_idle_time=0,
            message_ids=[message_id],
        )

    @staticmethod
    def parse_message(
        message: tuple[str, dict[str, str]],
    ) -> tuple[str, RunRequest | None, int, str, list[dict[str, object]] | None]:
        """解析任务消息，返回 ``(message_id, request, attempt, kind, decisions)``。

        ``kind=run`` 是普通运行投递；``kind=resume`` 是人工确认后的恢复投递，此时
        ``request`` 为 None，Worker 需要按 run_id 读取原始请求载荷后重建 Agent。
        """
        message_id, fields = message
        payload = fields.get("payload")
        if not payload:
            raise ValueError(f"Task message {message_id} has no payload")
        kind = fields.get("kind") or "run"
        try:
            attempt = int(fields.get("attempt", "0"))
        except ValueError:
            attempt = 0
        if kind == "resume":
            decoded = json.loads(payload)
            decisions = decoded.get("decisions") if isinstance(decoded, dict) else None
            if not isinstance(decisions, list) or not decisions:
                raise ValueError(f"Resume message {message_id} has no decisions")
            return message_id, None, attempt, kind, decisions
        return message_id, RunRequest.model_validate_json(payload), attempt, kind, None

    @staticmethod
    def new_consumer_name() -> str:
        """处理“new_consumer_name”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return f"worker-{uuid.uuid4().hex[:12]}"
