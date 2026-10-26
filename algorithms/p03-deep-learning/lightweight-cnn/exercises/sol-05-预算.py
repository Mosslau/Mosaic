"""参考解 5：3200 参数预算内选宽度（验证集选型，测试集只报告）。"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo  # noqa: E402
from impl import MobileNetLite, StandardCNN  # noqa: E402

BUDGET = 3200
EPOCHS = 8
CANDIDATES = [(8, 16, 32, 32), (12, 16, 32, 32), (8, 20, 32, 32), (8, 16, 36, 36)]

X_tr, X_te, y_tr, y_te = demo.load_data()
from sklearn.model_selection import train_test_split  # noqa: E402

X_fit, X_val, y_fit, y_val = train_test_split(
    X_tr, y_tr, train_size=1100, random_state=0, stratify=y_tr)
print(f"训练验证切分：{len(X_fit)} / {len(X_val)}，预算 {BUDGET}")

rows = []
for widths in CANDIDATES:
    params = MobileNetLite(widths=widths).init().n_params()
    if params > BUDGET:
        print(f"DS {widths}: {params} > 预算，跳过")
        continue
    model = MobileNetLite(widths=widths, lr=0.01, epochs=EPOCHS,
                          batch_size=64, random_state=0).fit(X_fit, y_fit)
    val = float(np.mean(model.predict(X_val) == y_val))
    rows.append((widths, params, val, model))
    print(f"DS {widths}: params={params} val_acc={val:.4f}")

rows.sort(key=lambda r: r[2], reverse=True)
best_w, best_p, best_val, best = rows[0]
test = float(np.mean(best.predict(X_te) == y_te))
print(f"\n验证集选中 {best_w}（{best_p} 参数，val {best_val:.4f}），测试 acc {test:.4f}")

std_params = StandardCNN(widths=(6, 8, 10, 16)).init().n_params()
assert std_params <= BUDGET
std = StandardCNN(widths=(6, 8, 10, 16), lr=0.01, epochs=EPOCHS,
                  batch_size=64, random_state=0).fit(X_fit, y_fit)
std_test = float(np.mean(std.predict(X_te) == y_te))
print(f"同预算标准 CNN {std_params} 参数，测试 acc {std_test:.4f}")

assert all(p <= BUDGET for _, p, _, _ in rows)
assert test >= 0.90
assert test >= std_test - 0.02
print("\n→ 同预算下两者接近：DS 能把宽度做大，标准 CNN 要压到 (6,8,10,16)。"
      "\n  本次标准 CNN 略高，说明 3200 参数内结构差异不是决定性的。")
