"""本文件模块职责：调用方提供的 Skill Bundle 下载、校验、缓存和物化模块。

本模块负责从对象存储地址获取 Skill 包，校验大小、文件数、路径和允许的主机，解压到受控缓存或工作区，并防止压缩包路径穿越和资源耗尽。

Download, validate, cache, and materialize caller-provided Skill bundles.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import shutil
import stat
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.signing import signing_headers
from data_agent_runtime.schemas import SkillSnapshot

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SkillArtifactError(RuntimeError):
    """Skill Artifact 无法安全下载、校验、解压或加载时抛出的异常。"""


@dataclass(frozen=True)
class MaterializedSkills:
    """一次 Run 中已通过摘要和路径校验的 Skill 本地只读目录。

    ``skill_paths`` 只保存已物化的受控路径，调用方不能借此访问临时目录之外的宿主机文件。
    """

    workspace_root: Path
    skill_sources: list[str]
    skill_paths: dict[str, str]


class SkillArtifactManager:
    """把不可变 Skill 快照解析为每次 Run 独立的只读源码目录。

    管理器负责 URL 主机白名单、可选 HMAC 下载签名、SHA-256、归档大小和路径安全校验；它
    不执行 Skill 中的任意命令。
    """

    def __init__(self, settings: Settings):
        """初始化 SkillArtifactManager，保存依赖对象、运行配置和后续方法所需的生命周期状态。"""
        self.settings = settings
        self._locks: dict[str, asyncio.Lock] = {}

    async def materialize(
        self,
        skills: list[SkillSnapshot],
        *,
        tenant_id: str,
        session_id: str,
        run_id: str,
        workspace_enabled: bool,
        workspace_id: str | None = None,
    ) -> MaterializedSkills:
        """下载、校验、解压并物化本次 Agent Run 使用的 Skill，返回可传给 DeepAgents 的 Skill 路径和工作区。"""
        should_create_workspace = workspace_enabled or bool(skills)
        workspace_root = self._run_workspace(
            tenant_id=tenant_id,
            session_id=session_id,
            run_id=run_id,
            workspace_id=workspace_id,
        )
        if should_create_workspace:
            await asyncio.to_thread(workspace_root.mkdir, parents=True, exist_ok=True)

        skill_paths: dict[str, str] = {}
        if not skills:
            return MaterializedSkills(workspace_root, [], skill_paths)

        skills_root = workspace_root / "skills"
        await asyncio.to_thread(skills_root.mkdir, parents=True, exist_ok=True)
        for skill in skills:
            skill_id = self._safe_component(skill.id, "skill id")
            if skill.bundle_url:
                source_dir = await self._ensure_cached(skill)
            elif skill.content:
                source_dir = await self._materialize_inline(skill, tenant_id=tenant_id)
            else:
                raise SkillArtifactError(
                    f"skill {skill.id!r} has neither bundle_url nor content"
                )

            target_dir = skills_root / skill_id
            await asyncio.to_thread(self._replace_tree, source_dir, target_dir)
            skill_paths[skill.id] = f"/skills/{skill_id}"

        # DeepAgents SkillsMiddleware 要求源码目录按 Skill 分子目录，每个目录包含 SKILL.md。
        return MaterializedSkills(workspace_root, ["/skills"], skill_paths)

    def _run_workspace(
        self,
        *,
        tenant_id: str,
        session_id: str,
        run_id: str,
        workspace_id: str | None,
    ) -> Path:
        """执行“_run_workspace”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        root = Path(self.settings.workspace_root).expanduser().resolve()
        tenant = self._safe_component(tenant_id, "tenant id")
        session = self._safe_component(session_id, "session id")
        run = self._safe_component(workspace_id or run_id, "run/workspace id")
        return root / tenant / session / run

    async def _ensure_cached(self, skill: SkillSnapshot) -> Path:
        """执行“_ensure_cached”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if not skill.bundle_url:
            raise SkillArtifactError(f"skill {skill.id!r} has no bundle URL")

        version = self._safe_component(str(skill.version), "skill version")
        skill_id = self._safe_component(skill.id, "skill id")
        expected_sha = self._normalize_sha256(skill.sha256)
        cache_key = (
            expected_sha or hashlib.sha256(skill.bundle_url.encode()).hexdigest()
        )
        cache_dir = (
            Path(self.settings.skill_cache_dir).expanduser().resolve()
            / skill_id
            / version
            / cache_key
        )
        marker = cache_dir / ".complete"
        if marker.exists():
            self._validate_skill_entry(cache_dir, skill)
            return self._entry_dir(cache_dir, skill)

        lock = self._locks.setdefault(str(cache_dir), asyncio.Lock())
        async with lock:
            if marker.exists():
                self._validate_skill_entry(cache_dir, skill)
                return self._entry_dir(cache_dir, skill)

            cache_dir.parent.mkdir(parents=True, exist_ok=True)
            temp_root = Path(
                tempfile.mkdtemp(prefix=f".{cache_dir.name}-", dir=cache_dir.parent)
            )
            bundle_path = temp_root / "bundle"
            extracted_path = temp_root / "extracted"
            try:
                await self._download(skill, bundle_path)
                actual_sha = await asyncio.to_thread(self._sha256_file, bundle_path)
                if expected_sha and actual_sha != expected_sha:
                    raise SkillArtifactError(
                        f"skill {skill.id!r} SHA256 mismatch: expected {expected_sha}, got {actual_sha}"
                    )
                await asyncio.to_thread(
                    self._safe_extract,
                    bundle_path,
                    extracted_path,
                )
                self._validate_skill_entry(extracted_path, skill)
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                os.replace(extracted_path, cache_dir)
                marker.write_text(actual_sha, encoding="utf-8")
                return self._entry_dir(cache_dir, skill)
            except Exception:
                shutil.rmtree(cache_dir, ignore_errors=True)
                raise
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)

    def _validate_bundle_url(self, value: str | None) -> None:
        """执行“_validate_bundle_url”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if not value:
            raise SkillArtifactError("Skill bundle URL is required")
        parsed = urlparse(value)
        if parsed.username or parsed.password:
            raise SkillArtifactError("Skill bundle URL must not contain credentials")
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise SkillArtifactError("Skill bundle URL must be an absolute HTTP(S) URL")

        local = self.settings.app_env.lower() in {"local", "dev", "development"}
        if parsed.scheme == "http" and not (
            local
            and self.settings.skill_allow_http_local
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise SkillArtifactError("Skill bundle URL must use HTTPS")

        allowed_hosts = {
            host.strip().lower()
            for host in self.settings.skill_allowed_hosts.split(",")
            if host.strip()
        }
        if not local and not allowed_hosts:
            raise SkillArtifactError(
                "SKILL_ALLOWED_HOSTS must be configured outside local development"
            )
        if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
            raise SkillArtifactError(
                f"Skill bundle host is not allowed: {parsed.hostname}"
            )

    def _download_headers(self, bundle_url: str) -> dict[str, str]:
        """根据部署配置生成 Skill Artifact 下载 Header。

        配置完整 AK/SK 时，使用与 Runtime 入站认证一致的 HMAC-SHA256
        协议访问对象存储适配层或 Artifact Gateway；没有配置任何凭证时
        不附加认证 Header，直接访问 HTTPS 公开 URL 或预签名 URL。
        """
        access_key = self.settings.skill_artifact_access_key
        secret_key = self.settings.skill_artifact_secret_key
        if bool(access_key) != bool(secret_key):
            raise SkillArtifactError(
                "SKILL_ARTIFACT_ACCESS_KEY and SKILL_ARTIFACT_SECRET_KEY must be configured together"
            )
        if not access_key:
            return {}

        parsed = urlparse(bundle_url)
        return signing_headers(
            access_key=access_key,
            secret_key=secret_key or "",
            method="GET",
            path=parsed.path or "/",
            query=parsed.query,
            body=b"",
            timestamp=str(int(time.time())),
            nonce=secrets.token_urlsafe(18),
        )

    async def _download(self, skill: SkillSnapshot, destination: Path) -> None:
        """执行“_download”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        self._validate_bundle_url(skill.bundle_url)
        timeout = httpx.Timeout(self.settings.skill_download_timeout_seconds)
        limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
        try:
            # 不跟随重定向；带签名的对象 URL 不能把 Runtime 重定向到未批准的 Host。
            headers = self._download_headers(skill.bundle_url or "")
            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    follow_redirects=False,
                ) as client,
                client.stream(
                    "GET",
                    skill.bundle_url,
                    headers=headers,
                ) as response,
            ):
                response.raise_for_status()
                declared = response.headers.get("content-length")
                if declared and int(declared) > self.settings.skill_max_bundle_bytes:
                    raise SkillArtifactError(
                        f"skill {skill.id!r} bundle exceeds configured size limit"
                    )
                if (
                    skill.size_bytes
                    and skill.size_bytes > self.settings.skill_max_bundle_bytes
                ):
                    raise SkillArtifactError(
                        f"skill {skill.id!r} size_bytes exceeds configured limit"
                    )
                size = 0
                with destination.open("wb") as output:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > self.settings.skill_max_bundle_bytes:
                            raise SkillArtifactError(
                                f"skill {skill.id!r} bundle exceeds configured size limit"
                            )
                        output.write(chunk)
                if skill.size_bytes and size != skill.size_bytes:
                    raise SkillArtifactError(
                        f"skill {skill.id!r} size mismatch: expected {skill.size_bytes}, got {size}"
                    )
        except httpx.HTTPError as exc:
            raise SkillArtifactError(
                f"failed to download Skill {skill.id!r}: {exc}"
            ) from exc

    async def _materialize_inline(
        self, skill: SkillSnapshot, *, tenant_id: str = "local"
    ) -> Path:
        """把内联 Skill 落盘到按租户与内容摘要隔离的目录。

        目录必须同时包含租户与内容摘要：只按 ``id + version`` 缓存会让不同租户
        （或同租户改了内容但版本未变）互相覆盖，构成跨租户 Prompt 投毒面。
        """
        skill_id = self._safe_component(skill.id, "skill id")
        version = self._safe_component(str(skill.version), "skill version")
        tenant = self._safe_component(tenant_id, "tenant id")
        content = skill.content or ""
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        root = (
            Path(self.settings.workspace_root).expanduser().resolve() / ".inline-skills"
        )
        target = root / tenant / f"{skill_id}-{version}-{digest}"
        if target.exists():
            return target
        target.mkdir(parents=True, exist_ok=True)
        if not content.lstrip().startswith("---"):
            content = (
                "---\n"
                f"name: {skill_id}\n"
                f"description: Skill {skill_id}\n"
                "---\n\n"
                f"{content}\n"
            )
        (target / "SKILL.md").write_text(content, encoding="utf-8")
        return target

    def _entry_dir(self, extracted_root: Path, skill: SkillSnapshot) -> Path:
        """执行“_entry_dir”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        entry_path = skill.entry_path
        if entry_path:
            relative = self._safe_relative_path(entry_path)
            target = extracted_root / relative
            if not target.is_dir():
                raise SkillArtifactError(
                    f"Skill {skill.id!r} entry_path does not point to a directory: {entry_path}"
                )
            return target

        candidates = list(extracted_root.rglob("SKILL.md"))
        if len(candidates) != 1:
            raise SkillArtifactError(
                f"Skill {skill.id!r} must contain exactly one SKILL.md when entry_path is omitted"
            )
        return candidates[0].parent

    def _validate_skill_entry(self, extracted_root: Path, skill: SkillSnapshot) -> None:
        """执行“_validate_skill_entry”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        entry = self._entry_dir(extracted_root, skill)
        if not (entry / "SKILL.md").is_file():
            raise SkillArtifactError(f"Skill {skill.id!r} is missing SKILL.md")

    def _safe_extract(self, archive: Path, destination: Path) -> None:
        """执行“_safe_extract”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        destination.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(archive):
            self._safe_extract_zip(archive, destination)
        elif tarfile.is_tarfile(archive):
            self._safe_extract_tar(archive, destination)
        else:
            raise SkillArtifactError("Skill bundle must be a ZIP or TAR archive")

    def _safe_extract_zip(self, archive: Path, destination: Path) -> None:
        """执行“_safe_extract_zip”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        total = 0
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            self._check_file_count(members)
            for member in members:
                relative = self._safe_relative_path(member.filename)
                mode = (member.external_attr >> 16) & 0o170000
                if stat.S_ISLNK(mode):
                    raise SkillArtifactError(
                        f"unsupported symbolic link in Skill bundle: {member.filename}"
                    )
                target = destination / relative
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += member.file_size
                self._check_extracted_size(total)
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_file, target.open("wb") as output:
                    shutil.copyfileobj(input_file, output, length=1024 * 1024)

    def _safe_extract_tar(self, archive: Path, destination: Path) -> None:
        """执行“_safe_extract_tar”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        total = 0
        with tarfile.open(archive) as source:
            members = source.getmembers()
            self._check_file_count(members)
            for member in members:
                relative = self._safe_relative_path(member.name)
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise SkillArtifactError(
                        f"unsupported archive entry in Skill bundle: {member.name}"
                    )
                total += member.size
                self._check_extracted_size(total)
                target.parent.mkdir(parents=True, exist_ok=True)
                input_file = source.extractfile(member)
                if input_file is None:
                    raise SkillArtifactError(
                        f"cannot read archive entry: {member.name}"
                    )
                with input_file, target.open("wb") as output:
                    shutil.copyfileobj(input_file, output, length=1024 * 1024)
                target.chmod(member.mode & 0o777)

    def _check_file_count(self, members: list[object]) -> None:
        """执行“_check_file_count”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if len(members) > self.settings.skill_max_files:
            raise SkillArtifactError("Skill bundle contains too many files")

    def _check_extracted_size(self, total: int) -> None:
        """执行“_check_extracted_size”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if total > self.settings.skill_max_extracted_bytes:
            raise SkillArtifactError(
                "Skill bundle expands beyond configured size limit"
            )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """执行“_sha256_file”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalize_sha256(value: str | None) -> str | None:
        """执行“_normalize_sha256”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if value is None:
            return None
        normalized = value.lower().removeprefix("sha256:").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise SkillArtifactError("sha256 must be a 64-character hexadecimal digest")
        return normalized

    @staticmethod
    def _safe_relative_path(value: str) -> Path:
        """执行“_safe_relative_path”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise SkillArtifactError(f"unsafe Skill archive path: {value!r}")
        return Path(*path.parts)

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        """执行“_safe_component”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if not value or not _SAFE_ID.fullmatch(value):
            raise SkillArtifactError(f"invalid {label}: {value!r}")
        return value

    @staticmethod
    def _replace_tree(source: Path, target: Path) -> None:
        """执行“_replace_tree”内部辅助步骤，完成必要的校验、转换和资源处理。"""
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
