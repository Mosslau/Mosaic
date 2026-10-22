"""迷你 Transformer Block — demo：next-token 训练、残差消融、torch 对照

    uv run python demo.py

    实验一  小语料 next-token：手写 Block 的训练/测试 loss 与准确率
    实验二  残差消融：有/无残差的训练曲线
    实验三  手写 vs torch 的 loss/准确率/耗时
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import TransformerBlock


def build_corpus() -> str:
    """离线合成小语料：主谓宾模板，字符级，不依赖下载。"""
    subjects = ["the cat", "a dog", "the bird", "the child", "my friend", "the teacher"]
    verbs = ["sees", "likes", "finds", "helps", "follows", "calls"]
    objects = ["the ball", "a book", "the tree", "the house", "a song", "the river"]
    lines = []
    for i, s in enumerate(subjects):
        for j, v in enumerate(verbs):
            lines.append(f"{s} {v} {objects[(i + j) % len(objects)]}.")
    text = " ".join(lines) + " "
    return (text * 4).strip()


class CharTokenizer:
    def __init__(self, text: str):
        # <unk> 固定为 0；字符表只从训练文本构建，避免测试集泄漏
        chars = ["<unk>"] + sorted(set(text))
        self.stoi = {c: i for i, c in enumerate(chars)}
        self.itos = chars

    def encode(self, text: str):
        return np.array([self.stoi.get(c, 0) for c in text], dtype=int)

    def decode(self, ids):
        return "".join(self.itos[i] for i in ids)


def split_tokens(text: str):
    cut = int(len(text) * 0.8)
    return text[:cut], text[cut:]


def main() -> None:
    text = build_corpus()
    tr_text, te_text = split_tokens(text)
    tok = CharTokenizer(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    print(f"语料 {len(text)} 字符，词表 {len(tok.itos)}，训练/测试 token {len(tr)}/{len(te)}")
    print(f"样例：{tr_text[:70]!r}\n")

    print("== 实验一：手写 Block next-token（40 轮） ==")
    block = TransformerBlock(d_model=32, n_heads=4, d_ff=64, vocab_size=len(tok.itos),
                             context=16, random_state=0)
    t0 = time.perf_counter()
    block.train(tr, epochs=40, lr=3e-3, batch_size=32)
    t_hand = time.perf_counter() - t0
    train_m = block.evaluate(tr)
    test_m = block.evaluate(te)
    print(f"手写：train loss {train_m['loss']:.3f} / acc {train_m['acc']:.3f}；"
          f"test loss {test_m['loss']:.3f} / acc {test_m['acc']:.3f}；{t_hand:.1f}s")
    print(f"loss 曲线首/末：{block.loss_history[0]:.3f} → {block.loss_history[-1]:.3f}\n")

    print("== 实验二：残差消融（同样 40 轮） ==")
    no_res = TransformerBlock(d_model=32, n_heads=4, d_ff=64, vocab_size=len(tok.itos),
                              context=16, use_residual=False, random_state=0)
    no_res.train(tr, epochs=40, lr=3e-3, batch_size=32)
    m_no = no_res.evaluate(te)
    print(f"无残差：test loss {m_no['loss']:.3f} / acc {m_no['acc']:.3f}")
    print(f"有残差：test loss {test_m['loss']:.3f} / acc {test_m['acc']:.3f}\n")

    print("== 实验三：手写 vs torch ==")
    fm = framework.run_framework(tr, te, vocab_size=len(tok.itos), context=16, epochs=40)
    print(f"torch：train loss {fm['train_loss']:.3f}；test loss {fm['test_loss']:.3f} / "
          f"acc {fm['test_acc']:.3f}；{fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
