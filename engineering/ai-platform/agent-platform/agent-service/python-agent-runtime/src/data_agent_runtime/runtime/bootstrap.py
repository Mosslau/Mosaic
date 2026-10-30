"""本文件模块职责：API 进程和 Worker 进程共享的运行资源初始化模块。

本模块负责创建 Redis、事件发布器、任务队列、Run 状态、会话记忆和 PostgreSQL Checkpointer 等依赖，并在应用生命周期结束时统一释放连接。

Shared runtime dependency construction for API and worker processes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.events import EventPublisher
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.runtime.state import RedisRunState


@dataclass
class RuntimeResources:
    """API 或 Worker 生命周期内共享的 Redis、事件、状态和 Checkpointer 资源。

    这些资源由 ``runtime_resources`` 统一创建和释放，调用方不得自行绕过生命周期管理。
    """

    redis: Redis
    events: EventPublisher
    history: RedisConversationHistory
    memories: RedisLongTermMemory
    run_state: RedisRunState
    checkpointer: object
    store: object | None


@asynccontextmanager
async def runtime_resources(settings: Settings) -> AsyncIterator[RuntimeResources]:
    """创建 API 和 Worker 共享的 Redis、事件发布器、会话历史、长期记忆、Run 状态及 Checkpointer 资源，并在退出时统一释放。"""
    async with AsyncExitStack() as stack:
        # 统一在这里设置超时/重试/连接池，避免每个调用点各自为政；
        # Redis 不可用时认证与队列都会 fail-closed，超时保证失败是"快速失败"而非永久挂起。
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout_seconds,
            socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
            retry=Retry(
                ExponentialWithJitterBackoff(
                    base=settings.redis_retry_backoff_base_seconds,
                    cap=settings.redis_retry_backoff_cap_seconds,
                ),
                retries=settings.redis_retry_attempts,
            ),
            health_check_interval=settings.redis_health_check_interval_seconds,
            max_connections=settings.redis_max_connections,
        )
        events = EventPublisher(redis, settings)
        history = RedisConversationHistory(redis, settings)
        memories = RedisLongTermMemory(redis, settings)
        run_state = RedisRunState(redis, settings)

        if settings.checkpoint_backend == "postgres":
            if not settings.postgres_dsn:
                raise RuntimeError(
                    "POSTGRES_DSN is required when CHECKPOINT_BACKEND=postgres"
                )
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL Checkpointer is not installed; run `uv sync`"
                ) from exc
            checkpointer = await stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(settings.postgres_dsn)
            )
            await checkpointer.setup()
        else:
            checkpointer = InMemorySaver()

        store: object | None = None
        if settings.agent_store_backend == "memory":
            from langgraph.store.memory import InMemoryStore

            store = InMemoryStore()
        elif settings.agent_store_backend == "postgres":
            if not settings.postgres_dsn:
                raise RuntimeError(
                    "POSTGRES_DSN is required when AGENT_STORE_BACKEND=postgres"
                )
            try:
                from langgraph.store.postgres import AsyncPostgresStore
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL Store is not installed; run `uv sync`"
                ) from exc
            store = await stack.enter_async_context(
                AsyncPostgresStore.from_conn_string(settings.postgres_dsn)
            )
            await store.setup()

        try:
            yield RuntimeResources(
                redis=redis,
                events=events,
                history=history,
                memories=memories,
                run_state=run_state,
                checkpointer=checkpointer,
                store=store,
            )
        finally:
            await redis.aclose()
