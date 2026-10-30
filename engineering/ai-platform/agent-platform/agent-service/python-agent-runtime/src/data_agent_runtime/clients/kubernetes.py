"""本文件模块职责：Kubernetes Sandbox Provider 实现模块。

本模块通过 kubectl 结构化创建和回收临时 Pod 及必要的 NetworkPolicy，并在 Pod 内执行受控命令和文件操作；网络、资源和清理策略必须由平台配置与 Snapshot 共同约束。

Kubernetes Pod backed SandboxProvider.

The provider uses ``kubectl`` only as a structured Kubernetes control-plane
client. User commands are passed as argv to ``kubectl exec --`` and are never
interpreted by a local shell.

"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
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


class KubernetesSandboxProvider:
    """为一次 Agent Run 创建一个可销毁的 Kubernetes Pod。

    Provider 可同时配置拒绝出站的网络策略；它只调用 Kubernetes 控制面，不在 Runtime
    进程中直接运行调用方程序。
    """

    def __init__(
        self,
        settings: Settings,
        sandbox: SandboxConfig,
        context: SandboxRunContext,
    ) -> None:
        """初始化 KubernetesSandboxProvider，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.settings = settings
        self.sandbox = sandbox
        self.context = context
        suffix = uuid.uuid4().hex[:16]
        self.pod_name = f"data-agent-{suffix}"
        self.policy_name = f"{self.pod_name}-egress"
        self._created = False
        self._resources_applied = False
        self._closed = False
        # 多个 Agent Tool 并发调用时，串行化同一 Run 的创建和销毁转换。
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_created(self) -> bool:
        """处理“is_created”业务步骤，完成输入校验、依赖调用和结果返回。"""
        return self._created

    def _control_timeout(self) -> float:
        """执行“_control_timeout”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        return max(
            self.settings.kubernetes_control_timeout_seconds,
            float(self.sandbox.timeout_seconds),
        )

    def _kubectl_prefix(self) -> list[str]:
        """执行“_kubectl_prefix”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        args = [self.settings.kubectl_binary]
        if self.settings.kubernetes_kubeconfig:
            args.extend(["--kubeconfig", self.settings.kubernetes_kubeconfig])
        if self.settings.kubernetes_context:
            args.extend(["--context", self.settings.kubernetes_context])
        args.extend(["-n", self.settings.kubernetes_namespace])
        return args

    async def _kubectl(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: float | None = None,
    ):
        """执行“_kubectl”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self._closed:
            raise SandboxGatewayError("Kubernetes Sandbox provider is already closed")
        result = await run_control_command(
            [*self._kubectl_prefix(), *args],
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds or self._control_timeout(),
        )
        if result.timed_out:
            raise LocalSandboxError("kubectl control command timed out")
        return result

    @staticmethod
    def _label(value: str) -> str:
        """执行“_label”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
        return (normalized or "unknown")[:63].rstrip("-") or "unknown"

    def _pod_manifest(self) -> dict[str, object]:
        """执行“_pod_manifest”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        image = self.sandbox.image or self.settings.kubernetes_default_image
        if self.sandbox.image_digest:
            image = f"{image}@{self.sandbox.image_digest}"
        resources: dict[str, dict[str, str]] = {}
        limits: dict[str, str] = {}
        requests: dict[str, str] = {}
        if self.sandbox.cpu_limit is not None:
            limits["cpu"] = str(self.sandbox.cpu_limit)
            requests["cpu"] = str(min(self.sandbox.cpu_limit, 1.0))
        if self.sandbox.memory_limit_mb is not None:
            limits["memory"] = f"{self.sandbox.memory_limit_mb}Mi"
            requests["memory"] = f"{min(self.sandbox.memory_limit_mb, 512)}Mi"
        if limits:
            resources = {"limits": limits, "requests": requests}

        disk_mb = self.sandbox.disk_limit_mb or 10_240
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.pod_name,
                "labels": {
                    "app.kubernetes.io/name": "data-agent-sandbox",
                    "data-agent/run-id": self._label(self.context.run_id),
                    "data-agent/tenant-id": self._label(self.context.tenant_id),
                },
            },
            "spec": {
                "restartPolicy": "Never",
                "automountServiceAccountToken": False,
                "terminationGracePeriodSeconds": 1,
                "hostNetwork": False,
                "hostPID": False,
                "hostIPC": False,
                "securityContext": {
                    "runAsNonRoot": True,
                    "runAsUser": 65532,
                    "runAsGroup": 65532,
                    "fsGroup": 65532,
                    "seccompProfile": {"type": "RuntimeDefault"},
                },
                "containers": [
                    {
                        "name": "sandbox",
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "command": ["sh", "-c", "while true; do sleep 3600; done"],
                        "workingDir": "/workspace",
                        "stdin": True,
                        "tty": False,
                        "resources": resources,
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "volumeMounts": [
                            {"name": "workspace", "mountPath": "/workspace"},
                            {"name": "tmp", "mountPath": "/tmp"},
                        ],
                    }
                ],
                "volumes": [
                    {
                        "name": "workspace",
                        "emptyDir": {"sizeLimit": f"{disk_mb}Mi"},
                    },
                    {
                        "name": "tmp",
                        "emptyDir": {
                            "medium": "Memory",
                            "sizeLimit": f"{min(disk_mb, 1024)}Mi",
                        },
                    },
                ],
            },
        }

    def _network_policy(self) -> dict[str, object] | None:
        """执行“_network_policy”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if self.sandbox.network_mode == "full":
            return None
        # 默认拒绝出站；后续可由平台 Gateway 增加 restricted 白名单。
        # 本 Provider 不接受 AgentSnapshot 提供的任意 CIDR。
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": self.policy_name},
            "spec": {
                "podSelector": {"matchLabels": {"data-agent/pod": self.pod_name}},
                "policyTypes": ["Egress"],
                "egress": [],
            },
        }

    async def ensure_created(self) -> SandboxCreateResponse:
        """按需创建并返回隔离 Sandbox；重复调用时复用已经创建的会话。"""
        async with self._lifecycle_lock:
            if self._created:
                return SandboxCreateResponse(sandbox_id=self.pod_name, status="READY")
            manifest = self._pod_manifest()
            # 增加供可选 NetworkPolicy 使用的唯一选择器标签。
            manifest["metadata"]["labels"]["data-agent/pod"] = self.pod_name  # type: ignore[index]
            policy = self._network_policy()
            documents = [manifest] + ([policy] if policy else [])
            payload = "\n---\n".join(json.dumps(item) for item in documents).encode()
            # 调用 kubectl 前先标记需要清理；如果 API Server 已接受请求但后续超时，
            # 仍按确定性名称删除可能已经创建的 Pod/NetworkPolicy。
            self._resources_applied = True
            try:
                applied = await self._kubectl(["apply", "-f", "-"], input_bytes=payload)
                if applied.returncode != 0:
                    raise command_failure(applied, provider="kubectl apply")
                waited = await self._kubectl(
                    [
                        "wait",
                        "--for=condition=Ready",
                        f"pod/{self.pod_name}",
                        f"--timeout={max(1, int(self.sandbox.timeout_seconds))}s",
                    ],
                    timeout_seconds=self._control_timeout(),
                )
                if waited.returncode != 0:
                    raise command_failure(waited, provider="kubectl wait")
            except (Exception, asyncio.CancelledError):
                await asyncio.shield(self._destroy_resources())
                raise
            self._created = True
            return SandboxCreateResponse(sandbox_id=self.pod_name, status="READY")

    async def _exec(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: float | None = None,
    ):
        """执行“_exec”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        await self.ensure_created()
        command = ["exec"]
        if input_bytes is not None:
            command.append("-i")
        command.extend([self.pod_name, "-c", "sandbox", "--", *args])
        return await self._kubectl(
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
            raise command_failure(result, provider="kubectl exec tar")
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
            raise command_failure(result, provider="kubectl exec tar")
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
            await self.destroy()
            self._closed = True
            return SandboxCommandResult(
                status="TIMED_OUT",
                stdout=stdout,
                stderr=stderr or "Kubernetes command timed out",
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
            artifact_id=f"k8s-artifact-{uuid.uuid4().hex[:16]}",
            file_name=name or path.rsplit("/", 1)[-1],
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def _destroy_resources(self) -> None:
        """尽力删除当前 Provider 创建的 Pod 和 NetworkPolicy 等全部资源。

        清理过程即使遇到删除失败也不会覆盖原始业务异常；调用方可以通过日志、
        指标或平台控制器发现残留资源，并依靠资源 TTL、标签和运维策略继续回收。
        """
        if not self._resources_applied:
            return
        errors: list[Exception] = []
        for kind, name in (("pod", self.pod_name), ("networkpolicy", self.policy_name)):
            try:
                result = await run_control_command(
                    [
                        *self._kubectl_prefix(),
                        "delete",
                        kind,
                        name,
                        "--ignore-not-found",
                        "--wait=false",
                    ],
                    timeout_seconds=self._control_timeout(),
                )
                if result.returncode != 0:
                    errors.append(command_failure(result, provider=f"kubectl delete {kind}"))
            except (LocalSandboxError, SandboxGatewayError) as exc:
                errors.append(exc)
        self._created = False
        self._resources_applied = False
        # 清理故意采用尽力而为策略；原始操作错误对调用方更有价值，
        # 清理失败由 Provider 日志和指标供生命周期负责人观察。
        if errors:
            return

    async def destroy(self) -> None:
        """销毁底层 Sandbox 资源并使后续操作失效，确保容器、Pod 或远程会话不会泄漏。"""
        async with self._lifecycle_lock:
            await self._destroy_resources()

    async def aclose(self) -> None:
        """关闭网络客户端并销毁 Sandbox；该操作设计为幂等，便于成功、失败和取消路径统一调用。"""
        if self._closed:
            return
        try:
            await self.destroy()
        finally:
            self._closed = True
