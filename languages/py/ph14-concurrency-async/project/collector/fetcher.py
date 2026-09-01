"""并发采集器：aiohttp 异步抓取 + Semaphore 限速 + 指数退避重试。

核心心智（主文档 3.7/4.4）：一个事件循环里塞进几百个协程（每个协程一次 HTTP
请求），`await` 让出控制权，等待期间其他请求插队 —— 这就是「大量并发网络 IO
用 asyncio」的落地形态。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import aiohttp


@dataclass
class FetchResult:
    """一次采集的结果：车辆、成没成、重试了几次、状态码、耗时、遥测值。"""

    vehicle_id: str
    ok: bool
    status: int | None
    attempts: int
    elapsed_ms: float
    speed: float | None = None
    battery: float | None = None


async def fetch_one(
    session: aiohttp.ClientSession,
    base_url: str,
    vehicle_id: str,
    max_retries: int = 3,
    retry_delay: float = 0.01,
) -> FetchResult:
    """抓取单辆车的遥测：非 200 / 网络异常 → 指数退避重试，耗尽记为失败。"""
    for attempt in range(1, max_retries + 1):
        t0 = time.perf_counter()
        try:
            async with session.get(
                f"{base_url}/api/vehicles/{vehicle_id}/telemetry",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()  # 消费响应体，连接可复用
                    elapsed = (time.perf_counter() - t0) * 1000
                    return FetchResult(
                        vehicle_id=vehicle_id,
                        ok=True,
                        status=200,
                        attempts=attempt,
                        elapsed_ms=round(elapsed, 1),
                        speed=data.get("speed"),
                        battery=data.get("battery"),
                    )
                await asyncio.sleep(retry_delay * attempt)  # 503 → 退避后重试
        except (TimeoutError, aiohttp.ClientError):
            await asyncio.sleep(retry_delay * attempt)
    return FetchResult(
        vehicle_id=vehicle_id,
        ok=False,
        status=None,
        attempts=max_retries,
        elapsed_ms=0.0,
    )


async def collect(
    base_url: str,
    vehicle_ids: list[str],
    max_concurrency: int = 5,
    max_retries: int = 3,
    retry_delay: float = 0.01,
) -> list[FetchResult]:
    """并发采集一批车辆：Semaphore 把同时在途的请求压到 max_concurrency。"""
    sem = asyncio.Semaphore(max_concurrency)

    async with aiohttp.ClientSession() as session:  # ClientSession 复用 TCP 连接

        async def limited(vid: str) -> FetchResult:
            async with sem:  # 限速：拿不到令牌就排队
                return await fetch_one(session, base_url, vid, max_retries, retry_delay)

        return await asyncio.gather(*(limited(v) for v in vehicle_ids))
