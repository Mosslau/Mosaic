#!/usr/bin/env python3
# examples/ex06-async-fastapi.py —— 异步 FastAPI：事件循环并发模型实测（主文档 3.8/4.6）
# 验证环境：Python 3.13.9 + fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1（本机已装并实测）
# 运行：python3 ex06-async-fastapi.py（进程内起 uvicorn 自测，测完优雅退出，无残留进程）
# 验证状态：已验证 —— 本机实测：async 端点串行 ≈ 1.05s，并发 ≈ 0.07s（约 15~16 倍）；
#           time.sleep 阻塞端点并发 ≈ 1.15s —— 事件循环被卡死，并发失效
#           （数字随机器与负载波动 ±10~20%）
# 验证块数字实测：async 串行 1.051s / async 并发 0.067s / blocked 并发 1.154s（一次运行）
import asyncio
import time

import httpx
import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/slow/{n}")
async def slow(n: int) -> dict:
    """正常 async 端点：await 把控制权让回事件循环，等待期间处理其他请求。"""
    await asyncio.sleep(0.05)
    return {"n": n, "ok": True}


@app.get("/blocked/{n}")
async def blocked(n: int) -> dict:
    """错误示范：async 端点里用 time.sleep —— 整个事件循环被卡住，所有并发请求排队。"""
    time.sleep(0.05)  # 阻塞调用！事件循环无法切去其他请求
    return {"n": n, "ok": True}


async def run_probe(client: httpx.AsyncClient, path: str, n_req: int) -> None:
    """串行 vs 并发两组测量（同一端点）。"""
    t0 = time.perf_counter()
    rs = [await client.get(f"/{path}/{i}") for i in range(n_req)]
    t_serial = time.perf_counter() - t0
    t0 = time.perf_counter()
    rs = await asyncio.gather(*(client.get(f"/{path}/{i}") for i in range(n_req)))
    t_conc = time.perf_counter() - t0
    speedup = t_serial / t_conc
    print(
        f"{path} 端点: 串行 {t_serial:.3f}s / 并发 {t_conc:.3f}s"
        f"（≈ {speedup:.1f} 倍）status={rs[0].status_code}"
    )


async def main() -> None:
    # 进程内起 uvicorn（asyncio 任务），端口 0 = 系统分配，退出时 should_exit + await 收尾
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    print(f"== 进程内 uvicorn（{port}）并发压测：20 个请求 × 0.05s ==")

    async with httpx.AsyncClient(base_url=base) as client:
        await run_probe(client, "slow", 20)
        # blocked 端点只测并发：预期 ≈ 20 × 0.05s —— 阻塞把并发抹平
        t0 = time.perf_counter()
        rs = await asyncio.gather(*(client.get(f"/blocked/{i}") for i in range(20)))
        elapsed = time.perf_counter() - t0
        print(
            f"blocked 端点 并发: {elapsed:.3f}s（≈ 20 × 0.05s，阻塞反例）status={rs[0].status_code}"
        )

    server.should_exit = True  # 产物纪律：优雅关闭 uvicorn，不残留服务进程
    await server_task
    print("uvicorn 已退出（无残留进程）")


if __name__ == "__main__":
    asyncio.run(main())
