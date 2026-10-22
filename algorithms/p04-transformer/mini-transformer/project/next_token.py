"""迁移项目：训练 Block 做 next-token 续写

    uv run python next_token.py

在合成语料上训练一个 pre-LN Block，给定 prompt 连续预测下一个字符。
验收：测试 next-token acc > 0.7，且能生成非空续写。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import CharTokenizer, build_corpus, split_tokens  # noqa: E402
from impl import TransformerBlock  # noqa: E402


def main() -> None:
    text = build_corpus()
    tr_text, te_text = split_tokens(text)
    tok = CharTokenizer(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    block = TransformerBlock(32, 4, 64, vocab_size=len(tok.itos), context=16,
                             random_state=0)
    block.train(tr, epochs=40, lr=3e-3, batch_size=32)
    acc = block.evaluate(te)["acc"]

    prompt = "the cat"
    ids = list(tok.encode(prompt))
    for _ in range(40):
        idx, _ = block.predict_next(ids)
        ids.append(idx)
    out = tok.decode(ids)
    print(f"test next-token acc：{acc:.3f}")
    print(f"prompt：{prompt!r}")
    print(f"续写：{out!r}")
    assert acc > 0.7 and len(out) > len(prompt)


if __name__ == "__main__":
    main()
