"""运行保障层的单元测试：Redis 客户端韧性与优雅停机。

本模块验证三件事：共享 Redis 客户端带上超时/重试/连接池上限；Worker 收到停止请求后
先排空在跑的 Run、超时才取消；API 进程把停机预算传给 Uvicorn。
"""

import asyncio

import pytest

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.bootstrap import runtime_resources
from data_agent_runtime.runtime.worker import TaskWorker


def test_redis_client_applies_resilience_settings():
    """验证共享 Redis 客户端设置了超时、重试、健康检查与连接池上限。"""

    async def run() -> None:
        """进入资源上下文并检查连接池参数。"""
        settings = Settings(
            _env_file=None,
            redis_url="redis://127.0.0.1:6379/0",
            agent_store_backend="none",
            redis_socket_timeout_seconds=3.5,
            redis_socket_connect_timeout_seconds=2.5,
            redis_health_check_interval_seconds=17,
            redis_max_connections=23,
            redis_retry_attempts=4,
        )
        async with runtime_resources(settings) as resources:
            kwargs = resources.redis.connection_pool.connection_kwargs
            assert kwargs["socket_timeout"] == 3.5
            assert kwargs["socket_connect_timeout"] == 2.5
            assert kwargs["health_check_interval"] == 17
            assert kwargs["retry"] is not None
            # max_connections 属于连接池属性，不在单连接的 connection_kwargs 里。
            assert resources.redis.connection_pool.max_connections == 23

    asyncio.run(run())


def _worker() -> TaskWorker:
    """构造一个只用于测试 serve() 的 Worker（依赖不会被访问）。"""
    settings = Settings(_env_file=None)
    return TaskWorker(
        settings,
        queue=object(),
        executor=object(),
        run_state=object(),
        events=object(),
        consumer_name="test-worker",
    )


def test_serve_exits_promptly_when_idle():
    """验证空闲时收到停止请求可以立即退出，不等满 drain 超时。"""

    async def run() -> None:
        """启动 serve()、发出停止请求并检查退出耗时。"""
        worker = _worker()

        async def fake_run_forever() -> None:
            """模拟空闲消费循环：只检查停止标志。"""
            while not worker._stop.is_set():
                await asyncio.sleep(0.01)

        worker.run_forever = fake_run_forever  # type: ignore[method-assign]
        server = asyncio.create_task(worker.serve(shutdown_timeout=5.0))
        await asyncio.sleep(0.05)
        worker.stop()
        await asyncio.wait_for(server, timeout=2.0)
        assert server.done()

    asyncio.run(run())


def test_serve_drains_inflight_run_before_exit():
    """验证停止请求不会打断正在执行的 Run，而是等它完成。"""

    async def run() -> None:
        """在 Run 执行期间发出停止请求，确认它被排空而不是被取消。"""
        worker = _worker()
        finished = asyncio.Event()
        cancelled = {"value": False}

        async def fake_run_forever() -> None:
            """模拟一次正在执行的 Run。"""
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:  # pragma: no cover - 正常路径不应触发
                cancelled["value"] = True
                raise
            finished.set()

        worker.run_forever = fake_run_forever  # type: ignore[method-assign]
        server = asyncio.create_task(worker.serve(shutdown_timeout=5.0))
        await asyncio.sleep(0.03)
        worker.stop()
        await asyncio.wait_for(server, timeout=3.0)
        assert finished.is_set()
        assert cancelled["value"] is False

    asyncio.run(run())


def test_serve_cancels_after_drain_timeout():
    """验证 drain 超时后取消在跑的 Run，把消息留给重投递。"""

    async def run() -> None:
        """用永远不结束的 Run 触发 drain 超时路径。"""
        worker = _worker()
        cancelled = {"value": False}

        async def fake_run_forever() -> None:
            """模拟卡住的 Run。"""
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise

        worker.run_forever = fake_run_forever  # type: ignore[method-assign]
        server = asyncio.create_task(worker.serve(shutdown_timeout=0.1))
        await asyncio.sleep(0.03)
        worker.stop()
        await asyncio.wait_for(server, timeout=3.0)
        assert cancelled["value"] is True

    asyncio.run(run())


def test_api_process_passes_shutdown_budget_to_uvicorn(monkeypatch):
    """验证 API 进程把停机预算传给 Uvicorn，而不是用默认值。"""
    from data_agent_runtime import main as main_module

    captured: dict[str, object] = {}

    def fake_run(app, **kwargs):
        """记录 Uvicorn 启动参数。"""
        captured.update(kwargs)

    monkeypatch.setattr(main_module.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(_env_file=None, runtime_mode="api", shutdown_timeout_seconds=42),
    )
    monkeypatch.setattr(main_module, "configure_observability", lambda *a, **k: None)

    main_module.main()

    assert captured["timeout_graceful_shutdown"] == 42


def test_worker_rejects_wrong_runtime_mode(monkeypatch):
    """验证 Worker 入口在错误模式下快速失败，避免误起进程。"""
    from data_agent_runtime import worker_main

    monkeypatch.setattr(
        worker_main, "get_settings", lambda: Settings(_env_file=None, runtime_mode="api")
    )
    with pytest.raises(RuntimeError, match="RUNTIME_MODE"):
        asyncio.run(worker_main._run())
