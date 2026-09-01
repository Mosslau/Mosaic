#!/usr/bin/env python3
# examples/ex05-aiohttp-httpx.py —— aiohttp / httpx async：并发网络请求实测（主文档 3.7）
# 验证环境：Python 3.13.9 + aiohttp 3.13.2 + httpx 0.28.1（本机已装并实测）
# 运行：python3 ex05-aiohttp-httpx.py（本地起服务器自测，测完进程内关闭，无残留进程）
# 验证状态：已验证 —— 本机实测：aiohttp 串行 ≈ 1.1s，aiohttp gather ≈ 0.06s，httpx 并发 ≈ 0.07s
#           （约 18~19 倍）；Semaphore 限速 limit=2 ≈ 0.54s（= 20/2 × 0.05s，线性关系）
# 验证块数字实测：aiohttp 串行 1.098s / gather 0.059s / httpx 0.065s；限速 2 0.537s（一次运行）
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

N_REQUESTS = 20
SERVER_DELAY = 0.05  # 服务端每次处理耗时（模拟慢接口/遥测上报）


class Handler(BaseHTTPRequestHandler):
    """极简本地 HTTP 服务：GET /api/items/{i} → 睡 SERVER_DELAY 后返回 JSON。"""

    def do_GET(self) -> None:  # noqa: N802 —— BaseHTTPRequestHandler 协议方法名
        time.sleep(SERVER_DELAY)  # 模拟服务端处理耗时
        body = json.dumps({"path": self.path, "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # 静默访问日志
        pass


def start_server() -> tuple[ThreadingHTTPServer, int]:
    """在后台线程起本地服务器，返回 (server, port)；调用方负责 shutdown/close。"""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


async def main() -> None:
    srv, port = start_server()
    urls = [f"http://127.0.0.1:{port}/api/items/{i}" for i in range(N_REQUESTS)]

    import aiohttp

    print(
        f"== 本地 HTTP 服务（{port}）并发请求实测：{N_REQUESTS} 个请求 × 服务端 {SERVER_DELAY}s =="
    )
    async with aiohttp.ClientSession() as session:
        # 串行：一个请求等完再发下一个
        t0 = time.perf_counter()
        responses = [await session.get(u) for u in urls]
        t_serial = time.perf_counter() - t0
        print(f"aiohttp 串行: {t_serial:.3f}s（status={responses[0].status}）")

        # 并发：gather 一次发出，全部回来约等于单个请求耗时
        t0 = time.perf_counter()
        responses = await asyncio.gather(*(session.get(u) for u in urls))
        t_gather = time.perf_counter() - t0
        print(f"aiohttp gather 并发: {t_gather:.3f}s（≈ {t_serial / t_gather:.0f} 倍加速）")

        # Semaphore 限速：把并发上限压到 2，耗时线性变为 20/2 × 0.05s
        sem = asyncio.Semaphore(2)

        async def limited(u: str):
            async with sem:
                return await session.get(u)

        t0 = time.perf_counter()
        responses = await asyncio.gather(*(limited(u) for u in urls))
        elapsed = time.perf_counter() - t0
        print(f"aiohttp 限速(Semaphore=2): {elapsed:.3f}s（= {N_REQUESTS}/2 × {SERVER_DELAY}s）")

    import httpx

    async with httpx.AsyncClient() as client:
        t0 = time.perf_counter()
        responses = await asyncio.gather(*(client.get(u) for u in urls))
        print(f"httpx 并发: {time.perf_counter() - t0:.3f}s（status={responses[0].status_code}）")

    srv.shutdown()  # 产物纪律：测完关服务器，不残留进程
    srv.server_close()
    print("服务器已关闭（无残留进程）")


if __name__ == "__main__":
    asyncio.run(main())
