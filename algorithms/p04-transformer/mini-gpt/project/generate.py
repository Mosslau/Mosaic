"""迁移项目：多 prompt / 多采样策略生成

    uv run python generate.py

训练一个字符级 Mini-GPT，对两个 prompt 用 greedy/T/top-k 生成；
验收 test next-token acc > 0.85，且每个 prompt 都能生成非空文本。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import build_corpus, split_text  # noqa: E402
from impl import CharTokenizer, MiniGPT  # noqa: E402


def main() -> None:
    text = build_corpus()
    tr_text, te_text = split_text(text)
    tok = CharTokenizer().fit(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    gpt = MiniGPT(len(tok.itos), context=16, d_model=32, n_heads=4, n_layers=2,
                  d_ff=64, random_state=0)
    gpt.train(tr, epochs=80, lr=3e-3, batch_size=32)
    acc = gpt.evaluate(te)["acc"]
    print(f"test next-token acc：{acc:.3f}")

    for prompt in ("the cat", "a dog"):
        print(f"\nprompt：{prompt!r}")
        for name, kw in (("greedy", dict(temperature=0.0)),
                         ("T=0.8", dict(temperature=0.8, seed=1)),
                         ("top-k=5", dict(temperature=0.8, top_k=5, seed=1))):
            out = gpt.generate(prompt, tok, n_steps=36, **kw)
            print(f"  {name:8}: {out!r}")
    assert acc > 0.85


if __name__ == "__main__":
    main()
