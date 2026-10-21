"""随机森林 — 框架对照（监督估计器）

对照对象：sklearn `RandomForestClassifier`。
口径：同一份数据、同一 `n_estimators` / `max_features` / `max_depth`，比较
测试准确率、OOB 精度、特征重要性与耗时。sklearn 用 C 实现 + 多核并行，
并把 OOB 预测缓存为 `oob_decision_function_`。
"""

from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier


def fit_forest(X, y, n_trees: int = 100, max_features="sqrt",
               max_depth: int | None = None) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_trees, max_features=max_features, max_depth=max_depth,
        oob_score=True, random_state=0, n_jobs=1).fit(X, y)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
