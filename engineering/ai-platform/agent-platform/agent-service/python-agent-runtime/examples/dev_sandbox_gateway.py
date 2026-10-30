"""本文件模块职责：本地开发用的 Sandbox Gateway 模拟服务和契约示例。

本服务只提供确定性的文件与命令模拟，不执行宿主机命令，便于在没有 Docker 或 Kubernetes 的环境验证 HTTP Provider、Tool 调用、错误处理和生命周期逻辑。

本服务用于开发和契约测试，故意不执行宿主机命令，只模拟少量确定性的命令，
用于验证 Runtime、Tool、生命周期、文件交换和错误处理，而不要求安装 Docker 或 Kubernetes。

运行：
    uv run python examples/dev_sandbox_gateway.py

"""

from __future__ import annotations

import base64
import hashlib
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="dev-sandbox-gateway", version="0.1.0")
_ROOT = Path(tempfile.mkdtemp(prefix="data-agent-dev-sandboxes-"))
_SANDBOXES: dict[str, dict[str, Any]] = {}


class CreateRequest(BaseModel):
    """创建 Sandbox 会话时由 Runtime 发送的资源和租户上下文。"""

    run_id: str
    sandbox_scope: str = "root"
    tenant_id: str
    session_id: str
    user_id: str | None = None
    image: str | None = None
    image_digest: str | None = None
    timeout_seconds: int = 60
    max_output_bytes: int = 1_048_576
    allow_commands: list[str] = []


class WriteRequest(BaseModel):
    """开发网关文件写入接口的请求体。"""

    path: str
    content_base64: str
    encoding: str = "utf-8"


class ReadRequest(BaseModel):
    """开发网关文件读取接口的请求体。"""

    path: str


class CommandRequest(BaseModel):
    """开发网关结构化命令接口的请求体。"""

    executable: str
    args: list[str] = []
    timeout_seconds: int = 60
    max_output_bytes: int = 1_048_576


class ArtifactRequest(BaseModel):
    """开发网关产物收集接口的请求体。"""

    path: str
    name: str | None = None


def _sandbox(sandbox_id: str) -> dict[str, Any]:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的内部辅助步骤“_sandbox”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    value = _SANDBOXES.get(sandbox_id)
    if value is None:
        raise HTTPException(status_code=404, detail="sandbox not found")
    return value


def _safe_path(value: str) -> Path:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的内部辅助步骤“_safe_path”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - value: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        Path。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    if not value.startswith("/workspace/") and value != "/workspace":
        raise HTTPException(status_code=400, detail="path must remain under /workspace")
    parts = value.split("/")[2:] if value != "/workspace" else []
    if any(not part or part in {".", ".."} for part in parts):
        raise HTTPException(status_code=400, detail="unsafe path")
    sandbox_root = _CURRENT_ROOT.get().resolve()
    target = sandbox_root.joinpath(*parts).resolve()
    if target != sandbox_root and sandbox_root not in target.parents:
        raise HTTPException(status_code=400, detail="unsafe path")
    return target


# 请求处理器在单进程内使用该上下文变量解析路径，避免把宿主机路径暴露到公共 API。
from contextvars import ContextVar

_CURRENT_ROOT: ContextVar[Path] = ContextVar("sandbox_root")


def _with_root(sandbox_id: str):
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的内部辅助步骤“_with_root”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return _CURRENT_ROOT.set(_sandbox(sandbox_id)["root"])


def _clear_root(token: Any) -> None:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的内部辅助步骤“_clear_root”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - token: Any：由调用方传入，用于完成本函数的核心处理。

    返回：
        None。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    _CURRENT_ROOT.reset(token)


@app.post("/v1/sandboxes")
async def create_sandbox(payload: CreateRequest, request: Request) -> dict[str, Any]:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的“create_sandbox”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - payload: CreateRequest：由调用方传入，用于完成本函数的核心处理。
        - request: Request：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    sandbox_id = f"dev-sb-{uuid.uuid4().hex[:12]}"
    root = _ROOT / sandbox_id / "workspace"
    root.mkdir(parents=True)
    _SANDBOXES[sandbox_id] = {
        "root": root,
        "allow_commands": set(payload.allow_commands),
        "created_at": time.time(),
    }
    return {
        "sandbox_id": sandbox_id,
        "status": "READY",
        "workspace_path": "/workspace",
        "expires_at": None,
    }


