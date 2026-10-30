"""本文件模块职责：Runtime 调用方 Principal 和配额策略数据结构。

Principal 是认证成功后唯一可信的租户、主体、角色和 Scope 来源；请求体中的
user_context 只能作为兼容输入，不能覆盖 Principal 的身份边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuotaPolicy:
    """单个调用方允许使用的运行时资源配额。"""

    max_steps: int | None = None
    run_timeout_seconds: int | None = None
    max_concurrent_runs: int | None = None

    @classmethod
    def from_mapping(cls, value: Any) -> QuotaPolicy:
        """从凭证注册表中的映射构造调用方配额。

        非对象、非正整数和无法转换的值按未配置处理，避免无效配置意外放大资源权限。"""
        if not isinstance(value, dict):
            return cls()

        def positive_int(name: str) -> int | None:
            """读取并规范化一个正整数配额；非法值返回 ``None``。"""
            raw = value.get(name)
            if raw is None:
                return None
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

        return cls(
            max_steps=positive_int("max_steps"),
            run_timeout_seconds=positive_int("run_timeout_seconds"),
            max_concurrent_runs=positive_int("max_concurrent_runs"),
        )


@dataclass(frozen=True)
class Principal:
    """认证后注入请求上下文的可信调用方身份。"""

    principal_id: str
    access_key: str
    tenant_id: str
    subject_id: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    scopes: frozenset[str] = field(default_factory=frozenset)
    quotas: QuotaPolicy = field(default_factory=QuotaPolicy)
    auth_method: str = "hmac"

    @property
    def user_id(self) -> str:
        """返回用于资源隔离的用户标识。

        有明确 subject 时使用 subject，否则退回 Principal 标识，保证每个认证调用方都有稳定的资源归属键。"""
        return self.subject_id or self.principal_id

    def has_scope(self, scope: str) -> bool:
        """判断 Principal 是否拥有指定 Scope；通配 Scope ``*`` 可以覆盖具体 Scope。"""
        return "*" in self.scopes or scope in self.scopes

    def can_access_user(self, tenant_id: str, user_id: str) -> bool:
        """判断 Principal 是否可以访问指定租户下的用户资源。"""
        return self.tenant_id == tenant_id and (
            self.subject_id is None or self.subject_id == user_id
        )

    def can_access_tenant(self, tenant_id: str) -> bool:
        """判断 Principal 是否可以访问指定租户的资源。"""
        return self.tenant_id == tenant_id
