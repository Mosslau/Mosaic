"""Mini-GPT — demo：字符级训练与采样策略

    uv run python demo.py

    实验一  字符 tokenizer + N 个 Block 的 next-token 训练
    实验二  greedy / temperature / top-k 生成
    实验三  手写 vs torch
"""

from __future__ import annotations

import time
from random import Random

import framework
from impl import CharTokenizer, MiniGPT


def build_corpus() -> list[str]:
    """216 条唯一句子：6 主语 × 6 动词 × 6 宾语，打乱后按行切分。

    旧版用 `(" ".join(lines) + " ") * 4` 复制 4 份，再按字符 80/20 切；
    测试半句里必然出现训练半句的原句，test loss 会偏低。现在按**整行**切，
    train/test 的句子集合不重叠。
    """
    subjects = ["the cat", "a dog", "the bird", "the child", "my friend", "the teacher"]
    verbs = ["sees", "likes", "finds", "helps", "follows", "calls"]
    objects = ["the ball", "a book", "the tree", "the house", "a song", "the river"]
    lines = [f"{s} {v} {o}." for s in subjects for v in verbs for o in objects]
    Random(0).shuffle(lines)
    return lines


def split_lines(lines: list[str], frac: float = 0.8):
    cut = int(len(lines) * frac)
    return lines[:cut], lines[cut:]


def join_lines(lines: list[str]) -> str:
    return " ".join(lines) + " "


def main() -> None:
    lines = build_corpus()
    tr_lines, te_lines = split_lines(lines)
    tr_text, te_text = join_lines(tr_lines), join_lines(te_lines)
    tok = CharTokenizer().fit(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    print(f"语料 {len(lines)} 条唯一句，词表 {len(tok.itos)}，"
          f"训练/测试 token {len(tr)}/{len(te)}")
    print(f"样例：{tr_text[:80]!r}\n")

    print("== 实验一：Mini-GPT next-token（80 轮，2 层） ==")
    gpt = MiniGPT(len(tok.itos), context=16, d_model=32, n_heads=4, n_layers=2,
                  d_ff=64, random_state=0)
    t0 = time.perf_counter()
    gpt.train(tr, epochs=80, lr=3e-3, batch_size=32)
    t_hand = time.perf_counter() - t0
    trm, tem = gpt.evaluate(tr), gpt.evaluate(te)
    print(f"手写：train loss {trm['loss']:.3f}/acc {trm['acc']:.3f}；"
          f"test loss {tem['loss']:.3f}/acc {tem['acc']:.3f}；{t_hand:.1f}s")
    print(f"loss 首/末：{gpt.loss_history[0]:.3f} → {gpt.loss_history[-1]:.3f}\n")

    print("== 实验二：采样策略（prompt='the cat'，40 字符） ==")
    print(f"greedy        : {gpt.generate('the cat', tok, 40, temperature=0.0)!r}")
    print(f"T=0.8         : {gpt.generate('the cat', tok, 40, temperature=0.8, seed=1)!r}")
    print(f"T=1.2         : {gpt.generate('the cat', tok, 40, temperature=1.2, seed=1)!r}")
    topk = gpt.generate('the cat', tok, 40, temperature=0.8, top_k=5, seed=1)
    print(f"top-k=5, T=0.8: {topk!r}\n")

    print("== 实验三：手写 vs torch ==")
    fm = framework.run_framework(tr, te, len(tok.itos), context=16, n_layers=2, epochs=80)
    print(f"torch：train loss {fm['train_loss']:.3f}；test loss {fm['test_loss']:.3f}/"
          f"acc {fm['test_acc']:.3f}；{fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
