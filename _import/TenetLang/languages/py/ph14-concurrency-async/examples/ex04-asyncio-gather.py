#!/usr/bin/env python3
# examples/ex04-asyncio-gather.py —— asyncio：gather 并发与「不要阻塞事件循环」（主文档 3.5/3.6）
# 验证环境：Python 3.13.9（macOS arm64，标准库，零第三方依赖）
# 运行：python3 ex04-asyncio-gather.py（离线可跑，已验证）
# 验证状态：已验证 —— 本机实测：串行 await ≈ 1.02s，gather 并发 ≈ 0.05s（约 20 倍）；
#           gather + time.sleep（反例）≈ 1.08s —— 阻塞调用把并发抹平（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 1.020s / gather 0.051s / 反例 1.073s（一次运行）
import asyncio
import time

N_TASKS = 20
IO_WAIT = 0.05


async def async_io_task(i: int) -> int:
    """协程版 IO 等待：await asyncio.sleep 把控制权让回事件循环，等待期间其他任务插队。"""
    await asyncio.sleep(IO_WAIT)
    return i * 2


async def blocking_io_task(i: int) -> int:
    """错误示范：协程里用 time.sleep —— 阻塞调用，整个事件循环被卡住，并发失效。"""
    time.sleep(IO_WAIT)  # 阻塞！事件循环无法切去别的任务
    return i * 2


async def run_serial() -> list[int]:
    """串行 await：一个任务等完再等下一个。"""
    return [await async_io_task(i) for i in range(N_TASKS)]


async def run_gather() -> list[int]:
    """gather 并发：一次性把 20 个任务交给事件循环，谁先完成谁先回。"""
    return await asyncio.gather(*(async_io_task(i) for i in range(N_TASKS)))


async def run_blocked() -> list[int]:
    """反例：gather 20 个『假异步』任务（内部是 time.sleep）。"""
    return await asyncio.gather(*(blocking_io_task(i) for i in range(N_TASKS)))


async def main() -> None:
    print(f"== asyncio 实测：{N_TASKS} 个任务 × {IO_WAIT}s 模拟 IO ==")
    for name, coro in [
        ("串行 await", run_serial()),
        ("gather 并发", run_gather()),
        ("gather + time.sleep（反例）", run_blocked()),
    ]:
        t0 = time.perf_counter()
        results = await coro
        dt = time.perf_counter() - t0
        print(f"{name}: {dt:.3f}s（结果 {len(results)} 个，首尾 {results[0]}...{results[-1]}）")

    # 异常处理：return_exceptions=True 让单个失败不拖垮整批
    async def boom(i: int) -> int:
        if i == 3:
            raise ValueError("任务 3 挂了")
        return i

    rs = await asyncio.gather(*(boom(i) for i in range(5)), return_exceptions=True)
    print(f"\nreturn_exceptions=True: {rs}（第 3 个是异常对象，其余照常返回）")


if __name__ == "__main__":
    asyncio.run(main())  # 3.7+ 的标准入口：创建事件循环 → 跑协程 → 关闭
