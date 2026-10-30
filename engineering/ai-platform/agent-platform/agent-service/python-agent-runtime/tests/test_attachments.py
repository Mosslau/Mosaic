"""附件链路的单元测试：存储、执行器注入、准入校验与上传接口。

覆盖 CSV 文本注入、图片多模态块、沙箱落盘、附件数量与视觉模型校验。
"""

import asyncio
import base64
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langgraph.checkpoint.memory import InMemorySaver

from data_agent_runtime import api
from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.admission import (
    SnapshotAdmissionError,
    validate_attachments,
)
from data_agent_runtime.runtime.executor import RunExecutor
from data_agent_runtime.runtime.files import (
    RuntimeFileStore,
    UploadTooLargeError,
    decode_content,
)
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)
from data_agent_runtime.runtime.principal import Principal
from data_agent_runtime.schemas import (
    AgentSnapshot,
    FileAttachment,
    ModelConfig,
    RunRequest,
    UserContext,
)


class _Redis:
    """支持文件存储所需命令的最小 Redis 替身。"""

    def __init__(self) -> None:
        """初始化键值表。"""
        self.values: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        """写入键值。"""
        self.values[key] = value
        return True

    async def get(self, key):
        """读取键值。"""
        return self.values.get(key)

    async def delete(self, key):
        """删除键值并返回删除数量。"""
        return 1 if self.values.pop(key, None) is not None else 0

    async def lrange(self, key, start, end):
        """会话历史替身：始终为空。"""
        return []

    async def rpush(self, key, *values):
        """会话历史替身。"""
        return len(values)

    async def ltrim(self, key, start, end):
        """会话历史替身。"""
        return True


@pytest.mark.parametrize("content", [b"", b"abc"])
def test_file_store_round_trip(content):
    """验证写入/读取/删除的完整往返，并确认内容按 base64 保存。"""

    async def run() -> None:
        """执行一次往返。"""
        store = RuntimeFileStore(_Redis(), Settings(_env_file=None))
        meta = await store.put(
            tenant_id="t-1",
            user_id="u-1",
            file_name="data.csv",
            media_type="text/csv",
            data=content,
        )
        assert meta["size"] == len(content)
        record = await store.get(tenant_id="t-1", file_id=meta["file_id"])
        assert record is not None
        assert decode_content(record) == content
        # 跨租户不可读
        assert await store.get(tenant_id="t-2", file_id=meta["file_id"]) is None
        assert await store.delete(tenant_id="t-1", file_id=meta["file_id"]) is True
        assert await store.get(tenant_id="t-1", file_id=meta["file_id"]) is None

    asyncio.run(run())


def test_file_store_rejects_oversized_upload():
    """验证超过上限的上传被拒绝。"""

    async def run() -> None:
        """尝试写入超过上限的内容。"""
        settings = Settings(_env_file=None, max_upload_bytes=4)
        store = RuntimeFileStore(_Redis(), settings)
        with pytest.raises(UploadTooLargeError):
            await store.put(
                tenant_id="t-1",
                user_id="u-1",
                file_name="big.bin",
                media_type="application/octet-stream",
                data=b"12345",
            )

    asyncio.run(run())


def _request(*, media_type="text/csv", model="gpt-4o-mini") -> RunRequest:
    """构造一次带单个附件的 Run 请求。"""
    return RunRequest(
        run_id="run-file",
        message="看看这张表",
        agent=AgentSnapshot(
            id="agent-file",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name=model),
        ),
        attachments=[FileAttachment(file_id="f-1", media_type=media_type)],
        user_context=UserContext(user_id="u-1", tenant_id="t-1"),
    )


def test_validate_attachments_rejects_too_many():
    """验证附件数量超过部署上限时拒绝。"""
    settings = Settings(_env_file=None, max_attachments=1)
    request = _request()
    request.attachments = [
        FileAttachment(file_id="f-1"),
        FileAttachment(file_id="f-2"),
    ]
    with pytest.raises(SnapshotAdmissionError, match="too many attachments"):
        validate_attachments(settings, request)


def test_validate_attachments_requires_vision_allowlist():
    """验证未配置视觉模型白名单时拒绝图片附件。"""
    settings = Settings(_env_file=None, allowed_vision_models="")
    with pytest.raises(SnapshotAdmissionError, match="configure ALLOWED_VISION_MODELS"):
        validate_attachments(settings, _request(media_type="image/png"))


def test_validate_attachments_rejects_model_without_vision():
    """验证模型不在视觉白名单时拒绝图片附件。"""
    settings = Settings(_env_file=None, allowed_vision_models="vision-model")
    with pytest.raises(SnapshotAdmissionError, match="does not support image"):
        validate_attachments(settings, _request(media_type="image/png"))


class _Events:
    """记录事件的发布器替身。"""

    def __init__(self) -> None:
        """初始化事件列表。"""
        self.values: list[tuple[str, str, dict]] = []

    async def publish(self, run_id, event_type, payload):
        """记录事件。"""
        self.values.append((run_id, event_type, payload))


class _Agent:
    """记录输入载荷并正常结束的 Agent 替身。"""

    def __init__(self) -> None:
        """初始化载荷记录。"""
        self.payloads: list[object] = []

    async def astream_events(self, payload, config, version):
        """记录载荷并返回一个答案。"""
        self.payloads.append(payload)
        yield {
            "event": "on_chain_end",
            "data": {"output": {"messages": [{"role": "assistant", "content": "ok"}]}},
        }

    async def aget_state(self, config):
        """返回无中断状态。"""
        return SimpleNamespace(values={}, interrupts=())


