"""入口限流与队列背压的单元测试。

覆盖：限流器计数与窗口、超限返回 429、队列水位触发 503、限流依赖故障时 fail-closed。
"""

import asyncio

import pytest
from fastapi import HTTPException

from data_agent_runtime import api
from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.principal import Principal
from data_agent_runtime.runtime.ratelimit import RunRateLimiter
from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    UserContext,
)


class _Redis:
    """只实现限流所需命令的最小 Redis 替身。"""

    def __init__(self) -> None:
        """初始化计数与过期时间。"""
        self.values: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        """自增计数。"""
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> bool:
        """记录窗口长度。"""
        self.expires[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        """返回窗口剩余时间。"""
        return self.expires.get(key, 0)


def _request(run_id: str = "run-limit") -> RunRequest:
    """构造一次最小合法提交请求。"""
    return RunRequest(
        run_id=run_id,
        message="查询车辆数量",
        agent=AgentSnapshot(
            id="agent-limit",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="gpt-4o-mini"),
        ),
        user_context=UserContext(user_id="user-a", tenant_id="tenant-a"),
    )


def _principal() -> Principal:
    """构造具备提交权限的调用方身份。"""
    return Principal(
        principal_id="principal-a",
        access_key="caller-a",
        tenant_id="tenant-a",
        subject_id="user-a",
        scopes=frozenset({"runs:write"}),
    )


def test_rate_limiter_allows_up_to_limit_then_rejects():
    """验证窗口内放行到上限，超限后拒绝并给出重试秒数。"""

    async def run() -> None:
        """连续请求 limit+1 次并检查结果。"""
        limiter = RunRateLimiter(_Redis(), limit_per_minute=2)
        assert await limiter.check("principal-a") == (True, 0)
        assert await limiter.check("principal-a") == (True, 0)
        allowed, retry_after = await limiter.check("principal-a")
        assert allowed is False
        assert retry_after >= 1

    asyncio.run(run())


def test_rate_limiter_disabled_by_zero_limit():
    """验证上限为 0 时不做任何限制。"""

    async def run() -> None:
        """确认始终放行。"""
        limiter = RunRateLimiter(_Redis(), limit_per_minute=0)
        for _ in range(5):
            assert await limiter.check("principal-a") == (True, 0)

    asyncio.run(run())


class _DenyLimiter:
    """固定拒绝的限流器替身。"""

    async def check(self, principal_id: str) -> tuple[bool, int]:
        """始终拒绝并建议 30 秒后重试。"""
        return False, 30


class _BrokenLimiter:
    """模拟 Redis 故障的限流器替身。"""

    async def check(self, principal_id: str) -> tuple[bool, int]:
        """抛出异常以验证 fail-closed。"""
        raise RuntimeError("redis down")


class _Queue:
    """提交队列替身，可指定队列深度。"""

    def __init__(self, depth: int = 0) -> None:
        """保存深度返回值。"""
        self._depth = depth
        self.enqueued: list[RunRequest] = []

    async def enqueue(self, request: RunRequest) -> tuple[bool, str]:
        """记录入队。"""
        self.enqueued.append(request)
        return True, "1-0"

    async def depth(self) -> int:
        """返回预设深度。"""
        return self._depth


def test_submit_returns_429_with_retry_after_when_rate_limited(monkeypatch):
    """验证限流命中时返回 429 并带 Retry-After。"""

    async def run() -> None:
        """调用提交接口并检查错误码与响应头。"""
        monkeypatch.setattr(api.app.state, "rate_limiter", _DenyLimiter(), raising=False)
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)
        with pytest.raises(HTTPException) as excinfo:
            await api.submit_run(_request(), _principal())
        assert excinfo.value.status_code == 429
        assert excinfo.value.headers["Retry-After"] == "30"

    asyncio.run(run())


def test_submit_returns_503_when_backpressure_triggers(monkeypatch):
    """验证队列水位超限时返回 503 并带 Retry-After。"""

    async def run() -> None:
        """用极大深度触发背压。"""
        monkeypatch.setattr(api.app.state, "rate_limiter", None, raising=False)
        monkeypatch.setattr(
            api.app.state, "queue", _Queue(depth=10**9), raising=False
        )
        with pytest.raises(HTTPException) as excinfo:
            await api.submit_run(_request(), _principal())
        assert excinfo.value.status_code == 503
        assert "saturated" in str(excinfo.value.detail)
        assert excinfo.value.headers["Retry-After"] == "5"

    asyncio.run(run())


def test_submit_fails_closed_when_limiter_unavailable(monkeypatch):
    """验证限流依赖故障时拒绝提交，而不是放行。"""

    async def run() -> None:
        """调用提交接口并检查 503。"""
        monkeypatch.setattr(
            api.app.state, "rate_limiter", _BrokenLimiter(), raising=False
        )
        monkeypatch.setattr(api.app.state, "queue", _Queue(), raising=False)
        with pytest.raises(HTTPException) as excinfo:
            await api.submit_run(_request(), _principal())
        assert excinfo.value.status_code == 503
        assert "rate limiter" in str(excinfo.value.detail)

    asyncio.run(run())


def test_submit_succeeds_within_limits(monkeypatch):
    """验证未超限时正常入队。"""

    async def run() -> None:
        """在限流与背压都满足时提交。"""
        queue = _Queue(depth=10)
        # 使用干净的部署配置，避免本地 .env 的模型白名单影响准入结果。
        monkeypatch.setattr(api, "settings", Settings(_env_file=None))
        monkeypatch.setattr(api.app.state, "rate_limiter", None, raising=False)
        monkeypatch.setattr(api.app.state, "queue", queue, raising=False)
        result = await api.submit_run(_request(), _principal())
        assert result.status == "ACCEPTED"
        assert len(queue.enqueued) == 1

    asyncio.run(run())
