"""本文件模块职责：Runtime 入站 HMAC 认证和调用方身份解析模块。

本模块只接受 AK/SK + HMAC-SHA256 请求，并把 Access Key 映射为可信 Principal。
所有调用方必须在 INTERNAL_SERVICE_CREDENTIALS_JSON 中独立注册，Runtime 不提供单
AK/SK、固定 Token 或匿名回退；Principal 是后续租户隔离、Scope 校验和资源所有权
判断的唯一身份来源。
"""

from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import HTTPException, Request, status

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.principal import Principal, QuotaPolicy
from data_agent_runtime.runtime.signing import (
    SIGNATURE_VERSION,
    content_sha256,
    timestamp_is_fresh,
    verify_signature,
)

_PRODUCTION_ENVS = {"prod", "production", "staging"}


def _is_production(settings: Settings) -> bool:
    """判断当前部署是否启用生产级认证规则。"""
    return settings.app_env.lower() in _PRODUCTION_ENVS


def _as_string_list(value: Any, *, field_name: str, access_key: str) -> list[str]:
    """把注册表中的角色或 Scope 转换为字符串列表并拒绝不安全格式。"""
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{field_name} must be a string or array for access key {access_key}",
        )
    return values


def _configured_credentials(settings: Settings) -> dict[str, tuple[str, Principal]]:
    """加载唯一的多调用方 AK/SK 注册表。"""
    raw = settings.internal_service_credentials_json
    if not raw or not raw.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_SERVICE_CREDENTIALS_JSON is not configured",
        )
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_SERVICE_CREDENTIALS_JSON is invalid",
        ) from exc
    if not isinstance(values, list) or not values:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_SERVICE_CREDENTIALS_JSON must be a non-empty JSON array",
        )

    result: dict[str, tuple[str, Principal]] = {}
    for item in values:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="each configured credential must be a JSON object",
            )
        access_key = str(item.get("access_key") or "").strip()
        secret_key = str(item.get("secret_key") or "")
        tenant_id = str(item.get("tenant_id") or "").strip()
        principal_id = str(item.get("principal_id") or access_key).strip()
        if not access_key or not secret_key or not tenant_id or not principal_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="each configured credential requires access_key, secret_key, principal_id and tenant_id",
            )
        roles = _as_string_list(
            item.get("roles", []), field_name="roles", access_key=access_key
        )
        scopes = _as_string_list(
            item.get("scopes", []), field_name="scopes", access_key=access_key
        )
        principal = Principal(
            principal_id=principal_id,
            access_key=access_key,
            tenant_id=tenant_id,
            subject_id=str(item["subject_id"]) if item.get("subject_id") else None,
            roles=frozenset(roles),
            scopes=frozenset(scopes),
            quotas=QuotaPolicy.from_mapping(item.get("quotas")),
        )
        if access_key in result:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"duplicate configured access key: {access_key}",
            )
        result[access_key] = (secret_key, principal)
    return result


async def _claim_nonce(
    request: Request | None,
    settings: Settings,
    *,
    access_key: str,
    nonce: str,
) -> bool:
    """使用 Redis 原子 SET NX EX 占用 Nonce，阻止签名请求重放。"""
    redis = getattr(request.app.state, "redis", None) if request is not None else None
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable for HMAC replay protection",
        )
    key = f"agent:auth:nonce:{access_key}:{nonce}"
    try:
        claimed = await redis.set(
            key,
            "1",
            ex=settings.hmac_nonce_ttl_seconds,
            nx=True,
        )
    except Exception as exc:  # pragma: no cover - 由 Redis 客户端具体异常触发
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable for HMAC replay protection",
        ) from exc
    return bool(claimed)


async def require_hmac_principal(
    settings: Settings,
    *,
    request: Request | None = None,
    x_access_key: str | None = None,
    x_timestamp: str | None = None,
    x_nonce: str | None = None,
    x_content_sha256: str | None = None,
    x_signature: str | None = None,
    x_signature_version: str | None = None,
) -> Principal:
    """校验多调用方 HMAC 请求并返回可信 Principal。

    函数名保留以避免内部依赖产生无意义的迁移，但认证行为已经不再接受固定
    Token、Bearer、Query Token 或单 AK/SK 配置。
    """
    credentials = _configured_credentials(settings)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="signed request context is missing",
        )

    require_https = _is_production(settings) or (
        settings.public_mode
        and settings.app_env.lower() not in {"local", "dev", "development", "test"}
    )
    if require_https:
        if not settings.hmac_require_https:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HMAC_REQUIRE_HTTPS must be true for this deployment",
            )
        if request.url.scheme.lower() != "https":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTPS is required for signed internal requests",
            )
    if x_signature_version != SIGNATURE_VERSION:
        raise HTTPException(status_code=401, detail="unsupported signature version")
    if not all((x_access_key, x_timestamp, x_nonce, x_content_sha256, x_signature)):
        raise HTTPException(status_code=401, detail="missing HMAC authentication headers")

    configured = credentials.get(x_access_key or "")
    if configured is None:
        raise HTTPException(status_code=401, detail="invalid access key")
    secret_key, principal = configured
    if not timestamp_is_fresh(
        x_timestamp or "", skew_seconds=settings.hmac_clock_skew_seconds
    ):
        raise HTTPException(
            status_code=401, detail="request timestamp is outside the allowed window"
        )
    body = await request.body()
    if not hmac.compare_digest(x_content_sha256 or "", content_sha256(body)):
        raise HTTPException(status_code=401, detail="request body hash mismatch")
    if not verify_signature(
        signature=x_signature or "",
        secret_key=secret_key,
        access_key=principal.access_key,
        timestamp=x_timestamp or "",
        nonce=x_nonce or "",
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        body=body,
    ):
        raise HTTPException(status_code=401, detail="invalid request signature")
    if not await _claim_nonce(
        request, settings, access_key=principal.access_key, nonce=x_nonce or ""
    ):
        raise HTTPException(status_code=401, detail="request nonce has already been used")
    request.state.principal = principal
    return principal
