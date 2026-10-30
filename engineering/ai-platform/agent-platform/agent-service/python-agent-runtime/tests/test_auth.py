"""本文件模块职责：内部服务 AK/SK HMAC 认证和 Redis Nonce 防重放测试。

测试覆盖签名校验、时间戳、Body Hash、HTTPS、Nonce 幂等占用、Redis 故障和本地 HTTP 联调兼容。
"""

import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.auth import require_hmac_principal
from data_agent_runtime.runtime.signing import signing_headers


class FakeRedis:
    """用于认证测试的最小 Redis SET NX EX 行为 Stub。"""

    def __init__(self):
        """初始化测试替身及其调用记录。"""
        self.keys: set[str] = set()
        self.calls: list[tuple[str, str, int, bool]] = []
        self.fail = False

    async def set(self, key, value, ex, nx):
        """模拟 Redis SET NX EX 原子写入。"""
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.calls.append((key, value, ex, nx))
        if nx and key in self.keys:
            return False
        self.keys.add(key)
        return True


def make_request(
    *,
    method="POST",
    path="/v1/runs",
    query="",
    body=b"{}",
    redis=None,
    scheme="https",
):
    """构造带有测试 Redis 和原始请求体的 Starlette Request。"""
    app = SimpleNamespace(state=SimpleNamespace(redis=redis))
    received = False

    async def receive():
        """向 Starlette Request 提供一次原始 HTTP 请求体。"""
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": scheme,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [],
        "server": ("runtime.test", 443 if scheme == "https" else 80),
        "client": ("127.0.0.1", 1234),
        "root_path": "",
        "app": app,
    }
    request = Request(scope, receive)
    request._app = app  # type: ignore[attr-defined]
    return request


def signed_call(
    settings,
    *,
    request,
    nonce="nonce-1",
    timestamp=None,
    body=b"{}",
    **overrides,
):
    """使用测试 AK/SK 生成签名并调用入站认证函数。"""
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    headers = signing_headers(
        access_key="java-runtime",
        secret_key="secret-key",
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        body=body,
        timestamp=timestamp,
        nonce=nonce,
    )
    headers.update(overrides)
    values = {
        "x_access_key": headers["X-Access-Key"],
        "x_timestamp": headers["X-Timestamp"],
        "x_nonce": headers["X-Nonce"],
        "x_content_sha256": headers["X-Content-SHA256"],
        "x_signature": headers["X-Signature"],
        "x_signature_version": headers["X-Signature-Version"],
    }
    values.update(
        {key: value for key, value in overrides.items() if key.startswith("x_")}
    )
    return asyncio.run(
        require_hmac_principal(settings, request=request, **values)
    )


def hmac_settings(**kwargs):
    """构造认证测试所需的多调用方 HMAC 配置。"""
    return Settings(
        app_env="production",
        internal_service_credentials_json=(
            '[{"access_key":"java-runtime","secret_key":"secret-key",'
            '"principal_id":"runtime-test","tenant_id":"tenant-test",'
            '"scopes":["runs:write","runs:read"]}]'
        ),
        **kwargs,
    )


def test_valid_hmac_request_is_accepted_and_nonce_is_claimed():
    """验证有效 HMAC 请求可以认证成功，并且 Nonce 会被 Redis 原子占用。"""
    redis = FakeRedis()
    request = make_request(redis=redis)
    signed_call(hmac_settings(), request=request)
    assert redis.calls == [("agent:auth:nonce:java-runtime:nonce-1", "1", 300, True)]


