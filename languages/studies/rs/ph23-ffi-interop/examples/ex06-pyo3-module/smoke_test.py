"""ex06 冒烟测试：import 编译好的 Rust 扩展并验证三个导出函数。

教学点：Rust 的 PyResult 错误（Vec 长度不一致 / chunk_size=0 等）在 Python 侧
表现为 ValueError 异常——错误跨边界的形态由 pyo3 决定，与 C 错误码形成对照。

验证环境：Python 3.13.12（与编译 pyo3 时用的同一解释器）。
运行前提：先按 examples/README.md 构建并把 .so 放到本目录（或 sys.path）。
运行命令：python3 -B smoke_test.py   （-B 防止生成 __pycache__）
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ex06_geo as geo


def approx(a, b, tol=1e-12):
    return abs(a - b) < tol


def main() -> int:
    fail = 0

    # 1. 余弦相似度：同向=1、垂直=0（与纯 Python 参考结果对照）
    a = [1.0, 2.0, 3.0]
    b = [1.0, 2.0, 3.0]
    got = geo.cosine_similarity(a, b)
    if not approx(got, 1.0):
        print(f"FAIL cosine same dir: {got}")
        fail = 1

    def cos_pure(x, y):
        dot = sum(i * j for i, j in zip(x, y))
        return dot / (math.sqrt(sum(i * i for i in x)) * math.sqrt(sum(j * j for j in y)))

    c = [1.0, 0.0, 0.0]
    d = [0.0, 1.0, 0.0]
    assert approx(geo.cosine_similarity(c, d), 0.0)
    e = [3.0, 4.0, 0.0]
    f = [0.0, 1.0, 0.0]
    got = geo.cosine_similarity(e, f)
    if not approx(got, cos_pure(e, f)):
        print(f"FAIL cosine vs pure: {got}")
        fail = 1

    # 2. 欧氏距离
    if not approx(geo.euclidean([0.0, 0.0], [3.0, 4.0]), 5.0):
        print("FAIL euclidean")
        fail = 1

    # 3. chunk_text：与 Python 参考实现（同一切分规则）逐项比对
    text = "".join(f"{i % 10}" for i in range(60))  # 60 字符
    chunks = geo.chunk_text(text, 10, 2)

    def chunk_pure(s, size, overlap):
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

    expect = chunk_pure(text, 10, 2)
    if chunks != expect:
        print(f"FAIL chunk mismatch: {len(chunks)} vs {len(expect)}")
        fail = 1
    if any(len(c) > 10 for c in chunks):
        print("FAIL chunk size")
        fail = 1

    # 4. 错误路径应抛 ValueError（而非崩溃/静默）
    for bad_call in (
        lambda: geo.cosine_similarity([1.0], [1.0, 2.0]),
        lambda: geo.chunk_text("abc", 0, 0),
        lambda: geo.chunk_text("abc", 5, 5),
    ):
        try:
            bad_call()
            print("FAIL: expected ValueError")
            fail = 1
        except ValueError:
            pass

    # 5. Rust 侧传出的类型：Vec<String> → list[str]
    out = geo.chunk_text("hello world", 5, 1)
    assert isinstance(out, list) and all(isinstance(c, str) for c in out)

    print(f"smoke: chunks(len={len(chunks)}) / cos(3,4,0 vs 0,1,0)={got:.4f}")
    print("ALL OK" if fail == 0 else "FAIL")
    return fail


if __name__ == "__main__":
    sys.exit(main())
