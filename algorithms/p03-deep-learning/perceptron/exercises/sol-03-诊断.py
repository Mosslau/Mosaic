"""参考解：第 3 题（判断）——三个感知机 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import Perceptron  # noqa: E402


def main() -> None:
    X_tr, _, y_tr, _ = D.make_separable()

    print("A 标签 0/1：")
    try:
        Perceptron().fit(X_tr, np.where(y_tr > 0, 1, 0))
    except ValueError as e:
        print(f"   报错：{e}")

    print("\nB 不打乱顺序（用不同随机种子代表不同顺序）：")
    m1 = Perceptron(lr=0.1, epochs=20, random_state=1).fit(X_tr, y_tr)
    m2 = Perceptron(lr=0.1, epochs=20, random_state=2).fit(X_tr, y_tr)
    print(f"   种子 1 的 w={np.round(m1.w, 3)}；种子 2 的 w={np.round(m2.w, 3)}")
    assert not np.allclose(m1.w, m2.w)

    print("\nC sign(0) 约定冲突：")
    m = Perceptron(standardize=False)
    m.w = np.array([1.0, 0.0])
    m.b = 0.0
    x = np.array([[0.0, 1.0]])       # 恰好落在边界 x0=0 上
    print(f"   边界点 score={m.decision_function(x)[0]:.1f}，"
          f"当前约定 predict={m.predict(x)[0]:+d}")
    print("   若把判决改成 sign(0)=−1，但更新仍用 ≤0，边界点会判错又被更新。")

    print("\n→ A 标签错；B 顺序敏感；C 边界约定冲突。")


if __name__ == "__main__":
    main()
