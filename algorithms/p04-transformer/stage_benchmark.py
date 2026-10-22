"""p04 阶段横向对照（架构级）

    uv run python stage_benchmark.py

不是“同一任务排名”——BERT/GPT/T5 的目标不同；这里在同一 d_model/heads/context
下比较**参数量、前向延迟、任务位置**，避免把不同任务的精度硬放在一张表里。
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
D_MODEL, HEADS, CTX = 32, 4, 16


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BASE / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def nparams(obj):
    if hasattr(obj, "_params"):
        return int(sum(v.size for v in obj._params().values()))
    if hasattr(obj, "_all_params"):
        return int(sum(v.size for v in obj._all_params().values()))
    return int(sum(v.size for v in vars(obj).values() if isinstance(v, np.ndarray)))


def bench(fn, repeat=20):
    fn()
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - t0) * 1000 / repeat


def main() -> None:
    attn = load("p04_attn", "attention/impl.py")
    block = load("p04_block", "mini-transformer/impl.py")
    bert = load("p04_bert", "bert/impl.py")
    gpt = load("p04_gpt", "mini-gpt/impl.py")
    t5 = load("p04_t5", "t5/impl.py")

    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, CTX, D_MODEL))
    tokens = rng.integers(5, 20, size=(2, CTX))
    tokens[:, 0] = 2

    a = attn.MultiHeadAttention(D_MODEL, HEADS, random_state=0)
    b = block.TransformerBlock(D_MODEL, HEADS, 64, vocab_size=32, context=CTX)
    be = bert.BertMLM(27, context=CTX, d_model=D_MODEL, n_heads=HEADS, d_ff=64)
    g = gpt.MiniGPT(27, context=CTX, d_model=D_MODEL, n_heads=HEADS, n_layers=2, d_ff=64)
    t = t5.T5Toy(11, src_len=5, tgt_len=5, d_model=D_MODEL, n_heads=HEADS, d_ff=64)

    rows = [
        ("attention(MHA)", a, lambda: a.forward(X), "位置混合组件"),
        ("Block(1层)", b, lambda: b.forward(X), "可堆叠层"),
        ("BERT(1层)", be, lambda: be.forward(tokens), "双向 encoder"),
        ("Mini-GPT(2层)", g, lambda: g.forward(tokens), "causal decoder"),
        ("T5(enc+dec)", t, lambda: t.forward(
            rng.integers(3, 11, size=(2, 5)), rng.integers(3, 11, size=(2, 5))), "encoder-decoder"),
    ]
    print("== 架构级对照（d_model=32, heads=4, context=16, CPU） ==")
    print(f"{'模型':16} | {'参数量':>8} | {'前向 ms':>8} | {'任务位置'}")
    print("-" * 64)
    for name, obj, fn, role in rows:
        print(f"{name:16} | {nparams(obj):8d} | {bench(fn):8.2f} | {role}")

    # 注意力 O(T²) 单独验证
    print("\n== attention 前向随 T 增长 ==")
    print(f"{'T':>4} | {'ms':>7}")
    for T in (16, 32, 64, 128):
        Xt = rng.normal(size=(1, T, D_MODEL))
        print(f"{T:4d} | {bench(lambda: a.forward(Xt), repeat=10):7.2f}")
    print("\n→ 这里只比成本/结构；精度表见各实验 README（任务不同，不能横比）。")


if __name__ == "__main__":
    main()
