"""本文件模块职责：单次 Agent Run 执行编排模块。

本模块负责读取历史上下文、构建 DeepAgents、执行流式或非流式推理、发布运行事件、保存最终答案并更新 Run 状态；队列重试和死信决策由 Worker 负责。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from collections.abc import Mapping
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.documents import detect_kind, extract_text
from data_agent_runtime.runtime.events import EventPublisher
from data_agent_runtime.runtime.factory import build_agent
from data_agent_runtime.runtime.files import RuntimeFileStore, decode_content
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.runtime.metrics import RuntimeMetrics, get_metrics
from data_agent_runtime.runtime.observability import (
    bind_log_context,
    reset_log_context,
    start_span,
)
from data_agent_runtime.runtime.state import RedisRunState
from data_agent_runtime.schemas import RunRequest

logger = logging.getLogger(__name__)


def _message_content(message: Any) -> str:
    """执行“_message_content”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    content = (
        message.get("content")
        if isinstance(message, Mapping)
        else getattr(message, "content", message)
    )
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _assistant_answer(result: Any) -> str:
    """执行“_assistant_answer”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if isinstance(result, Mapping):
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                role = (
                    message.get("role")
                    if isinstance(message, Mapping)
                    else getattr(message, "type", None)
                )
                if role in {"assistant", "ai"}:
                    return _message_content(message)
        if "output" in result:
            return _message_content(result["output"])
    return _message_content(result)


def _structured_response(result: Any) -> Any:
    """从 Agent 终态中提取结构化输出。

    声明了 ``response_format`` 时，LangChain 会把符合 Schema 的对象放在
    ``structured_response``；没有声明或模型未产出时返回 ``None``。"""
    if isinstance(result, Mapping):
        return result.get("structured_response")
    return getattr(result, "structured_response", None)


def _normalise_usage(raw: Any) -> dict[str, int] | None:
    """把不同来源的 token 用量归一化为 input/output/total。

    兼容 ``usage_metadata``（LangChain 1.x 标准字段）与 ``token_usage``
    （OpenAI 兼容网关常见的原始字段），两者字段名不同但语义一致。
    """
    if not isinstance(raw, Mapping):
        return None
    input_tokens = raw.get("input_tokens", raw.get("prompt_tokens"))
    output_tokens = raw.get("output_tokens", raw.get("completion_tokens"))
    total_tokens = raw.get("total_tokens")
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    normalized = {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }
    details = raw.get("output_token_details")
    if isinstance(details, Mapping) and details.get("reasoning") is not None:
        normalized["reasoning_tokens"] = int(details.get("reasoning") or 0)
    normalized["total_tokens"] = int(
        total_tokens
        if total_tokens is not None
        else normalized["input_tokens"] + normalized["output_tokens"]
    )
    return normalized


def _usage_from_event(event: Mapping[str, Any]) -> tuple[str, dict[str, int]] | None:
    """从 ``on_chat_model_end`` 事件中提取 ``(model_name, usage)``。

    只统计**本次 Run 内**发生的模型调用：Checkpoint 里的历史消息会跨 Run 累积，
    直接遍历状态求和会重复计算上一轮对话的 token。
    """
    data = event.get("data")
    if not isinstance(data, Mapping):
        return None
    output = data.get("output")
    candidates: list[Any] = []
    if output is not None:
        candidates.append(output)
        # LLMResult.generations[0][0].message
        generations = getattr(output, "generations", None)
        if generations:
            try:
                candidates.append(generations[0][0].message)
            except (IndexError, AttributeError, TypeError):
                pass
    model_name = ""
    for candidate in candidates:
        usage = getattr(candidate, "usage_metadata", None)
        if usage is None and isinstance(candidate, Mapping):
            usage = candidate.get("usage_metadata")
        normalised = _normalise_usage(usage)
        if normalised is None:
            metadata = getattr(candidate, "response_metadata", None)
            if isinstance(metadata, Mapping):
                normalised = _normalise_usage(
                    metadata.get("token_usage") or metadata.get("usage")
                )
        if normalised is None:
            llm_output = getattr(candidate, "llm_output", None)
            if isinstance(llm_output, Mapping):
                normalised = _normalise_usage(
                    llm_output.get("token_usage") or llm_output.get("usage")
                )
        if normalised is None:
            continue
        metadata = getattr(candidate, "response_metadata", None)
        if isinstance(metadata, Mapping):
            model_name = str(
                metadata.get("model_name") or metadata.get("model") or ""
            )
        return model_name, normalised
    return None


def _merge_usage(
    target: dict[str, Any], model_name: str, usage: dict[str, int]
) -> None:
    """把一次模型调用的用量累加到 Run 级汇总（含按模型拆分与推理 token）。"""
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if "reasoning_tokens" in usage or "reasoning_tokens" in target:
        keys = (*keys, "reasoning_tokens")
    for key in keys:
        target[key] = int(target.get(key, 0)) + usage.get(key, 0)
    if model_name:
        by_model = target.setdefault("by_model", {})
        bucket = by_model.setdefault(
            model_name, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        )
        for key in keys:
            bucket[key] = int(bucket.get(key, 0)) + usage.get(key, 0)


def _state_extras(result: Any) -> dict[str, Any]:
    """提取计划与异步任务状态，供调用方展示进度。

    ``write_todos`` 与异步子 Agent 都把结果放在 Agent 状态里；只在存在时透出，
    避免给不需要这些能力的调用方增加无关字段。"""
    if not isinstance(result, Mapping):
        return {}
    extras: dict[str, Any] = {}
    for key in ("todos", "async_tasks"):
        value = result.get(key)
        if value is not None:
            extras[key] = value
    return extras


def _has_checkpoint_messages(snapshot: Any) -> bool:
    """执行“_has_checkpoint_messages”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    values = getattr(snapshot, "values", None)
    return isinstance(values, Mapping) and bool(values.get("messages"))


