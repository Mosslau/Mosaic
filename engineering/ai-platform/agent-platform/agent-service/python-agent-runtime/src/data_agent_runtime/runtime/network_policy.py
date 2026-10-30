"""公共 Runtime 的出站网络安全策略。

本模块只提供确定性的地址校验，不替代部署侧 egress firewall、DNS 解析保护或
MCP/Sandbox Gateway 的最终网络隔离。公共模式下，Runtime 至少拒绝明显的本地、
保留和私网目标，避免把 Snapshot 直接变成 SSRF 入口。
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time

# DNS 结果短时缓存：准入在每次提交/消费时都会校验 Host，
# 缓存避免反复阻塞解析；TTL 很短，兼顾 rebinding 风险与性能。
_DNS_CACHE: dict[str, tuple[float, bool]] = {}
_DNS_CACHE_TTL_SECONDS = 60.0
_DNS_CACHE_MAX_ENTRIES = 512


def clear_dns_cache() -> None:
    """清空 DNS 判定缓存（测试与配置热更新使用）。"""
    _DNS_CACHE.clear()


def _cached_lookup(host: str) -> bool | None:
    """读取未过期的缓存结果；不存在或已过期返回 None。"""
    entry = _DNS_CACHE.get(host)
    if entry is None:
        return None
    expires_at, value = entry
    if expires_at < time.monotonic():
        _DNS_CACHE.pop(host, None)
        return None
    return value


def _store_lookup(host: str, value: bool) -> None:
    """写入缓存，并在条目过多时做一次简单裁剪。"""
    if len(_DNS_CACHE) >= _DNS_CACHE_MAX_ENTRIES:
        _DNS_CACHE.clear()
    _DNS_CACHE[host] = (time.monotonic() + _DNS_CACHE_TTL_SECONDS, value)


def is_private_or_local_host(host: str) -> bool:
    """判断主机名/IP 是否解析到本地、私网或保留地址。

    对域名执行解析是为了在 Admission 和真正建立连接前尽早拒绝明显危险目标；
    生产环境仍必须在网络层限制 DNS rebinding、私网路由和跨租户 egress。
    解析失败按不安全处理，避免公共服务在无法确认目标时放行请求。
    """
    normalized = host.strip().strip("[]").lower().rstrip(".")
    if not normalized or normalized in {"localhost", "localhost.localdomain"}:
        return True
    if normalized.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        addresses = [ipaddress.ip_address(normalized)]
    except ValueError:
        cached = _cached_lookup(normalized)
        if cached is not None:
            return cached
        try:
            addresses = [
                ipaddress.ip_address(str(item[4][0]))
                for item in socket.getaddrinfo(normalized, None)
            ]
        except (OSError, ValueError):
            _store_lookup(normalized, True)
            return True
        resolved = any(
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
            or not address.is_global
            for address in addresses
        )
        _store_lookup(normalized, resolved)
        return resolved
    return any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        or not address.is_global
        for address in addresses
    )


async def is_private_or_local_host_async(host: str) -> bool:
    """异步版本：把同步 DNS 解析放到线程池，避免阻塞事件循环。

    准入路径（API 提交、Worker 二次准入、MCP 校验）都必须用这个版本；
    同步版本仅保留给纯同步调用方与测试。
    """
    return await asyncio.to_thread(is_private_or_local_host, host)
