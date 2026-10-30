"""本文件模块职责：独立 Agent Worker 消费和执行模块。

本模块消费 Redis Stream 任务，处理 Pending 消息接管、Worker/Session Lease、心跳、取消、成功 ACK、失败重试和死信；它应与 FastAPI API 进程分离运行。

Durable Agent Run worker.

Run this in a separate process from FastAPI:

    uv run data-agent-worker

One worker owns one Redis Stream consumer identity. Multiple worker processes
can safely consume the same consumer group because run execution is protected
by Redis leases and queue deliveries are ACKed only after terminal handling.

"""

from __future__ import annotations

import asyncio
import logging

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.admission import validate_bound_request_async
from data_agent_runtime.runtime.events import EventPublisher
from data_agent_runtime.runtime.executor import RunExecutor
from data_agent_runtime.runtime.metrics import RuntimeMetrics, get_metrics
from data_agent_runtime.runtime.observability import (
    bind_log_context,
    extract_trace_context,
    reset_log_context,
    start_span,
)
from data_agent_runtime.runtime.queue import RunTaskQueue
from data_agent_runtime.runtime.state import RedisRunState
from data_agent_runtime.schemas import RunRequest

logger = logging.getLogger(__name__)


class TaskWorker:
    """从 Redis Consumer Group 消费并执行 Agent Run 的 Worker。

    Worker 通过阻塞读取新消息、定期 reclaim Pending 消息，获取 Run/Session Lease 和并发槽位，
    然后构建 Agent、发布事件、更新状态并 ACK、重试或写入 Dead Letter。语义为 At-least-once，
    不宣称 Exactly-once。
    """

    def __init__(
        self,
        settings: Settings,
        queue: RunTaskQueue,
        executor: RunExecutor,
        run_state: RedisRunState,
        events: EventPublisher,
        *,
        consumer_name: str | None = None,
        metrics: RuntimeMetrics | None = None,
    ):
        """初始化 TaskWorker，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.settings = settings
        self.queue = queue
        self.executor = executor
        self.run_state = run_state
        self.events = events
        self.consumer_name = consumer_name or queue.new_consumer_name()
        self._stop = asyncio.Event()
        self.metrics = metrics or get_metrics()

    def stop(self) -> None:
        """请求停止消费：当前 Run 会继续执行完毕，之后不再领取新任务。"""
        self._stop.set()

    async def serve(self, *, shutdown_timeout: float) -> None:
        """运行消费循环，并在收到停止请求后按 drain 超时优雅退出。

        停止信号只影响"是否继续领取新任务"：正在执行的 Run 会被等待完成（最多
        ``shutdown_timeout`` 秒）。超时则取消该 Run——消息不会被 ACK，其他 Worker
        会在可见性超时后接管，语义仍是 At-least-once。
        """
        loop_task = asyncio.create_task(
            self.run_forever(), name=f"agent-worker-{self.consumer_name}"
        )
        while not self._stop.is_set() and not loop_task.done():
            await asyncio.sleep(0.2)
        if loop_task.done():
            await loop_task
            return
        logger.info(
            "Graceful shutdown requested; draining in-flight run (timeout=%ss)",
            shutdown_timeout,
        )
        try:
            await asyncio.wait_for(asyncio.shield(loop_task), timeout=shutdown_timeout)
        except TimeoutError:
            logger.warning(
                "Drain timeout reached; cancelling in-flight run and leaving delivery pending"
            )
            loop_task.cancel()
            await asyncio.gather(loop_task, return_exceptions=True)
        else:
            logger.info("Worker drained and stopped cleanly")

    async def run_forever(self) -> None:
        """持续消费 Redis Stream 中的任务；同时负责 Pending 任务接管、执行、心跳和正常停止。"""
        await self.queue.ensure_group()
        logger.info(
            "Agent worker started consumer=%s group=%s stream=%s",
            self.consumer_name,
            self.queue.group_name,
            self.queue.stream_key,
        )
        while not self._stop.is_set():
            self.metrics.record_queue_depth(await self.queue.depth())
            reclaimed = await self.queue.reclaim(self.consumer_name)
            if reclaimed:
                for message in reclaimed:
                    await self._handle_message(message)
                continue
            messages = await self.queue.read(self.consumer_name)
            for message in messages:
                await self._handle_message(message)

    async def _handle_message(self, message: tuple[str, dict[str, str]]) -> None:
        """创建消息消费 Span 和日志上下文，再执行实际任务处理。"""
        message_id, fields = message
        parent_context = extract_trace_context(
            {
                key: value
                for key in ("traceparent", "tracestate")
                if (value := fields.get(key))
            }
        )
        token = bind_log_context(
            run_id=fields.get("run_id"),
            request_id=fields.get("request_id"),
            traceparent=fields.get("traceparent"),
            worker_id=self.consumer_name,
            message_id=message_id,
        )
        try:
            with start_span(
                "agent.worker.consume",
                parent_context=parent_context,
                attributes={
                    "messaging.system": "redis",
                    "messaging.destination": self.queue.stream_key,
                    "messaging.message.id": message_id,
                    "worker.id": self.consumer_name,
                    "run.id": fields.get("run_id", ""),
                    "messaging.operation": "process",
                },
            ) as span:
                span.set_attribute("worker.consumer", self.consumer_name)
                await self._handle_message_inner(message)
        finally:
            reset_log_context(token)

    async def _handle_message_inner(self, message: tuple[str, dict[str, str]]) -> None:
        """执行“_handle_message”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        message_id = message[0]
        request = None
        decisions: list[dict[str, object]] | None = None
        kind = "run"
        try:
            message_id, request, attempt, kind, decisions = self.queue.parse_message(
                message
            )
            if kind == "resume":
                # 恢复投递不带 Snapshot；用入队时保存的原始请求重建同一个 Agent。
                run_id = str(message[1].get("run_id") or "")
                stored = await self.run_state.load_request_payload(run_id)
                if not stored:
                    raise ValueError(
                        f"Resume message {message_id} has no stored request payload"
                    )
                request = RunRequest.model_validate_json(stored)
            await validate_bound_request_async(self.settings, request)
        except Exception as exc:
            logger.exception("Invalid Agent task message %s", message_id)
            # Poison Message 无法解析，因此不能重试，必须直接进入 Dead Letter。
            self.metrics.queue_dead_letter(run_id=(request.run_id if request else None))
            await self.queue.dead_letter(
                message_id,
                message[1],
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            if request is not None:
                state = await self.run_state.get(request.run_id)
                if not state or state.get("status") not in {
                    "COMPLETED",
                    "FAILED",
                    "CANCELLED",
                }:
                    error = {
                        "type": "TASK_ADMISSION_FAILED",
                        "message": str(exc),
                        "retryable": False,
                    }
                    await self.run_state.set_status(
                        request.run_id,
                        "FAILED",
                        session_id=request.session_id or request.run_id,
                        agent_id=request.agent.id,
                        tenant_id=(
                            request.user_context.tenant_id
                            if request.user_context
                            else None
                        ),
                        user_id=(
                            request.user_context.user_id
                            if request.user_context
                            else None
                        ),
                        error=error,
                    )
                    await self.events.publish(
                        request.run_id,
                        "run_failed",
                        {"error": error},
                    )
            await self.queue.ack(message_id)
            return

        state = await self.run_state.get(request.run_id)
        if state and state.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
            await self.queue.ack(message_id)
            return
        if kind == "resume" and (not state or state.get("status") != "WAITING_CONFIRMATION"):
            # 非等待确认状态的恢复投递（重复投递或已被处理）直接确认，避免误恢复。
            await self.queue.ack(message_id)
            return

        if not await self.run_state.try_acquire_worker_lease(
            request.run_id, self.consumer_name, attempt
        ):
            # 其他 Worker 已拥有同一个 Run；确认这条重复投递，最终结果仍由持有者负责。
            await self.queue.ack(message_id)
            return

        session_id = request.session_id or request.run_id
        session_owner = f"{self.consumer_name}:{request.run_id}"
        principal_id = (
            request.user_context.principal_id
            or f"{request.user_context.tenant_id}:{request.user_context.user_id}"
        )
        # Session/并发准入可能长时间等待；获取这些 Lease 前先保持 Run Lease，
        # 否则第二个 Worker 可能在第一个 Worker 等待时 reclaim 同一投递并并发执行 Run。
        worker_lease_lost = asyncio.Event()
        run_lease_heartbeat = asyncio.create_task(
            self._run_lease_heartbeat(request.run_id, worker_lease_lost),
            name=f"run-lease-heartbeat-{request.run_id}",
        )
        configured_concurrency = self.settings.max_concurrent_runs_per_principal
        principal_concurrency = request.user_context.max_concurrent_runs
        concurrency_limit = min(
            value
            for value in (configured_concurrency, principal_concurrency)
            if value is not None
        )
        # 等待同一 Session 的其他 Run 完成时，也要保持当前 Pending 投递存活。
        delivery_heartbeat = asyncio.create_task(
            self._delivery_heartbeat(message_id),
            name=f"delivery-heartbeat-{request.run_id}",
        )
        session_acquired = False
        concurrency_acquired = False
        worker_heartbeat = None
        try:
            while not await self.run_state.try_acquire_concurrency(
                principal_id, request.run_id, concurrency_limit
            ):
                # 并发配额不足时保留 Pending 投递，等待其他 Run 释放槽位；
                # delivery heartbeat 保证长时间排队不会被误接管。
                if worker_lease_lost.is_set():
                    raise RuntimeError("worker lease was lost while waiting for concurrency")
                if await self.run_state.is_cancel_requested(request.run_id):
                    await self.run_state.mark_cancelled(request.run_id)
                    await self.events.publish(
                        request.run_id,
                        "run_cancelled",
                        {"session_id": session_id},
                    )
                    await self.queue.ack(message_id)
                    return
                await asyncio.sleep(0.5)
            concurrency_acquired = True
            while not await self.run_state.try_acquire_session_lease(
                request.user_context.tenant_id, session_id, session_owner
            ):
                # 一个 Session 在所有 Worker 进程之间串行执行；前一个 Run 结束前，当前投递保持 Pending。
                if worker_lease_lost.is_set():
                    raise RuntimeError("worker lease was lost while waiting for session")
                if await self.run_state.is_cancel_requested(request.run_id):
                    await self.run_state.mark_cancelled(request.run_id)
                    await self.events.publish(
                        request.run_id,
                        "run_cancelled",
                        {"session_id": session_id},
                    )
                    await self.queue.ack(message_id)
                    return
                await asyncio.sleep(0.5)
            session_acquired = True
            worker_heartbeat = asyncio.create_task(
                self._worker_heartbeat(
                    request.run_id,
                    request.user_context.tenant_id,
                    session_id,
                    session_owner,
                    principal_id,
                    renew_worker=False,
                ),
                name=f"run-heartbeat-{request.run_id}",
            )
            if await self.run_state.is_cancel_requested(request.run_id):
                await self.run_state.mark_cancelled(request.run_id)
                await self.events.publish(
                    request.run_id,
                    "run_cancelled",
                    {"session_id": session_id},
                )
            elif kind == "resume":
                await self._execute_resume(request, attempt, decisions or [])
            else:
                await self._execute_with_cancellation(request, attempt)
            await self.queue.ack(message_id)
        except asyncio.CancelledError:
            # 不确认当前 Pending 投递；进程终止后，其他 Worker 可在可见性超时后 reclaim。
            raise
        except Exception as exc:  # noqa: BLE001  # convert task errors into retry/dead-letter state
            await self._handle_failure(request, attempt, exc, message)
            await self.queue.ack(message_id)
        finally:
            delivery_heartbeat.cancel()
            run_lease_heartbeat.cancel()
            if worker_heartbeat:
                worker_heartbeat.cancel()
            await asyncio.gather(
                delivery_heartbeat,
                run_lease_heartbeat,
                *( [worker_heartbeat] if worker_heartbeat else [] ),
                return_exceptions=True,
            )
            await self.run_state.release_worker_lease(
                request.run_id, self.consumer_name
            )
            if session_acquired:
                await self.run_state.release_session_lease(
                    request.user_context.tenant_id, session_id, session_owner
                )
            if concurrency_acquired:
                await self.run_state.release_concurrency(principal_id, request.run_id)

    async def _execute_with_cancellation(
        self, request: RunRequest, attempt: int
    ) -> None:
        """执行“_execute_with_cancellation”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        execution = asyncio.create_task(
            self.executor.execute_queued(
                request,
                worker_id=self.consumer_name,
                attempt=attempt,
            ),
            name=f"agent-run-{request.run_id}",
        )
        try:
            while True:
                done, _ = await asyncio.wait({execution}, timeout=1.0)
                if execution in done:
                    await execution
                    return
                if await self.run_state.is_cancel_requested(request.run_id):
                    execution.cancel()
                    try:
                        await execution
                    except asyncio.CancelledError:
                        await self.run_state.mark_cancelled(request.run_id)
                        await self.events.publish(
                            request.run_id,
                            "run_cancelled",
                            {"session_id": request.session_id or request.run_id},
                        )
                    return
        except asyncio.CancelledError:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            raise

    async def _execute_resume(
        self,
        request: RunRequest,
        attempt: int,
        decisions: list[dict[str, object]],
    ) -> None:
        """用人工决策恢复执行，并在等待期间保持取消语义。"""
        execution = asyncio.create_task(
            self.executor.execute_resume(request, decisions),
            name=f"agent-resume-{request.run_id}",
        )
        try:
            while True:
                done, _ = await asyncio.wait({execution}, timeout=1.0)
                if execution in done:
                    await execution
                    return
                if await self.run_state.is_cancel_requested(request.run_id):
                    execution.cancel()
                    try:
                        await execution
                    except asyncio.CancelledError:
                        await self.run_state.mark_cancelled(request.run_id)
                        await self.events.publish(
                            request.run_id,
                            "run_cancelled",
                            {"session_id": request.session_id or request.run_id},
                        )
                    return
        except asyncio.CancelledError:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            raise

    async def _handle_failure(
        self,
        request: RunRequest,
        attempt: int,
        exc: Exception,
        message: tuple[str, dict[str, str]],
    ) -> None:
        """执行“_handle_failure”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        error = {"error_type": type(exc).__name__, "message": str(exc)}
        next_attempt = attempt + 1
        if next_attempt < self.settings.task_max_attempts:
            self.metrics.queue_retry(run_id=request.run_id)
            await self.run_state.mark_retrying(request.run_id, next_attempt, error)
            if self.settings.task_retry_delay_seconds > 0:
                await asyncio.sleep(self.settings.task_retry_delay_seconds)
            retry_id = await self.queue.enqueue_retry(request, next_attempt)
            await self.events.publish(
                request.run_id,
                "run_retry_scheduled",
                {
                    "session_id": request.session_id or request.run_id,
                    "attempt": next_attempt,
                    "max_attempts": self.settings.task_max_attempts,
                    "task_id": retry_id,
                    "error_type": error["error_type"],
                },
            )
            return

        self.metrics.queue_dead_letter(run_id=request.run_id)
        await self.queue.dead_letter(
            message[0],
            message[1],
            error_type=error["error_type"],
            error_message=error["message"],
        )
        await self.run_state.set_status(
            request.run_id,
            "FAILED",
            session_id=request.session_id or request.run_id,
            agent_id=request.agent.id,
            tenant_id=request.user_context.tenant_id,
            user_id=request.user_context.user_id,
            stream=request.stream,
            error={**error, "attempt": attempt},
        )
        await self.events.publish(
            request.run_id,
            "run_failed",
            {
                "session_id": request.session_id or request.run_id,
                **error,
                "attempt": attempt,
            },
        )

    async def _run_lease_heartbeat(
        self, run_id: str, lease_lost: asyncio.Event
    ) -> None:
        """在等待配额/会话租约时续期 Run Worker Lease。"""
        interval = max(1, self.settings.task_visibility_timeout_seconds // 3)
        try:
            while True:
                await asyncio.sleep(interval)
                if not await self.run_state.renew_worker_lease(
                    run_id, self.consumer_name
                ):
                    lease_lost.set()
                    return
        except asyncio.CancelledError:
            return

    async def _worker_heartbeat(
        self,
        run_id: str,
        tenant_id: str,
        session_id: str,
        session_owner: str,
        principal_id: str,
        *,
        renew_worker: bool = True,
    ) -> None:
        """执行“_worker_heartbeat”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        try:
            while True:
                await asyncio.sleep(self.settings.worker_heartbeat_interval_seconds)
                if renew_worker and not await self.run_state.renew_worker_lease(
                    run_id, self.consumer_name
                ):
                    return
                if not await self.run_state.renew_session_lease(
                    tenant_id, session_id, session_owner
                ):
                    return
                if not await self.run_state.renew_concurrency(
                    principal_id, run_id
                ):
                    return
        except asyncio.CancelledError:
            return

    async def _delivery_heartbeat(self, message_id: str) -> None:
        """执行“_delivery_heartbeat”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        interval = max(1, self.settings.task_visibility_timeout_seconds // 3)
        try:
            while True:
                await asyncio.sleep(interval)
                await self.queue.renew_delivery(self.consumer_name, message_id)
        except asyncio.CancelledError:
            return


def create_worker(
    settings: Settings,
    *,
    redis,
    events: EventPublisher,
    history,
    memories,
    checkpointer,
    run_state: RedisRunState,
    store=None,
    files=None,
) -> TaskWorker:
    """组装任务队列、状态、事件和执行器，创建一个可以持续消费 Redis Stream 的 Worker。"""
    queue = RunTaskQueue(redis, settings, run_state)
    executor = RunExecutor(
        settings,
        events,
        history,
        memories,
        checkpointer,
        run_state,
        store=store,
        files=files,
    )
    return TaskWorker(settings, queue, executor, run_state, events, consumer_name=settings.task_consumer_name)
