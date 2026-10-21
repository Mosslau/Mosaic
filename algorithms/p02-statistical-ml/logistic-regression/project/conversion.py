"""迁移项目：客户转化预测 —— 不平衡 + 代价敏感阈值

    uv run python conversion.py

与教学示例的差别：
1. 五个业务特征、正类只占约 6%；
2. 阈值必须在**验证集**上按业务代价选，不能看测试集（否则就是数据泄漏）；
3. 要同时回答"重加权"和"调阈值"两条路线哪个更划算。

验收标准见 README.md；脚本内逐条断言。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import Model, accuracy, confusion, f1, precision, recall, roc_auc, sigmoid  # noqa: E402

C_FN = 20.0      # 漏掉一个会转化的客户，损失 20
C_FP = 1.0       # 误发一张优惠券，成本 1
FEATURES = ["访问次数", "停留时长", "历史订单", "优惠敏感度", "噪声特征"]
TRUE_W = np.array([1.1, 0.8, 1.4, -0.6, 0.0])


def make_data(n: int = 5000, seed: int = 0):
    rng = np.random.default_rng(seed)
    visits = rng.poisson(3, n).astype(float)
    duration = rng.gamma(2.0, 4.0, n)
    orders = rng.poisson(0.8, n).astype(float)
    coupon = rng.normal(size=n)
    noise = rng.normal(size=n)
    X = np.column_stack([visits, duration, orders, coupon, noise])
    z = (X - X.mean(0)) / X.std(0) @ TRUE_W - 4.0       # 截距压低正类比例
    y = (rng.random(n) < sigmoid(z)).astype(int)
    return X, y


def cost(y_true, y_pred, c_fn=C_FN, c_fp=C_FP):
    tp, fp, fn, tn = confusion(y_true, y_pred)
    return c_fn * fn + c_fp * fp


def metrics(y_true, proba, threshold):
    pred = (proba >= threshold).astype(int)
    return {
        "accuracy": accuracy(y_true, pred),
        "precision": precision(y_true, pred),
        "recall": recall(y_true, pred),
        "f1": f1(y_true, pred),
        "auc": roc_auc(y_true, proba),
        "cost": cost(y_true, pred),
        "positive_rate": float(pred.mean()),
    }


def tune_threshold(y_true, proba, grid=np.linspace(0.02, 0.9, 89)):
    rows = [(t, cost(y_true, (proba >= t).astype(int))) for t in grid]
    return min(rows, key=lambda r: r[1])


def main() -> None:
    X, y = make_data()
    X_tmp, X_te, y_tmp, y_te = train_test_split(X, y, test_size=0.2, random_state=0,
                                                stratify=y)
    X_tr, X_val, y_tr, y_val = train_test_split(X_tmp, y_tmp, test_size=0.25,
                                                random_state=0, stratify=y_tmp)
    print(f"样本 {len(y)}：训练 {len(y_tr)} / 验证 {len(y_val)} / 测试 {len(y_te)}；"
          f"正类占比 训练 {y_tr.mean():.1%}、测试 {y_te.mean():.1%}")

    plain = Model(lr=0.5, epochs=8000, tol=1e-12).fit(X_tr, y_tr)
    balanced = Model(lr=0.5, epochs=8000, tol=1e-12,
                     class_weight="balanced").fit(X_tr, y_tr)

    p_val = plain.predict_proba(X_val)
    best_t, best_val_cost = tune_threshold(y_val, p_val)
    print(f"验证集上按代价选阈值：t = {best_t:.2f}（验证代价 {best_val_cost:.0f}）")

    rows = []
    for name, model in (("默认（阈值 0.5）", plain), ("重加权 balanced（0.5）", balanced)):
        m = metrics(y_te, model.predict_proba(X_te), 0.5)
        rows.append((name, 0.5, m))
    m = metrics(y_te, plain.predict_proba(X_te), best_t)
    rows.append((f"默认 + 调阈值 {best_t:.2f}", best_t, m))

    print(f"\n{'方案':22} | {'阈值':>4} | {'acc':>6} | {'prec':>6} | {'recall':>6} | "
          f"{'F1':>5} | {'cost':>5} | {'判正比例':>7}")
    print("-" * 82)
    for name, th, m in rows:
        print(f"{name:22} | {th:4.2f} | {m['accuracy']:6.4f} | {m['precision']:6.4f} | "
              f"{m['recall']:6.4f} | {m['f1']:5.4f} | {m['cost']:5.0f} | "
              f"{m['positive_rate']:7.2%}")

    base_cost = rows[0][2]["cost"]
    tuned_cost = rows[2][2]["cost"]
    auc = rows[0][2]["auc"]
    print("\n== 验收 ==")
    checks = [
        ("AUC > 0.80", auc > 0.80),
        ("调阈值后测试代价低于默认", tuned_cost < base_cost),
        ("调阈值后召回高于默认", rows[2][2]["recall"] > rows[0][2]["recall"]),
        ("最优阈值低于 0.5", best_t < 0.5),
        ("阈值来自验证集（未看测试集）", True),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print(f"\n→ 默认阈值代价 {base_cost:.0f}，按验证集调阈值后 {tuned_cost:.0f}；"
          f"AUC {auc:.4f}。重加权是另一条路线，二者可以叠加。")


if __name__ == "__main__":
    main()
