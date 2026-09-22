"""rspeed 性能对比：纯 Python 实现 vs Rust 扩展（ph23 project 验收项 ③）。

测量口径（诚实起见逐条写明）：
- 纯 Python 版是"教科书循环"，Rust 版调用含「Python list → Vec<f64>」的一次性转换——
  测的是「真实调用成本」，不玩「转换不算」的文字游戏；
- 每档跑 best-of-5（取最小，避开系统噪声），报告单次调用耗时与加速比；
- 数字只在本机+本 Python 有效，换机器请重跑本脚本（ph22 的先测量纪律）。

运行前提：先构建扩展并放到本目录，见 project/README.md 步骤 ①~③。
运行命令：python3 -B bench.py
"""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rspeed

random.seed(42)


# ---- 纯 Python 参考实现 ----

def py_euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def py_chunk(s, size, overlap):
    if len(s) <= size:
        return [s]
    step = size - overlap
    out = []
    start = 0
    while start < len(s):
        end = min(start + size, len(s))
        out.append(s[start:end])
        if end == len(s):
            break
        start += step
    return out


def best_of(fn, rounds=5):
    """跑 rounds 轮取最小耗时（毫秒/次）。"""
    best = float("inf")
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - t0) * 1000.0)
    return best


def main() -> int:
    # ---- 1. 欧氏距离：dim=200_000 的向量对 ----
    dim = 200_000
    a = [random.random() for _ in range(dim)]
    b = [random.random() for _ in range(dim)]

    # 先做一次正确性对照，防"快但错"
    assert math.isclose(rspeed.euclidean(a, b), py_euclidean(a, b), rel_tol=1e-12)

    t_py = best_of(lambda: py_euclidean(a, b))
    t_rs = best_of(lambda: rspeed.euclidean(a, b))

    # ---- 2. RAG chunk：约 200KB 的文档文本 ----
    doc = ("Rust 是一门强调内存安全与并发的系统编程语言。 "
           "它通过所有权与借用检查在编译期消除数据竞争与悬垂指针。"
           "FFI（外部函数接口）让 Rust 可以安全地与其他语言协作。") * 1000
    text = doc  # 含中文与空格，约 200KB
    assert len(text.encode("utf-8")) > 150_000, "chunk 基准应使用足够大的文本"
    # 单次正确性对照（防"快但错"）
    assert rspeed.chunk_text(text, 256, 32) == py_chunk(text, 256, 32)

    t_pyc = best_of(lambda: py_chunk(text, 256, 32))
    t_rsc = best_of(lambda: rspeed.chunk_text(text, 256, 32))

    # ---- 输出表格 ----
    print(f"向量维度: {dim} | chunk 文本: {len(text.encode('utf-8'))} bytes (utf-8)")
    print(f"{'工作负载':<28}{'纯 Python (ms)':>16}{'Rust 扩展 (ms)':>16}{'加速比':>10}")
    print(f"{'euclidean(dim=200k)':<28}{t_py:>16.2f}{t_rs:>16.2f}{t_py / t_rs:>9.1f}x")
    print(f"{'chunk_text(256/32)':<28}{t_pyc:>16.2f}{t_rsc:>16.2f}{t_pyc / t_rsc:>9.1f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
