"""模型 Provider 注册表。

Admission 和 Factory 必须共享同一份 Provider 能力声明，避免配置看起来允许某个
Provider、但实际构建时才失败，导致合法 Snapshot 被异步执行失败。
"""

from __future__ import annotations

# 当前安装的模型适配器基于 OpenAI 协议，兼容 OpenAI 官方、DeepSeek 和其他
# OpenAI-compatible 网关。这里登记的是 Runtime 已实现的 Provider 名称到适配器
# 能力的映射，不是部署白名单；部署白名单仍由 ALLOWED_MODEL_PROVIDERS 控制。
MODEL_PROVIDER_ADAPTERS: dict[str, str] = {
    "openai": "openai",
    "openai-compatible": "openai-compatible",
    "deepseek": "openai-compatible",
}
SUPPORTED_MODEL_PROVIDERS: frozenset[str] = frozenset(MODEL_PROVIDER_ADAPTERS)


def normalize_provider(provider: str | None, default: str = "openai") -> str:
    """规范化 Snapshot 中的 Provider 名称，避免大小写造成准入/构建结果不一致。"""
    return (provider or default).strip().lower()


def provider_adapter(provider: str | None, default: str = "openai") -> str | None:
    """返回 Provider 对应的已安装适配器；未知 Provider 返回 ``None``。"""
    return MODEL_PROVIDER_ADAPTERS.get(normalize_provider(provider, default))
