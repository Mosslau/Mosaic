"""本文件模块职责：HTTP Sandbox Provider 客户端模块，实现 Runtime 与独立 Sandbox Gateway 之间的 HTTP 契约。

本模块负责创建会话、读写工作区文件、执行结构化命令、收集产物和关闭会话；真正的隔离由远端 Gateway 或其底层容器平台提供，Runtime 不在宿主机执行用户命令。

HTTP SandboxProvider implementation for the Sandbox HTTP contract.

The Python runtime deliberately does not execute commands on its own host.  It
uses this client to create an isolated execution session and to exchange files,
commands, and artifact references with an external Sandbox Gateway.

"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.observability import (
    current_trace_identifiers,
    current_traceparent,
    current_tracestate,
    start_span,
)
from data_agent_runtime.runtime.signing import signing_headers
from data_agent_runtime.schemas import (
    SandboxArtifact,
    SandboxCommandResult,
    SandboxConfig,
    SandboxCreateResponse,
    SandboxFileResponse,
)


class SandboxGatewayError(RuntimeError):
    """调用 Sandbox Gateway 时返回或抛出的结构化错误。

    异常保留 HTTP 状态、网关错误码和请求 ID，便于 API、Worker 和审计日志定位失败原因。
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """初始化 SandboxGatewayError，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


@dataclass(frozen=True)
class SandboxRunContext:
    """一次 Agent 或 SubAgent Sandbox 会话的租户与追踪上下文。

    ``run_id`` 用于审计和幂等，``agent_path`` 用于区分同一 Run 下的多个 SubAgent；上下文
    不包含 Secret，也不能改变 Provider 的资源或网络策略。
    """

    run_id: str
    tenant_id: str
    session_id: str
    user_id: str | None = None
    trace_id: str | None = None
    # 一个顶层 Run 可能包含多个 SubAgent；各 Sandbox 会话和幂等键必须隔离，同时保留顶层 run_id 便于审计关联。
    sandbox_scope: str = "root"


class HttpSandboxProvider:
    """通过 HTTP Sandbox Gateway 管理一次 Agent Run 的隔离会话。

    会话在第一次 Sandbox 工具调用时惰性创建，避免普通对话产生无用的基础设施请求；``close``
    必须幂等，并在会话已创建时销毁远端资源。
    """

    def __init__(
        self,
        settings: Settings,
        sandbox: SandboxConfig,
        context: SandboxRunContext,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化 HttpSandboxProvider，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        if not settings.sandbox_gateway_base_url:
            raise SandboxGatewayError(
                "SANDBOX_GATEWAY_BASE_URL is required when sandbox.enabled=true"
            )
        self.settings = settings
        self.sandbox = sandbox
        self.context = context
        self.base_url = settings.sandbox_gateway_base_url.rstrip("/")
        # 生产环境的 Sandbox Gateway 必须使用 HTTPS，避免凭证和执行数据被窃听。
        if (
            settings.app_env.lower() in {"prod", "production", "staging"}
            and urlparse(self.base_url).scheme.lower() != "https"
        ):
            raise SandboxGatewayError(
                "SANDBOX_GATEWAY_BASE_URL must use HTTPS in production"
            )
        self._http = http_client
        self._owns_http = http_client is None
        self.sandbox_id: str | None = None
        self._closed = False

    @property
    def is_created(self) -> bool:
        """处理“is_created”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return self.sandbox_id is not None

    async def _http_client(self) -> httpx.AsyncClient:
        """执行“_http_client”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.settings.sandbox_connect_timeout_seconds,
                    read=self.settings.sandbox_read_timeout_seconds,
                    write=self.settings.sandbox_connect_timeout_seconds,
                    pool=self.settings.sandbox_connect_timeout_seconds,
                ),
                follow_redirects=False,
            )
        return self._http

    def _headers(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        """构造 Sandbox Gateway 通用请求头，并根据配置选择 HMAC 或本地迁移 Token。"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Run-Id": self.context.run_id,
            "X-Tenant-Id": self.context.tenant_id,
            "X-Session-Id": self.context.session_id,
            "X-Sandbox-Scope": self.context.sandbox_scope,
        }
        if self.context.user_id:
            headers["X-User-Id"] = self.context.user_id
        trace_values = current_trace_identifiers()
        trace_id = self.context.trace_id or trace_values.get("trace_id")
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        traceparent = current_traceparent()
        tracestate = current_tracestate()
        if traceparent:
            headers["traceparent"] = traceparent
        if tracestate:
            headers["tracestate"] = tracestate

        # Sandbox Gateway 使用独立凭证，不能复用 Runtime 入站 AK/SK。
        access_key = self.settings.sandbox_gateway_access_key
        secret_key = self.settings.sandbox_gateway_secret_key
        if bool(access_key) != bool(secret_key):
            raise SandboxGatewayError(
                "SANDBOX_GATEWAY_ACCESS_KEY and SANDBOX_GATEWAY_SECRET_KEY must be configured together"
            )
        if access_key and secret_key:
            # 签名使用即将发送的原始 Body，避免 JSON 重新序列化导致验签失败。
            headers.update(
                signing_headers(
                    secret_key=secret_key,
                    access_key=access_key,
                    method=method,
                    path=path,
                    query="",
                    body=body,
                    timestamp=str(int(time.time())),
                    nonce=secrets.token_urlsafe(18),
                )
            )
        elif self.settings.app_env.lower() in {"prod", "production", "staging"}:
            raise SandboxGatewayError(
                "Sandbox Gateway AK/SK credentials are not configured"
            )
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _idempotency_key(self, operation: str) -> str:
        """执行“_idempotency_key”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        return (
            f"{self.context.run_id}:sandbox:{self.context.sandbox_scope}:"
            f"{operation}"
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """执行“_request”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self._closed:
            raise SandboxGatewayError("Sandbox provider is already closed")
        client = await self._http_client()
        with start_span(
            "sandbox.http.request",
            attributes={
                "http.request.method": method,
                "server.address": self.base_url,
                "url.path": path,
                "sandbox.provider": "http",
                "run.id": self.context.run_id,
                "tenant.id": self.context.tenant_id,
                "session.id": self.context.session_id,
            },
        ) as span:
            try:
                # 先确定性序列化 JSON，再用同一份原始字节计算 Body Hash 并发送。
                body = (
                    b""
                    if json_body is None
                    else json.dumps(
                        json_body,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                )
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(
                        method=method,
                        path=path,
                        body=body,
                        idempotency_key=idempotency_key,
                    ),
                    content=body,
                )
                span.set_attribute("http.response.status_code", response.status_code)
            except httpx.HTTPError as exc:
                raise SandboxGatewayError(f"Sandbox Gateway request failed: {exc}") from exc

        if response.is_success:
            return response

        code = None
        message = response.text[:1000]
        request_id = response.headers.get("X-Request-Id")
        try:
            body = response.json()
            if isinstance(body, dict):
                code = body.get("code") or body.get("error_code")
                message = str(body.get("message") or body.get("detail") or message)
                request_id = request_id or body.get("request_id")
        except (ValueError, json.JSONDecodeError):
            pass
        raise SandboxGatewayError(
            f"Sandbox Gateway returned HTTP {response.status_code}: {message}",
            status_code=response.status_code,
            code=code,
            request_id=request_id,
        )

    async def ensure_created(self) -> SandboxCreateResponse:
        """按需创建并返回隔离 Sandbox；重复调用时复用已经创建的会话。"""
        if self.sandbox_id:
            return SandboxCreateResponse(
                sandbox_id=self.sandbox_id,
                status="READY",
            )
        response = await self._request(
            "POST",
            "/v1/sandboxes",
            json_body={
                "run_id": self.context.run_id,
                "tenant_id": self.context.tenant_id,
                "session_id": self.context.session_id,
                "user_id": self.context.user_id,
                "sandbox_scope": self.context.sandbox_scope,
                "image": self.sandbox.image,
                "image_digest": self.sandbox.image_digest,
                "timeout_seconds": self.sandbox.timeout_seconds,
                "cpu_limit": self.sandbox.cpu_limit,
                "memory_limit_mb": self.sandbox.memory_limit_mb,
                "disk_limit_mb": self.sandbox.disk_limit_mb,
                "max_output_bytes": self.sandbox.max_output_bytes,
                "max_processes": self.sandbox.max_processes,
                "network_mode": self.sandbox.network_mode,
                "allow_commands": self.sandbox.allow_commands,
            },
            idempotency_key=self._idempotency_key("create"),
        )
        try:
            created = SandboxCreateResponse.model_validate(response.json())
        except (ValueError, json.JSONDecodeError) as exc:
            raise SandboxGatewayError("Sandbox Gateway returned invalid create response") from exc
        self.sandbox_id = created.sandbox_id
        return created

    def _require_workspace_path(self, path: str) -> str:
        """执行“_require_workspace_path”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        value = path.strip()
        if not value:
            raise SandboxGatewayError("sandbox path must not be empty")
        if not value.startswith("/workspace/") and value != "/workspace":
            raise SandboxGatewayError("sandbox path must remain under /workspace")
        parts = value.split("/")[1:]
        if "\\" in value or any(part in {"", ".", ".."} for part in parts):
            raise SandboxGatewayError("sandbox path contains an unsafe path segment")
        return value

    async def write_file(self, path: str, content: bytes, *, encoding: str = "utf-8") -> SandboxFileResponse:
        """在 Sandbox 的受控工作区写入文件，不允许越过工作区路径边界。"""
        sandbox = await self.ensure_created()
        safe_path = self._require_workspace_path(path)
        response = await self._request(
            "PUT",
            f"/v1/sandboxes/{sandbox.sandbox_id}/files",
            json_body={
                "path": safe_path,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "encoding": encoding,
            },
            idempotency_key=self._idempotency_key(f"write:{safe_path}"),
        )
        try:
            return SandboxFileResponse.model_validate(response.json())
        except (ValueError, json.JSONDecodeError) as exc:
            raise SandboxGatewayError("Sandbox Gateway returned invalid file response") from exc

    async def read_file(self, path: str) -> bytes:
        """从 Sandbox 的受控工作区读取文件内容，并保持路径校验和大小限制。"""
        sandbox = await self.ensure_created()
        safe_path = self._require_workspace_path(path)
        response = await self._request(
            "POST",
            f"/v1/sandboxes/{sandbox.sandbox_id}/files:read",
            json_body={"path": safe_path},
            idempotency_key=self._idempotency_key(f"read:{safe_path}"),
        )
        try:
            body = SandboxFileResponse.model_validate(response.json())
            return base64.b64decode(body.content_base64, validate=True)
        except (ValueError, json.JSONDecodeError) as exc:
            raise SandboxGatewayError("Sandbox Gateway returned invalid file content") from exc

    async def run(
        self,
        executable: str,
        args: list[str],
        *,
        timeout_seconds: int | None = None,
        max_output_bytes: int | None = None,
    ) -> SandboxCommandResult:
        """在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。"""
        sandbox = await self.ensure_created()
        if not executable or executable.strip() != executable or "/" in executable:
            raise SandboxGatewayError("executable must be a command name, not a path or shell expression")
        if self.sandbox.allow_commands and executable not in self.sandbox.allow_commands:
            raise SandboxGatewayError(f"executable is not allowed by the Agent Snapshot: {executable}")
        response = await self._request(
            "POST",
            f"/v1/sandboxes/{sandbox.sandbox_id}/commands",
            json_body={
                "executable": executable,
                "args": args,
                "timeout_seconds": timeout_seconds or self.sandbox.timeout_seconds,
                "max_output_bytes": max_output_bytes or self.sandbox.max_output_bytes,
            },
            idempotency_key=self._idempotency_key(
                "command:"
                f"{hashlib.sha256(json.dumps([executable, *args], ensure_ascii=False).encode()).hexdigest()[:24]}"
            ),
        )
        try:
            return SandboxCommandResult.model_validate(response.json())
        except (ValueError, json.JSONDecodeError) as exc:
            raise SandboxGatewayError("Sandbox Gateway returned invalid command response") from exc

    async def collect_artifact(self, path: str, *, name: str | None = None) -> SandboxArtifact:
        """将 Sandbox 工作区中的文件收集为可审计、可下载的产物引用。"""
        sandbox = await self.ensure_created()
        safe_path = self._require_workspace_path(path)
        response = await self._request(
            "POST",
            f"/v1/sandboxes/{sandbox.sandbox_id}/artifacts",
            json_body={"path": safe_path, "name": name},
            idempotency_key=self._idempotency_key(f"artifact:{safe_path}"),
        )
        try:
            return SandboxArtifact.model_validate(response.json())
        except (ValueError, json.JSONDecodeError) as exc:
            raise SandboxGatewayError("Sandbox Gateway returned invalid artifact response") from exc

    async def destroy(self) -> None:
        """销毁底层 Sandbox 资源并使后续操作失效，确保容器、Pod 或远程会话不会泄漏。"""
        if not self.sandbox_id or self._closed:
            return
        sandbox_id = self.sandbox_id
        try:
            await self._request(
                "DELETE",
                f"/v1/sandboxes/{sandbox_id}",
                idempotency_key=self._idempotency_key("destroy"),
            )
        finally:
            self.sandbox_id = None

    async def aclose(self) -> None:
        """关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。"""
        if self._closed:
            return
        try:
            await self.destroy()
        finally:
            self._closed = True
            if self._owns_http and self._http is not None:
                await self._http.aclose()


# 中性兼容别名；HttpSandboxProvider 只依赖通用 HTTP 契约，不绑定任何具体网关实现。
SandboxClient = HttpSandboxProvider