class _Sandbox:
    """记录沙箱写入的替身。"""

    def __init__(self) -> None:
        """初始化写入记录。"""
        self.written: list[tuple[str, bytes]] = []

    async def write_file(self, path, content, encoding="utf-8"):
        """记录写入路径与内容。"""
        self.written.append((path, content))
        return SimpleNamespace(path=path, size_bytes=len(content))


def _executor(monkeypatch, agent, store) -> tuple[RunExecutor, _Events]:
    """构造带文件存储的 Executor。"""

    async def fake_build_agent(*args, **kwargs):
        """返回替身 Agent 与带沙箱的句柄。"""
        return agent, SimpleNamespace(sandbox_provider=_Sandbox())

    monkeypatch.setattr(
        "data_agent_runtime.runtime.executor.build_agent", fake_build_agent
    )
    settings = Settings(_env_file=None)
    redis = _Redis()
    events = _Events()
    executor = RunExecutor(
        settings,
        events,
        RedisConversationHistory(redis, settings),
        RedisLongTermMemory(redis, settings),
        InMemorySaver(),
        None,
        files=store,
    )
    return executor, events


def test_executor_injects_csv_as_text(monkeypatch):
    """验证 CSV 附件被解析成表格文本拼进用户消息。"""

    async def run() -> None:
        """执行一次带 CSV 附件的 Run。"""
        redis = _Redis()
        store = RuntimeFileStore(redis, Settings(_env_file=None))
        meta = await store.put(
            tenant_id="t-1",
            user_id="u-1",
            file_name="cars.csv",
            media_type="text/csv",
            data="车型,数量\nNQi,128\n".encode(),
        )
        agent = _Agent()
        executor, _events = _executor(monkeypatch, agent, store)
        request = _request()
        request.attachments = [FileAttachment(file_id=meta["file_id"], media_type="text/csv")]

        await executor.execute_queued(request, worker_id="w-1", attempt=0)

        content = agent.payloads[0]["messages"][-1]["content"]
        assert "看看这张表" in content
        assert "# 附件 1: cars.csv" in content
        assert "| NQi | 128 |" in content

    asyncio.run(run())


def test_executor_sends_image_as_multimodal_block(monkeypatch):
    """验证图片附件被转成 data URL 的图像块，而不是文本。"""

    async def run() -> None:
        """执行一次带图片附件的 Run。"""
        redis = _Redis()
        store = RuntimeFileStore(redis, Settings(_env_file=None))
        payload = b"\x89PNG\r\n\x1a\n"
        meta = await store.put(
            tenant_id="t-1",
            user_id="u-1",
            file_name="chart.png",
            media_type="image/png",
            data=payload,
        )
        agent = _Agent()
        executor, _events = _executor(monkeypatch, agent, store)
        request = _request(media_type="image/png")
        request.attachments = [
            FileAttachment(file_id=meta["file_id"], media_type="image/png")
        ]

        await executor.execute_queued(request, worker_id="w-1", attempt=0)

        content = agent.payloads[0]["messages"][-1]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        image_block = content[1]
        assert image_block["type"] == "image_url"
        assert image_block["image_url"]["url"].startswith("data:image/png;base64,")
        assert base64.b64encode(payload).decode() in image_block["image_url"]["url"]

    asyncio.run(run())


def test_executor_fails_when_attachment_missing(monkeypatch):
    """验证附件已过期时快速失败，而不是静默忽略。"""

    async def run() -> None:
        """引用一个不存在的 file_id。"""
        store = RuntimeFileStore(_Redis(), Settings(_env_file=None))
        agent = _Agent()
        executor, _events = _executor(monkeypatch, agent, store)
        with pytest.raises(RuntimeError, match="missing or expired"):
            await executor.execute_queued(_request(), worker_id="w-1", attempt=0)

    asyncio.run(run())


def _principal() -> Principal:
    """构造具备提交权限的调用方身份。"""
    return Principal(
        principal_id="p-1",
        access_key="ak-1",
        tenant_id="t-1",
        subject_id="u-1",
        scopes=frozenset({"runs:write"}),
    )


def test_upload_endpoint_stores_file(monkeypatch):
    """验证上传接口返回文件引用并落到存储。"""

    async def run() -> None:
        """调用上传接口。"""
        redis = _Redis()
        monkeypatch.setattr(
            api, "settings", Settings(_env_file=None), raising=False
        )
        monkeypatch.setattr(
            api.app.state,
            "files",
            RuntimeFileStore(redis, Settings(_env_file=None)),
            raising=False,
        )

        class _Upload:
            """UploadFile 替身。"""

            filename = "cars.csv"
            content_type = "text/csv"

            async def read(self):
                """返回文件内容。"""
                return b"a,b\n1,2\n"

        result = await api.upload_file(_Upload(), _principal())
        assert result["name"] == "cars.csv"
        assert result["size"] == 8
        assert result["file_id"]

    asyncio.run(run())


def test_upload_endpoint_rejects_oversized_file(monkeypatch):
    """验证超过上限的上传返回 413。"""

    async def run() -> None:
        """上传超限内容。"""
        monkeypatch.setattr(
            api.app.state,
            "files",
            RuntimeFileStore(_Redis(), Settings(_env_file=None, max_upload_bytes=2)),
            raising=False,
        )

        class _Upload:
            """UploadFile 替身。"""

            filename = "big.csv"
            content_type = "text/csv"

            async def read(self):
                """返回超限内容。"""
                return b"12345"

        with pytest.raises(HTTPException) as excinfo:
            await api.upload_file(_Upload(), _principal())
        assert excinfo.value.status_code == 413

    asyncio.run(run())