def test_replayed_nonce_is_rejected():
    """验证同一个 Nonce 重复提交时会被拒绝，防止请求重放。"""
    redis = FakeRedis()
    settings = hmac_settings()
    signed_call(settings, request=make_request(redis=redis), nonce="replay")
    with pytest.raises(HTTPException) as error:
        signed_call(settings, request=make_request(redis=redis), nonce="replay")
    assert error.value.status_code == 401
    assert "already" in error.value.detail


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"x_access_key": "wrong-ak"}, "access key"),
        ({"x_signature": "wrong-signature"}, "signature"),
        ({"x_content_sha256": "0" * 64}, "body hash"),
        ({"x_signature_version": "old"}, "signature version"),
    ],
)
def test_invalid_hmac_headers_are_rejected(overrides, expected):
    """验证缺失或篡改 HMAC 请求头时认证失败。"""
    with pytest.raises(HTTPException) as error:
        signed_call(
            hmac_settings(), request=make_request(redis=FakeRedis()), **overrides
        )
    assert error.value.status_code == 401
    assert expected in error.value.detail


def test_expired_timestamp_is_rejected():
    """验证超出时钟偏差窗口的签名请求会被拒绝。"""
    with pytest.raises(HTTPException) as error:
        signed_call(
            hmac_settings(),
            request=make_request(redis=FakeRedis()),
            timestamp=int(time.time()) - 301,
        )
    assert error.value.status_code == 401
    assert "timestamp" in error.value.detail


def test_production_signed_requests_require_https():
    """验证生产环境签名请求必须通过 HTTPS 发送。"""
    with pytest.raises(HTTPException) as error:
        signed_call(
            hmac_settings(),
            request=make_request(redis=FakeRedis(), scheme="http"),
        )
    assert error.value.status_code == 400
    assert "HTTPS" in error.value.detail


def test_local_signed_requests_can_use_http_for_local_testing():
    """验证本地联调在显式允许时可以使用 HTTP。"""
    settings = Settings(
        _env_file=None,
        app_env="local",
        hmac_require_https=False,
        internal_service_credentials_json=(
            '[{"access_key":"java-runtime","secret_key":"secret-key",'
            '"principal_id":"runtime-test","tenant_id":"tenant-test",'
            '"scopes":["runs:write","runs:read"]}]'
        ),
    )
    signed_call(settings, request=make_request(redis=FakeRedis(), scheme="http"))


def test_production_cannot_disable_https_requirement():
    """验证生产环境不能通过配置关闭 HTTPS 强制要求。"""
    settings = hmac_settings(hmac_require_https=False)
    with pytest.raises(HTTPException) as error:
        signed_call(settings, request=make_request(redis=FakeRedis()))
    assert error.value.status_code == 503
    assert "HMAC_REQUIRE_HTTPS" in error.value.detail


def test_production_requires_credential_registry():
    """验证生产环境必须配置多调用方凭证注册表。"""
    settings = Settings(_env_file=None, app_env="production")
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_hmac_principal(settings))
    assert error.value.status_code == 503
    assert "CREDENTIALS_JSON" in error.value.detail


def test_invalid_credential_registry_fails_closed():
    """验证凭证注册表格式无效时认证会安全失败。"""
    for raw in ("not-json", "[]", '[{"access_key":"only-ak"}]'):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                require_hmac_principal(
                    Settings(
                        _env_file=None,
                        app_env="production",
                        internal_service_credentials_json=raw,
                    )
                )
            )
        assert error.value.status_code == 503


def test_local_requires_hmac_credential_registry():
    """验证本地 HMAC 认证同样要求有效的凭证注册表。"""
    settings = Settings(_env_file=None, app_env="local")
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_hmac_principal(settings))
    assert error.value.status_code == 503


def test_production_requires_redis_for_replay_protection():
    """验证生产环境没有 Redis 时不会绕过 Nonce 防重放。"""
    settings = hmac_settings()
    request = make_request(redis=None)
    with pytest.raises(HTTPException) as error:
        signed_call(settings, request=request)
    assert error.value.status_code == 503
    assert "Redis" in error.value.detail


def test_redis_failure_fails_closed():
    """验证 Redis 防重放检查故障时请求会拒绝而不是放行。"""
    settings = hmac_settings()
    redis = FakeRedis()
    redis.fail = True
    with pytest.raises(HTTPException) as error:
        signed_call(settings, request=make_request(redis=redis))
    assert error.value.status_code == 503
    assert "Redis" in error.value.detail
