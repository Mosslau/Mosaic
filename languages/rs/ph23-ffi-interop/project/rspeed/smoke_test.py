"""rspeed Python 冒烟测试：正确性对照（纯 Python 参考实现 vs Rust 扩展）。

验证环境：Python 3.13.12（与编译 pyo3 时相同的解释器）。
运行前提：先构建扩展并放到本目录，见 project/README.md 的步骤 ①~③。
运行命令：python3 -B smoke_test.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rspeed


def approx(a, b, tol=1e-12):
    return abs(a - b) < tol


# ---- 纯 Python 参考实现（正确性基准）----

def py_cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


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


def main() -> int:
    fail = 0

    # 1. 余弦相似度：多组向量对照纯 Python 实现
    cases = [
        ([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]),
        ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ([3.0, 4.0, 0.0], [0.0, 1.0, 0.0]),
        ([float(i) for i in range(500)], [float(499 - i) for i in range(500)]),
    ]
    for a, b in cases:
        if not approx(rspeed.cosine_similarity(a, b), py_cosine(a, b)):
            print("FAIL cosine")
            fail = 1
        if not approx(rspeed.euclidean(a, b), py_euclidean(a, b)):
            print("FAIL euclidean")
            fail = 1

    # 2. 欧氏距离已知值
    if not approx(rspeed.euclidean([0.0, 0.0], [3.0, 4.0]), 5.0):
        print("FAIL euclidean 3-4-5")
        fail = 1

    # 3. chunk：长度/内容对照
    text = ("The quick brown fox jumps over the lazy dog. " * 20)  # 900 字符
    for size, overlap in [(64, 8), (128, 16), (500, 100), (1000, 10)]:
        got = rspeed.chunk_text(text, size, overlap)
        want = py_chunk(text, size, overlap)
        if got != want:
            print(f"FAIL chunk size={size} overlap={overlap}")
            fail = 1
        if any(len(c) > size for c in got):
            print("FAIL chunk too big")
            fail = 1

    # 4. Unicode：按字符不按字节（"你" 是 3 字节）
    u = "你" * 40
    uc = rspeed.chunk_text(u, 7, 1)
    if any(len(c.encode("utf-8")) > 7 * 3 or len(c) > 7 for c in uc):
        print("FAIL unicode chunk")
        fail = 1

    # 5. 错误路径 → ValueError（不是 panic / 崩溃 / 静默）
    for bad in (
        lambda: rspeed.cosine_similarity([1.0], [1.0, 2.0]),
        lambda: rspeed.cosine_similarity([0.0, 0.0], [1.0, 1.0]),
        lambda: rspeed.euclidean([], [1.0]),
        lambda: rspeed.chunk_text("abc", 0, 0),
        lambda: rspeed.chunk_text("abc", 5, 5),
    ):
        try:
            bad()
            print("FAIL: expected ValueError")
            fail = 1
        except ValueError:
            pass

    print("ALL OK" if fail == 0 else "FAIL")
    return fail


if __name__ == "__main__":
    sys.exit(main())
