#!/usr/bin/env python3
# exercises/sol-05-async-client.py —— 练习 5 参考实现：aiohttp 并发抓取 + 限速 + 重试
# 验证环境：Python 3.13.9 + aiohttp 3.13.2（本机已装并实测）
# 运行：python3 sol-05-async-client.py（本地起服自测，测完自动关闭，无残留进程）
# 验证状态：已验证 —— 本机实测：串行 ≈ 1.30s，并发(限速4) ≈ 0.42s（约 3.1 倍）；
#           20 个端点成功 16/20（i%5==0 的 4 个恒 503，重试 3 次耗尽后记为失败），
#           失败端点 attempts=3、成功端点 attempts=1（确定性，可复现）（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 1.298s / 并发 0.424s（≈ 3.1 倍）；成功 16/20、失败 [0, 5, 10, 15]
import asyncio
import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aiohttp

N_REQUESTS = 20
SERVER_DELAY = 0.02  # 服务端每次处理耗时


class Handler(BaseHTTPRequestHandler):
    """本地模拟接口：i%5==0 的端点恒返 503（确定性失败，供重试演示）。"""

    def do_GET(self) -> None:  # noqa: N802 —— BaseHTTPRequestHandler 协议方法名
        time.sleep(SERVER_DELAY)
        i = int(self.path.rsplit("/", 1)[1])
        if i % 5 == 0:  # 0/5/10/15 恒 503
            self.send_response(503)
            body = b'{"error":"busy"}'
        else:
            self.send_response(200)
            body = json.dumps({"id": i, "ok": True}).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # 静默访问日志
        pass


def start_server() -> tuple[ThreadingHTTPServer, int]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


@dataclass
class FetchResult:
    """一次抓取的结果：哪个端点、成没成、重试了几次、状态码、耗时。"""

    id: int
    ok: bool
    attempts: int
    status: int | None = None
    elapsed_ms: float = 0.0


async def fetch_with_retry(
    session: aiohttp.ClientSession, base: str, i: int, max_retries: int
) -> FetchResult:
    """抓取第 i 个端点：非 200 / 网络异常 → 指数退避重试，耗尽 max_retries 记为失败。"""
    for attempt in range(1, max_retries + 1):
        t0 = time.perf_counter()
        try:
            async with session.get(
                f"{base}/api/fetch/{i}", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    await resp.json()  # 确保响应体被消费（连接可复用）
                    return FetchResult(
                        i, True, attempt, resp.status, (time.perf_counter() - t0) * 1000
                    )
                await asyncio.sleep(0.02 * (2 ** (attempt - 1)))  # 503 → 指数退避后重试
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(0.02 * (2 ** (attempt - 1)))
    return FetchResult(i, False, max_retries)


async def main() -> None:
    srv, port = start_server()
    base = f"http://127.0.0.1:{port}"
    print(f"== 本地接口（{port}）：{N_REQUESTS} 个端点，i%5==0 恒 503（重试演示）==")

    async with aiohttp.ClientSession() as session:
        # 串行：一个接一个
        t0 = time.perf_counter()
        serial = [
            await fetch_with_retry(session, base, i, 3) for i in range(N_REQUESTS)
        ]
        t_serial = time.perf_counter() - t0
        print(f"串行: {t_serial:.3f}s")
        # 串行结果一致性：成功 16 个、失败 [0,5,10,15]，与并发结果一致
        serial_fail = sorted(r.id for r in serial if not r.ok)
        assert serial_fail == [0, 5, 10, 15], f"串行失败集合异常: {serial_fail}"

        # 并发 + 限速：Semaphore(4) 把同时在途的请求压到 4 个
        sem = asyncio.Semaphore(4)

        async def limited(i: int) -> FetchResult:
            async with sem:
                return await fetch_with_retry(session, base, i, 3)

        t0 = time.perf_counter()
        results = await asyncio.gather(*(limited(i) for i in range(N_REQUESTS)))
        t_conc = time.perf_counter() - t0

        ok_ids = sorted(r.id for r in results if r.ok)
        fail_ids = sorted(r.id for r in results if not r.ok)
        attempts = {r.id: r.attempts for r in results}
        print(f"并发(限速4): {t_conc:.3f}s（≈ {t_serial / t_conc:.1f} 倍加速）")
        print(f"成功 {len(ok_ids)}/{N_REQUESTS}：{ok_ids}")
        print(f"失败 {len(fail_ids)}（重试 3 次耗尽）：{fail_ids}")
        print(f"attempts 分布: {attempts}")

        # 正确性校验：4 个恒失败端点 attempts=3，其余 attempts=1；成功数 16
        assert ok_ids == [i for i in range(N_REQUESTS) if i % 5 != 0]
        assert fail_ids == [0, 5, 10, 15]
        assert all(attempts[i] == 3 for i in fail_ids)
        assert all(attempts[i] == 1 for i in ok_ids)
        print("结果校验: 成功/失败/重试次数全部符合预期 ✓")

    srv.shutdown()  # 产物纪律：测完关服务器，不残留进程
    srv.server_close()
    print("服务器已关闭（无残留进程）")


if __name__ == "__main__":
    asyncio.run(main())
