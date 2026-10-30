"""本文件模块职责：Agent Run 运行事件发布模块。

本模块将状态变化、工具生命周期、Token 增量、最终答案、失败和取消等事件写入 Redis Stream，供受保护调用方、审计系统和本地调试页面消费。
"""

import json
from datetime import UTC, datetime

from redis.asyncio import Redis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.observability import start_span


class EventPublisher:
    """把 Agent 生命周期和输出事件写入 Redis Event Stream。

    发布器为每个 Run 维护事件序列和最大长度策略；API 通过它向 SSE 调用方提供可恢复的事件流。
    """

    def __init__(self, redis: Redis, settings: Settings):
        """初始化 EventPublisher，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.redis = redis
        self.settings = settings

    async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
        # INCR 由所有 API/Worker 进程共享，因此 Worker 重启或流量负载均衡时事件序号不会重置。
        """为运行事件分配全局递增序号并写入对应 Run 的 Redis Event Stream。"""
        with start_span(
            "redis.run_event.publish",
            attributes={
                "messaging.system": "redis",
                "messaging.destination": f"agent:run:{run_id}:events",
                "run.id": run_id,
                "run.event.type": event_type,
            },
        ) as span:
            sequence_key = f"agent:run:{run_id}:sequence"
            sequence = await self.redis.incr(sequence_key)
            await self.redis.expire(sequence_key, self.settings.run_state_ttl_seconds)
            event = {
                "run_id": run_id,
                "event_type": event_type,
                "payload": payload,
                "sequence": sequence,
                "created_at": datetime.now(UTC).isoformat(),
            }
            message_id = await self.redis.xadd(
                f"agent:run:{run_id}:events",
                {"event": json.dumps(event, ensure_ascii=False)},
                maxlen=self.settings.event_stream_maxlen,
                approximate=True,
            )
            span.set_attribute("messaging.message.id", message_id)
            span.set_attribute("run.event.sequence", sequence)
