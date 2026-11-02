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
    """24 条**唯一**句子：6 个主语 × 2 个句式 × 正/负各一。

    不再用 `texts * 4` 做重复增强——那会让同一条句子同时落进 train/test，
    探针指标会变成记忆而不是泛化。数据量靠句式与主语扩展，不靠复制。
    """
    subjects = ["the cat", "a dog", "the bird", "the child", "my friend",
                "the teacher", "the doctor", "the artist", "the pilot", "the chef"]
    pos = ["happy", "friendly", "kind", "calm", "cheerful",
           "gentle", "bright", "patient", "honest", "lively"]
    neg = ["sad", "angry", "cruel", "tired", "gloomy",
           "strict", "dull", "rude", "lazy", "anxious"]
    templates = ["{s} is {a} .", "{s} looks {a} .", "{s} seems {a} .", "{s} feels {a} ."]
    texts, labels = [], []
    for subject, p, n in zip(subjects, pos, neg):
        for template in templates:
            texts.append(template.format(s=subject, a=p))
            labels.append(1)
            texts.append(template.format(s=subject, a=n))
            labels.append(0)
    return texts, np.array(labels)


def main() -> None:
    texts, labels = build_data()
    idx = np.arange(len(texts))
    train_idx, test_idx = train_test_split(idx, test_size=0.3, random_state=0,
                                           stratify=labels)
    train_texts = [texts[i] for i in train_idx]
    test_texts = [texts[i] for i in test_idx]
    train_labels = labels[train_idx]
    test_labels = labels[test_idx]

    tok = BertTokenizer(texts)
    train_tokens = tok.encode(train_texts, context=16)
    test_tokens = tok.encode(test_texts, context=16)
    print(f"句子 {len(texts)}（唯一 {len(set(texts))}），train/test = "
          f"{len(train_texts)}/{len(test_texts)}；词表 {len(tok.itos)}，context 16")
    print(f"样例：{train_texts[0]!r} → {train_tokens[0][:10].tolist()} ...")

    model = BertMLM(len(tok.itos), context=16, d_model=32, n_heads=4, d_ff=64,
                    random_state=0)
    t0 = time.perf_counter()
    model.train(train_tokens, epochs=200, lr=1e-3)
    t_hand = time.perf_counter() - t0
    ev = model.evaluate(test_tokens)
    print(f"MLM：train loss {model.loss_history[0]:.3f} → {model.loss_history[-1]:.3f}；"
          f"test loss {ev['loss']:.3f} / masked acc {ev['acc']:.3f}；{t_hand:.1f}s")

    # [CLS] 线性探针：train 编码训练，test 编码评估，句子级不重叠
    Xtr = model.encode(train_tokens)
    Xte = model.encode(test_tokens)
    clf = LogisticRegression(max_iter=2000).fit(Xtr, train_labels)
    print(f"[CLS] 线性探针 test acc：{clf.score(Xte, test_labels):.3f}")

    # 一个 mask 预测示例
    demo = test_tokens[:1].copy()
    demo[0, 2] = MASK
    pred = model.predict_masked(demo)[0]
    print(f"mask 位置预测：{tok.decode([pred[2]])!r}（原文 {tok.decode([test_tokens[0, 2]])!r}）\n")

    print("== 手写 vs torch ==")
    fm = framework.run_framework(train_tokens, train_labels, tok, context=16, epochs=200,
                                 test_tokens=test_tokens, test_labels=test_labels)
    print(f"torch：MLM loss {fm['loss']:.3f}，masked acc {fm['acc']:.3f}，"
          f"probe acc {fm['probe']:.3f}，{fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
