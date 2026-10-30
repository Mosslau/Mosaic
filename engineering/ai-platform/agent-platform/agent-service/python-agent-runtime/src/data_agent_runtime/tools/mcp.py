"""本文件模块职责：MCP Server 到 DeepAgents Tool 的适配和公共网络安全校验模块。

Runtime 不执行任意 stdio 命令，不允许 Snapshot 把 MCP 变成 SSRF 或 Secret 外带通道；
生产 MCP 凭证由服务端 credential_ref 解析，Snapshot 只声明引用。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from data_agent_runtime.config import Settings, get_settings
from data_agent_runtime.runtime.network_policy import (
    is_private_or_local_host,
    is_private_or_local_host_async,
)
from data_agent_runtime.schemas import MCPServerConfig


async def _validate_server_async(
    server: MCPServerConfig, settings: Settings
) -> None:
    """异步校验 MCP Server：DNS 判定放到线程池，避免阻塞事件循环。"""
    if server.transport != "stdio" and settings.public_mode and server.url:
        host = urlparse(server.url).hostname
        if host and await is_private_or_local_host_async(host):
            raise ValueError("MCP endpoint resolves to a private or local address")
    _validate_server(server, settings, resolved_private=True)


def _validate_server(
    server: MCPServerConfig, settings: Settings, *, resolved_private: bool = False
) -> None:
    """校验单个 MCP Server 的传输、URL、Host、Header 和 stdio 策略。

    该函数在创建 MCP Client 前执行，防止公共 Runtime 被用作 SSRF、私网探测或凭证外带通道。"""
    if server.transport == "stdio":
        if settings.public_mode or not settings.allow_mcp_stdio:
            raise ValueError("stdio MCP transport is disabled by Runtime policy")
        if not server.command or not server.command.strip():
            raise ValueError(f"stdio MCP server {server.id!r} requires command")
        return
    if not server.url:
        raise ValueError(f"MCP server {server.id!r} requires url")
    parsed = urlparse(server.url)
    if parsed.username or parsed.password:
        raise ValueError(f"MCP server {server.id!r} URL must not contain userinfo")
    if parsed.fragment:
        raise ValueError(f"MCP server {server.id!r} URL must not contain a fragment")
    if parsed.scheme not in {"https"} and not (
        not settings.public_mode
        and settings.app_env.lower() in {"local", "dev", "development"}
        and parsed.scheme == "http"
    ):
        raise ValueError("MCP HTTP endpoints must use HTTPS")
    host = parsed.hostname
    if not host:
        raise ValueError(f"MCP server {server.id!r} has invalid url")
    allowed_hosts = {
        item.strip().lower()
        for item in settings.allowed_mcp_hosts.split(",")
        if item.strip()
    }
    if settings.public_mode and host.lower() not in allowed_hosts:
        raise ValueError(f"MCP host {host!r} is not in ALLOWED_MCP_HOSTS")
    if (
        settings.public_mode
        and not resolved_private
        and is_private_or_local_host(host)
    ):
        raise ValueError("MCP endpoint resolves to a private or local address")
    if settings.public_mode and server.headers:
        raise ValueError(
            "inline MCP headers are disabled in public mode; use credential_ref"
        )


def _tool_name(tool: Any) -> str | None:
    """读取 LangChain Tool 的名称，兼容 dict 形式的工具描述。"""
    if isinstance(tool, dict):
        return tool.get("name")
    return getattr(tool, "name", None)


def _credential_headers(settings: Settings, credential_ref: str) -> dict[str, str]:
    """从部署侧注册表解析 MCP 凭证，绝不从 Snapshot 读取 Secret。"""
    raw = settings.mcp_credentials_json
    if not raw:
        raise ValueError(
            f"MCP credential_ref {credential_ref!r} is configured but the server credential registry is empty"
        )
    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("MCP_CREDENTIALS_JSON is invalid") from exc
    if not isinstance(registry, dict):
        raise TypeError("MCP_CREDENTIALS_JSON must be a JSON object")
    value = registry.get(credential_ref)
    if not isinstance(value, dict):
        raise TypeError(f"MCP credential_ref {credential_ref!r} is not registered")
    headers = value.get("headers", value)
    if not isinstance(headers, dict) or not headers:
        raise ValueError(f"MCP credential_ref {credential_ref!r} has no headers")
    return {str(key): str(header_value) for key, header_value in headers.items()}


async def load_mcp_tools(
    servers: list[MCPServerConfig], settings: Settings | None = None
) -> tuple[Any, list[Any]]:
    """创建 MCP 客户端、解析服务端凭证并按白名单过滤工具。"""
    if not servers:
        return None, []
    settings = settings or get_settings()
    from langchain_mcp_adapters.client import MultiServerMCPClient

    server_config: dict[str, Mapping[str, Any]] = {}
    for server in servers:
        await _validate_server_async(server, settings)
        if server.transport in {"streamable_http", "sse"}:
            config: dict[str, Any] = {"transport": server.transport, "url": server.url}
            headers = (
                _credential_headers(settings, server.credential_ref)
                if server.credential_ref
                else dict(server.headers)
            )
            if headers:
                config["headers"] = headers
        else:
            config = {
                "transport": "stdio",
                "command": server.command,
                "args": server.args,
            }
        server_config[server.id] = config

    client = MultiServerMCPClient(server_config)
    # 按 Server 逐个取工具再套用该 Server 的 allowlist：
    # 旧实现把"任一 Server 的白名单"套到所有 Server 的工具上，导致未配白名单的
    # Server 工具被静默删光。逐个取也顺带避免不同 Server 同名工具的歧义。
    tools: list[Any] = []
    for server in servers:
        server_tools = await client.get_tools(server_name=server.id)
        if server.tool_allowlist:
            allowed = set(server.tool_allowlist)
            server_tools = [
                tool for tool in server_tools if _tool_name(tool) in allowed
            ]
        tools.extend(server_tools)
    return client, tools
