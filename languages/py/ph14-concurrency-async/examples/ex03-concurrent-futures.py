#!/usr/bin/env python3
# examples/ex03-concurrent-futures.py —— concurrent.futures：统一 Executor 接口（主文档 3.4）
# 验证环境：Python 3.13.9（macOS arm64，14 核，标准库，零第三方依赖）
# 运行：python3 ex03-concurrent-futures.py（离线可跑，已验证）
# 验证状态：已验证 —— as_completed 按完成顺序返回（b→c→d→a，与各自延迟一致，同一延迟内顺序不定）；
#           ProcessPool.map 与 ThreadPool.map 接口完全一致（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：as_completed 完成时刻 b@0.05s / c@0.10s / d@0.16s / a@0.21s（一次运行）
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor, as_completed

IO_DELAYS = {"a": 0.20, "b": 0.05, "c": 0.10, "d": 0.15}  # 每个 IO 任务的延迟（秒）


def io_task(name: str, delay: float) -> str:
    """IO 密集任务：睡 delay 秒后返回。"""
    time.sleep(delay)
    return f"{name}:io-{delay:.2f}"


def cpu_task(n: int) -> int:
    """CPU 密集任务：平方和。"""
    return sum(i * i for i in range(n))


def part_a_map() -> None:
    """executor.map：一行代码把函数应用到整个序列，接口与内置 map 一致。"""
    print("== A. executor.map：ThreadPool 与 ProcessPool 接口一致 ==")
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(io_task, ["a", "b", "c", "d"], [0.1, 0.05, 0.2, 0.08]))
    print(f"ThreadPool.map: {results}")

    with ProcessPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(cpu_task, [5_000_000] * 4))
    print(f"ProcessPool.map: 4 个结果，总和 = {sum(results):,}")


def part_b_as_completed() -> None:
    """submit + as_completed：谁先完成先处理谁（流式消费，不等最慢的）。"""
    print("== B. submit + as_completed：按完成顺序取结果 ==")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures: dict[Future, str] = {
            ex.submit(io_task, name, delay): name for name, delay in IO_DELAYS.items()
        }
        for fut in as_completed(futures):
            name = futures[fut]
            print(f"  {name} 完成 -> {fut.result()}（t={time.perf_counter() - t0:.2f}s）")


def choose_executor(kind: str):
    """选型助手：IO 密集返回线程池，CPU 密集返回进程池 —— 调用方只面对 Executor 接口。"""
    if kind == "io":
        return ThreadPoolExecutor(max_workers=8)
    if kind == "cpu":
        return ProcessPoolExecutor(max_workers=4)
    raise ValueError(f"未知任务类型: {kind!r}")


def part_c_selection() -> None:
    """混合场景：IO 任务用线程池、CPU 任务用进程池，同一套 map 语法。"""
    print("== C. 按任务类型选 Executor：IO 用线程、CPU 用进程 ==")
    with choose_executor("io") as ex:
        r_io = list(ex.map(io_task, ["x", "y"], [0.05, 0.08]))
    with choose_executor("cpu") as ex:
        r_cpu = list(ex.map(cpu_task, [3_000_000, 3_000_000]))
    print(f"IO 任务结果: {r_io}")
    print(f"CPU 任务结果长度: {len(r_cpu)}（总和 {sum(r_cpu):,}）")


if __name__ == "__main__":
    part_a_map()
    part_b_as_completed()
    part_c_selection()
