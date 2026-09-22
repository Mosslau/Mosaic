# examples/ex06-async-concurrency.py —— 异步接口与并发（httpx AsyncClient + ASGITransport 验证）
# 验证环境：Python 3.13.9，fastapi 0.139.1 / httpx 0.28.1 / anyio
# 运行：python3 ex06-async-concurrency.py（离线可跑，已验证，不起真实服务）
# 说明：演示「async def 路由并发处理慢 I/O」——事件循环用 await 让出控制权，
#       三个并发请求的总耗时 ≈ 单请求耗时（而不是串行 ×3）。原理见主文档 4.1。
import asyncio
import time

import anyio
import httpx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI(title="异步并发 Demo")


async def current_ts() -> str:                     # 异步依赖：依赖本身也可以是 async def（3.12）
    await asyncio.sleep(0)                         # 让出一次事件循环
    return time.strftime("%H:%M:%S")


@app.get("/slow/{n}")
async def slow(n: int, ts: str = Depends(current_ts)):
    """async 路由：I/O 等待期间让出事件循环，其他请求可插队执行。"""
    await asyncio.sleep(0.3)                       # 模拟慢 I/O（真实场景：DB/外部 API 调用）
    return {"n": n, "ts": ts}


@app.get("/blocking/{n}")
def blocking(n: int):
    """普通 def 路由：FastAPI 丢进线程池执行（同步阻塞代码不会卡死事件循环）。"""
    time.sleep(0.3)
    return {"n": n, "thread": "threadpool"}


def measure_sequential() -> None:
    """TestClient 串行发 3 个慢请求：总耗时 ≈ 3 × 单请求。"""
    with TestClient(app) as client:
        t0 = time.perf_counter()
        for i in range(3):
            client.get(f"/slow/{i}")
        elapsed = time.perf_counter() - t0
    print(f"串行 3 个 /slow 请求: {elapsed:.2f}s（每个 await asyncio.sleep(0.3)，预期 ~0.9s）")


async def measure_concurrent() -> None:
    """httpx.AsyncClient + asyncio.gather 并发发 3 个慢请求：总耗时 ≈ 单请求。"""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),    # ASGI 直驱：不占端口、不起真实服务
        base_url="http://test",
    ) as client:
        t0 = anyio.current_time()
        responses = await asyncio.gather(*(client.get(f"/slow/{i}") for i in range(3)))
        elapsed = anyio.current_time() - t0
    print(f"并发 3 个 /slow 请求: {elapsed:.2f}s（事件循环让出并发，预期 ~0.3s）")
    print("  响应:", [(r.status_code, r.json()) for r in responses])


def main() -> None:
    measure_sequential()
    asyncio.run(measure_concurrent())


if __name__ == "__main__":
    main()
