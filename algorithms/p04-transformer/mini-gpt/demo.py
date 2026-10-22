"""Mini-GPT — demo：字符级训练与采样策略

    uv run python demo.py

    实验一  字符 tokenizer + N 个 Block 的 next-token 训练
    实验二  greedy / temperature / top-k 生成
    实验三  手写 vs torch
"""

from __future__ import annotations

import time

import framework
from impl import CharTokenizer, MiniGPT


def build_corpus() -> str:
    subjects = ["the cat", "a dog", "the bird", "the child", "my friend", "the teacher"]
    verbs = ["sees", "likes", "finds", "helps", "follows", "calls"]
    objects = ["the ball", "a book", "the tree", "the house", "a song", "the river"]
    lines = []
    for i, s in enumerate(subjects):
        for j, v in enumerate(verbs):
            lines.append(f"{s} {v} {objects[(i + j) % len(objects)]}.")
    return (" ".join(lines) + " ") * 4


def split_text(text: str):
    cut = int(len(text) * 0.8)
    return text[:cut], text[cut:]


def main() -> None:
    text = build_corpus()
    tr_text, te_text = split_text(text)
    tok = CharTokenizer().fit(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    print(f"语料 {len(text)} 字符，词表 {len(tok.itos)}，训练/测试 token {len(tr)}/{len(te)}")
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