def _stream_chunks(event: Mapping[str, Any]) -> list[tuple[str, str]]:
    """把 ``on_chat_model_stream`` 事件拆成 ``[(kind, delta)]``。

    ``kind`` 只有两种：``text``（最终答案增量）与 ``reasoning``（模型思考过程）。
    两者必须分开：把思考内容混进答案会让前端把推理过程粘到最终回复里。

    兼容三种常见形态：
    - ``content`` 为字符串；
    - ``content`` 为内容块列表（``{"type": "text"}`` / ``{"type": "reasoning"}``）；
    - 推理内容放在 ``additional_kwargs.reasoning_content``（DeepSeek 等网关）。
    """
    data = event.get("data")
    if not isinstance(data, Mapping):
        return []
    chunk = data.get("chunk")
    if chunk is None:
        return []
    content = (
        chunk.get("content")
        if isinstance(chunk, Mapping)
        else getattr(chunk, "content", None)
    )
    parts: list[tuple[str, str]] = []
    if isinstance(content, str):
        if content:
            parts.append(("text", content))
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                if item:
                    parts.append(("text", item))
                continue
            if not isinstance(item, Mapping):
                continue
            block_type = item.get("type")
            if block_type in {"reasoning", "thinking"}:
                text = (
                    item.get("reasoning")
                    or item.get("thinking")
                    or item.get("text")
                )
                if isinstance(text, str) and text:
                    parts.append(("reasoning", text))
            elif isinstance(item.get("text"), str) and item["text"]:
                parts.append(("text", item["text"]))
    if not any(kind == "reasoning" for kind, _ in parts):
        extra = (
            chunk.get("additional_kwargs")
            if isinstance(chunk, Mapping)
            else getattr(chunk, "additional_kwargs", None)
        )
        if isinstance(extra, Mapping):
            reasoning = extra.get("reasoning_content") or extra.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                parts.append(("reasoning", reasoning))
    return parts


