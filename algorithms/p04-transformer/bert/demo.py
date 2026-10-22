"""BERT / MLM — demo：15% mask、MLM、[CLS] 分类探针、torch 对照

    uv run python demo.py
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import BertMLM
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

PAD, MASK, CLS, SEP, UNK = 0, 1, 2, 3, 4


class BertTokenizer:
    def __init__(self, texts):
        chars = sorted({c for t in texts for c in t})
        self.itos = ["<pad>", "<mask>", "<cls>", "<sep>", "<unk>"] + chars
        self.stoi = {c: i for i, c in enumerate(self.itos)}

    def encode(self, texts, context=16):
        out = np.full((len(texts), context), PAD, dtype=int)
        for i, text in enumerate(texts):
            ids = [CLS] + [self.stoi.get(c, UNK) for c in text[:context - 2]] + [SEP]
            out[i, :len(ids)] = ids
        return out

    def decode(self, ids):
        return "".join(self.itos[i] for i in ids)


def build_data():
    pos = ["the cat is happy", "a dog is friendly", "the bird is kind", "the child is calm",
           "my friend is cheerful", "the teacher is gentle"]
    neg = ["the cat is sad", "a dog is angry", "the bird is cruel", "the child is tired",
           "my friend is gloomy", "the teacher is strict"]
    texts, labels = [], []
    for s in pos:
        texts.append(s + " .")
        labels.append(1)
    for s in neg:
        texts.append(s + " .")
        labels.append(0)
    # 重复增强，让 MLM 有更多样本
    texts = texts * 4
    labels = labels * 4
    return texts, np.array(labels)


def main() -> None:
    texts, labels = build_data()
    tok = BertTokenizer(texts)
    tokens = tok.encode(texts, context=16)
    print(f"句子 {len(texts)}，词表 {len(tok.itos)}，context 16")
    print(f"样例：{texts[0]!r} → {tokens[0][:10].tolist()} ...")

    model = BertMLM(len(tok.itos), context=16, d_model=32, n_heads=4, d_ff=64,
                    random_state=0)
    t0 = time.perf_counter()
    model.train(tokens, epochs=200, lr=1e-3)
    t_hand = time.perf_counter() - t0
    ev = model.evaluate(tokens)
    print(f"MLM：train loss {model.loss_history[0]:.3f} → {model.loss_history[-1]:.3f}；"
          f"eval loss {ev['loss']:.3f} / masked acc {ev['acc']:.3f}；{t_hand:.1f}s")

    # [CLS] 线性探针
    X = model.encode(tokens)
    Xtr, Xte, ytr, yte = train_test_split(X, labels, test_size=0.3, random_state=0,
                                          stratify=labels)
    clf = LogisticRegression(max_iter=2000).fit(Xtr, ytr)
    print(f"[CLS] 线性探针 acc：{clf.score(Xte, yte):.3f}")

    # 一个 mask 预测示例
    demo = tokens[:1].copy()
    demo[0, 2] = MASK
    pred = model.predict_masked(demo)[0]
    print(f"mask 位置预测：{tok.decode([pred[2]])!r}（原文 {tok.decode([tokens[0, 2]])!r}）\n")

    print("== 手写 vs torch ==")
    fm = framework.run_framework(tokens, labels, tok, context=16, epochs=200)
    print(f"torch：MLM loss {fm['loss']:.3f}，masked acc {fm['acc']:.3f}，"
          f"probe acc {fm['probe']:.3f}，{fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
