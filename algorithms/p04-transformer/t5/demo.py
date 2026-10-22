"""T5 / encoder-decoder — demo：copy/reverse 生成

    uv run python demo.py
"""

from __future__ import annotations

import itertools
import time

import framework
import numpy as np
from impl import BOS, EOS, T5Toy, Vocab


def build_pairs():
    vocab = Vocab("abcdef")
    seqs = ["".join(p) for p in itertools.product("abcdef", repeat=4)]
    rng = np.random.default_rng(0)
    order = rng.permutation(len(seqs))
    tr = [seqs[i] for i in order[:700]]
    te = [seqs[i] for i in order[700:900]]

    def make(s, rev):
        target = s[::-1] if rev else s
        src = [vocab.stoi["<rev>" if rev else "<copy>"]] + vocab.encode(s)
        return src, [BOS] + vocab.encode(target), vocab.encode(target) + [EOS]

    train = [make(s, i % 2 == 1) for i, s in enumerate(tr)]
    test = [make(s, i % 2 == 1) for i, s in enumerate(te)]
    return vocab, train, test


def exact(pred, target):
    chars = [i for i in pred if i >= 5]
    return chars == target[:-1]


def main() -> None:
    vocab, train, test = build_pairs()
    print(f"词表 {len(vocab.itos)}，训练 {len(train)} 对，测试 {len(test)} 对（copy/reverse 各半）")

    model = T5Toy(len(vocab.itos), src_len=5, tgt_len=5, d_model=32, n_heads=4,
                  d_ff=64, random_state=0)
    t0 = time.perf_counter()
    model.train(train, epochs=80, lr=3e-3)
    t_hand = time.perf_counter() - t0
    print(f"手写：loss {model.loss_history[0]:.3f} → {model.loss_history[-1]:.4f}；"
          f"train token acc {model.acc_history[-1]:.3f}；{t_hand:.1f}s")

    preds = [model.generate(p[0], 5, vocab) for p in test]
    ex = [exact(pr, p[2]) for pr, p in zip(preds, test)]
    print(f"test：exact {np.mean(ex):.3f}（copy {np.mean(ex[0::2]):.3f} / "
          f"reverse {np.mean(ex[1::2]):.3f}）")

    for i in (0, 1):
        print(f"  示例 {i}: src={vocab.decode(test[i][0])!r} → "
              f"{vocab.decode(preds[i])!r}（target {vocab.decode(test[i][2])!r}）")

    print("\n== 手写 vs torch ==")
    fm = framework.run_framework(train, test, len(vocab.itos), epochs=300)
    print(f"torch：loss {fm['loss']:.4f}；token acc {fm['acc']:.3f}；"
          f"exact {fm['exact']:.3f}；{fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
