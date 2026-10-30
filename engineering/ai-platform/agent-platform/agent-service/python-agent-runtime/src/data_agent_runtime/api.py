"""本文件模块职责：独立公共 Agent Runtime 的 FastAPI API。

API 只负责认证、Principal/Scope 绑定、Snapshot 准入和任务入队；Agent 推理由独立
Worker 执行。任何实现 Runtime API 契约的外部调用方都可以接入，Runtime 不依赖特定控制面才能运行。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError

from data_agent_runtime.config import get_settings
from data_agent_runtime.runtime.admission import (
    SnapshotAdmissionError,
    admit_snapshot_async,
    bind_principal_context,
    validate_attachments,
)
from data_agent_runtime.runtime.auth import require_hmac_principal
from data_agent_runtime.runtime.bootstrap import runtime_resources
from data_agent_runtime.runtime.executor import RunExecutor
from data_agent_runtime.runtime.files import RuntimeFileStore, UploadTooLargeError
from data_agent_runtime.runtime.metrics import configure_metrics, get_metrics
from data_agent_runtime.runtime.observability import (
    bind_log_context,
    configure_observability,
    current_trace_identifiers,
    extract_trace_context,
    new_request_id,
    reset_log_context,
    start_span,
)
from data_agent_runtime.runtime.principal import Principal
from data_agent_runtime.runtime.queue import RunTaskQueue
from data_agent_runtime.runtime.ratelimit import RunRateLimiter
from data_agent_runtime.schemas import (
    ConversationMessage,
    MemoryItem,
    MemoryUpsertRequest,
    RunAccepted,
    RunRequest,
    RunResumeRequest,
)

settings = get_settings()
configure_observability(settings, role="api")
configure_metrics(settings)


def _hmac_headers(request: Request) -> dict[str, str | None]:
    """从 HTTP 请求提取 HMAC 头；SK 永远不在请求头中出现。"""
    return {
        "x_access_key": request.headers.get("X-Access-Key"),
        "x_timestamp": request.headers.get("X-Timestamp"),
        "x_nonce": request.headers.get("X-Nonce"),
        "x_content_sha256": request.headers.get("X-Content-SHA256"),
        "x_signature": request.headers.get("X-Signature"),
        "x_signature_version": request.headers.get("X-Signature-Version"),
    }


async def _require_principal(request: Request) -> Principal:
    """认证请求并返回 Principal，供所有受保护路由执行授权和资源隔离。"""
    return await require_hmac_principal(
        settings, request=request, **_hmac_headers(request)
    )


async def _require_sse_principal(request: Request) -> Principal:
    """认证 SSE 请求；SSE 也必须使用完整的 HMAC 请求头。"""
    return await require_hmac_principal(
        settings, request=request, **_hmac_headers(request)
    )


def _require_scope(principal: Principal, scope: str) -> None:
    """校验认证 Principal 是否具有访问当前路由所需的 Scope。

    缺少权限时统一返回 403；该函数不读取请求体，也不改变 Principal。"""
    if not principal.has_scope(scope):
        raise HTTPException(status_code=403, detail=f"missing required scope: {scope}")


async def _enforce_admission_guards(principal: Principal) -> None:
    """执行入口限流与队列背压检查。

    两者都在入队前执行：限流保护提交动作，背压保护任务流。任一不满足都立即返回可重试的
    错误（429/503 + ``Retry-After``），而不是把请求排进队列后长时间等待。
    """
    limiter = getattr(app.state, "rate_limiter", None)
    if limiter is not None:
        try:
            allowed, retry_after = await limiter.check(principal.principal_id)
        except Exception as exc:  # 限流依赖不可用时拒绝，而不是放行。
            logging.getLogger(__name__).exception(
                "Rate limiter unavailable",
                extra={"event": "rate_limiter_unavailable"},
            )
            raise HTTPException(
                status_code=503, detail="rate limiter is unavailable"
            ) from exc
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="too many runs submitted; please retry later",
                headers={"Retry-After": str(retry_after)},
            )
    queue = getattr(app.state, "queue", None)
    depth_fn = getattr(queue, "depth", None)
    if depth_fn is None:
        # 未提供深度接口的实现（例如测试替身）不参与背压判定。
        return
    try:
        depth = await depth_fn()
    except (RedisError, OSError):  # 深度读取失败时不阻断提交，交由队列自身的告警兜底。
        return
    if depth >= settings.task_max_queue_depth:
        raise HTTPException(
            status_code=503,
            detail="runtime queue is saturated; please retry later",
            headers={"Retry-After": "5"},
        )


def _require_user(principal: Principal, tenant_id: str, user_id: str) -> None:
    """校验租户和用户路径是否属于当前认证 Principal。

    资源归属以 HMAC 认证得到的 Principal 为准，不能由调用方请求体中的 user_context 覆盖。"""
    if not principal.can_access_user(tenant_id, user_id):
        raise HTTPException(
            status_code=403, detail="resource is outside authenticated Principal"
        )


def _state_owner(principal: Principal, state: dict[str, object]) -> None:
    """根据 Run 状态中的租户和用户字段执行资源归属校验。

    状态不存在或字段为空的处理由调用方负责；本函数只负责把状态身份交给统一的用户权限检查。"""
    tenant_id = str(state.get("tenant_id") or "")
    user_id = str(state.get("user_id") or "")
    _require_user(principal, tenant_id, user_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """创建并注册 API 进程使用的 Redis、队列、状态、事件和执行资源。

    启动时确保 Consumer Group 存在，关闭时由资源上下文释放连接；API 只入队，不在生命周期内执行 Agent。"""
    async with runtime_resources(settings) as resources:
        queue = RunTaskQueue(resources.redis, settings, resources.run_state)
        await queue.ensure_group()
        app.state.redis = resources.redis
        app.state.history = resources.history
        app.state.memories = resources.memories
        app.state.events = resources.events
        app.state.run_state = resources.run_state
        app.state.checkpointer = resources.checkpointer
        app.state.queue = queue
        app.state.files = RuntimeFileStore(resources.redis, settings)
        app.state.rate_limiter = (
            RunRateLimiter(resources.redis, settings.rate_limit_runs_per_minute)
            if settings.rate_limit_runs_per_minute > 0
            else None
        )
        app.state.executor = RunExecutor(
            settings,
            resources.events,
            resources.history,
            resources.memories,
            resources.checkpointer,
            resources.run_state,
            store=resources.store,
            files=RuntimeFileStore(resources.redis, settings),
        )
        yield


app = FastAPI(title="Data Agent Runtime", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """为每个 HTTP 请求绑定请求 ID、Trace 上下文和结构化日志字段。

    中间件不参与业务鉴权；它负责记录耗时、状态码和异常，并在请求结束后恢复日志上下文。"""
    request_id = new_request_id(request.headers.get("X-Request-ID"))
    parent_context = extract_trace_context(dict(request.headers))
    started_at = time.monotonic()
    log_token = bind_log_context(
        request_id=request_id, http_method=request.method, http_path=request.url.path
    )
    try:
        with start_span(
            "http.server",
            parent_context=parent_context,
            attributes={
                "http.request.method": request.method,
                "url.path": request.url.path,
                "server.address": request.url.hostname or "",
                "http.request.header.x_request_id": request_id,
            },
        ) as span:
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = current_trace_identifiers().get(
                "trace_id", request_id
            )
            span.set_attribute("http.response.status_code", response.status_code)
            logging.getLogger(__name__).info(
                "HTTP request completed",
                extra={
                    "event": "http_request_completed",
                    "http_status_code": response.status_code,
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
                },
            )
            return response
    finally:
        reset_log_context(log_token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    """返回 Runtime API 的存活状态。

    该接口用于进程级健康检查，不执行 Agent、不读取业务 Run，也不替代 Redis/Worker 就绪检查。"""
    return {"status": "UP", "service": settings.app_name, "mode": "public-runtime"}


@app.get("/v1/ready")
async def readiness() -> dict[str, str]:
    """检查 Runtime 是否具备接收任务所需的 Redis 依赖。"""
    redis = getattr(app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="runtime dependencies are not initialized")
    try:
        await redis.ping()
    except Exception as exc:  # 就绪检查失败时必须拒绝启动或继续服务。
        logging.getLogger(__name__).warning(
            "Runtime readiness check failed",
            extra={"event": "runtime_not_ready", "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=503, detail="redis is unavailable") from exc
    return {"status": "READY", "service": settings.app_name}


@app.post("/v1/runs", response_model=RunAccepted, status_code=202)
async def submit_run(
    request: RunRequest, principal: Annotated[Principal, Depends(_require_principal)]
) -> RunAccepted:
    """认证、准入并把一次 Agent Run 写入 Redis Task Stream。

    该路由绑定 Principal、校验租户与用户归属、初始化 Run 状态并返回 202；它不直接构建或执行 Agent，实际执行由 Worker 完成。重复 ``run_id`` 按队列的幂等约定处理。"""
    _require_scope(principal, "runs:write")
    await _enforce_admission_guards(principal)
    try:
        request = bind_principal_context(request, principal)
    except SnapshotAdmissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        await admit_snapshot_async(settings, request.agent, principal)
        validate_attachments(settings, request)
    except SnapshotAdmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if request.agent.plan.require_approval:
        try:
            created = await app.state.run_state.create_pending_approval(request)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="failed to persist approval request") from exc
        if not created:
            raise HTTPException(status_code=409, detail="run_id has already been submitted")
        try:
            await app.state.events.publish(
                request.run_id,
                "run_pending_approval",
                {"session_id": request.session_id or request.run_id},
            )
        except Exception:  # 状态持久化结果是权威来源。
            logging.getLogger(__name__).exception(
                "Failed to publish pending approval event",
                extra={"event": "run_pending_approval_event_failed", "run_id": request.run_id},
            )
        get_metrics().run_accepted(
            tenant_id=request.user_context.tenant_id,
            agent_id=request.agent.id,
        )
        return RunAccepted(run_id=request.run_id, status="PENDING_APPROVAL")
    try:
        accepted, _ = await app.state.queue.enqueue(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not accepted:
        raise HTTPException(status_code=409, detail="run_id has already been submitted")
    get_metrics().run_accepted(
        tenant_id=request.user_context.tenant_id,
        agent_id=request.agent.id,
    )
    return RunAccepted(run_id=request.run_id, status="ACCEPTED")


@app.post("/v1/runs/{run_id}/approve")
async def approve_run(
    run_id: str, principal: Annotated[Principal, Depends(_require_principal)]
) -> dict[str, object]:
    """审批等待中的 Run，并原子投递到 Worker 任务队列。"""
    _require_scope(principal, "runs:approve")
    state = await app.state.run_state.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    _state_owner(principal, state)
    try:
        status_value, message_id = await app.state.queue.approve(run_id)
    except Exception as exc:  # Redis 故障不能被伪装成客户端请求错误。
        logging.getLogger(__name__).exception(
            "Failed to approve Run",
            extra={"event": "run_approval_failed", "run_id": run_id},
        )
        raise HTTPException(
            status_code=503, detail="runtime queue is unavailable"
        ) from exc
    if status_value == "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="run approval could not be completed")
    if status_value == "FAILED":
        try:
            await app.state.events.publish(
                run_id, "run_failed", {"type": "APPROVAL_PAYLOAD_MISSING"}
            )
        except Exception:  # 事件发布失败不能掩盖原始执行错误。
            logging.getLogger(__name__).exception(
                "Failed to publish approval failure event",
                extra={"event": "run_approval_failure_event_failed", "run_id": run_id},
            )
        raise HTTPException(status_code=500, detail="approval payload is unavailable")
    if status_value == "CANCELLED":
        try:
            await app.state.events.publish(run_id, "run_cancelled", {})
        except Exception:  # 取消状态已经持久化，响应可以直接返回。
            logging.getLogger(__name__).exception(
                "Failed to publish cancelled approval event",
                extra={"event": "run_approval_cancel_event_failed", "run_id": run_id},
            )
        return {"run_id": run_id, "status": "CANCELLED"}
    if status_value not in {"ACCEPTED", "COMPLETED", "FAILED", "CANCELLED", "RETRYING", "RUNNING"}:
        raise HTTPException(status_code=409, detail=f"run cannot be approved from {status_value}")
    if message_id:
        try:
            await app.state.events.publish(
                run_id, "run_approved", {"message_id": message_id}
            )
        except Exception:  # 队列原子转换结果是审批状态的权威来源。
            logging.getLogger(__name__).exception(
                "Failed to publish approved event",
                extra={"event": "run_approved_event_failed", "run_id": run_id},
            )
    return {"run_id": run_id, "status": status_value}


@app.post("/v1/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    request: RunResumeRequest,
    principal: Annotated[Principal, Depends(_require_principal)],
) -> dict[str, object]:
    """用人工决策恢复一次等待确认的 Run。

    该路由只接受 ``runs:approve`` Scope、且状态为 ``WAITING_CONFIRMATION`` 的 Run；
    决策通过任务队列投递给 Worker，由 LangGraph ``Command(resume=...)`` 从 checkpoint
    继续执行，不会重跑已完成的推理步骤。
    """
    _require_scope(principal, "runs:approve")
    await _enforce_admission_guards(principal)
    state = await app.state.run_state.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    _state_owner(principal, state)
    if state.get("status") != "WAITING_CONFIRMATION":
        raise HTTPException(
            status_code=409,
            detail=f"run is not waiting for confirmation: {state.get('status')}",
        )
    try:
        message_id = await app.state.queue.enqueue_resume(run_id, request.decisions)
    except Exception as exc:  # Redis 故障不能被伪装成客户端错误。
        logging.getLogger(__name__).exception(
            "Failed to enqueue Run resume",
            extra={"event": "run_resume_enqueue_failed", "run_id": run_id},
        )
        raise HTTPException(
            status_code=503, detail="runtime queue is unavailable"
        ) from exc
    try:
        await app.state.events.publish(
            run_id,
            "run_resumed",
            {
                "session_id": state.get("session_id") or run_id,
                "decisions": len(request.decisions),
                "message_id": message_id,
            },
        )
    except Exception:  # 队列投递结果是恢复状态的权威来源。
        logging.getLogger(__name__).exception(
            "Failed to publish resumed event",
            extra={"event": "run_resumed_event_failed", "run_id": run_id},
        )
    return {"run_id": run_id, "status": "RESUMING"}


@app.get("/v1/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    principal: Annotated[Principal, Depends(_require_sse_principal)],
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    cursor: str | None = Query(default=None),
) -> StreamingResponse:
    """通过 Redis Event Stream 将指定 Run 转换为可恢复的 SSE 响应。

    每条事件包含 SSE ``id``、``event`` 和 JSON ``data``；服务端会在读到终态事件，或终态状态已无剩余事件时关闭连接。调用方应使用 HMAC 请求头并通过 ``Last-Event-ID`` 续读。"""
    _require_scope(principal, "runs:read")
    state = await app.state.run_state.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    _state_owner(principal, state)
    stream_key = f"agent:run:{run_id}:events"

    async def generate() -> AsyncIterator[str]:
        """阻塞读取 Redis 事件并逐条生成 SSE 文本。

        生成器只读取已授权 Run 的事件，不执行 Agent；客户端断线时由 StreamingResponse 取消迭代。"""
        last_id = last_event_id or cursor or "0-0"
        terminal_events = {"run_completed", "run_failed", "run_cancelled"}
        terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
        while True:
            entries = await app.state.redis.xread(
                {stream_key: last_id}, count=100, block=1000
            )
            if not entries:
                # 终态事件可能已经被消费、裁剪，或因上游发布异常而缺失；检查持久化状态，
                # 确保客户端在终态事件之后重连时不会一直保持连接。
                current_state = await app.state.run_state.get(run_id)
                if current_state and current_state.get("status") in terminal_statuses:
                    return
                yield ": keep-alive\n\n"
                continue
            for _, records in entries:
                for record_id, fields in records:
                    last_id = record_id
                    raw_event = fields.get("event")
                    if not raw_event:
                        continue
                    try:
                        event = json.loads(raw_event)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    event_type = event.get("event_type", "message")
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"id: {record_id}\nevent: {event_type}\ndata: {data}\n\n"
                    if event_type in terminal_events:
                        return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/v1/runs/{run_id}")
async def get_run_status(
    run_id: str, principal: Annotated[Principal, Depends(_require_principal)]
) -> dict[str, object]:
    """查询指定 Run 的最新状态。

    请求需要 ``runs:read`` Scope，且只能读取当前 Principal 所属租户和用户的状态；返回值来自 Redis 状态投影。"""
    _require_scope(principal, "runs:read")
    state = await app.state.run_state.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    _state_owner(principal, state)
    return state


@app.post("/v1/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str, principal: Annotated[Principal, Depends(_require_principal)]
) -> dict[str, object]:
    """为指定 Run 设置取消请求。

    路由只接受具备 ``runs:cancel`` Scope 且拥有该 Run 的调用方，实际停止由 Worker 在执行检查点处理。"""
    _require_scope(principal, "runs:cancel")
    state = await app.state.run_state.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    _state_owner(principal, state)
    if not await app.state.executor.cancel(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "status": "CANCEL_REQUESTED"}


@app.post("/v1/files", status_code=201)
async def upload_file(
    file: Annotated[UploadFile, File(description="要注入本次 Run 的文件")],
    principal: Annotated[Principal, Depends(_require_principal)],
) -> dict[str, object]:
    """上传一个文件并返回引用 ID，供 ``POST /v1/runs`` 的 ``attachments`` 使用。

    文件按租户隔离存放并带 TTL；内容不进入任务流。大小超过部署上限时返回 413。
    """
    _require_scope(principal, "runs:write")
    store = getattr(app.state, "files", None)
    if store is None:
        raise HTTPException(status_code=503, detail="file storage is unavailable")
    data = await file.read()
    try:
        return await store.put(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            file_name=file.filename or "upload",
            media_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.delete("/v1/files/{file_id}")
async def delete_file(
    file_id: str, principal: Annotated[Principal, Depends(_require_principal)]
) -> dict[str, object]:
    """删除一个已上传文件（仅限本租户）。"""
    _require_scope(principal, "runs:write")
    store = getattr(app.state, "files", None)
    if store is None:
        raise HTTPException(status_code=503, detail="file storage is unavailable")
    if not await store.delete(tenant_id=principal.tenant_id, file_id=file_id):
        raise HTTPException(status_code=404, detail="file not found")
    return {"file_id": file_id, "status": "DELETED"}


@app.get("/v1/sessions/{session_id}/messages", response_model=list[ConversationMessage])
async def list_session_messages(
    session_id: str,
    principal: Annotated[Principal, Depends(_require_principal)],
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ConversationMessage]:
    """读取当前 Principal 所属 Session 的对话历史。

    需要 ``sessions:read`` Scope；查询由 Redis 历史存储执行，并按部署级数量上限返回消息。"""
    _require_scope(principal, "sessions:read")
    _require_user(principal, principal.tenant_id, principal.user_id)
    values = await app.state.history.list_messages(
        session_id, limit, tenant_id=principal.tenant_id, user_id=principal.user_id
    )
    return [ConversationMessage.model_validate(value) for value in values]


@app.delete("/v1/sessions/{session_id}/messages")
async def clear_session_messages(
    session_id: str, principal: Annotated[Principal, Depends(_require_principal)]
) -> dict[str, object]:
    """清空当前 Principal 所属 Session 的对话历史。

    需要 ``sessions:write`` Scope；操作按租户和用户隔离，不会影响其他 Principal 的同名 Session。"""
    _require_scope(principal, "sessions:write")
    await app.state.history.clear(
        session_id, tenant_id=principal.tenant_id, user_id=principal.user_id
    )
    return {"session_id": session_id, "status": "CLEARED"}


@app.get("/v1/memories/{tenant_id}/{user_id}", response_model=list[MemoryItem])
async def list_memories(
    tenant_id: str,
    user_id: str,
    principal: Annotated[Principal, Depends(_require_principal)],
) -> list[MemoryItem]:
    """读取指定租户和用户的长期记忆。

    需要 ``memory:read`` Scope，并先校验路径归属；Runtime 不允许调用方读取其他租户的记忆。"""
    _require_scope(principal, "memory:read")
    _require_user(principal, tenant_id, user_id)
    values = await app.state.memories.list_memories(tenant_id, user_id)
    return [MemoryItem.model_validate(value) for value in values]


@app.put("/v1/memories/{tenant_id}/{user_id}/{memory_id}", response_model=MemoryItem)
async def upsert_memory(
    tenant_id: str,
    user_id: str,
    memory_id: str,
    request: MemoryUpsertRequest,
    principal: Annotated[Principal, Depends(_require_principal)],
) -> MemoryItem:
    """创建或更新一条长期记忆。

    需要 ``memory:write`` Scope；路径参数和请求体 ID 必须一致，创建时间在首次写入时保留，更新时间由 Runtime 生成。"""
    _require_scope(principal, "memory:write")
    _require_user(principal, tenant_id, user_id)
    if (
        request.tenant_id != tenant_id
        or request.user_id != user_id
        or request.memory_id != memory_id
    ):
        raise HTTPException(
            status_code=400, detail="memory path and payload identifiers must match"
        )
    now = datetime.now(UTC)
    existing = {
        item["memory_id"]: item
        for item in await app.state.memories.list_memories(tenant_id, user_id)
    }.get(memory_id)
    value = request.model_dump()
    value["created_at"] = (
        existing.get("created_at", now.isoformat()) if existing else now.isoformat()
    )
    value["updated_at"] = now.isoformat()
    return MemoryItem.model_validate(await app.state.memories.upsert(value))


@app.delete("/v1/memories/{tenant_id}/{user_id}/{memory_id}")
async def delete_memory(
    tenant_id: str,
    user_id: str,
    memory_id: str,
    principal: Annotated[Principal, Depends(_require_principal)],
) -> dict[str, object]:
    """删除指定的长期记忆。

    需要 ``memory:write`` Scope，并校验租户、用户和记忆 ID 的资源归属；不存在时返回 404。"""
    _require_scope(principal, "memory:write")
    _require_user(principal, tenant_id, user_id)
    if not await app.state.memories.delete(tenant_id, user_id, memory_id):
        raise HTTPException(status_code=404, detail="memory not found")
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "memory_id": memory_id,
        "status": "DELETED",
    }
