"""本文件模块职责：Redis 会话历史与受控长期记忆模块。

本模块负责按租户、会话和用户隔离读取与写入上下文，并限制注入模型的消息数量；长期记忆的业务权限和最终治理策略仍由 外部控制面或调用方负责。

Redis-backed conversation history and controlled long-term memory.
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


def _session_key(
    session_id: str, tenant_id: str | None = None, user_id: str | None = None
) -> str:
    """生成带租户和主体隔离的会话 Key。

    tenant_id/user_id 为空时保留旧单元测试和本地迁移的兼容 Key；公共 API 永远
    传入完整身份，避免不同租户使用同名 session_id 发生碰撞。
    """
    identity = ":".join(value for value in (tenant_id, user_id, session_id) if value)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"agent:session:{digest}:messages"


def _memory_key(tenant_id: str, user_id: str) -> str:
    """执行“_memory_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    tenant = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
    user = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return f"agent:memory:{tenant}:{user}"


class RedisConversationHistory:
    """基于 Redis List 持久保存的用户可见 Session 对话历史。

    读写均按 tenant、user 和 session 隔离，并受部署级消息数量上限约束。
    """

    def __init__(self, redis: Redis, settings: Settings):
        """初始化 RedisConversationHistory，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.redis = redis
        self.settings = settings

    async def list_messages(
        self,
        session_id: str,
        limit: int | None = None,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """处理“list_messages”业务步骤，完成输入校验、依赖调用和结果返回。"""
        count = min(
            limit or self.settings.conversation_history_max_messages,
            self.settings.conversation_history_max_messages,
        )
        values = await self.redis.lrange(
            _session_key(session_id, tenant_id, user_id), -count, -1
        )
        messages: list[dict[str, Any]] = []
        for value in values:
            try:
                item = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                messages.append(item)
        return messages

    async def append_message(
        self,
        *,
        session_id: str,
        run_id: str,
        role: str,
        content: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """处理“append_message”业务步骤，完成输入校验、依赖调用和结果返回。"""
        message = {
            "message_id": f"{run_id}:{role}:{int(datetime.now(UTC).timestamp() * 1000)}",
            "session_id": session_id,
            "run_id": run_id,
            "role": role,
            "content": content,
            "created_at": _now(),
        }
        key = _session_key(session_id, tenant_id, user_id)
        encoded = json.dumps(message, ensure_ascii=False)
        await self.redis.rpush(key, encoded)
        await self.redis.ltrim(
            key, -self.settings.conversation_history_max_messages, -1
        )
        # 本地旧客户端仍使用未命名空间的 Session API；公共模式绝不写入兼容 Key。
        if (tenant_id or user_id) and not self.settings.public_mode:
            legacy_key = _session_key(session_id)
            await self.redis.rpush(legacy_key, encoded)
            await self.redis.ltrim(
                legacy_key, -self.settings.conversation_history_max_messages, -1
            )
        return message

    async def clear(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """处理“clear”业务步骤，完成输入校验、依赖调用和结果返回。"""
        await self.redis.delete(_session_key(session_id, tenant_id, user_id))
        if (tenant_id or user_id) and not self.settings.public_mode:
            await self.redis.delete(_session_key(session_id))


class RedisLongTermMemory:
    """按租户和用户隔离的显式长期记忆记录。

    Runtime 只把允许读取的记录作为提示词上下文；写入应由已认证调用方和 memory:write Scope
    控制，不能由模型自行扩大权限。
    """

    def __init__(self, redis: Redis, settings: Settings):
        """初始化 RedisLongTermMemory，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.redis = redis
        self.settings = settings

    async def list_memories(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        """处理“list_memories”业务步骤，完成输入校验、依赖调用和结果返回。"""
        values = await self.redis.lrange(
            _memory_key(tenant_id, user_id),
            -self.settings.long_term_memory_max_items,
            -1,
        )
        memories: list[dict[str, Any]] = []
        for value in values:
            try:
                item = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                memories.append(item)
        return memories

    async def upsert(self, memory: dict[str, Any]) -> dict[str, Any]:
        """处理“upsert”业务步骤，完成输入校验、依赖调用和结果返回。"""
        tenant_id = str(memory["tenant_id"])
        user_id = str(memory["user_id"])
        memory_id = str(memory["memory_id"])
        key = _memory_key(tenant_id, user_id)
        existing = await self.list_memories(tenant_id, user_id)
        updated = False
        for index, item in enumerate(existing):
            if item.get("memory_id") == memory_id:
                existing[index] = memory
                updated = True
                break
        if not updated:
            existing.append(memory)
        existing = existing[-self.settings.long_term_memory_max_items :]
        pipe = self.redis.pipeline()
        pipe.delete(key)
        if existing:
            pipe.rpush(
                key, *[json.dumps(item, ensure_ascii=False) for item in existing]
            )
        await pipe.execute()
        return memory

    async def delete(self, tenant_id: str, user_id: str, memory_id: str) -> bool:
        """处理“delete”业务步骤，完成输入校验、依赖调用和结果返回。"""
        key = _memory_key(tenant_id, user_id)
        existing = await self.list_memories(tenant_id, user_id)
        remaining = [item for item in existing if item.get("memory_id") != memory_id]
        if len(remaining) == len(existing):
            return False
        pipe = self.redis.pipeline()
        pipe.delete(key)
        if remaining:
            pipe.rpush(
                key, *[json.dumps(item, ensure_ascii=False) for item in remaining]
            )
        await pipe.execute()
        return True
