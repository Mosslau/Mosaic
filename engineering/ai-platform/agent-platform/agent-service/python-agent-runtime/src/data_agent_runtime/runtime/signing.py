"""本文件模块职责：内部服务 AK/SK HMAC-SHA256 请求签名模块。

本模块定义 外部控制面或调用方、Python Runtime 和 Sandbox Gateway 之间共享的
Canonical Request、Body Hash、Timestamp、Nonce 以及请求头生成规则；Secret Key
只用于本地计算签名，绝不通过网络传输。各语言实现必须严格遵守 README.md 中的
协议约定，确保签名结果可以跨语言互操作。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode

SIGNATURE_VERSION = "DATA_AGENT-HMAC-SHA256"
ACCESS_KEY_HEADER = "X-Access-Key"
TIMESTAMP_HEADER = "X-Timestamp"
NONCE_HEADER = "X-Nonce"
CONTENT_SHA256_HEADER = "X-Content-SHA256"
SIGNATURE_HEADER = "X-Signature"
SIGNATURE_VERSION_HEADER = "X-Signature-Version"


def canonical_query(query: str | bytes | None) -> str:
    """规范化 Query 参数，确保调用方与 Python 使用完全一致的签名输入。"""
    if not query:
        return ""
    raw = query.decode("utf-8") if isinstance(query, bytes) else query
    pairs = sorted(
        parse_qsl(raw, keep_blank_values=True),
        key=lambda item: (item[0], item[1]),
    )
    return urlencode(pairs, doseq=True)


def content_sha256(body: bytes) -> str:
    """计算请求原始 Body 的 SHA-256 摘要，用于请求头和 Canonical Request。"""
    return hashlib.sha256(body).hexdigest()


def canonical_request(
    *,
    access_key: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    query: str | bytes | None,
    body: bytes,
) -> str:
    """按固定协议构造 Canonical Request，供签名方和验签方共同使用。"""
    return "\n".join(
        (
            SIGNATURE_VERSION,
            access_key,
            timestamp,
            nonce,
            method.upper(),
            path or "/",
            canonical_query(query),
            content_sha256(body),
        )
    )


def sign_request(
    *,
    secret_key: str,
    access_key: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    query: str | bytes | None,
    body: bytes,
) -> str:
    """使用 Secret Key 对 Canonical Request 计算 HMAC-SHA256 签名。"""
    message = canonical_request(
        access_key=access_key,
        timestamp=timestamp,
        nonce=nonce,
        method=method,
        path=path,
        query=query,
        body=body,
    ).encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_signature(
    *,
    signature: str,
    secret_key: str,
    access_key: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    query: str | bytes | None,
    body: bytes,
) -> bool:
    """重新计算期望签名，并使用常量时间比较判断收到的签名是否有效。"""
    expected = sign_request(
        secret_key=secret_key,
        access_key=access_key,
        timestamp=timestamp,
        nonce=nonce,
        method=method,
        path=path,
        query=query,
        body=body,
    )
    return hmac.compare_digest(signature, expected)


def timestamp_is_fresh(
    timestamp: str,
    *,
    now: float | None = None,
    skew_seconds: int = 300,
) -> bool:
    """校验请求时间戳是否处于当前时间允许的偏差范围内。"""
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else now
    return abs(current - value) <= skew_seconds


def signing_headers(
    *,
    secret_key: str,
    access_key: str,
    method: str,
    path: str,
    query: str | bytes | None,
    body: bytes,
    timestamp: str | None = None,
    nonce: str,
) -> dict[str, str]:
    """生成发送内部服务请求所需的全部 HMAC 认证请求头。"""
    timestamp = timestamp or str(int(time.time()))
    return {
        ACCESS_KEY_HEADER: access_key,
        TIMESTAMP_HEADER: timestamp,
        NONCE_HEADER: nonce,
        CONTENT_SHA256_HEADER: content_sha256(body),
        SIGNATURE_VERSION_HEADER: SIGNATURE_VERSION,
        SIGNATURE_HEADER: sign_request(
            secret_key=secret_key,
            access_key=access_key,
            timestamp=timestamp,
            nonce=nonce,
            method=method,
            path=path,
            query=query,
            body=body,
        ),
    }
