"""本文件模块职责：Redis Run 生命周期状态和分布式租约模块。

本模块保存 Run 的可查询状态、取消标记、Worker Lease、Session Lease 和心跳信息，为多 Worker 互斥执行、同会话串行和故障接管提供一致性保护。

Redis-backed run lifecycle state.

The Redis Stream remains the append-only event source for a run.  This module
keeps a compact, queryable projection so an external Caller can render a Run status
without replaying the entire stream.

"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from data_agent_runtime.config import Settings


def _now() -> str:
    """执行“_now”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return datetime.now(UTC).isoformat()


def _state_key(run_id: str) -> str:
    """执行“_state_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return f"agent:run:{run_id}:state"


def _claim_key(run_id: str) -> str:
    """执行“_claim_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return f"agent:run:{run_id}:claim"


def _request_payload_key(run_id: str) -> str:
    """返回 Run 原始请求载荷的 Key，供人工确认后恢复执行时重建 Agent。"""
    return f"agent:run:{run_id}:request"


def _approval_payload_key(run_id: str) -> str:
    """返回等待审批 Run 的内部请求载荷 Key。"""
    return f"agent:run:{run_id}:approval-payload"


def _lease_key(run_id: str) -> str:
    """执行“_lease_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return f"agent:run:{run_id}:lease"


def _concurrency_key(principal_id: str) -> str:
    """返回调用方并发配额的稳定 Redis Key，不把外部身份原文放入 Key。"""
    digest = hashlib.sha256(principal_id.encode("utf-8")).hexdigest()
    return f"agent:principal:{digest}:concurrency"


def _session_lease_key(tenant_id: str, session_id: str) -> str:
    """执行“_session_lease_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    return f"agent:session:{tenant_id}:{session_id}:lease"


