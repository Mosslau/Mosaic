#!/usr/bin/env python3
# examples/ex02-multiprocessing-cpu.py —— multiprocessing：CPU 密集实测与 GIL 反例（主文档 3.3）
# 验证环境：Python 3.13.9（macOS arm64，14 核，标准库，零第三方依赖）
# 运行：python3 ex02-multiprocessing-cpu.py（离线可跑，已验证；ProcessPoolExecutor 必须放在
#       if __name__ == "__main__": 保护内，见文件末尾）
# 验证状态：已验证 —— 本机实测：串行 ≈ 2.4~2.5s，多进程(4) ≈ 0.7s（约 3.2~3.6 倍加速）；
#           线程(4) ≈ 2.3s（GIL 反例：无加速）（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 2.357s / 多进程(4) 0.739s / 线程(4) 2.304s（一次运行）
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

N_TASKS = 4
LIMIT = 20_000_000  # 每个任务累加到 2000 万


def cpu_task(_: int) -> int:
    """纯计算任务：0..LIMIT 的平方和。整个循环都不释放 GIL。"""
    return sum(i * i for i in range(LIMIT))


def run_serial() -> list[int]:
    return [cpu_task(i) for i in range(N_TASKS)]


def run_process() -> list[int]:
    # 进程池：每个 worker 是独立进程，各占一个核，绕过 GIL 真并行
    with ProcessPoolExecutor(max_workers=4) as ex:
        return list(ex.map(cpu_task, range(N_TASKS)))


def run_thread() -> list[int]:
    # 线程池跑纯计算：GIL 反例 —— 线程轮流抢锁执行字节码，无法并行
    with ThreadPoolExecutor(max_workers=4) as ex:
        return list(ex.map(cpu_task, range(N_TASKS)))


def main() -> None:
    print(f"== CPU 密集实测：{N_TASKS} 个任务 × {LIMIT:,} 次平方和 ==")
    cases = [("串行", run_serial), ("多进程(4)", run_process), ("线程(4) GIL反例", run_thread)]
    for name, fn in cases:
        t0 = time.perf_counter()
        results = fn()
        dt = time.perf_counter() - t0
        print(f"{name}: {dt:.3f}s（结果校验 sum={sum(results):,}）")

    # 关键结论打印
    print("\n结论：多进程真并行（每核一个进程）；线程被 GIL 卡住，纯计算无加速（甚至略慢）。")


if __name__ == "__main__":
    # 必须保护：spawn/fork 子进程会重新导入本模块，没有这层保护会无限递归创建进程
    main()
