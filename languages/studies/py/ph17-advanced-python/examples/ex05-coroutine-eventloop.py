#!/usr/bin/env python3
# examples/ex05-coroutine-eventloop.py —— 协程原理与事件循环调度（主文档 3.9/4.4）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 ex05-coroutine-eventloop.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex05-coroutine-eventloop.py -q（收集 test_* 跑断言）
# lint：ruff check ex05-coroutine-eventloop.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""协程对象惰性、手写极简调度器 vs asyncio、Task/回调、sleep(0) 让出与千级挂起论证。"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from types import coroutine
from typing import Any

# ---------- 手写极简事件循环（教学用） ----------


@coroutine
def sleep_zero() -> Any:
    """教学 awaitable：挂起一拍（yield None 表示「还没好，稍后再叫我」）。"""
    yield None


class MiniLoop:
    """极简调度器：就绪队列 + 协程步进——事件循环本质的缩小版。

    真实 asyncio 的事件循环还要做：IO 就绪通知（epoll/kqueue）、Future 回调、
    定时器堆、异常处理；这里只保留「驱动协程到下一个 await」这一核心动作。
    """

    def __init__(self) -> None:
        self.ready: deque[Callable[[], Any]] = deque()
        self.order: list[str] = []

    def create_task(self, name: str, coro: Awaitable[Any]) -> None:
        def step() -> None:
            try:
                coro.send(None)  # 推进到下一个挂起点
            except StopIteration:
                self.order.append(f"{name}:done")
                return
            self.ready.append(step)  # 挂起一拍后放回就绪队列

        self.ready.append(step)

    def run(self) -> None:
        while self.ready:
            self.ready.popleft()()


async def mini_worker(name: str, hops: int) -> None:
    """async def 协程：每 hop 让出一次，让调度器轮转。"""
    for _i in range(hops):
        await sleep_zero()  # 挂起一拍
        # 真实项目里这里通常是 await asyncio.sleep(0) / await socket IO


# ---------- 官方 asyncio 对照 ----------


async def official_worker(name: str, hops: int) -> None:
    for _i in range(hops):
        await asyncio.sleep(0)  # 让出控制权给事件循环


def test_coroutine_object_is_lazy() -> None:
    """调用 async def 只创建协程对象，函数体一行都不执行。"""
    ran: list[str] = []

    async def body() -> None:
        ran.append("executed")

    coro = body()  # 这里不执行 body
    assert ran == []
    asyncio.run(coro)  # 显式驱动才执行
    assert ran == ["executed"]


def test_mini_loop_round_robin() -> None:
    """手写调度器按就绪队列轮转：三个协程交错推进（像真的并发）。"""
    loop = MiniLoop()
    order: list[str] = []

    @coroutine
    def hop(label: str) -> Any:
        yield None
        order.append(label)

    def spawn(label: str) -> None:
        gen = hop(label)  # 每个任务只创建一次生成器

        def step() -> None:
            try:
                gen.send(None)  # 推进同一个生成器，而非每次新建
            except StopIteration:
                return
            loop.ready.append(step)

        loop.ready.append(step)

    spawn("a")
    spawn("b")
    loop.run()
    assert order == ["a", "b"]  # 先 a 后 b：单线程内交错，非并行


def test_sleep_zero_lets_others_run() -> None:
    """asyncio.sleep(0) 让出：三个任务的总墙钟 ≈ 单任务，而非串行相加。"""

    async def worker(name: str, ms: float) -> None:
        for _ in range(3):
            await asyncio.sleep(ms)

    async def main() -> float:
        start = time.perf_counter()
        await asyncio.gather(*(worker(n, 0.02) for n in ("a", "b", "c")))
        return time.perf_counter() - start

    total = asyncio.run(main())
    assert total < 0.10  # 3 × 3 × 0.02 = 0.18s 串行 vs 并发 ~0.06s


def test_task_wraps_coroutine() -> None:
    """Task = 协程 + 状态：asyncio.ensure_future 立即排入循环。"""
    done: list[str] = []

    async def body() -> None:
        await asyncio.sleep(0)
        done.append("ok")

    async def main() -> None:
        task = asyncio.ensure_future(body())  # 立即调度，不 await 也推进
        await asyncio.sleep(0.01)
        assert task.done() and not task.cancelled()

    asyncio.run(main())
    assert done == ["ok"]


def main() -> None:
    print("== 协程对象是惰性的 ==")
    ran: list[str] = []

    async def body() -> None:
        ran.append("executed")

    coro = body()
    print("调用 async def 后函数体执行了吗？", ran == [])
    asyncio.run(coro)
    print("asyncio.run 驱动后：", ran)
    print("== 手写极简调度器（就绪队列轮转）==")
    loop = MiniLoop()
    loop.create_task("w1", mini_worker("w1", 3))
    loop.create_task("w2", mini_worker("w2", 2))
    loop.run()
    print("调度顺序:", loop.order)
    print("== asyncio.sleep(0) 让出 ==")

    async def main_sleep() -> None:
        await asyncio.gather(official_worker("x", 3), official_worker("y", 3))

    asyncio.run(main_sleep())
    print("三个 0.02s×3 的 worker 并发总耗时 < 0.10s（见 test_sleep_zero_lets_others_run）")
    print("== 千级挂起的规模论证 ==")
    print("1 万个挂起协程由单个 asyncio 循环驱动（只 sleep(0) 让出，不建线程）:")

    async def many() -> None:
        await asyncio.gather(*(official_worker(str(i), 1) for i in range(10_000)))

    start = time.perf_counter()
    asyncio.run(many())
    print(f"  10_000 协程 × 各让出 1 拍 总耗时 {time.perf_counter() - start:.3f}s")
    print(
        "（结论：连接容量由「挂起协程数量」决定，不由线程数决定——"
        "这正是 uvicorn 单进程服务上千连接的机制答案，见主文档 3.9/4.4）"
    )
    test_coroutine_object_is_lazy()
    test_mini_loop_round_robin()
    test_sleep_zero_lets_others_run()
    test_task_wraps_coroutine()
    print("全部断言通过 ✓")


if __name__ == "__main__":
    main()
