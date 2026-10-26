"""迁移项目：3200 参数预算内的轻量分类器选型。

流程：
1. 从 digits 训练集切 1100 / 300 训练-验证，测试集 397 只在最后用；
2. 枚举 DS 宽度，数参数、淘汰超预算项，训练 10 轮，用验证 acc 选型；
3. 同预算标准 CNN 对照，报告参数量、测试 acc、macro F1。

运行：uv run python budget.py（约 40 秒，CPU）
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import demo  # noqa: E402
from impl import MobileNetLite, StandardCNN  # noqa: E402

BUDGET = 3200
EPOCHS = 10
DS_CANDIDATES = [(8, 16, 32, 32), (12, 16, 32, 32), (8, 20, 32, 32), (8, 16, 36, 36)]
STD_WIDTHS = (6, 8, 10, 16)
SEED = 0


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X_tr, X_te, y_tr, y_te = demo.load_data()
    X_fit, X_val, y_fit, y_val = train_test_split(
        X_tr, y_tr, train_size=1100, random_state=SEED, stratify=y_tr)
    print(f"参数预算 {BUDGET}；训练 {len(X_fit)} / 验证 {len(X_val)} / 测试 {len(X_te)}")

    rows = []
    for widths in DS_CANDIDATES:
        params = MobileNetLite(widths=widths).init().n_params()
        if params > BUDGET:
            print(f"DS {str(widths):>16}  {params:5d} 参数  ✗ 超预算")
            continue
        model = MobileNetLite(widths=widths, lr=0.01, epochs=EPOCHS,
                              batch_size=64, random_state=SEED).fit(X_fit, y_fit)
        val = acc(y_val, model.predict(X_val))
        rows.append((widths, params, val, model))
        print(f"DS {str(widths):>16}  {params:5d} 参数  val acc {val:.4f}  ✓")

    assert rows, "预算内没有可用候选"
    widths, params, val, best = max(rows, key=lambda r: r[2])
    pred = best.predict(X_te)
    test, f1 = acc(y_te, pred), f1_score(y_te, pred, average="macro")
    print(f"\n验证集选中 DS {widths}：{params} 参数，val {val:.4f}，"
          f"测试 acc {test:.4f}，macro F1 {f1:.4f}")

    std_params = StandardCNN(widths=STD_WIDTHS).init().n_params()
    std = StandardCNN(widths=STD_WIDTHS, lr=0.01, epochs=EPOCHS,
                      batch_size=64, random_state=SEED).fit(X_fit, y_fit)
    std_pred = std.predict(X_te)
    std_test, std_f1 = acc(y_te, std_pred), f1_score(y_te, std_pred, average="macro")
    print(f"同预算标准 CNN {STD_WIDTHS}：{std_params} 参数，"
          f"测试 acc {std_test:.4f}，macro F1 {std_f1:.4f}")

    # 验收：预算、精度、同预算对照、F1
    assert params <= BUDGET and std_params <= BUDGET
    assert test >= 0.95
    assert test >= std_test - 0.02
    assert f1 >= 0.95
    headroom = BUDGET - params
    print(f"\n验收通过：{params} ≤ {BUDGET}（余量 {headroom}），"
          f"acc {test:.4f} ≥ 0.95，与同预算标准 CNN 差 {test - std_test:+.4f}。")


if __name__ == "__main__":
    main()