async def _interrupt_payload(
    agent: Any, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """从 Agent 状态中提取等待人工确认的中断。

    LangGraph 把 HumanInTheLoopMiddleware 产生的中断挂在最新 StateSnapshot 的
    ``interrupts`` 上；读取最新状态时该字段只包含仍在等待答复的中断。"""
    snapshot = await agent.aget_state(config)
    interrupts = getattr(snapshot, "interrupts", ()) or ()
    payload: list[dict[str, Any]] = []
    for interrupt in interrupts:
        payload.append(
            {
                "interrupt_id": str(getattr(interrupt, "id", "")),
                "request": getattr(interrupt, "value", None),
            }
        )
    return payload


def _run_timeout_seconds(request: RunRequest, settings: Settings) -> int:
    """计算单次 Run 的有效超时，始终不超过部署硬上限。"""
    requested = request.user_context.run_timeout_seconds if request.user_context else None
    if requested is None:
        return settings.run_timeout_seconds
    return min(requested, settings.run_timeout_seconds)


class RunExecutor:
    """构建并执行一次 Agent Run，同时协调事件、历史、记忆和终态资源。

    Executor 运行在 Worker 进程，不负责 HTTP 认证或任务入队；失败必须更新 Run 状态并释放
    Agent、MCP、Sandbox 和 Checkpointer 资源。
    """

    def __init__(
        self,
        settings: Settings,
        events: EventPublisher,
        history: RedisConversationHistory,
        memories: RedisLongTermMemory,
        checkpointer: BaseCheckpointSaver,
        run_state: RedisRunState | None = None,
        store: Any | None = None,
        metrics: RuntimeMetrics | None = None,
        files: RuntimeFileStore | None = None,
    ):
        """初始化 RunExecutor，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.settings = settings
        self.events = events
        self.history = history
        self.memories = memories
        self.checkpointer = checkpointer
        self.run_state = run_state
        self.store = store
        self.metrics = metrics or get_metrics()
        self.files = files
        self.tasks: dict[str, asyncio.Task[Any]] = {}
        self.session_locks: dict[str, asyncio.Lock] = {}

    def _session_lock(self, thread_id: str) -> asyncio.Lock:
        """执行“_session_lock”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        lock = self.session_locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self.session_locks[thread_id] = lock
        return lock

    async def submit(self, request: RunRequest) -> None:
        """处理“submit”业务步骤，完成输入校验、依赖调用和结果返回。"""
        if request.run_id in self.tasks:
            return
        if self.run_state:
            existing = await self.run_state.get(request.run_id)
            if existing and existing.get("status") in {
                "ACCEPTED",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
            }:
                return
            await self.run_state.set_status(
                request.run_id,
                "ACCEPTED",
                session_id=request.session_id or request.run_id,
                agent_id=request.agent.id,
                tenant_id=request.user_context.tenant_id,
                user_id=request.user_context.user_id,
                stream=request.stream,
            )
        task = asyncio.create_task(
            self._run(request), name=f"agent-run-{request.run_id}"
        )
        self.tasks[request.run_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(request.run_id, None))

    async def cancel(self, run_id: str) -> bool:
        """请求取消本地正在执行的任务，或在持久化状态中写入取消标记以供远程 Worker 处理。"""
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            return True
        if self.run_state:
            return await self.run_state.request_cancel(run_id)
        return False

    async def execute_queued(
        self, request: RunRequest, *, worker_id: str, attempt: int
    ) -> str:
        """执行一次已经由可靠性队列投递的 Agent Run。

        返回 ``completed`` 或 ``interrupted``：后者表示 Agent 在工具执行前中断并等待
        人工确认，Worker 不应重试。队列和执行异常会继续抛给 ``TaskWorker``。
        """
        return await self._run(
            request,
            finalize_failure=False,
            finalize_cancelled=False,
        )

    async def execute_resume(
        self, request: RunRequest, decisions: list[dict[str, Any]]
    ) -> str:
        """用人工决策恢复一次等待确认的 Run。

        恢复通过 LangGraph ``Command(resume=...)`` 从 checkpoint 继续，不重新执行
        已经完成的推理步骤，也不会重复写入用户消息。
        """
        return await self._run(
            request,
            finalize_failure=False,
            finalize_cancelled=False,
            resume={"decisions": decisions},
        )

    async def _load_attachments(
        self, request: RunRequest
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """读取并解析本次 Run 的附件。

        返回 ``(注入的文本段落, 图片内容块, 原始文件列表)``：
        表格/PDF 转成文本段落拼到用户消息里，图片转成多模态内容块，原始字节留给沙箱落盘。
        """
        if not request.attachments:
            return "", [], []
        if self.files is None:
            raise RuntimeError("attachment storage is unavailable")
        tenant_id = request.user_context.tenant_id
        sections: list[str] = []
        images: list[dict[str, Any]] = []
        raw_files: list[dict[str, Any]] = []
        for index, ref in enumerate(request.attachments, start=1):
            record = await self.files.get(tenant_id=tenant_id, file_id=ref.file_id)
            if record is None:
                raise RuntimeError(
                    f"attachment {ref.file_id!r} is missing or expired"
                )
            name = str(record.get("name") or ref.name or ref.file_id)
            media_type = str(record.get("media_type") or ref.media_type or "")
            data = decode_content(record)
            kind = detect_kind(name, media_type)
            raw_files.append({"name": name, "media_type": media_type, "data": data})
            if kind == "image":
                encoded = base64.b64encode(data).decode("ascii")
                images.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type or 'image/png'};base64,{encoded}"
                        },
                    }
                )
                sections.append(
                    f"\n\n# 附件 {index}: {name}（图片，已作为多模态输入提供）"
                )
                continue
            if kind == "unsupported":
                sections.append(
                    f"\n\n# 附件 {index}: {name}\n（不支持的文件类型，未解析）"
                )
                continue
            text = extract_text(
                kind,
                data,
                max_rows=self.settings.attachment_preview_rows,
                max_chars=self.settings.attachment_max_chars,
            )
            sections.append(
                f"\n\n# 附件 {index}: {name}（{kind}）\n```\n{text}\n```"
            )
        return "".join(sections), images, raw_files

    async def _write_attachments_to_sandbox(
        self, runtime_handle: Any, raw_files: list[dict[str, Any]], run_id: str
    ) -> None:
        """把原始附件写入沙箱工作区，便于工具（如 pandas）直接读取。

        写失败只记录告警：已注入的文本仍然可用，不应因沙箱问题让整个 Run 失败。
        """
        provider = getattr(runtime_handle, "sandbox_provider", None)
        if provider is None or not raw_files:
            return
        for item in raw_files:
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", item["name"]).strip(".-")
            safe_name = safe_name[:96] or "upload.bin"
            try:
                await provider.write_file(f"/workspace/uploads/{safe_name}", item["data"])
            except Exception:
                logger.warning(
                    "Failed to write attachment %s into sandbox for run %s",
                    item["name"],
                    run_id,
                    exc_info=True,
                )

    async def _stream_agent(
        self,
        agent: Any,
        payload: dict[str, Any],
        config: dict[str, Any],
        run_id: str,
        session_id: str,
        *,
        publish_tokens: bool = True,
    ) -> tuple[Any, dict[str, Any]]:
        """运行 DeepAgents 图，并把选定的内部事件转换为 Runtime 运行事件。

        返回 ``(final_output, usage)``；``usage`` 是本 Run 内所有模型调用的 token 汇总。

        当 ``publish_tokens=False`` 时表示外部非流式模式：Agent 仍然执行并上报
        工具生命周期事件，但不会把模型 Token 增量发布到 Redis Stream；流式模式
        则会逐段发布 ``agent_message_delta`` 事件。
        """
        final_output: Any = None
        usage: dict[str, Any] = {}
        with start_span(
            "agent.graph",
            attributes={
                "run.id": run_id,
                "session.id": session_id,
                "agent.stream": publish_tokens,
            },
        ) as graph_span:
            async for event in agent.astream_events(
                payload,
                config=config,
                version="v2",
            ):
                if not isinstance(event, Mapping):
                    continue
                event_name = event.get("event")
                if event_name == "on_chat_model_start":
                    graph_span.add_event(
                        "agent.model.start",
                        {"event.run_id": str(event.get("run_id", ""))},
                    )
                elif event_name == "on_chat_model_end":
                    extracted = _usage_from_event(event)
                    if extracted is not None:
                        _merge_usage(usage, extracted[0], extracted[1])
                    graph_span.add_event(
                        "agent.model.end",
                        {"event.run_id": str(event.get("run_id", ""))},
                    )
                elif event_name == "on_chat_model_stream":
                    if publish_tokens:
                        for kind, delta in _stream_chunks(event):
                            graph_span.add_event(
                                "agent.model.token",
                                {"token.length": len(delta), "token.kind": kind},
                            )
                            await self.events.publish(
                                run_id,
                                (
                                    "agent_thinking_delta"
                                    if kind == "reasoning"
                                    else "agent_message_delta"
                                ),
                                {
                                    "session_id": session_id,
                                    "delta": delta,
                                },
                            )
                elif event_name == "on_tool_start":
                    graph_span.add_event(
                        "agent.tool.start",
                        {
                            "tool.name": str(event.get("name", "unknown")),
                            "tool.call_id": str(event.get("run_id", "")),
                        },
                    )
                    await self.events.publish(
                        run_id,
                        "tool_started",
                        {
                            "session_id": session_id,
                            "tool_name": event.get("name", "unknown"),
                            "tool_call_id": event.get("run_id"),
                        },
                    )
                elif event_name == "on_tool_end":
                    graph_span.add_event(
                        "agent.tool.end",
                        {
                            "tool.name": str(event.get("name", "unknown")),
                            "tool.call_id": str(event.get("run_id", "")),
                        },
                    )
                    self.metrics.tool_call(
                        tool_name=str(event.get("name", "unknown")),
                        status="completed",
                    )
                    await self.events.publish(
                        run_id,
                        "tool_completed",
                        {
                            "session_id": session_id,
                            "tool_name": event.get("name", "unknown"),
                            "tool_call_id": event.get("run_id"),
                        },
                    )
                elif event_name == "on_tool_error":
                    graph_span.add_event(
                        "agent.tool.error",
                        {
                            "tool.name": str(event.get("name", "unknown")),
                            "tool.call_id": str(event.get("run_id", "")),
                        },
                    )
                    self.metrics.tool_call(
                        tool_name=str(event.get("name", "unknown")),
                        status="failed",
                    )
                    await self.events.publish(
                        run_id,
                        "tool_failed",
                        {
                            "session_id": session_id,
                            "tool_name": event.get("name", "unknown"),
                            "tool_call_id": event.get("run_id"),
                        },
                    )
                elif event_name == "on_chain_end":
                    data = event.get("data")
                    if isinstance(data, Mapping) and data.get("output") is not None:
                        final_output = data["output"]
        return final_output, usage

    async def _run(
        self,
        request: RunRequest,
        *,
        finalize_failure: bool = True,
        finalize_cancelled: bool = True,
        resume: dict[str, Any] | None = None,
    ) -> str:
        """为一次 Agent Run 创建根 Span，再进入实际执行编排。"""
        log_token = bind_log_context(
            run_id=request.run_id,
            session_id=request.session_id or request.run_id,
            tenant_id=request.user_context.tenant_id,
            user_id=request.user_context.user_id,
            agent_id=request.agent.id,
        )
        started_at = time.monotonic()
        try:
            with start_span(
                "agent.run",
                attributes={
                    "run.id": request.run_id,
                    "session.id": request.session_id or request.run_id,
                    "tenant.id": request.user_context.tenant_id,
                    "user.id": request.user_context.user_id,
                    "agent.id": request.agent.id,
                    "agent.version": request.agent.version,
                    "agent.stream": request.stream,
                },
            ) as span:
                outcome = await self._run_inner(
                    request,
                    finalize_failure=finalize_failure,
                    finalize_cancelled=finalize_cancelled,
                    resume=resume,
                )
                span.set_attribute("agent.status", outcome)
                self.metrics.run_finished(
                    status=outcome, duration_seconds=time.monotonic() - started_at
                )
                return outcome
        finally:
            reset_log_context(log_token)

    async def _run_inner(
        self,
        request: RunRequest,
        *,
        finalize_failure: bool = True,
        finalize_cancelled: bool = True,
        resume: dict[str, Any] | None = None,
    ) -> str:
        """执行一次 Run；``resume`` 存在时从 checkpoint 继续而不是重跑。

        返回值：``completed``（终态完成）或 ``interrupted``（等待人工确认）。"""
        run_id = request.run_id
        session_id = request.session_id or run_id
        # Thread Key 包含租户，避免不同租户意外碰撞。
        thread_id = f"{request.user_context.tenant_id}:{session_id}"
        lock = self._session_lock(thread_id)

        async with lock:
            runtime_handle = None
            try:
                if self.run_state:
                    await self.run_state.set_status(
                        run_id,
                        "RUNNING",
                        session_id=session_id,
                        agent_id=request.agent.id,
                        tenant_id=request.user_context.tenant_id,
                        user_id=request.user_context.user_id,
                        stream=request.stream,
                    )
                await self.events.publish(
                    run_id,
                    "run_started",
                    {
                        "agent_id": request.agent.id,
                        "session_id": session_id,
                        "stream": request.stream,
                    },
                )

                previous_messages = await self.history.list_messages(
                    session_id,
                    tenant_id=request.user_context.tenant_id,
                    user_id=request.user_context.user_id,
                )
                memory_items = await self.memories.list_memories(
                    request.user_context.tenant_id,
                    request.user_context.user_id,
                )
                attachment_text, image_blocks, raw_files = await self._load_attachments(
                    request
                )
                # 重试投递复用同一个 run_id；如果第一次尝试已经持久化用户消息，不要重复追加到 Redis 对话历史。
                # 恢复投递（resume）一定已经写过用户消息，直接跳过。
                if resume is None and not any(
                    item.get("run_id") == run_id and item.get("role") == "user"
                    for item in previous_messages
                ):
                    await self.history.append_message(
                        session_id=session_id,
                        run_id=run_id,
                        role="user",
                        content=request.message,
                        tenant_id=request.user_context.tenant_id,
                        user_id=request.user_context.user_id,
                    )

                agent, runtime_handle = await build_agent(
                    request.agent,
                    self.settings,
                    checkpointer=self.checkpointer,
                    store=self.store,
                    memories=memory_items,
                    run_id=run_id,
                    session_id=session_id,
                    tenant_id=request.user_context.tenant_id,
                )

                await self.events.publish(
                    run_id,
                    "agent_started",
                    {"session_id": session_id},
                )
                await self._write_attachments_to_sandbox(runtime_handle, raw_files, run_id)

                config = {
                    # DeepAgents 使用图递归推进模型和 Tool 轮次；递归上限应与快照提交的 max_steps 成比例。
                    "recursion_limit": max(10, request.agent.max_steps * 4),
                    "configurable": {"thread_id": thread_id},
                    "metadata": {
                        "run_id": run_id,
                        "session_id": session_id,
                        "agent_id": request.agent.id,
                        "agent_version": request.agent.version,
                        "user_id": request.user_context.user_id,
                        "tenant_id": request.user_context.tenant_id,
                    },
                }
                user_text = f"{request.message}{attachment_text}"
                user_content: Any = (
                    [{"type": "text", "text": user_text}, *image_blocks]
                    if image_blocks
                    else user_text
                )
                if resume is not None:
                    # 人工确认后从 checkpoint 继续；不需要重新构造消息列表。
                    payload: Any = Command(resume=resume)
                else:
                    checkpoint = await agent.aget_state(config)
                    if _has_checkpoint_messages(checkpoint):
                        messages = [{"role": "user", "content": user_content}]
                    else:
                        messages = [
                            {"role": item["role"], "content": item["content"]}
                            for item in previous_messages
                            if item.get("role") in {"user", "assistant"}
                            and item.get("content")
                        ]
                        messages.append({"role": "user", "content": user_content})
                    payload: dict[str, Any] = {"messages": messages}
                    if request.agent.rubric:
                        # RubricMiddleware 从调用状态读取评分标准。
                        payload["rubric"] = request.agent.rubric
                if request.stream:
                    result, usage = await asyncio.wait_for(
                        self._stream_agent(
                            agent,
                            payload,
                            config,
                            run_id,
                            session_id,
                        ),
                        timeout=_run_timeout_seconds(request, self.settings),
                    )
                    if result is None:
                        checkpoint = await agent.aget_state(config)
                        result = getattr(checkpoint, "values", checkpoint)
                else:
                    result, usage = await asyncio.wait_for(
                        self._stream_agent(
                            agent,
                            payload,
                            config,
                            run_id,
                            session_id,
                            publish_tokens=False,
                        ),
                        timeout=_run_timeout_seconds(request, self.settings),
                    )
                    if result is None:
                        checkpoint = await agent.aget_state(config)
                        result = getattr(checkpoint, "values", checkpoint)
                interrupts = await _interrupt_payload(agent, config)
                if interrupts:
                    if usage:
                        # 中断也会产生真实成本，指标照记；载荷留给恢复后的终态。
                        self.metrics.llm_tokens(usage=usage)
                    # 工具执行前中断：保存待决策请求、标记状态并结束本次投递。
                    # Worker 会 ACK 这条消息，等待调用方通过 /resume 恢复。
                    if self.run_state:
                        await self.run_state.mark_waiting_confirmation(
                            run_id, interrupt_count=len(interrupts)
                        )
                    await self.events.publish(
                        run_id,
                        "tool_permission_request",
                        {
                            "session_id": session_id,
                            "interrupts": interrupts,
                            "resume_endpoint": f"/v1/runs/{run_id}/resume",
                        },
                    )
                    return "interrupted"

                structured = _structured_response(result)
                if structured is not None:
                    # 声明了 response_format 时，结构化结果就是权威答案。
                    answer = json.dumps(structured, ensure_ascii=False, default=str)
                else:
                    answer = _assistant_answer(result)
                await self.history.append_message(
                    session_id=session_id,
                    run_id=run_id,
                    role="assistant",
                    content=answer,
                    tenant_id=request.user_context.tenant_id,
                    user_id=request.user_context.user_id,
                )

                completed_payload: dict[str, Any] = {
                    "session_id": session_id,
                    "answer": answer,
                }
                if structured is not None:
                    completed_payload["structured"] = structured
                completed_payload.update(_state_extras(result))
                if usage:
                    # token 用量随终态事件与状态投影一起返回，供计费/配额/成本分析使用。
                    completed_payload["usage"] = usage
                    self.metrics.llm_tokens(usage=usage)
                if self.run_state:
                    await self.run_state.set_status(
                        run_id,
                        "COMPLETED",
                        session_id=session_id,
                        agent_id=request.agent.id,
                        tenant_id=request.user_context.tenant_id,
                        user_id=request.user_context.user_id,
                        stream=request.stream,
                        result=completed_payload,
                    )
                await self.events.publish(run_id, "run_completed", completed_payload)
                return "completed"
            except asyncio.CancelledError:
                if not finalize_cancelled:
                    raise
                if self.run_state:
                    await self.run_state.set_status(
                        run_id,
                        "CANCELLED",
                        session_id=session_id,
                        agent_id=request.agent.id,
                        tenant_id=request.user_context.tenant_id,
                        user_id=request.user_context.user_id,
                        stream=request.stream,
                    )
                await self.events.publish(
                    run_id,
                    "run_cancelled",
                    {"session_id": session_id},
                )
                raise
            except Exception as exc:
                logger.exception("Agent run failed: %s", run_id)
                if not finalize_failure:
                    raise
                if self.run_state:
                    await self.run_state.set_status(
                        run_id,
                        "FAILED",
                        session_id=session_id,
                        agent_id=request.agent.id,
                        tenant_id=request.user_context.tenant_id,
                        user_id=request.user_context.user_id,
                        stream=request.stream,
                        error={
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                await self.events.publish(
                    run_id,
                    "run_failed",
                    {
                        "session_id": session_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                return "failed"
            finally:
                if runtime_handle is not None:
                    close = getattr(runtime_handle, "aclose", None)
                    if close is not None:
                        try:
                            result = close()
                            if hasattr(result, "__await__"):
                                await result
                        except Exception:
                            # 清理失败不能掩盖 Agent 的终态结果。
                            logger.exception(
                                "Failed to close Agent runtime resources: %s", run_id
                            )
