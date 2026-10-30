"""上传文件的短期存储。

文件内容不进任务流（Redis Stream 消息体只放引用），而是按租户隔离存放并设置 TTL：
Worker 执行时按 ``file_id`` 读取，Run 结束后自然过期，避免长期占用内存。

选 Redis 而不是对象存储，是为了让运行时在**不引入新依赖**的前提下具备完整闭环；
生产环境可把本类替换为对象存储实现，接口保持不变。
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from data_agent_runtime.config import Settings


class UploadTooLargeError(ValueError):
    """上传内容超过部署上限。"""


class RuntimeFileStore:
    """按租户隔离的上传文件存储。"""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        """保存 Redis 客户端与部署配置。"""
        self.redis = redis
        self.settings = settings

    @staticmethod
    def _key(tenant_id: str, file_id: str) -> str:
        """生成带租户前缀的存储 Key，避免跨租户读取。"""
        return f"agent:file:{tenant_id}:{file_id}"

    async def put(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        file_name: str,
        media_type: str,
        data: bytes,
    ) -> dict[str, object]:
        """保存一个文件并返回元数据。"""
        if len(data) > self.settings.max_upload_bytes:
            raise UploadTooLargeError(
                f"file exceeds {self.settings.max_upload_bytes} bytes"
            )
        file_id = uuid.uuid4().hex
        record = {
            "file_id": file_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "name": file_name,
            "media_type": media_type,
            "size": len(data),
            "created_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(data).decode("ascii"),
        }
        try:
            await self.redis.set(
                self._key(tenant_id, file_id),
                json.dumps(record, ensure_ascii=False),
                ex=self.settings.upload_ttl_seconds,
            )
        except (RedisError, OSError) as exc:
            raise RuntimeError("failed to persist upload") from exc
        return {
            key: record[key]
            for key in ("file_id", "name", "media_type", "size", "created_at")
        }

    async def get(self, *, tenant_id: str, file_id: str) -> dict[str, object] | None:
        """读取文件元数据与内容；不存在或已过期返回 None。"""
        try:
            raw = await self.redis.get(self._key(tenant_id, file_id))
        except (RedisError, OSError):
            return None
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None

    async def delete(self, *, tenant_id: str, file_id: str) -> bool:
        """删除文件；返回是否确实删除了一条记录。"""
        try:
            return bool(await self.redis.delete(self._key(tenant_id, file_id)))
        except (RedisError, OSError):
            return False


def decode_content(record: dict[str, object]) -> bytes:
    """把存储记录中的 base64 内容解码为原始字节。"""
    encoded = record.get("content_base64")
    if not isinstance(encoded, str) or not encoded:
        return b""
    return base64.b64decode(encoded)
