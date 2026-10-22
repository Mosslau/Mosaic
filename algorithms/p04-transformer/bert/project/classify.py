"""迁移项目：MLM 预训练 + [CLS] 情感分类探针

    uv run python classify.py

在合成情感句上做 MLM，再用 [CLS] 表示训练逻辑回归；验收探针 acc > 0.85。
"""

import sys
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import BertTokenizer, build_data  # noqa: E402
from impl import BertMLM  # noqa: E402


def main() -> None:
    texts, labels = build_data()
    tok = BertTokenizer(texts)
    tokens = tok.encode(texts, context=16)
    model = BertMLM(len(tok.itos), context=16, d_model=32, n_heads=4, d_ff=64,
                    random_state=0)
    model.train(tokens, epochs=200, lr=1e-3)
    mlm = model.evaluate(tokens)
    X = model.encode(tokens)
    Xtr, Xte, ytr, yte = train_test_split(X, labels, test_size=0.3, random_state=0,
                                          stratify=labels)
    clf = LogisticRegression(max_iter=2000).fit(Xtr, ytr)
    acc = clf.score(Xte, yte)
    print(f"MLM loss {mlm['loss']:.3f}，masked acc {mlm['acc']:.3f}")
    print(f"[CLS] 探针 acc：{acc:.3f}")
    assert acc > 0.85
    print("→ [CLS] 表示保留情感信息；探针是评估表示质量的轻量方式。")


if __name__ == "__main__":
    main()
