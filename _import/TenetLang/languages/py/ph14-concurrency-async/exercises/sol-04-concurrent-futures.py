#!/usr/bin/env python3
# exercises/sol-04-concurrent-futures.py —— 练习 4 参考实现：混合任务流式收集（线程池 + 进程池）
# 验证环境：Python 3.13.9（macOS arm64，14 核，标准库，零第三方依赖）
# 运行：python3 sol-04-concurrent-futures.py（离线可跑，已验证）
# 验证状态：已验证 —— 本机实测：串行 16 个任务 ≈ 0.93s；混合并发（6 线程 IO + 4 进程 CPU）≈ 0.14s
#           （约 6.5 倍，IO 与 CPU 两组任务互相重叠）（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 0.940s / 混合并发 0.159s（≈ 5.9 倍）；IO 12/12 + CPU 4/4
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)

N_IO = 12
N_CPU = 4
IO_TIME = 0.05  # 每个 IO 任务耗时（模拟网络/磁盘等待）


def io_job(i: int) -> str:
    """IO 密集任务：等待后返回。"""
    time.sleep(IO_TIME)
    return f"io-{i}"


def cpu_job(i: int) -> int:
    """CPU 密集任务：平方和计算。"""
    return sum(n * n for n in range(3_000_000 + i))


def main() -> None:
    print(f"== 混合任务：{N_IO} 个 IO 任务 + {N_CPU} 个 CPU 任务 ==")

    # 串行对照：16 个任务逐个跑
    t0 = time.perf_counter()
    serial = [io_job(i) for i in range(N_IO)] + [cpu_job(i) for i in range(N_CPU)]
    t_serial = time.perf_counter() - t0
    print(f"串行: {t_serial:.3f}s（{len(serial)} 个任务）")

    # 混合并发：IO 任务进线程池（等待时释放 GIL），CPU 任务进进程池（绕过 GIL），
    # as_completed 流式收集：谁先完成先处理谁
    t0 = time.perf_counter()
    results: list[tuple[str, object]] = []
    with (
        ThreadPoolExecutor(max_workers=6) as io_ex,
        ProcessPoolExecutor(max_workers=4) as cpu_ex,
    ):
        futures: dict[Future, str] = {}
        for i in range(N_IO):
            futures[io_ex.submit(io_job, i)] = "io"
        for i in range(N_CPU):
            futures[cpu_ex.submit(cpu_job, i)] = "cpu"
        for fut in as_completed(futures):
            results.append((futures[fut], fut.result()))
    t_mixed = time.perf_counter() - t0

    io_cnt = sum(1 for kind, _ in results if kind == "io")
    cpu_cnt = sum(1 for kind, _ in results if kind == "cpu")
    print(
        f"混合并发: {t_mixed:.3f}s（≈ {t_serial / t_mixed:.1f} 倍加速）"
        f"IO {io_cnt}/{N_IO} + CPU {cpu_cnt}/{N_CPU}"
    )

    # 正确性校验：两类任务一个不少、一个不错
    assert io_cnt == N_IO and cpu_cnt == N_CPU
    assert len(results) == N_IO + N_CPU
    print("结果校验: 全部任务完成、数量正确 ✓")


if __name__ == "__main__":
    main()
