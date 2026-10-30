#!/usr/bin/env python3
"""本地联调栈端到端验证脚本。

脚本使用指定的环境文件加载 Runtime 配置，通过 HTTP/HMAC 调用真实 API，覆盖健康检查、
任务入队、Worker 执行、Run 状态、SSE 事件、MCP 协议、RAG 工具、Session、Memory、幂等和鉴权失败场景。
脚本不会打印 Secret Key、模型 API Key、数据库密码或 Redis 凭证。
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import secrets
import sys
import time
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
TERMINAL_EVENTS = {"run_completed", "run_failed", "run_cancelled"}


@dataclass(frozen=True)
class Credential:
    """从部署注册表加载的调用方凭证；Secret 只保存在进程内，不参与输出。"""

    access_key: str
    secret_key: str
    tenant_id: str
    principal_id: str
    subject_id: str | None
    scopes: frozenset[str]

    @property
    def user_id(self) -> str:
        """返回该调用方在 Runtime 中使用的资源归属用户。"""
        return self.subject_id or self.principal_id


class VerificationError(RuntimeError):
    """表示端到端验证中发现了契约、配置或运行时错误。"""


class LocalStackVerifier:
    """执行本地 API、Worker、Redis Stream 和外部资源接口的完整联调验证。"""

    def __init__(self, args: argparse.Namespace) -> None:
        """初始化验证器，加载配置并准备 HTTP 客户端和临时 Run 标识。"""
        self.args = args
        self.env_file = Path(args.env_file).expanduser().resolve()
        if not self.env_file.is_file():
            raise VerificationError(f"没有找到配置文件：{self.env_file}")
        os.environ["DATA_AGENT_ENV_FILE"] = str(self.env_file)

        # 必须在设置 DATA_AGENT_ENV_FILE 后再导入配置，避免误读其他环境文件。
        from data_agent_runtime.config import Settings

        self.settings = Settings(_env_file=str(self.env_file))
        api_port = os.environ.get("RUNTIME_PORT") or str(self.settings.port)
        mcp_port = os.environ.get("TEST_MCP_PORT") or "8810"
        web_port = os.environ.get("WEB_PORT") or "5500"
        self.base_url = (args.base_url or f"http://127.0.0.1:{api_port}").rstrip("/")
        self.mcp_url = (args.mcp_url or f"http://127.0.0.1:{mcp_port}").rstrip("/")
        self.web_url = (args.web_url or f"http://127.0.0.1:{web_port}").rstrip("/")
        self.client = httpx.Client(
            timeout=httpx.Timeout(args.request_timeout, connect=5.0),
            follow_redirects=False,
        )
        self.checks = 0
        self.skips = 0
        self.run_id = f"verify-local-{uuid.uuid4().hex}"
        self.session_id = f"verify-session-{uuid.uuid4().hex}"
        self.run_payload: dict[str, Any] | None = None
        self.run_body: bytes | None = None
        self.run_credential: Credential | None = None
        self.memory_credential: Credential | None = None
        self.run_state: dict[str, Any] | None = None

    def close(self) -> None:
        """关闭 HTTP 客户端，释放验证进程创建的网络资源。"""
        self.client.close()

    def log(self, message: str) -> None:
        """输出不包含 Secret 的验证进度。"""
        print(f"[verify-e2e] {message}", flush=True)

    def check(self, condition: bool, message: str) -> None:
        """记录断言结果；失败时抛出统一的验证异常。"""
        self.checks += 1
        if not condition:
            raise VerificationError(message)
        self.log(f"PASS {message}")

    def skip(self, message: str) -> None:
        """记录被显式跳过的可选验证项。"""
        self.skips += 1
        self.log(f"SKIP {message}")

    @staticmethod
    def _scope_values(value: Any) -> frozenset[str]:
        """把注册表 Scope 兼容转换为不可变字符串集合。"""
        if isinstance(value, str):
            return frozenset(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, list):
            return frozenset(str(item).strip() for item in value if str(item).strip())
        return frozenset()

    def load_credentials(self) -> list[Credential]:
        """读取多调用方 AK/SK 注册表，并验证至少存在可用的运行调用方。"""
        raw = self.settings.internal_service_credentials_json
        self.check(bool(raw and raw.strip()), "已加载 HMAC 调用方注册表")
        try:
            values = json.loads(raw or "")
        except json.JSONDecodeError as exc:
            raise VerificationError("INTERNAL_SERVICE_CREDENTIALS_JSON 不是有效 JSON") from exc
        self.check(isinstance(values, list) and bool(values), "HMAC 调用方注册表是非空数组")

        credentials: list[Credential] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            access_key = str(item.get("access_key") or "").strip()
            secret_key = str(item.get("secret_key") or "")
            tenant_id = str(item.get("tenant_id") or "").strip()
            principal_id = str(item.get("principal_id") or access_key).strip()
            if not access_key or not secret_key or not tenant_id or not principal_id:
                continue
            credentials.append(
                Credential(
                    access_key=access_key,
                    secret_key=secret_key,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                    subject_id=(str(item["subject_id"]) if item.get("subject_id") else None),
                    scopes=self._scope_values(item.get("scopes", [])),
                )
            )
        self.check(bool(credentials), "至少存在一组完整 AK/SK 调用方")
        return credentials

    @staticmethod
    def choose_credential(
        credentials: list[Credential], required_scopes: set[str]
    ) -> Credential | None:
        """选择包含所需 Scope 的调用方；不打印其 Secret。"""
        for credential in credentials:
            if "*" in credential.scopes or required_scopes.issubset(credential.scopes):
                return credential
        return None

    def show_configuration(self, credentials: list[Credential]) -> None:
        """输出脱敏配置摘要，确认 API 和 Worker 将使用同一个 .env。"""
        allowed_providers = [
            item.strip()
            for item in self.settings.allowed_model_providers.split(",")
            if item.strip()
        ]
        self.log(f"ENV_FILE={self.env_file}")
        self.log(f"APP_ENV={self.settings.app_env}")
        self.log(f"PUBLIC_MODE={self.settings.public_mode}")
        self.log(f"MODEL_PROVIDER={self.settings.model_provider}")
        self.log(f"ALLOWED_MODEL_PROVIDERS={','.join(allowed_providers)}")
        self.log(f"CHECKPOINT_BACKEND={self.settings.checkpoint_backend}")
        self.log(f"RUNTIME_MODE={self.settings.runtime_mode}（local-stack 会分别注入 api/worker）")
        self.log(f"HMAC_REQUIRE_HTTPS={self.settings.hmac_require_https}")
        self.log(f"REDIS_CONFIGURED={bool(self.settings.redis_url)}")
        self.log(f"POSTGRES_CONFIGURED={bool(self.settings.postgres_dsn)}")
        self.log(f"MODEL_CONFIGURED={bool(self.settings.openai_api_key and self.settings.openai_base_url)}")
        self.log(f"HMAC_CREDENTIAL_COUNT={len(credentials)}（不显示 Secret）")
        self.check(
            self.settings.runtime_mode in {"api", "all"},
            "配置中的 RUNTIME_MODE 可用于本地 API/Worker 联调",
        )
        self.check(
            self.settings.model_provider in allowed_providers,
            f"MODEL_PROVIDER={self.settings.model_provider} 在 ALLOWED_MODEL_PROVIDERS 白名单中",
        )

    def signed_headers(
        self,
        credential: Credential,
        *,
        method: str,
        path: str,
        query: str = "",
        body: bytes = b"",
    ) -> dict[str, str]:
        """使用 Runtime 同一签名实现生成一次性 HMAC 请求头。"""
        from data_agent_runtime.runtime.signing import signing_headers

        headers = signing_headers(
            access_key=credential.access_key,
            secret_key=credential.secret_key,
            method=method,
            path=path,
            query=query,
            body=body,
            nonce=secrets.token_urlsafe(18),
        )
        if body:
            headers["Content-Type"] = "application/json"
        return headers

    def request(
        self,
        credential: Credential | None,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        query: str = "",
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """发送带签名或匿名的 HTTP 请求，并保持签名 Body 与实际 Body 完全一致。"""
        request_headers = dict(headers or {})
        if credential is not None:
            request_headers.update(
                self.signed_headers(
                    credential,
                    method=method,
                    path=path,
                    query=query,
                    body=body,
                )
            )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        return self.client.request(method, url, headers=request_headers, content=body)

    @staticmethod
    def response_detail(response: httpx.Response) -> str:
        """提取不包含敏感请求头的短错误摘要。"""
        try:
            value = response.json()
        except (ValueError, json.JSONDecodeError):
            return response.text[:240].replace("\n", " ")
        if isinstance(value, dict):
            return str(value.get("detail") or value.get("status") or "")[:240]
        return str(value)[:240]

    def verify_health(self) -> None:
        """验证 API、Ready、Web 和测试 MCP 服务均已可访问。"""
        response = self.client.get(f"{self.base_url}/v1/health")
        self.check(response.status_code == 200, f"GET /v1/health 返回 200（{response.status_code}）")
        response = self.client.get(f"{self.base_url}/v1/ready")
        self.check(response.status_code == 200, f"GET /v1/ready 返回 200（{response.status_code}）")
        response = self.client.get(f"{self.web_url}/agent-chat-runtime.html")
        self.check(response.status_code == 200, f"前端页面可访问（{response.status_code}）")
        response = self.client.get(f"{self.mcp_url}/mcp")
        self.check(
            response.status_code < 500,
            f"测试 MCP 端口可达（普通 GET 返回 HTTP {response.status_code}，协议请求随后验证）",
        )

    def verify_mcp_protocol(self) -> None:
        """通过官方 MCP 客户端验证初始化、工具发现和 RAG 工具调用。"""
        try:
            asyncio.run(self._verify_mcp_protocol())
        except ImportError as exc:
            raise VerificationError("当前 Python 环境未安装 MCP 客户端依赖") from exc
        except VerificationError:
            raise
        except Exception as exc:
            detail = str(exc).replace("\n", " ")[:240]
            raise VerificationError(f"MCP 协议验证失败：{detail}") from exc

    async def _verify_mcp_protocol(self) -> None:
        """使用 Streamable HTTP 完成一次完整的 MCP JSON-RPC 会话。"""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        endpoint = f"{self.mcp_url}/mcp"
        timeout = httpx.Timeout(self.args.request_timeout, connect=5.0)
        async with AsyncExitStack() as stack:
            http_client = await stack.enter_async_context(
                httpx.AsyncClient(timeout=timeout, follow_redirects=False)
            )
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamable_http_client(endpoint, http_client=http_client)
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            initialize_result = await session.initialize()
            self.check(
                bool(getattr(initialize_result, "protocolVersion", None)),
                "MCP initialize 返回 protocolVersion",
            )
            self.check(
                getattr(initialize_result, "serverInfo", None) is not None,
                "MCP initialize 返回 serverInfo",
            )
            self.check(
                getattr(initialize_result, "capabilities", None) is not None,
                "MCP initialize 返回 capabilities",
            )

            tools_result = await session.list_tools()
            tools = list(getattr(tools_result, "tools", []) or [])
            tool_names = {
                str(getattr(tool, "name", ""))
                for tool in tools
                if getattr(tool, "name", None)
            }
            expected_tools = {
                "metadata_search",
                "search_metric_definition",
                "search_knowledge",
                "sql_validate",
                "query_readonly",
            }
            self.check(bool(tools), "MCP tools/list 返回工具列表")
            self.check(
                expected_tools.issubset(tool_names),
                "MCP tools/list 包含测试数据和 RAG 工具",
            )

            call_result = await session.call_tool(
                "search_knowledge",
                {"query": "平均电池电压", "top_k": 2},
            )
            self.check(
                not bool(getattr(call_result, "isError", False)),
                "MCP tools/call search_knowledge 执行成功",
            )
            rag_result = self._decode_mcp_tool_result(call_result)
            self.check(
                rag_result.get("source") == "test-knowledge-base",
                "RAG search_knowledge 返回测试知识库来源",
            )
            items = rag_result.get("items")
            self.check(
                isinstance(items, list) and bool(items),
                "RAG search_knowledge 实际返回知识条目",
            )
            serialized_items = json.dumps(items, ensure_ascii=False)
            self.check(
                "kb-vehicle-battery-001" in serialized_items
                or "车辆电池电压分析口径" in serialized_items,
                "RAG 结果包含电池电压知识内容",
            )

    @staticmethod
    def _decode_mcp_tool_result(call_result: Any) -> dict[str, Any]:
        """把 MCP 工具结果兼容解析为 JSON 对象，便于验证业务返回值。"""
        structured = getattr(call_result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured

        content = getattr(call_result, "content", []) or []
        for item in content:
            text = getattr(item, "text", None)
            if not isinstance(text, str):
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise VerificationError("MCP tools/call 返回中没有可解析的 JSON 工具结果")

    def build_run_payload(self) -> tuple[dict[str, Any], bytes]:
        """读取本地示例 Snapshot，生成不带伪造身份的唯一 Run 请求体。"""
        source = PROJECT_ROOT / "examples" / "run.json"
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VerificationError(f"无法读取 {source}") from exc
        if not isinstance(payload, dict):
            raise VerificationError("examples/run.json 必须是 JSON 对象")
        payload["run_id"] = self.run_id
        payload["session_id"] = self.session_id
        # 由 API 根据认证 Principal 注入 user_context，避免示例文件身份与 .env 不一致。
        payload.pop("user_context", None)
        payload.pop("internal_token", None)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return payload, body

    def verify_authentication_failures(self, credential: Credential) -> None:
        """验证缺少签名、错误签名和 Nonce 重放都会被拒绝。"""
        path = "/v1/runs/not-found"
        response = self.request(None, "GET", path)
        self.check(response.status_code == 401, f"缺少 HMAC 请求头返回 401（{response.status_code}）")

        headers = self.signed_headers(credential, method="GET", path=path)
        headers["X-Signature"] = "invalid-signature"
        response = self.client.get(f"{self.base_url}{path}", headers=headers)
        self.check(response.status_code == 401, f"错误 HMAC 签名返回 401（{response.status_code}）")

        body_hash_headers = self.signed_headers(credential, method="GET", path=path)
        body_hash_headers["X-Content-SHA256"] = "0" * 64
        response = self.client.get(f"{self.base_url}{path}", headers=body_hash_headers)
        self.check(response.status_code == 401, f"错误 Body SHA-256 返回 401（{response.status_code}）")

        replay_headers = self.signed_headers(credential, method="GET", path=path)
        first = self.client.get(f"{self.base_url}{path}", headers=replay_headers)
        second = self.client.get(f"{self.base_url}{path}", headers=replay_headers)
        self.check(first.status_code == 404, f"有效签名请求先通过认证再返回资源 404（{first.status_code}）")
        self.check(second.status_code == 401, f"重复 Nonce 返回 401（{second.status_code}）")

    def verify_scope_and_identity_failures(
        self, credentials: list[Credential], payload: dict[str, Any]
    ) -> None:
        """验证 Scope 不足和请求体伪造用户上下文都会被拒绝。"""
        no_write = next(
            (
                item
                for item in credentials
                if "runs:write" not in item.scopes and "*" not in item.scopes
            ),
            None,
        )
        if no_write is None:
            self.skip("没有 Scope 不足的调用方，跳过 runs:write 拒绝验证")
        else:
            denied = copy.deepcopy(payload)
            denied["run_id"] = f"verify-denied-{uuid.uuid4().hex}"
            body = json.dumps(denied, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            response = self.request(no_write, "POST", "/v1/runs", body=body)
            self.check(response.status_code == 403, f"缺少 runs:write Scope 返回 403（{response.status_code}）")

        assert self.run_credential is not None
        mismatch = copy.deepcopy(payload)
        mismatch["run_id"] = f"verify-mismatch-{uuid.uuid4().hex}"
        mismatch["user_context"] = {
            "tenant_id": "tenant-not-authorized",
            "user_id": "user-not-authorized",
        }
        body = json.dumps(mismatch, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = self.request(self.run_credential, "POST", "/v1/runs", body=body)
        self.check(response.status_code == 403, f"伪造 user_context 返回 403（{response.status_code}）")

    def submit_run(self, payload: dict[str, Any], body: bytes) -> None:
        """提交真实 AgentSnapshot，确认 API 返回 Accepted 或待审批状态。"""
        assert self.run_credential is not None
        response = self.request(self.run_credential, "POST", "/v1/runs", body=body)
        self.check(response.status_code == 202, f"POST /v1/runs 返回 202（{response.status_code}）")
        try:
            accepted = response.json()
        except ValueError as exc:
            raise VerificationError("/v1/runs 返回的不是 JSON") from exc
        self.check(accepted.get("run_id") == self.run_id, "Accepted 响应中的 run_id 与请求一致")
        self.check(
            accepted.get("status") in {"ACCEPTED", "PENDING_APPROVAL"},
            f"Run 初始状态为 {accepted.get('status')}",
        )
        if accepted.get("status") == "PENDING_APPROVAL":
            approver = self.run_credential
            if "runs:approve" not in approver.scopes and "*" not in approver.scopes:
                raise VerificationError("Run 需要审批，但当前调用方没有 runs:approve Scope")
            response = self.request(approver, "POST", f"/v1/runs/{self.run_id}/approve")
            self.check(response.status_code == 200, f"审批 Run 返回 200（{response.status_code}）")

    def wait_for_terminal(self) -> dict[str, Any]:
        """轮询 Run 状态，确认 Worker 已从 Redis Stream 消费并完成状态投影。"""
        assert self.run_credential is not None
        deadline = time.monotonic() + self.args.run_timeout
        last_status = ""
        while time.monotonic() < deadline:
            response = self.request(self.run_credential, "GET", f"/v1/runs/{self.run_id}")
            if response.status_code != 200:
                raise VerificationError(
                    f"查询 Run 状态失败：HTTP {response.status_code}，{self.response_detail(response)}"
                )
            state = response.json()
            status = str(state.get("status") or "")
            if status != last_status:
                self.log(f"Run 状态：{status or 'UNKNOWN'}")
                last_status = status
            if status in TERMINAL_STATUSES:
                self.run_state = state
                if status == "COMPLETED":
                    self.check(True, "Worker 执行成功，Run 进入 COMPLETED")
                elif self.args.allow_run_failure:
                    self.skip(f"Run 进入 {status}；按 --allow-run-failure 继续验证队列和事件闭环")
                else:
                    self.check(False, f"Worker 执行失败，Run 进入 {status}")
                return state
            time.sleep(self.args.poll_interval)
        raise VerificationError(f"Run 在 {self.args.run_timeout:g} 秒内没有进入终态")

    def verify_idempotency(self) -> None:
        """复用相同 run_id 和相同请求体，确认重复提交不会重复入队。"""
        assert self.run_credential is not None and self.run_body is not None
        response = self.request(self.run_credential, "POST", "/v1/runs", body=self.run_body)
        self.check(response.status_code == 409, f"重复 run_id 返回 409（{response.status_code}）")

    def verify_sse(self) -> None:
        """读取 SSE 直到服务端在终态事件后关闭，并检查 id/event/data 三类字段。"""
        assert self.run_credential is not None
        path = f"/v1/runs/{self.run_id}/events"
        headers = self.signed_headers(self.run_credential, method="GET", path=path)
        timeout = httpx.Timeout(self.args.sse_read_timeout, connect=5.0)
        ids: list[str] = []
        event_names: list[str] = []
        terminal_seen = False
        data_seen = False
        closed_naturally = False
        started = time.monotonic()
        try:
            with self.client.stream("GET", f"{self.base_url}{path}", headers=headers, timeout=timeout) as response:
                self.check(response.status_code == 200, f"SSE 返回 200（{response.status_code}）")
                content_type = response.headers.get("content-type", "")
                self.check("text/event-stream" in content_type, "SSE Content-Type 为 text/event-stream")
                for line in response.iter_lines():
                    if time.monotonic() - started > self.args.sse_timeout:
                        raise VerificationError("SSE 超过整体超时时间仍未关闭")
                    if not line:
                        continue
                    if line.startswith("id:"):
                        value = line[3:].strip()
                        if value:
                            ids.append(value)
                    elif line.startswith("event:"):
                        event_names.append(line[6:].strip())
                    elif line.startswith("data:"):
                        data_seen = True
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if event.get("event_type") in TERMINAL_EVENTS:
                            terminal_seen = True
                closed_naturally = True
        except httpx.ReadTimeout as exc:
            raise VerificationError("SSE 未在终态事件后自动关闭") from exc
        self.check(bool(ids), "SSE 每条事件包含非空 id 字段")
        self.check(bool(event_names), "SSE 至少输出一条 event 字段")
        self.check(data_seen, "SSE 至少输出一条 data 字段")
        self.check(terminal_seen, "SSE 输出了 Run 终态事件")
        self.check(closed_naturally, "SSE 读取到终态后自然关闭连接")

    def verify_session(self) -> None:
        """读取 Run 对应 Session，确认 Worker 写入了可查询的对话历史。"""
        assert self.run_credential is not None
        if self.run_state and self.run_state.get("status") != "COMPLETED":
            self.skip("Run 未成功完成，跳过 Agent 回复内容的 Session 验证")
            return
        if "sessions:read" not in self.run_credential.scopes and "*" not in self.run_credential.scopes:
            self.skip("Run 调用方没有 sessions:read，跳过 Session 历史验证")
            return
        response = self.request(
            self.run_credential,
            "GET",
            f"/v1/sessions/{self.session_id}/messages",
        )
        self.check(response.status_code == 200, f"读取 Session 消息返回 200（{response.status_code}）")
        messages = response.json()
        self.check(isinstance(messages, list) and bool(messages), "Session 至少包含一条消息")
        self.check(
            any(item.get("role") == "user" for item in messages if isinstance(item, dict)),
            "Session 历史包含用户消息",
        )
        self.check(
            any(item.get("role") == "assistant" for item in messages if isinstance(item, dict)),
            "Session 历史包含 Agent 消息",
        )

    def verify_memory(self, credentials: list[Credential]) -> None:
        """执行 Memory 的写入、读取和删除闭环验证。"""
        memory = self.choose_credential(credentials, {"memory:read", "memory:write"})
        if memory is None:
            self.skip("没有同时具备 memory:read 和 memory:write 的调用方，跳过 Memory 验证")
            return
        self.memory_credential = memory
        memory_id = f"verify-memory-{uuid.uuid4().hex}"
        path_prefix = f"/v1/memories/{memory.tenant_id}/{memory.user_id}"
        payload = {
            "memory_id": memory_id,
            "tenant_id": memory.tenant_id,
            "user_id": memory.user_id,
            "memory_type": "fact",
            "key": "verify_local_stack",
            "content": "端到端验证临时记忆",
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = self.request(memory, "PUT", f"{path_prefix}/{memory_id}", body=body)
        self.check(response.status_code == 200, f"Memory 写入返回 200（{response.status_code}）")
        response = self.request(memory, "GET", path_prefix)
        self.check(response.status_code == 200, f"Memory 查询返回 200（{response.status_code}）")
        values = response.json()
        self.check(any(item.get("memory_id") == memory_id for item in values), "查询结果包含刚写入的 Memory")
        response = self.request(memory, "DELETE", f"{path_prefix}/{memory_id}")
        self.check(response.status_code == 200, f"Memory 删除返回 200（{response.status_code}）")
        response = self.request(memory, "GET", path_prefix)
        self.check(response.status_code == 200, f"删除后再次查询 Memory 返回 200（{response.status_code}）")
        self.check(
            not any(item.get("memory_id") == memory_id for item in response.json()),
            "删除后查询结果不再包含临时 Memory",
        )

    def run(self) -> None:
        """按 API 接入、队列执行、事件读取和资源接口顺序执行全部验证。"""
        credentials = self.load_credentials()
        self.show_configuration(credentials)
        self.verify_health()
        self.verify_mcp_protocol()

        run_credential = self.choose_credential(credentials, {"runs:write", "runs:read"})
        if run_credential is None:
            raise VerificationError("没有同时具备 runs:write 和 runs:read 的调用方")
        self.run_credential = run_credential
        self.log(f"使用 Access Key={run_credential.access_key}（Secret 不显示）")
        self.verify_authentication_failures(run_credential)

        payload, body = self.build_run_payload()
        self.verify_scope_and_identity_failures(credentials, payload)
        if self.args.smoke:
            self.log("SMOKE 模式不提交真实模型 Run；基础服务和鉴权验证已完成")
            self.verify_memory(credentials)
            return

        self.run_payload = payload
        self.run_body = body
        self.submit_run(payload, body)
        self.wait_for_terminal()
        self.verify_sse()
        self.verify_idempotency()
        self.verify_session()
        self.verify_memory(credentials)

        self.log(f"完成：{self.checks} 项通过，{self.skips} 项跳过，run_id={self.run_id}")


def parse_args() -> argparse.Namespace:
    """解析端到端验证脚本参数。"""
    parser = argparse.ArgumentParser(description="验证 Python Agent Runtime 本地联调全流程")
    parser.add_argument("--env-file", default=os.environ.get("DATA_AGENT_ENV_FILE", str(PROJECT_ROOT / ".env")))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--mcp-url", default=None)
    parser.add_argument("--web-url", default=None)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--run-timeout", type=float, default=180.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--sse-timeout", type=float, default=30.0)
    parser.add_argument("--sse-read-timeout", type=float, default=5.0)
    parser.add_argument("--allow-run-failure", action="store_true", help="Run 失败时继续验证状态、SSE 和幂等链路")
    parser.add_argument("--smoke", action="store_true", help="只验证健康、鉴权和资源接口，不执行真实模型 Run")
    return parser.parse_args()


def main() -> int:
    """运行验证器并以适合 CI 的退出码结束。"""
    args = parse_args()
    verifier: LocalStackVerifier | None = None
    try:
        verifier = LocalStackVerifier(args)
        verifier.run()
    except (VerificationError, httpx.HTTPError, ValueError) as exc:
        print(f"[verify-e2e][ERROR] {exc}", file=sys.stderr, flush=True)
        print("[verify-e2e][ERROR] 请查看 .local/logs/api.log 和 .local/logs/worker.log。", file=sys.stderr)
        return 1
    finally:
        if verifier is not None:
            verifier.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
