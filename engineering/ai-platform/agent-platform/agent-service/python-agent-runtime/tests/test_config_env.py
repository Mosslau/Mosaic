"""本文件模块职责：部署配置和 .env/.env.example 契约测试。

测试确认 Settings 的字段都能在环境文件中找到，并防止示例配置意外提交真实 API Key、Redis 密码或 PostgreSQL 密码。
"""

from __future__ import annotations

import re
from pathlib import Path

from data_agent_runtime.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_keys(path: Path) -> set[str]:
    """
    中文说明：
        实现 tests/test_config_env 的内部辅助步骤“_env_keys”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - path: Path：由调用方传入，用于完成本函数的核心处理。

    返回：
        set[str]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _settings_env_names() -> set[str]:
    """
    中文说明：
        实现 tests/test_config_env 的内部辅助步骤“_settings_env_names”，负责完成调用方不应直接依赖的校验、转换或资源操作。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        set[str]。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    # Settings 中声明的每个部署配置都必须在示例文件中有明确说明。
    return {
        field.alias or field_name.upper()
        for field_name, field in Settings.model_fields.items()
    }


def test_env_files_cover_all_settings() -> None:
    """
    中文说明：
        验证 tests/test_config_env 中“env_files_cover_all_settings”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        None。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    expected = _settings_env_names()
    for filename in (".env", ".env.example"):
        actual = _env_keys(PROJECT_ROOT / filename)
        assert expected <= actual, f"{filename} 缺少配置: {sorted(expected - actual)}"


def test_env_example_has_no_real_api_key_or_production_password() -> None:
    """
    中文说明：
        验证 tests/test_config_env 中“env_example_has_no_real_api_key_or_production_password”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        None。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"OPENAI_API_KEY=sk-[A-Za-z0-9_-]+", example)
    assert "REDIS_URL=redis://default:root@" not in example
    assert "POSTGRES_DSN=postgresql://postgres:root@" not in example
    assert "INTERNAL_SERVICE_TOKEN=" not in example
    assert "SANDBOX_GATEWAY_TOKEN=" not in example

    assignments = {}
    for line in example.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            assignments[key.strip()] = value.strip()
    assert assignments["APP_ENV"] == "production"
    assert assignments["PUBLIC_MODE"] == "true"
    assert assignments["HMAC_REQUIRE_HTTPS"] == "true"
    assert assignments["CHECKPOINT_BACKEND"] == "postgres"
    assert all(assignments.values()), "生产样例不应存在空配置值"
