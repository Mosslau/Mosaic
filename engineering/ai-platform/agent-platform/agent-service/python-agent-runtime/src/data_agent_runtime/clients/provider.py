"""本文件模块职责：每次 Agent Run 或 SubAgent Run 使用的 Sandbox Provider 协议定义模块。

上层工具只依赖该抽象，不依赖 Java 类或具体容器实现，从而支持 HTTP Gateway、Docker、Kubernetes 以及其他隔离执行后端的可替换接入。

Provider interfaces for per-run Sandbox execution.

The Agent Tools depend on this protocol instead of a concrete Java client.  A
provider can be backed by an HTTP gateway, a local Docker executor, a
Kubernetes executor, or another isolated runtime.  Implementations must keep
all execution inside an isolated boundary; the Python Agent Runtime must never
fall back to host ``subprocess`` execution.

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from data_agent_runtime.schemas import (
    SandboxArtifact,
    SandboxCommandResult,
    SandboxCreateResponse,
    SandboxFileResponse,
)


@runtime_checkable
class SandboxProvider(Protocol):
    """每个 Agent 或 SubAgent 独立 Sandbox 的 Provider 协议。

    实现必须提供创建、文件读写、结构化命令执行、产物收集和关闭能力，并在 Provider 内部
    强制执行路径、命令、资源、网络、超时和输出限制。
    """

    @property
    def is_created(self) -> bool:
        """返回当前隔离 Sandbox 会话是否已经创建并可供工具调用。

        Provider 实现应将该属性作为本地生命周期状态的快速判断，不应借此绕过
        ensure_created、权限校验或底层资源健康检查。
        """
        ...

    async def ensure_created(self) -> SandboxCreateResponse:
        """按需创建并返回隔离 Sandbox；重复调用时复用已经创建的会话。"""
        ...

    async def write_file(
        self,
        path: str,
        content: bytes,
        *,
        encoding: str = "utf-8",
    ) -> SandboxFileResponse:
        """在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。"""
        ...

    async def read_file(self, path: str) -> bytes:
        """从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。"""
        ...

    async def run(
        self,
        executable: str,
        args: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        max_output_bytes: int | None = None,
    ) -> SandboxCommandResult:
        """在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。"""
        ...

    async def collect_artifact(
        self,
        path: str,
        *,
        name: str | None = None,
    ) -> SandboxArtifact:
        """将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。"""
        ...

    async def destroy(self) -> None:
        """销毁底层 Sandbox 资源并使后续操作失效，确保容器、Pod 或远程会话不会泄漏。"""
        ...

    async def aclose(self) -> None:
        """关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。"""
        ...
