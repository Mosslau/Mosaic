"""迁移项目：copy/reverse seq2seq 生成

    uv run python copy_reverse.py

训练 encoder-decoder，在测试集上做 copy/reverse；验收 exact > 0.9。
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import demo as D  # noqa: E402
from impl import T5Toy  # noqa: E402


def main() -> None:
    vocab, train, test = D.build_pairs()
    model = T5Toy(len(vocab.itos), src_len=5, tgt_len=5, d_model=32, n_heads=4,
                  d_ff=64, random_state=0)
    model.train(train, epochs=80, lr=3e-3)
    ex = []
    for p in test:
        pred = model.generate(p[0], 5, vocab)
        ex.append(D.exact(pred, p[2]))
    print(f"train token acc：{model.acc_history[-1]:.3f}")
    print(f"test exact：{np.mean(ex):.3f}")
    for i in (0, 1):
        pred = model.generate(test[i][0], 5, vocab)
        print(f"  {vocab.decode(test[i][0])!r} → {vocab.decode(pred)!r} "
              f"(target {vocab.decode(test[i][2])!r})")
    assert np.mean(ex) > 0.9
    print("→ copy/reverse 都能做；结构有效，但不代表真实翻译能力。")


if __name__ == "__main__":
    main()