@app.put("/v1/sandboxes/{sandbox_id}/files")
async def write_file(sandbox_id: str, payload: WriteRequest) -> dict[str, Any]:
    """
    中文说明：
        在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。
        - payload: WriteRequest：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    token = _with_root(sandbox_id)
    try:
        target = _safe_path(payload.path)
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid content_base64") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return {
            "path": payload.path,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    finally:
        _clear_root(token)


@app.post("/v1/sandboxes/{sandbox_id}/files:read")
async def read_file(sandbox_id: str, payload: ReadRequest) -> dict[str, Any]:
    """
    中文说明：
        从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。
        - payload: ReadRequest：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    token = _with_root(sandbox_id)
    try:
        target = _safe_path(payload.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        content = target.read_bytes()
        return {
            "path": payload.path,
            "content_base64": base64.b64encode(content).decode("ascii"),
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    finally:
        _clear_root(token)


@app.post("/v1/sandboxes/{sandbox_id}/commands")
async def run_command(sandbox_id: str, payload: CommandRequest) -> dict[str, Any]:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的“run_command”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。
        - payload: CommandRequest：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    sandbox = _sandbox(sandbox_id)
    allowed = sandbox["allow_commands"]
    if allowed and payload.executable not in allowed:
        raise HTTPException(status_code=403, detail="executable is not allowed")

    # 这里绝不能调用 subprocess；该模拟服务只测试 HTTP/Tool 契约。
    if payload.executable == "echo":
        stdout = " ".join(payload.args)
        exit_code = 0
        status = "COMPLETED"
        stderr = ""
    elif payload.executable in {"python", "python3"}:
        stdout = "[dev-mock] python execution simulated; no host code was run"
        exit_code = 0
        status = "COMPLETED"
        stderr = ""
    elif payload.executable == "true":
        stdout = ""
        exit_code = 0
        status = "COMPLETED"
        stderr = ""
    else:
        stdout = ""
        exit_code = 127
        status = "FAILED"
        stderr = f"[dev-mock] unsupported command: {payload.executable}"

    if len(stdout.encode()) > payload.max_output_bytes:
        stdout = stdout.encode()[: payload.max_output_bytes].decode(errors="replace")
        truncated = True
    else:
        truncated = False
    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": truncated,
        "duration_ms": 0,
    }


@app.post("/v1/sandboxes/{sandbox_id}/artifacts")
async def collect_artifact(sandbox_id: str, payload: ArtifactRequest) -> dict[str, Any]:
    """
    中文说明：
        将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。
        - payload: ArtifactRequest：由调用方传入，用于完成本函数的核心处理。

    返回：
        dict[str, Any]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    token = _with_root(sandbox_id)
    try:
        target = _safe_path(payload.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        content = target.read_bytes()
        return {
            "artifact_id": f"dev-artifact-{uuid.uuid4().hex[:12]}",
            "file_name": payload.name or target.name,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "download_url": None,
        }
    finally:
        _clear_root(token)


@app.delete("/v1/sandboxes/{sandbox_id}")
async def destroy_sandbox(sandbox_id: str) -> Response:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的“destroy_sandbox”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - sandbox_id: str：由调用方传入，用于完成本函数的核心处理。

    返回：
        Response。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    sandbox = _SANDBOXES.pop(sandbox_id, None)
    if sandbox is None:
        return Response(status_code=204)
    shutil.rmtree(sandbox["root"].parent, ignore_errors=True)
    return Response(status_code=204)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    """
    中文说明：
        实现 examples/dev_sandbox_gateway 的“health”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        dict[str, str]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    return {"status": "ok", "service": "dev-sandbox-gateway"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8810)
