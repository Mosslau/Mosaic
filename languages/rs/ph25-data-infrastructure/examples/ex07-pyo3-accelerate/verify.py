#!/usr/bin/env python3
"""ph25 ex07 verify：Python 3.13 实际 import 并调用 ph25_accel 模块。

运行方式（需先 cargo build --release，再把它产出的动态库按解释器后缀改名）：
    mkdir -p /tmp/ph25-py && cp /tmp/ph25-ex07-target/release/libph25_accel.dylib \
        /tmp/ph25-py/ph25_accel.cpython-313-darwin.so
    PYTHONPATH=/tmp/ph25-py <python3.13> verify.py
"""
import time
import random

import ph25_accel as accel

# —— 1. parse_frames：帧拆分 + 错误路径 ——
frames = accel.parse_frames(b"\x03\x00\x00\x00abc\x02\x00\x00\x00de\x00\x00\x00\x00")
assert frames == [b"abc", b"de", b""], frames
print(f"[1] parse_frames 正常流 → {frames}")
for bad in (b"\x03\x00\x00\x00abc\x02", b"\x0a\x00\x00\x00short"):
    try:
        accel.parse_frames(bad)
        raise AssertionError("坏流应当抛 ValueError")
    except ValueError as e:
        print(f"[1] parse_frames 坏流 → ValueError：{e}")

# —— 2. l2_distance / bruteforce_topk ——
assert accel.l2_distance([1.0, 2.0, 2.0], [4.0, 6.0, 2.0]) == 5.0
items = [[1.0, 0.0], [100.0, 100.0], [0.5, 0.0]]
assert accel.bruteforce_topk([0.0, 0.0], items, 2) == [2, 0]
print("[2] l2_distance/bruteforce_topk 正确性通过")

# —— 3. 热路径演示：Rust 暴力 top-k vs 纯 Python 循环（真实计时，非 benchmark） ——
DIM, N = 8, 20_000
random.seed(7)
items = [[random.random() for _ in range(DIM)] for _ in range(N)]
q = [random.random() for _ in range(DIM)]

t0 = time.perf_counter()
top = accel.bruteforce_topk(q, items, 10)
t_rust = time.perf_counter() - t0

def py_topk(query, data, k):
    d = [(sum((x - y) ** 2 for x, y in zip(query, vec)) ** 0.5, i) for i, vec in enumerate(data)]
    d.sort()
    return [i for _, i in d[:k]]

t0 = time.perf_counter()
top_py = py_topk(q, items, 10)
t_py = time.perf_counter() - t0
assert top == top_py, "Rust 与 Python 的 top-k 结果应一致"
print(f"[3] 暴力 top-k（N={N}, dim={DIM}）：Rust {t_rust*1e3:.1f} ms vs 纯 Python {t_py*1e3:.1f} ms（本机一次实测，供参考）")

print("verify.py 全部通过")
