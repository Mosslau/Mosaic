#!/usr/bin/env python3
# exercises/sol-02-cpu-processes.py —— 练习 2 参考实现：多进程处理大计算（CPU 密集 + GIL 反例）
# 验证环境：Python 3.13.9（macOS arm64，14 核，标准库，零第三方依赖）
# 运行：python3 sol-02-cpu-processes.py（离线可跑，已验证；ProcessPoolExecutor 必须在 main 内创建）
# 验证状态：已验证 —— 本机实测：串行 ≈ 2.7s，多进程(4) ≈ 0.95s（约 2.7~2.8 倍）；线程(4) ≈ 2.6~2.9s
#           （GIL 反例，无加速）（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 2.666s / 多进程(4) 0.937s（≈ 2.8 倍）/ 线程(4) 2.875s；质数总数 78,498
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def count_primes(lo: int, hi: int) -> int:
    """统计 [lo, hi) 内质数个数（简单试除法，纯 CPU 计算，不释放 GIL）。"""
    cnt = 0
    for n in range(lo, hi):
        if n < 2:
            continue
        is_prime = True
        d = 2
        while d * d <= n:
            if n % d == 0:
                is_prime = False
                break
            d += 1
        if is_prime:
            cnt += 1
    return cnt


def main() -> None:
    LIMIT = 1_000_000
    CHUNKS = 4
    # 把 [2, 1_000_000) 切成 4 段，每段交给一个 worker
    bounds = [(i * LIMIT // CHUNKS, (i + 1) * LIMIT // CHUNKS) for i in range(CHUNKS)]
    los = [b[0] for b in bounds]
    his = [b[1] for b in bounds]

    print(f"== 质数统计：1~{LIMIT:,} 切成 {CHUNKS} 段 ==")

    t0 = time.perf_counter()
    serial = sum(count_primes(*b) for b in bounds)
    t_serial = time.perf_counter() - t0
    print(f"串行: {t_serial:.3f}s 质数总数={serial}")

    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as ex:  # 4 个进程各占一个核，真并行
        parts = list(ex.map(count_primes, los, his))
    t_proc = time.perf_counter() - t0
    print(f"多进程(4): {t_proc:.3f}s（≈ {t_serial / t_proc:.1f} 倍）每段={parts}")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:  # GIL 反例：线程轮流抢锁，无加速
        tparts = list(ex.map(count_primes, los, his))
    t_thr = time.perf_counter() - t0
    print(f"线程(4) GIL反例: {t_thr:.3f}s（≈ 串行，纯计算无法并行）")

    # 正确性校验：三种方式质数总数必须一致
    assert serial == sum(parts) == sum(tparts), "质数统计结果不一致！"
    print(f"结果校验: 三种方式质数总数一致（{serial}）✓")


if __name__ == "__main__":
    # 必须保护：spawn 子进程会重新导入本模块，无保护会无限递归创建进程
    main()
