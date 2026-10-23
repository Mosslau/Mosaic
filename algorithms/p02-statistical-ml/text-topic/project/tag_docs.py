"""迁移项目：给文档打主题标签"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import make_docs  # noqa: E402
from impl import NMF, Tfidf  # noqa: E402


def main() -> None:
    docs, labels, names = make_docs()
    tf = Tfidf().fit(docs)
    X = tf.transform(docs)
    m = NMF(3, 300, 0).fit(X)
    pred = m.transform(X).argmax(1)
    for i in range(3):
        print(f"doc {i}: topic {pred[i]} -> {m.top_words(tf.vocab, 3)[pred[i]]}")
    assert len(set(pred.tolist())) == 3


if __name__ == "__main__":
    main()
