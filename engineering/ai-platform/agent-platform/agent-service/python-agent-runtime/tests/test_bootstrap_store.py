"""Runtime 资源生命周期的单元测试。

本模块验证 `runtime_resources` 按 `AGENT_STORE_BACKEND` 创建或跳过跨会话 Store，
并把 Store 纳入统一释放流程。测试不连接 Redis 或 PostgreSQL。
"""

import asyncio

from langgraph.store.memory import InMemoryStore

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.bootstrap import runtime_resources


def test_runtime_resources_creates_memory_store():
    """验证 memory 模式创建进程内 Store，并由资源上下文释放。"""

    async def run() -> None:
        """进入资源上下文并检查 Store 类型。"""
        settings = Settings(
            _env_file=None,
            agent_store_backend="memory",
            redis_url="redis://127.0.0.1:6379/0",
        )
        async with runtime_resources(settings) as resources:
            assert isinstance(resources.store, InMemoryStore)

    asyncio.run(run())


def test_runtime_resources_skips_store_when_disabled():
    """验证 none 模式不创建 Store，避免无需要的部署多一份状态载体。"""

    async def run() -> None:
        """进入资源上下文并确认 Store 为 None。"""
        settings = Settings(
            _env_file=None,
            agent_store_backend="none",
            redis_url="redis://127.0.0.1:6379/0",
        )
        async with runtime_resources(settings) as resources:
            assert resources.store is None

    asyncio.run(run())


def test_postgres_store_requires_dsn():
    """验证 postgres 模式缺少 DSN 时快速失败，而不是启动后再报错。"""

    async def run() -> None:
        """期望进入资源上下文时抛出配置错误。"""
        settings = Settings(
            _env_file=None,
            agent_store_backend="postgres",
            postgres_dsn=None,
            redis_url="redis://127.0.0.1:6379/0",
        )
        try:
            async with runtime_resources(settings):
                pass
        except RuntimeError as exc:
            assert "POSTGRES_DSN is required" in str(exc)
        else:  # pragma: no cover - 配置错误必须抛出
            raise AssertionError("expected RuntimeError for missing POSTGRES_DSN")

    asyncio.run(run())
