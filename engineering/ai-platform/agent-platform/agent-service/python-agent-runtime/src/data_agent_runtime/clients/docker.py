"""本文件模块职责：Docker Sandbox Provider 实现模块。

本模块通过结构化 Docker CLI 控制容器创建、命令执行、文件交换和资源销毁，Agent 命令始终在容器内运行，Python Runtime 不执行宿主机 Shell，也不拼接未经校验的命令字符串。

Docker Engine backed SandboxProvider.

The provider talks to the Docker CLI as a control-plane client. Agent commands
are executed inside a container via ``docker exec``; the Runtime never calls a
host shell and never interpolates a command string.

"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Sequence

from data_agent_runtime.clients.local import (
    LocalSandboxError,
    command_failure,
    duration_ms,
    extract_single_file,
    require_executable,
    require_workspace_path,
    run_control_command,
    tar_single_file,
    truncate_output,
)
from data_agent_runtime.clients.sandbox import SandboxGatewayError, SandboxRunContext
from data_agent_runtime.config import Settings
from data_agent_runtime.schemas import (
    SandboxArtifact,
    SandboxCommandResult,
    SandboxConfig,
    SandboxCreateResponse,
    SandboxFileResponse,
)


class DockerSandboxProvider:
    """为一次 Agent Run 创建一个可销毁的 Docker 隔离容器。

    Provider 只通过 Docker 控制命令管理容器，不把调用方命令交给宿主机 Shell；文件、命令、
    资源和网络边界由 SandboxConfig 与部署策略共同限制。
    """

    def __init__(
        self,
        settings: Settings,
        sandbox: SandboxConfig,
        context: SandboxRunContext,
    ) -> None:
        """初始化 DockerSandboxProvider，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.settings = settings
        self.sandbox = sandbox
        self.context = context
        self.container_id: str | None = None
        self.container_name = f"data-agent-{uuid.uuid4().hex[:20]}"
        self._closed = False
        # Tool 调用可能并发；串行化生命周期转换，避免同一 Agent Run 创建两个容器。
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_created(self) -> bool:
        """处理“is_created”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return self.container_id is not None

    def _control_timeout(self) -> float:
        """执行“_control_timeout”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        return max(
            self.settings.docker_control_timeout_seconds,
            float(self.sandbox.timeout_seconds),
        )

    async def _docker(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: float | None = None,
    ):
        """执行“_docker”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self._closed:
            raise SandboxGatewayError("Docker Sandbox provider is already closed")
        result = await run_control_command(
            [self.settings.docker_binary, *args],
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds or self._control_timeout(),
        )
        if result.timed_out:
            raise LocalSandboxError("Docker control command timed out")
        return result

    def _network(self) -> str:
        """执行“_network”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self.sandbox.network_mode in {"none", "restricted"}:
            # restricted 白名单需要平台策略层；本地安全失败，不能静默授予 bridge 网络。
            return "none"
        return "bridge"

    async def ensure_created(self) -> SandboxCreateResponse:
        """按需创建并返回隔离 Sandbox；重复调用时复用已经创建的会话。"""
        async with self._lifecycle_lock:
            if self.container_id:
                return SandboxCreateResponse(sandbox_id=self.container_id, status="READY")

            image = self.sandbox.image or self.settings.docker_default_image
            if self.sandbox.image_digest:
                image = f"{image}@{self.sandbox.image_digest}"
            disk_mb = self.sandbox.disk_limit_mb or 10_240
            args = [
                "create",
                "--name",
                self.container_name,
                "--workdir",
                "/workspace",
                "--network",
                self._network(),
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--pids-limit",
                str(self.sandbox.max_processes),
                "--user",
                "65532:65532",
                "--tmpfs",
                f"/workspace:rw,nosuid,nodev,size={disk_mb}m,uid=65532,gid=65532,mode=1770",
                "--tmpfs",
                f"/tmp:rw,nosuid,nodev,size={min(disk_mb, 1024)}m,uid=65532,gid=65532,mode=1770",
            ]
            if self.sandbox.cpu_limit is not None:
                args.extend(["--cpus", str(self.sandbox.cpu_limit)])
            if self.sandbox.memory_limit_mb is not None:
                args.extend(["--memory", f"{self.sandbox.memory_limit_mb}m"])
            args.extend([image, "sleep", "infinity"])

            try:
                created = await self._docker(args)
                if created.returncode != 0:
                    raise command_failure(created, provider="docker create")
                container_id = created.stdout.decode().strip()
                if not container_id:
                    raise LocalSandboxError("docker create returned an empty container id")
                started = await self._docker(["start", container_id])
                if started.returncode != 0:
                    await self._remove_container(container_id, suppress_errors=True)
                    raise command_failure(started, provider="docker start")
                self.container_id = container_id
                return SandboxCreateResponse(sandbox_id=container_id, status="READY")
            except (Exception, asyncio.CancelledError):
                # 即使 CLI 超时或调用方在返回容器 ID 前按下 Ctrl-C，后台守护进程也可能已经创建容器；
                # 按名称尽力清理，避免宿主机遗留孤儿 Sandbox。
                await asyncio.shield(
                    self._remove_container(self.container_name, suppress_errors=True)
                )
                raise

    async def _remove_container(
        self,
        container: str,
        *,
        suppress_errors: bool = False,
    ) -> None:
        """执行“_remove_container”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        try:
            result = await run_control_command(
                [self.settings.docker_binary, "rm", "-f", container],
                timeout_seconds=self._control_timeout(),
            )
        except LocalSandboxError:
            if not suppress_errors:
                raise
            return
        if (
            result.returncode != 0
            and b"No such container" not in result.stderr
            and not suppress_errors
        ):
            raise command_failure(result, provider="docker rm")

    async def _exec(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: float | None = None,
    ):
        """执行“_exec”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        container = (await self.ensure_created()).sandbox_id
        command = ["exec"]
        if input_bytes is not None:
            command.append("-i")
        command.extend([container, *args])
        return await self._docker(
            command,
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds,
        )

    async def write_file(
        self,
        path: str,
        content: bytes,
        *,
        encoding: str = "utf-8",
    ) -> SandboxFileResponse:
        """在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。"""
        require_workspace_path(path)
        result = await self._exec(
            ["tar", "-x", "-f", "-", "-C", "/workspace"],
            input_bytes=tar_single_file(path, content),
        )
        if result.returncode != 0:
            raise command_failure(result, provider="docker exec tar")
        return SandboxFileResponse(
            path=path,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def read_file(self, path: str) -> bytes:
        """从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。"""
        relative = require_workspace_path(path)
        result = await self._exec(
            ["tar", "-c", "-f", "-", "-C", "/workspace", relative],
        )
        if result.returncode != 0:
            raise command_failure(result, provider="docker exec tar")
        return extract_single_file(result.stdout, path)

    async def run(
        self,
        executable: str,
        args: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        max_output_bytes: int | None = None,
    ) -> SandboxCommandResult:
        """在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。"""
        require_executable(executable, self.sandbox.allow_commands)
        started_at = time.monotonic()
        result = await self._exec(
            [executable, *list(args)],
            timeout_seconds=timeout_seconds or self.sandbox.timeout_seconds,
        )
        limit = max_output_bytes or self.sandbox.max_output_bytes
        stdout, stdout_truncated = truncate_output(result.stdout, limit)
        stderr, stderr_truncated = truncate_output(result.stderr, limit)
        if result.timed_out:
            # 杀死容器比留下无界进程更安全；本次 Run 的后续 Tool 调用将安全失败。
            await self.destroy()
            self._closed = True
            return SandboxCommandResult(
                status="TIMED_OUT",
                stdout=stdout,
                stderr=stderr or "Docker command timed out",
                truncated=True,
                duration_ms=duration_ms(started_at),
            )
        return SandboxCommandResult(
            status="COMPLETED" if result.returncode == 0 else "FAILED",
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
            truncated=stdout_truncated or stderr_truncated,
            duration_ms=duration_ms(started_at),
        )

    async def collect_artifact(self, path: str, *, name: str | None = None) -> SandboxArtifact:
        """将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。"""
        content = await self.read_file(path)
        return SandboxArtifact(
            artifact_id=f"docker-artifact-{uuid.uuid4().hex[:16]}",
            file_name=name or path.rsplit("/", 1)[-1],
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def destroy(self) -> None:
        """销毁底层 Sandbox 资源并使后续操作失效，确保容器、Pod 或远程会话不会泄漏。"""
        async with self._lifecycle_lock:
            container_id = self.container_id
            self.container_id = None
            if not container_id:
                return
            await self._remove_container(container_id)

    async def aclose(self) -> None:
        """关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。"""
        if self._closed:
            return
        try:
            await self.destroy()
        finally:
            self._closed = True
