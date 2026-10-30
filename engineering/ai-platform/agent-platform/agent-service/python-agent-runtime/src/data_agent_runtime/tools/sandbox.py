"""本文件模块职责：SandboxProvider 到 DeepAgents Tool 的适配模块。

本模块只暴露受限的文件读写、结构化命令执行和产物收集工具，具体命令白名单、路径、超时、输出、资源和网络限制由 Provider 与 SandboxConfig 共同执行。
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from data_agent_runtime.clients.provider import SandboxProvider


class SandboxWriteFileInput(BaseModel):
    """Sandbox 文件写入工具的输入。

    路径必须位于 Provider 允许的 ``/workspace`` 工作区内；工具不会直接访问 Runtime
    宿主机文件系统，文件大小和实际权限由 Sandbox Provider 再次限制。
    """

    path: str = Field(description="绝对路径，必须位于 /workspace 下")
    content: str = Field(description="要写入的 UTF-8 文本内容")


class SandboxRunInput(BaseModel):
    """Sandbox 结构化命令工具的输入。

    ``executable`` 和参数分开传递，不接受 shell 字符串或管道表达式；命令白名单、超时、
    资源和网络策略由 Provider 执行，调用方不能通过参数绕过这些限制。
    """

    executable: str = Field(description="可执行文件名，例如 python3；不能是 shell 表达式")
    args: list[str] = Field(default_factory=list, description="命令参数，不支持 shell 拼接")
    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)


class SandboxReadFileInput(BaseModel):
    """Sandbox 文件读取工具的输入。

    路径必须位于受控工作区内，返回值会受到 Provider 的文件大小和输出限制。
    """

    path: str = Field(description="绝对路径，必须位于 /workspace 下")


class SandboxArtifactInput(BaseModel):
    """Sandbox 产物收集工具的输入。

    只能收集工作区内的文件；可选名称仅影响对外展示，不改变实际文件路径和权限边界。
    """

    path: str = Field(description="绝对路径，必须位于 /workspace 下")
    name: str | None = Field(default=None, description="下载产物名称")


def _json(value: Any) -> str:
    """执行“_json”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, default=str)


def create_sandbox_tools(client: SandboxProvider) -> list[StructuredTool]:
    """为一次 Agent Run 创建受限的 Sandbox 工具集合。

    工具只暴露文件写入、文件读取、结构化命令执行和产物收集能力；具体 Provider、
    命令白名单、工作区路径、超时、输出大小及网络策略由 Sandbox 配置统一约束。
    """

    async def write_file(path: str, content: str) -> str:
        """在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。"""
        result = await client.write_file(path, content.encode("utf-8"))
        return _json(result)

    async def run_command(
        executable: str,
        args: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> str:
        """处理“run_command”业务步骤，完成输入校验、依赖调用和结果返回。"""
        result = await client.run(
            executable,
            args or [],
            timeout_seconds=timeout_seconds,
        )
        return _json(result)

    async def read_file(path: str) -> str:
        """从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。"""
        content = await client.read_file(path)
        return content.decode("utf-8", errors="replace")

    async def collect_artifact(path: str, name: str | None = None) -> str:
        """将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。"""
        result = await client.collect_artifact(path, name=name)
        return _json(result)

    return [
        StructuredTool.from_function(
            coroutine=write_file,
            name="sandbox_write_file",
            description=(
                "在隔离 Sandbox 的 /workspace 下写入 UTF-8 文本文件。"
                "不能访问宿主机文件系统。"
            ),
            args_schema=SandboxWriteFileInput,
        ),
        StructuredTool.from_function(
            coroutine=run_command,
            name="sandbox_run",
            description=(
                "在隔离 Sandbox 中执行一个受策略约束的命令。"
                "只接受 executable 和参数数组，不支持 shell、管道或宿主机命令。"
            ),
            args_schema=SandboxRunInput,
        ),
        StructuredTool.from_function(
            coroutine=read_file,
            name="sandbox_read_file",
            description="读取隔离 Sandbox /workspace 下的 UTF-8 文本文件。",
            args_schema=SandboxReadFileInput,
        ),
        StructuredTool.from_function(
            coroutine=collect_artifact,
            name="sandbox_collect_artifact",
            description="将 Sandbox /workspace 下的文件提交为受审计的下载产物。",
            args_schema=SandboxArtifactInput,
        ),
    ]
