"""三个高危修复的回归测试。

覆盖：MCP 工具白名单按 Server 生效、内联 Skill 按租户与内容隔离、准入路径的
DNS 解析带缓存且不阻塞事件循环。
"""

import asyncio
import socket
from types import SimpleNamespace

import pytest

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.network_policy import (
    clear_dns_cache,
    is_private_or_local_host,
    is_private_or_local_host_async,
)
from data_agent_runtime.runtime.skill_artifacts import SkillArtifactManager
from data_agent_runtime.schemas import MCPServerConfig, SkillSnapshot
from data_agent_runtime.tools.mcp import _validate_server_async, load_mcp_tools


def test_mcp_allowlist_is_applied_per_server(monkeypatch):
    """验证每个 MCP Server 的 allowlist 只作用于自己的工具。"""

    async def run() -> None:
        """加载两个 Server 的工具并检查过滤结果。"""
        per_server = {
            "server-a": [SimpleNamespace(name="allowed_tool"), SimpleNamespace(name="other_tool")],
            "server-b": [SimpleNamespace(name="free_tool")],
        }

        class _Client:
            """按 server_name 返回不同工具的 MCP 客户端替身。"""

            def __init__(self, config):
                """保存连接配置。"""
                self.config = config

            async def get_tools(self, *, server_name=None):
                """返回该 Server 的工具列表。"""
                return list(per_server[server_name])

        monkeypatch.setattr(
            "langchain_mcp_adapters.client.MultiServerMCPClient", _Client
        )
        servers = [
            MCPServerConfig(
                id="server-a",
                url="https://a.example.com",
                tool_allowlist=["allowed_tool"],
            ),
            MCPServerConfig(id="server-b", url="https://b.example.com"),
        ]
        settings = Settings(_env_file=None, app_env="test")
        _, tools = await load_mcp_tools(servers, settings)

        names = sorted(tool.name for tool in tools)
        # server-a 只保留白名单内的工具；server-b 未配白名单，工具必须全部保留。
        assert names == ["allowed_tool", "free_tool"]

    asyncio.run(run())


def test_inline_skill_is_isolated_by_tenant_and_content(tmp_path):
    """验证同名同版本的内联 Skill 不会跨租户复用同一目录。"""

    async def run() -> None:
        """为两个租户物化同名 Skill 并比较目录与内容。"""
        settings = Settings(_env_file=None, workspace_root=str(tmp_path))
        manager = SkillArtifactManager(settings)

        async def materialize(tenant: str, content: str, run_id: str) -> str:
            """物化一次并返回 Skill 目录。"""
            result = await manager.materialize(
                [SkillSnapshot(id="shared", version=1, content=content)],
                tenant_id=tenant,
                session_id="session-1",
                run_id=run_id,
                workspace_enabled=False,
            )
            return result.skill_paths["shared"]

        first = await materialize("tenant-a", "A 租户的口径", "run-a")
        second = await materialize("tenant-b", "B 租户的口径", "run-b")

        cache_root = tmp_path / ".inline-skills"
        dirs = sorted(path for path in cache_root.rglob("shared-1-*") if path.is_dir())
        assert len(dirs) == 2
        assert {path.parent.name for path in dirs} == {"tenant-a", "tenant-b"}
        # 同一租户重复物化应命中缓存，目录集合不变。
        await materialize("tenant-a", "A 租户的口径", "run-c")
        assert len([p for p in cache_root.rglob("shared-1-*") if p.is_dir()]) == 2
        # skill_paths 对外仍是工作区内的稳定路径，不暴露缓存布局。
        assert first == second == "/skills/shared"

    asyncio.run(run())


def test_dns_lookup_is_cached(monkeypatch):
    """验证同一主机的 DNS 判定会命中缓存，避免每次准入都解析。"""
    clear_dns_cache()
    calls = {"count": 0}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        """统计解析次数并返回公网地址。"""
        calls["count"] += 1
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert is_private_or_local_host("example.com") is False
    assert is_private_or_local_host("example.com") is False
    assert calls["count"] == 1
    clear_dns_cache()
    assert is_private_or_local_host("example.com") is False
    assert calls["count"] == 2


def test_dns_lookup_failure_is_treated_as_unsafe(monkeypatch):
    """验证解析失败按不安全处理（fail-closed）。"""
    clear_dns_cache()

    def failing_getaddrinfo(*args, **kwargs):
        """模拟解析失败。"""
        raise OSError("dns failure")

    monkeypatch.setattr(socket, "getaddrinfo", failing_getaddrinfo)
    assert is_private_or_local_host("unresolvable.example") is True


def test_async_dns_helper_runs_without_blocking(monkeypatch):
    """验证异步 DNS 助手可用，且对 IP 字面量直接判定。"""

    async def run() -> None:
        """调用异步判定。"""
        assert await is_private_or_local_host_async("127.0.0.1") is True
        assert await is_private_or_local_host_async("localhost") is True

    asyncio.run(run())


def test_mcp_async_validation_rejects_private_endpoint():
    """验证公共模式下 MCP 私网地址会被异步校验拒绝。"""

    async def run() -> None:
        """调用异步校验并期望抛出 ValueError。"""
        settings = Settings(
            _env_file=None,
            app_env="test",
            public_mode=True,
            allowed_mcp_hosts="127.0.0.1",
        )
        clear_dns_cache()
        with pytest.raises(ValueError, match="private or local"):
            await _validate_server_async(
                MCPServerConfig(id="local", url="https://127.0.0.1:8080"), settings
            )

    asyncio.run(run())
