"""迁移项目：图文检索"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import CLIP, make_pairs  # noqa: E402


def main() -> None:
    Xi, Xt, y = make_pairs(20, 12, 200, 0)
    m = CLIP(d=16, lr=.2, epochs=300).fit(Xi, Xt)
    print(f"identity {m.retrieval_accuracy(Xi, Xt):.3f}；"
          f"class {m.retrieval_accuracy(Xi, Xt, y):.3f}")
    print(f"图像 0 的 top-3 文本：{m.similarity(Xi[:1], Xt)[0].argsort()[::-1][:3].tolist()}")
    assert m.retrieval_accuracy(Xi, Xt, y) > .9


if __name__ == "__main__":
    main()
