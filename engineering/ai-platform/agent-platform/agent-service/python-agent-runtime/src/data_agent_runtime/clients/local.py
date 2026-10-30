"""本文件模块职责：Docker 和 Kubernetes Provider 共用的本地控制面辅助模块。

本模块只允许执行固定的 Docker/kubectl 控制命令，负责超时、取消、路径校验、tar 文件封装和输出截断；严禁退化为宿主机 Shell 执行 Agent 命令。

Shared helpers for local Docker/Kubernetes Sandbox Providers.

These providers invoke only fixed control-plane binaries (Docker or kubectl)
with structured argv. They never invoke a shell and never run Agent commands
on the Runtime host directly.

"""

from __future__ import annotations

import asyncio
import io
import tarfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from data_agent_runtime.clients.sandbox import SandboxGatewayError


class LocalSandboxError(SandboxGatewayError):
    """本地 Docker 或 Kubernetes Provider 执行控制命令失败时抛出的异常。"""


@dataclass(frozen=True)
class ProcessResult:
    """本地 Provider 控制命令的标准化进程结果。

    结果保留退出码、标准输出、标准错误和超时标记，供 Docker/Kubernetes 适配器统一处理。
    """

    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


async def run_control_command(
    argv: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    timeout_seconds: float,
) -> ProcessResult:
    """不经过 Shell，仅以结构化参数执行固定的 Docker 或 kubectl 控制命令。

    该函数只用于控制面操作，不执行 Agent 提交的宿主机命令；超时、取消、
    启动失败和非零退出码均保留可供上层审计和错误转换的信息。
    """
    if not argv or any(not isinstance(value, str) for value in argv):
        raise LocalSandboxError("control command argv must be a non-empty string list")
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if input_bytes is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_bytes),
                timeout=max(float(timeout_seconds), 0.1),
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return ProcessResult(process.returncode or -9, stdout, stderr, True)
        except asyncio.CancelledError:
            # Ctrl-C 或调用方取消不能让 docker/kubectl 子进程继续持有管道；
            # 传播取消前先排空子进程，确保 asyncio.run() 可以干净关闭事件循环。
            process.kill()
            try:
                await asyncio.shield(process.communicate())
            except (ProcessLookupError, asyncio.CancelledError):
                pass
            raise
    except OSError as exc:
        raise LocalSandboxError(f"failed to start control command {argv[0]!r}: {exc}") from exc
    return ProcessResult(process.returncode or 0, stdout, stderr)


def require_workspace_path(path: str) -> str:
    """规范化 Sandbox 虚拟路径，并拒绝越过 /workspace 的路径穿越请求。

    返回值是去掉工作区前缀后的安全相对路径，供 Docker tar、kubectl cp 或
    HTTP Gateway 继续使用；反斜杠、空路径片段、`.` 和 `..` 都会被拒绝。
    """
    if not path or not path.startswith("/workspace"):
        raise LocalSandboxError("sandbox path must remain under /workspace")
    if path != "/workspace" and not path.startswith("/workspace/"):
        raise LocalSandboxError("sandbox path must remain under /workspace")
    if "\\" in path:
        raise LocalSandboxError("sandbox path contains an unsafe path segment")
    raw = path.removeprefix("/workspace").lstrip("/")
    parts = PurePosixPath(raw).parts if raw else ()
    if any(part in {"", ".", ".."} for part in parts):
        raise LocalSandboxError("sandbox path contains an unsafe path segment")
    return "/".join(parts)


def require_executable(executable: str, allow_commands: list[str]) -> None:
    """处理“require_executable”业务步骤，完成输入校验、依赖调用和结果返回。"""
    if not executable or executable.strip() != executable:
        raise LocalSandboxError("executable must be a non-empty command name")
    if "/" in executable or "\\" in executable:
        raise LocalSandboxError("executable must be a command name, not a path")
    if allow_commands and executable not in allow_commands:
        raise LocalSandboxError(f"executable is not allowed: {executable}")


def tar_single_file(path: str, content: bytes) -> bytes:
    """为工作区中的单个文件创建 tar 字节流，供容器文件写入使用。

    文件名会先经过工作区路径校验，生成的归档只包含一个普通文件，不允许
    借助符号链接或路径片段把内容写到 Sandbox 工作区之外。
    """
    relative = require_workspace_path(path)
    if not relative:
        raise LocalSandboxError("file path must not be /workspace")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        info = tarfile.TarInfo(name=relative)
        info.size = len(content)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


def extract_single_file(archive_bytes: bytes, requested_path: str) -> bytes:
    """处理“extract_single_file”业务步骤，完成输入校验、依赖调用和结果返回。"""
    relative = require_workspace_path(requested_path)
    if not relative:
        raise LocalSandboxError("file path must not be /workspace")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            members = archive.getmembers()
            for member in members:
                # 拒绝可能逃逸虚拟工作区的归档条目。
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise LocalSandboxError("Sandbox returned an unsafe tar path")
            member = archive.getmember(relative)
            if not member.isfile():
                raise LocalSandboxError("Sandbox path is not a regular file")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise LocalSandboxError("Sandbox file content is unavailable")
            return extracted.read()
    except KeyError as exc:
        raise LocalSandboxError(f"sandbox file not found: {requested_path}") from exc
    except tarfile.TarError as exc:
        raise LocalSandboxError("Sandbox returned an invalid tar archive") from exc


def truncate_output(value: bytes, max_output_bytes: int) -> tuple[str, bool]:
    """处理“truncate_output”业务步骤，完成输入校验、依赖调用和结果返回。"""
    limited = value[: max(1, max_output_bytes)]
    return limited.decode("utf-8", errors="replace"), len(value) > len(limited)


def command_failure(result: ProcessResult, *, provider: str) -> LocalSandboxError:
    """处理“command_failure”业务步骤，完成输入校验、依赖调用和结果返回。"""
    detail = result.stderr.decode("utf-8", errors="replace").strip()[:1000]
    return LocalSandboxError(
        f"{provider} control command failed with exit code {result.returncode}: {detail or 'unknown error'}"
    )


def duration_ms(started_at: float) -> int:
    """处理“duration_ms”业务步骤，完成输入校验、依赖调用和结果返回。"""
    import time

    return max(0, int((time.monotonic() - started_at) * 1000))
