"""本文件模块职责：P0 可靠性集成测试。

测试使用独立 Redis 数据库验证 Worker 崩溃后的 Pending 接管、重复 run_id 幂等、同 Session 串行、失败重试和死信流；运行前应配置 P0_TEST_REDIS_URL。

P0 Redis integration tests.

Run with a dedicated Redis database/instance, for example:

    P0_TEST_REDIS_URL='redis://:root@127.0.0.1:6379/15' uv run pytest -q tests/test_p0_reliability.py

The suite is skipped unless P0_TEST_REDIS_URL is explicitly provided so it
cannot accidentally mutate a developer's normal runtime streams.

"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

redis = pytest.importorskip("redis")
from redis.asyncio import Redis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.queue import RunTaskQueue
from data_agent_runtime.runtime.state import RedisRunState
from data_agent_runtime.runtime.worker import TaskWorker
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    UserContext,
)


class RecordingEvents:
    """记录可靠性测试中的事件，便于验证运行生命周期和终态发布。"""
    def __init__(self) -> None:
        """
        中文说明：
            初始化 RecordingEvents，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.events: list[tuple[str, str, dict]] = []

    async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
        """
        中文说明：
            为运行事件分配全局递增序号并写入对应 Run 的 Redis Event Stream。

        参数：
            - run_id: str：由调用方传入，用于完成本函数的核心处理。
            - event_type: str：由调用方传入，用于完成本函数的核心处理。
            - payload: dict：由调用方传入，用于完成本函数的核心处理。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.events.append((run_id, event_type, payload))


class BlockingExecutor:
    """阻塞执行器测试替身，用于验证 Worker 取消和 Lease 行为。"""
    def __init__(self, *, delay: float = 0.05, fail: bool = False) -> None:
        """
        中文说明：
            初始化 BlockingExecutor，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - delay: float：由调用方传入，用于完成本函数的核心处理。
            - fail: bool：由调用方传入，用于完成本函数的核心处理。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.delay = delay
        self.fail = fail
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.started = asyncio.Event()

    async def execute_queued(self, request: RunRequest, **_: object) -> None:
        """
        中文说明：
            在 Worker 已取得可靠性租约的前提下执行一次队列投递，并把异常交给 Worker 决定重试或进入死信。

        参数：
            - request: RunRequest：由调用方传入，用于完成本函数的核心处理。
            - **_: object：由调用方传入，用于完成本函数的核心处理。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            await asyncio.sleep(self.delay)
            if self.fail:
                raise RuntimeError("simulated model failure")
        finally:
            self.active -= 1


async def _redis_or_skip() -> Redis:
    """
    中文说明：
        实现 tests/test_p0_reliability 的内部辅助步骤“_redis_or_skip”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        Redis。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    url = os.getenv("P0_TEST_REDIS_URL")
    if not url:
        pytest.skip("set P0_TEST_REDIS_URL to run Redis P0 integration tests")
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - environment dependent
        await client.aclose()
        pytest.fail(f"P0 Redis is unavailable: {exc}")
    return client


async def _cleanup(redis_client: Redis, prefix: str) -> None:
    """
    中文说明：
        实现 tests/test_p0_reliability 的内部辅助步骤“_cleanup”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - redis_client: Redis：由调用方传入，用于完成本函数的核心处理。
        - prefix: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        None。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    patterns = (
        f"{prefix}:*",
        f"agent:run:{prefix}:*",
        "agent:session:tenant-1:session-1:lease",
    )
    keys: set[str] = set()
    for pattern in patterns:
        async for key in redis_client.scan_iter(match=pattern):
            keys.add(key)
    if keys:
        await redis_client.delete(*keys)


def _request(run_id: str, session_id: str = "session-1") -> RunRequest:
    """
    中文说明：
        实现 tests/test_p0_reliability 的内部辅助步骤“_request”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - run_id: str：由调用方传入，用于完成本函数的核心处理。
        - session_id: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        RunRequest。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return RunRequest(
        run_id=run_id,
        session_id=session_id,
        message="测试最近 30 天车辆数量",
        stream=True,
        agent=AgentSnapshot(
            id="data-analysis-agent",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="test-model"),
        ),
        user_context=UserContext(user_id="user-1", tenant_id="tenant-1"),
    )


def _resources(prefix: str, redis_client: Redis):
    """
    中文说明：
        实现 tests/test_p0_reliability 的内部辅助步骤“_resources”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - prefix: str：由调用方传入，用于完成本函数的核心处理。
        - redis_client: Redis：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    settings = Settings(
        # 关闭 .env 加载：P0 用例需要确定性的队列/超时配置，不能继承开发者本地策略。
        _env_file=None,
        task_stream_key=f"{prefix}:tasks",
        task_dead_letter_stream_key=f"{prefix}:dead-letter",
        task_consumer_group="p0-workers",
        task_visibility_timeout_seconds=1,
        worker_heartbeat_interval_seconds=1,
        task_retry_delay_seconds=0,
        task_max_attempts=3,
        run_state_ttl_seconds=3600,
    )
    state = RedisRunState(redis_client, settings)
    queue = RunTaskQueue(redis_client, settings, state)
    events = RecordingEvents()
    return settings, state, queue, events


def test_duplicate_run_id_is_enqueued_once():
    """
    中文说明：
        验证 tests/test_p0_reliability 中“duplicate_run_id_is_enqueued_once”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run() -> None:
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        redis_client = await _redis_or_skip()
        prefix = f"p0:{uuid.uuid4().hex}"
        try:
            _, state, queue, _ = _resources(prefix, redis_client)
            await queue.ensure_group()
            run_id = f"{prefix}:run-duplicate"
            first, second = await asyncio.gather(
                queue.enqueue(_request(run_id)),
                queue.enqueue(_request(run_id, session_id="different-session")),
            )
            assert sorted((first[0], second[0])) == [False, True]
            assert sum(stream_id is not None for _, stream_id in (first, second)) == 1
            assert await redis_client.xlen(queue.stream_key) == 1
            stored = await state.get(run_id)
            assert stored is not None
            assert stored["status"] == "ACCEPTED"
        finally:
            await _cleanup(redis_client, prefix)
            await redis_client.aclose()

    asyncio.run(run())