class RedisRunState:
    """保存单个 Agent Run 最新状态的 Redis Hash 投影。

    状态对象用于查询、Lease、幂等和终态判断，不替代 Event Stream 的完整事件历史。
    """

    def __init__(self, redis: Redis, settings: Settings):
        """初始化 RedisRunState，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.redis = redis
        self.settings = settings

    @staticmethod
    def now() -> str:
        """处理“now”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return _now()

    @staticmethod
    def state_key(run_id: str) -> str:
        """处理“state_key”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return _state_key(run_id)

    @staticmethod
    def claim_key(run_id: str) -> str:
        """处理“claim_key”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return _claim_key(run_id)

    @staticmethod
    def lease_key(run_id: str) -> str:
        """处理“lease_key”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return _lease_key(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        """处理“get”业务步骤，完成输入校验、依赖调用和结果返回。"""
        values = await self.redis.hgetall(_state_key(run_id))
        if not values:
            return None
        result: dict[str, Any] = dict(values)
        for field in ("sequence",):
            if field in result:
                try:
                    result[field] = int(result[field])
                except (TypeError, ValueError):
                    pass
        if "result" in result:
            try:
                result["result"] = json.loads(result["result"])
            except (TypeError, json.JSONDecodeError):
                pass
        if "error" in result:
            try:
                result["error"] = json.loads(result["error"])
            except (TypeError, json.JSONDecodeError):
                pass
        return result

    async def create_pending_approval(self, request: Any) -> bool:
        """原子创建等待审批的 Run，并保存去除 Secret 后的请求载荷。

        审批中的请求不进入任务 Stream，因此 Worker 不可能在审批前执行。请求
        载荷只由后续审批脚本读取，状态查询不会把 Snapshot 原文暴露给调用方。
        """
        session_id = request.session_id or request.run_id
        context = request.user_context
        if context is None:
            raise ValueError("bound user_context is required for approval")
        script = """
        local claimed = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
        if not claimed then return 0 end
        redis.call('HSET', KEYS[2],
          'run_id', ARGV[1], 'status', 'PENDING_APPROVAL',
          'session_id', ARGV[3], 'agent_id', ARGV[4],
          'tenant_id', ARGV[5], 'user_id', ARGV[6],
          'principal_id', ARGV[7], 'stream', ARGV[8],
          'attempt', '0', 'updated_at', ARGV[9])
        redis.call('EXPIRE', KEYS[2], ARGV[2])
        redis.call('SET', KEYS[3], ARGV[10], 'EX', ARGV[2])
        return 1
        """
        result = await self.redis.eval(
            script,
            3,
            _claim_key(request.run_id),
            _state_key(request.run_id),
            _approval_payload_key(request.run_id),
            request.run_id,
            str(self.settings.run_state_ttl_seconds),
            session_id,
            request.agent.id,
            context.tenant_id,
            context.user_id,
            context.principal_id or f"{context.tenant_id}:{context.user_id}",
            str(request.stream).lower(),
            _now(),
            request.model_dump_json(),
        )
        return bool(int(result))

    @staticmethod
    def request_payload_key(run_id: str) -> str:
        """返回恢复执行时读取原始 RunRequest 的 Redis Key。"""
        return _request_payload_key(run_id)

    @staticmethod
    def approval_payload_key(run_id: str) -> str:
        """返回审批队列脚本使用的请求载荷 Key。"""
        return _approval_payload_key(run_id)

    async def request_cancel(self, run_id: str) -> bool:
        """持久化取消请求，使执行该 Run 的任意 Worker 都能观察到取消信号。

        该操作只写入取消标记，不直接终止远程模型或工具进程；Worker 在安全边界
        检查到标记后负责停止执行、更新终态并发布取消事件。
        """
        script = """
        local status = redis.call('HGET', KEYS[1], 'status')
        if not status or status == 'COMPLETED' or status == 'FAILED' or status == 'CANCELLED' then
          return 0
        end
        redis.call('HSET', KEYS[1], 'cancel_requested', 'true', 'updated_at', ARGV[1])
        redis.call('EXPIRE', KEYS[1], ARGV[2])
        return 1
        """
        result = await self.redis.eval(
            script,
            1,
            _state_key(run_id),
            _now(),
            str(self.settings.run_state_ttl_seconds),
        )
        return bool(int(result))

    async def is_cancel_requested(self, run_id: str) -> bool:
        """处理“is_cancel_requested”业务步骤，完成输入校验、依赖调用和结果返回。"""
        value = await self.redis.hget(_state_key(run_id), "cancel_requested")
        return str(value).lower() == "true"

    async def try_acquire_worker_lease(
        self, run_id: str, worker_id: str, attempt: int
    ) -> bool:
        """以 Redis 原子操作为单个 Worker 抢占 Run Lease，直到租约过期。

        已进入终态的 Run 或仍被其他 Worker 持有有效租约的 Run 不会被重复执行；
        租约配合心跳续期和 Pending 消息接管，构成多 Worker 下的执行互斥保护。
        """
        script = """
        local status = redis.call('HGET', KEYS[2], 'status')
        if status == 'COMPLETED' or status == 'FAILED' or status == 'CANCELLED' then
          return 0
        end
        local acquired = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
        if not acquired then return 0 end
        redis.call('HSET', KEYS[2],
          'status', 'RUNNING', 'worker_id', ARGV[1], 'attempt', ARGV[3],
          'updated_at', ARGV[4])
        redis.call('EXPIRE', KEYS[2], ARGV[5])
        return 1
        """
        result = await self.redis.eval(
            script,
            2,
            _lease_key(run_id),
            _state_key(run_id),
            worker_id,
            str(self.settings.task_visibility_timeout_seconds),
            str(attempt),
            _now(),
            str(self.settings.run_state_ttl_seconds),
        )
        return bool(int(result))

    async def try_acquire_session_lease(
        self, tenant_id: str, session_id: str, owner: str
    ) -> bool:
        """原子获取租户会话 Lease，保证同一 tenant_id/session_id 的多个 Run 串行执行。"""
        return bool(
            int(
                await self.redis.set(
                    _session_lease_key(tenant_id, session_id),
                    owner,
                    nx=True,
                    ex=self.settings.task_visibility_timeout_seconds,
                )
                or 0
            )
        )

    async def renew_session_lease(
        self, tenant_id: str, session_id: str, owner: str
    ) -> bool:
        """处理“renew_session_lease”业务步骤，完成输入校验、依赖调用和结果返回。"""
        script = """
        if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
        redis.call('EXPIRE', KEYS[1], ARGV[2])
        return 1
        """
        result = await self.redis.eval(
            script,
            1,
            _session_lease_key(tenant_id, session_id),
            owner,
            str(self.settings.task_visibility_timeout_seconds),
        )
        return bool(int(result))

    async def release_session_lease(
        self, tenant_id: str, session_id: str, owner: str
    ) -> None:
        """处理“release_session_lease”业务步骤，完成输入校验、依赖调用和结果返回。"""
        script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then redis.call('DEL', KEYS[1]) end
        return 1
        """
        await self.redis.eval(
            script,
            1,
            _session_lease_key(tenant_id, session_id),
            owner,
        )

    async def renew_worker_lease(self, run_id: str, worker_id: str) -> bool:
        """处理“renew_worker_lease”业务步骤，完成输入校验、依赖调用和结果返回。"""
        script = """
        if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
        redis.call('EXPIRE', KEYS[1], ARGV[2])
        redis.call('HSET', KEYS[2], 'heartbeat_at', ARGV[3], 'updated_at', ARGV[3])
        redis.call('EXPIRE', KEYS[2], ARGV[4])
        return 1
        """
        result = await self.redis.eval(
            script,
            2,
            _lease_key(run_id),
            _state_key(run_id),
            worker_id,
            str(self.settings.task_visibility_timeout_seconds),
            _now(),
            str(self.settings.run_state_ttl_seconds),
        )
        return bool(int(result))

    async def release_worker_lease(self, run_id: str, worker_id: str) -> None:
        """处理“release_worker_lease”业务步骤，完成输入校验、依赖调用和结果返回。"""
        script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
          redis.call('DEL', KEYS[1])
        end
        return 1
        """
        await self.redis.eval(script, 1, _lease_key(run_id), worker_id)

    async def try_acquire_concurrency(
        self, principal_id: str, run_id: str, limit: int
    ) -> bool:
        """原子获取调用方并发槽位，并使用 ZSET 过期时间避免 Worker 崩溃泄漏。"""
        if limit <= 0:
            return False
        now = int(datetime.now(UTC).timestamp())
        expires_at = now + self.settings.task_visibility_timeout_seconds
        script = """
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
        if redis.call('ZSCORE', KEYS[1], ARGV[3]) then
          redis.call('EXPIRE', KEYS[1], ARGV[4])
          return 1
        end
        if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
          return 0
        end
        redis.call('ZADD', KEYS[1], ARGV[5], ARGV[3])
        redis.call('EXPIRE', KEYS[1], ARGV[4])
        return 1
        """
        result = await self.redis.eval(
            script,
            1,
            _concurrency_key(principal_id),
            str(now),
            str(limit),
            run_id,
            str(self.settings.task_visibility_timeout_seconds),
            str(expires_at),
        )
        return bool(int(result))

    async def renew_concurrency(
        self, principal_id: str, run_id: str
    ) -> bool:
        """续期并发槽位；只有仍持有槽位的 Run 才能续期。"""
        now = int(datetime.now(UTC).timestamp())
        expires_at = now + self.settings.task_visibility_timeout_seconds
        script = """
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
        if not redis.call('ZSCORE', KEYS[1], ARGV[2]) then return 0 end
        redis.call('ZADD', KEYS[1], ARGV[3], ARGV[2])
        redis.call('EXPIRE', KEYS[1], ARGV[4])
        return 1
        """
        result = await self.redis.eval(
            script,
            1,
            _concurrency_key(principal_id),
            str(now),
            run_id,
            str(expires_at),
            str(self.settings.task_visibility_timeout_seconds),
        )
        return bool(int(result))

    async def release_concurrency(self, principal_id: str, run_id: str) -> None:
        """释放调用方并发槽位；重复释放是安全的。"""
        await self.redis.zrem(_concurrency_key(principal_id), run_id)

    async def mark_retrying(self, run_id: str, attempt: int, error: dict[str, Any]) -> None:
        """处理“mark_retrying”业务步骤，完成输入校验、依赖调用和结果返回。"""
        await self.set_status(
            run_id,
            "RETRYING",
            sequence=attempt,
            error=error,
        )

    async def mark_waiting_confirmation(
        self, run_id: str, *, interrupt_count: int
    ) -> None:
        """把 Run 标记为等待人工确认，并记录待决策的中断数量。"""
        await self.set_status(
            run_id,
            "WAITING_CONFIRMATION",
            sequence=interrupt_count,
        )

    async def load_request_payload(self, run_id: str) -> str | None:
        """读取入队时保存的原始请求载荷，用于恢复执行时重建 Agent。"""
        return await self.redis.get(_request_payload_key(run_id))

    async def mark_cancelled(self, run_id: str) -> None:
        """处理“mark_cancelled”业务步骤，完成输入校验、依赖调用和结果返回。"""
        await self.set_status(run_id, "CANCELLED")

    async def set_status(
        self,
        run_id: str,
        status: str,
        *,
        session_id: str | None = None,
        agent_id: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        stream: bool | None = None,
        sequence: int | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """更新 Run 状态投影，并把状态、租户、用户、结果或错误信息按 TTL 保存到 Redis。"""
        mapping: dict[str, str] = {
            "run_id": run_id,
            "status": status,
            "updated_at": _now(),
        }
        optional_values: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "stream": stream,
            "sequence": sequence,
        }
        for field, value in optional_values.items():
            if value is not None:
                mapping[field] = (
                    str(value).lower() if isinstance(value, bool) else str(value)
                )
        if result is not None:
            mapping["result"] = json.dumps(result, ensure_ascii=False, default=str)
        if error is not None:
            mapping["error"] = json.dumps(error, ensure_ascii=False, default=str)

        await self.redis.hset(_state_key(run_id), mapping=mapping)
        await self.redis.expire(
            _state_key(run_id), self.settings.run_state_ttl_seconds
        )
        stored = await self.get(run_id)
        return stored or mapping
