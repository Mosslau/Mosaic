"""文本主题模型 — demo：TF-IDF + NMF 主题发现"""

from __future__ import annotations

import numpy as np
from impl import NMF, Tfidf

TOPICS = {
    "space": "rocket orbit nasa planet launch astronaut space moon satellite".split(),
    "food": "pizza pasta cheese bread recipe kitchen food cook meal".split(),
    "sport": "tennis football match player team score sport coach game".split(),
}


def make_docs(n_per=8, seed=0):
    rng = np.random.default_rng(seed)
    docs, labels = [], []
    names = list(TOPICS)
    for k, name in enumerate(names):
        for _ in range(n_per):
            words = rng.choice(TOPICS[name], size=6, replace=True).tolist()
            docs.append(" ".join(words))
            labels.append(k)
    return docs, labels, names


def main() -> None:
    docs, labels, names = make_docs()
    tf = Tfidf().fit(docs)
    X = tf.transform(docs)
    m = NMF(n_topics=3, epochs=300, random_state=0).fit(X)
    print(f"文档 {len(docs)}，词表 {len(tf.vocab)}，主题 3")
    for k, words in enumerate(m.top_words(tf.vocab, 5)):
        print(f"topic {k}: {words}")
    W = m.transform(X)
    pred = W.argmax(1)
    # 主题编号与真实标签对齐（匈牙利/贪心）
    labels_arr = np.asarray(labels)
    mapping = {}
    for k in range(3):
        if (pred == k).any():
            mapping[k] = int(np.bincount(labels_arr[pred == k], minlength=3).argmax())
        else:
            mapping[k] = -1
    acc = float(np.mean([mapping[p] == y for p, y in zip(pred, labels)]))
    print(f"loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}；主题纯度 {acc:.3f}")
    assert acc >= 0.9


if __name__ == "__main__":
    main()