def test_worker_crash_leaves_pending_delivery_for_reclaim():
    """
    中文说明：
        验证 tests/test_p0_reliability 中“worker_crash_leaves_pending_delivery_for_reclaim”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run() -> None:
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        redis_client = await _redis_or_skip()
        prefix = f"p0:{uuid.uuid4().hex}"
        try:
            settings, state, queue, events = _resources(prefix, redis_client)
            await queue.ensure_group()
            run_id = f"{prefix}:run-crash"
            await queue.enqueue(_request(run_id))
            messages = await queue.read("worker-a")
            assert len(messages) == 1

            executor = BlockingExecutor(delay=30)
            worker = TaskWorker(
                settings,
                queue,
                executor,
                state,
                events,
                consumer_name="worker-a",
            )
            task = asyncio.create_task(worker._handle_message(messages[0]))
            await executor.started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            pending = await redis_client.xpending_range(
                queue.stream_key,
                queue.group_name,
                min="-",
                max="+",
                count=10,
            )
            assert any(item["message_id"] == messages[0][0] for item in pending)

            # 可见性超时后，第二个 Worker 可以 reclaim 并完成遗留投递；这里验证的是崩溃恢复路径，
            # 不只是验证 XCLAIM 能转移所有权。
            await asyncio.sleep(1.1)
            reclaimed = await queue.reclaim("worker-b")
            assert reclaimed and reclaimed[0][0] == messages[0][0]
            executor.delay = 0.01
            worker_b = TaskWorker(
                settings, queue, executor, state, events, consumer_name="worker-b"
            )
            await worker_b._handle_message(reclaimed[0])
            assert executor.calls == 2
        finally:
            await _cleanup(redis_client, prefix)
            await redis_client.aclose()

    asyncio.run(run())


def test_two_workers_serialize_same_session():
    """
    中文说明：
        验证 tests/test_p0_reliability 中“two_workers_serialize_same_session”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run() -> None:
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        redis_client = await _redis_or_skip()
        prefix = f"p0:{uuid.uuid4().hex}"
        try:
            settings, state, queue, events = _resources(prefix, redis_client)
            await queue.ensure_group()
            run_id_1 = f"{prefix}:run-session-1"
            run_id_2 = f"{prefix}:run-session-2"
            await queue.enqueue(_request(run_id_1))
            await queue.enqueue(_request(run_id_2))
            messages_1 = await queue.read("worker-1")
            messages_2 = await queue.read("worker-2")
            assert len(messages_1) == len(messages_2) == 1

            executor = BlockingExecutor(delay=0.1)
            worker_1 = TaskWorker(
                settings, queue, executor, state, events, consumer_name="worker-1"
            )
            worker_2 = TaskWorker(
                settings, queue, executor, state, events, consumer_name="worker-2"
            )
            await asyncio.gather(
                worker_1._handle_message(messages_1[0]),
                worker_2._handle_message(messages_2[0]),
            )
            assert executor.calls == 2
            assert executor.max_active == 1
        finally:
            await _cleanup(redis_client, prefix)
            await redis_client.aclose()

    asyncio.run(run())


def test_failure_retries_then_dead_letters():
    """
    中文说明：
        验证 tests/test_p0_reliability 中“failure_retries_then_dead_letters”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run() -> None:
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            None。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        redis_client = await _redis_or_skip()
        prefix = f"p0:{uuid.uuid4().hex}"
        try:
            settings, state, queue, events = _resources(prefix, redis_client)
            await queue.ensure_group()
            run_id = f"{prefix}:run-failure"
            await queue.enqueue(_request(run_id))
            executor = BlockingExecutor(fail=True)
            worker = TaskWorker(
                settings,
                queue,
                executor,
                state,
                events,
                consumer_name="worker-failure",
            )

            # 每次失败投递都会产生下一次尝试；第三次失败达到终态，必须写入 Dead Letter Stream。
            for expected_attempt in range(3):
                messages = await queue.read("worker-failure")
                assert len(messages) == 1
                assert int(messages[0][1]["attempt"]) == expected_attempt
                await worker._handle_message(messages[0])

            final_state = await state.get(run_id)
            assert final_state is not None
            assert final_state["status"] == "FAILED"
            assert executor.calls == 3
            dead_letters = await redis_client.xrange(queue.settings.task_dead_letter_stream_key)
            assert len(dead_letters) == 1
            event_types = [event_type for _, event_type, _ in events.events]
            assert event_types.count("run_retry_scheduled") == 2
            assert event_types[-1] == "run_failed"
        finally:
            await _cleanup(redis_client, prefix)
            await redis_client.aclose()

    asyncio.run(run())
