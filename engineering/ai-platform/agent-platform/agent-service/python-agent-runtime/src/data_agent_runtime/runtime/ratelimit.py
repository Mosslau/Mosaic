"""入口限流（每调用方固定窗口）实现。

限流放在 API 入口而不是 Worker：它保护的是"提交"这一动作，避免瞬时洪峰把任务流打满，
也让被限流的调用方立即得到 429 反馈，而不是排进队列后长时间等待。
"""

from __future__ import annotations

from redis.asyncio import Redis

_WINDOW_SECONDS = 60


class RunRateLimiter:
    """基于 Redis 计数的每调用方每分钟限流器。

    固定窗口从该调用方的第一次请求开始计时，窗口内计数超过上限即拒绝；返回剩余等待
    时间，调用方据此设置 ``Retry-After``。Redis 故障时向上抛出，由 API 转成 503：
    宁可拒绝也不在不明状态下放行。
    """

    def __init__(self, redis: Redis, limit_per_minute: int) -> None:
        """保存 Redis 客户端与上限；上限 <= 0 视为关闭（调用方不应创建实例）。"""
        self.redis = redis
        self.limit = max(limit_per_minute, 0)

    @staticmethod
    def _key(principal_id: str) -> str:
        """生成按调用方隔离的计数 Key。"""
        return f"agent:rate:{principal_id}"

    async def check(self, principal_id: str) -> tuple[bool, int]:
        """占用一次配额，返回 ``(是否放行, 建议重试秒数)``。"""
        if self.limit <= 0:
            return True, 0
        key = self._key(principal_id)
        current = int(await self.redis.incr(key))
        if current == 1:
            await self.redis.expire(key, _WINDOW_SECONDS)
        if current <= self.limit:
            return True, 0
        ttl = int(await self.redis.ttl(key))
        return False, max(ttl, 1)
