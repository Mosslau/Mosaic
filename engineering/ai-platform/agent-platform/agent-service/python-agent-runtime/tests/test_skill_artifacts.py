"""本文件模块职责：Skill Artifact 下载、校验、解压、缓存和物化测试。

测试覆盖压缩包路径穿越、大小/文件数限制、允许主机、重复缓存和工作区输出等安全边界。
"""

import asyncio
import io
import tarfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.signing import verify_signature
from data_agent_runtime.runtime.skill_artifacts import (
    SkillArtifactError,
    SkillArtifactManager,
)
from data_agent_runtime.schemas import SkillSnapshot


def test_skill_artifact_download_authentication_modes(tmp_path):
    """验证 Skill Bundle 下载认证按部署配置选择直拉或 HMAC。"""
    bundle_url = "https://storage.example/skills/data-analysis.tar.gz?version=1"
    direct_manager = SkillArtifactManager(
        Settings(_env_file=None, skill_cache_dir=str(tmp_path / "cache"))
    )
    assert direct_manager._download_headers(bundle_url) == {}

    signed_manager = SkillArtifactManager(
        Settings(
            _env_file=None,
            skill_cache_dir=str(tmp_path / "signed-cache"),
            skill_artifact_access_key="artifact-reader",
            skill_artifact_secret_key="artifact-secret",
        )
    )
    headers = signed_manager._download_headers(bundle_url)
    assert headers["X-Access-Key"] == "artifact-reader"
    assert headers["X-Signature-Version"] == "DATA_AGENT-HMAC-SHA256"
    assert verify_signature(
        signature=headers["X-Signature"],
        secret_key="artifact-secret",
        access_key=headers["X-Access-Key"],
        timestamp=headers["X-Timestamp"],
        nonce=headers["X-Nonce"],
        method="GET",
        path="/skills/data-analysis.tar.gz",
        query="version=1",
        body=b"",
    )

    partial_manager = SkillArtifactManager(
        Settings(
            _env_file=None,
            skill_artifact_access_key="artifact-reader",
        )
    )
    with pytest.raises(SkillArtifactError, match="must be configured together"):
        partial_manager._download_headers(bundle_url)

def test_inline_skill_is_materialized_as_native_skill(tmp_path):
    """
    中文说明：
        验证 tests/test_skill_artifacts 中“inline_skill_is_materialized_as_native_skill”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run():
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        settings = Settings(
            workspace_root=str(tmp_path / "workspaces"),
            skill_cache_dir=str(tmp_path / "cache"),
        )
        result = await SkillArtifactManager(settings).materialize(
            [
                SkillSnapshot(
                    id="vehicle-analysis",
                    version="1.0.0",
                    content="只分析车辆域数据。",
                )
            ],
            tenant_id="tenant-1",
            session_id="session-1",
            run_id="run-1",
            workspace_enabled=False,
        )

        skill_file = (
            Path(result.workspace_root)
            / "skills"
            / "vehicle-analysis"
            / "SKILL.md"
        )
        assert result.skill_sources == ["/skills"]
        assert result.skill_paths == {"vehicle-analysis": "/skills/vehicle-analysis"}
        assert skill_file.exists()
        assert "name: vehicle-analysis" in skill_file.read_text()

    asyncio.run(run())


def test_tar_path_traversal_is_rejected(tmp_path):
    """
    中文说明：
        验证 tests/test_skill_artifacts 中“tar_path_traversal_is_rejected”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    archive = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        payload = b"owned"
        info = tarfile.TarInfo("../../escaped.txt")
        info.size = len(payload)
        output.addfile(info, io.BytesIO(payload))

    destination = tmp_path / "extracted"
    manager = SkillArtifactManager(
        Settings(
            workspace_root=str(tmp_path / "workspaces"),
            skill_cache_dir=str(tmp_path / "cache"),
        )
    )
    with pytest.raises(SkillArtifactError, match="unsafe"):
        manager._safe_extract(archive, destination)


def test_skill_snapshot_requires_one_source():
    """
    中文说明：
        验证 tests/test_skill_artifacts 中“skill_snapshot_requires_one_source”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    with pytest.raises(ValidationError):
        SkillSnapshot(id="missing", version="1")

    with pytest.raises(ValidationError):
        SkillSnapshot(
            id="ambiguous",
            version="1",
            bundle_url="https://storage.example/skill.zip",
            content="# inline",
        )


def test_production_bundle_host_allowlist_is_enforced(tmp_path):
    """
    中文说明：
        验证 tests/test_skill_artifacts 中“production_bundle_host_allowlist_is_enforced”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - tmp_path: 未声明类型：由调用方传入，用于完成本函数的核心处理。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    manager = SkillArtifactManager(
        Settings(
            app_env="production",
            skill_cache_dir=str(tmp_path / "cache"),
            workspace_root=str(tmp_path / "workspace"),
            skill_allowed_hosts="storage.example",
        )
    )
    manager._validate_bundle_url("https://storage.example/skill.zip")
    with pytest.raises(SkillArtifactError):
        manager._validate_bundle_url("https://evil.example/skill.zip")
