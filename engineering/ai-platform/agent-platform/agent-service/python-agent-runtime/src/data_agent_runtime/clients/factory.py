"""本文件模块职责：Sandbox Provider 工厂模块，根据部署级配置选择 HTTP Gateway、Docker 或 Kubernetes 实现。

Provider 的选择属于 Runtime 部署能力，不允许 Agent Snapshot 随意切换到更高权限的执行后端；所有实现都必须满足统一的 SandboxProvider 协议。

Construction of the configured Sandbox provider.
"""

from __future__ import annotations

import httpx

from data_agent_runtime.clients.docker import DockerSandboxProvider
from data_agent_runtime.clients.kubernetes import KubernetesSandboxProvider
from data_agent_runtime.clients.provider import SandboxProvider
from data_agent_runtime.clients.sandbox import (
    HttpSandboxProvider,
    SandboxGatewayError,
    SandboxRunContext,
)
from data_agent_runtime.config import Settings
from data_agent_runtime.schemas import SandboxConfig


class SandboxProviderConfigurationError(ValueError):
    """当部署配置没有选择受支持的 Sandbox Provider 时抛出的配置错误。"""


def create_sandbox_provider(
    settings: Settings,
    sandbox: SandboxConfig,
    context: SandboxRunContext,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> SandboxProvider:
    """根据部署级配置为一次 Agent Run 创建一个 Sandbox Provider。

    ``http`` 表示通用 HTTP Sandbox 契约：任何实现该契约的网关（独立 Sidecar、
    云厂商托管服务或自研网关）都可以作为 Provider，Runtime 不绑定具体实现。
    Docker、Kubernetes 等本地或平台 Provider 也可以在此扩展，而无需修改
    DeepAgents 的工具层接口。
    """
    provider = (settings.sandbox_provider or "http").strip().lower()
    if provider in {"http", "http_gateway"}:
        return HttpSandboxProvider(
            settings,
            sandbox,
            context,
            http_client=http_client,
        )
    if provider == "docker":
        if http_client is not None:
            raise SandboxProviderConfigurationError(
                "http_client injection is only supported by HTTP Sandbox providers"
            )
        return DockerSandboxProvider(settings, sandbox, context)
    if provider in {"kubernetes", "k8s"}:
        if http_client is not None:
            raise SandboxProviderConfigurationError(
                "http_client injection is only supported by HTTP Sandbox providers"
            )
        return KubernetesSandboxProvider(settings, sandbox, context)
    raise SandboxProviderConfigurationError(
        f"unsupported SANDBOX_PROVIDER={provider!r}; supported providers are: "
        "http, docker, kubernetes"
    )


__all__ = [
    "DockerSandboxProvider",
    "KubernetesSandboxProvider",
    "SandboxGatewayError",
    "SandboxProviderConfigurationError",
    "SandboxRunContext",
    "create_sandbox_provider",
]
