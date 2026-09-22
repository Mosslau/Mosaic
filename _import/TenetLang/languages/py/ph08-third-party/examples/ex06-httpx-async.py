# examples/ex06-httpx-async.py —— 主文档 3.1：httpx 同步 / 异步双模式对比（并发耗时差异）
# 验证环境：Python 3.13.9，httpx 0.28.1；运行：python3 ex06-httpx-async.py（需联网，已验证）
import asyncio
import time

import httpx

URL = "https://httpbin.org/uuid"
N = 3


def fetch_sync() -> float:
    """同步串行：N 次请求耗时约 N × RTT。"""
    start = time.perf_counter()
    with httpx.Client(timeout=10) as client:
        for _ in range(N):
            client.get(URL)
    return time.perf_counter() - start


async def fetch_async() -> float:
    """异步并发：N 次请求耗时约 1 × RTT。"""
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=10) as client:
        await asyncio.gather(*(client.get(URL) for _ in range(N)))
    return time.perf_counter() - start


if __name__ == "__main__":
    sync_cost = fetch_sync()
    async_cost = asyncio.run(fetch_async())
    print(f"同步 {N} 次: {sync_cost:.2f}s")
    print(f"异步 {N} 次: {async_cost:.2f}s")
    print("结论：同一套 API，异步并发把 N×RTT 压到约 1×RTT")
