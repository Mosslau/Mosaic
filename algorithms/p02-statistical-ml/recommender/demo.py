"""推荐系统 — demo：ItemCF / 矩阵分解 / 流行度基线"""

from __future__ import annotations

import time

from impl import ItemCF, MatrixFactorization, Popularity, make_data, recall_ndcg, train_test_mask


def main() -> None:
    R = make_data(120, 60, seed=0)
    train, test = train_test_mask(R, 0.2, seed=0)
    Rtr = R * train
    print(f"用户 {R.shape[0]}，物品 {R.shape[1]}，评分 {int((R>0).sum())}，"
          f"测试 {int(test.sum())}")

    models = [
        ("ItemCF", ItemCF(20), lambda m: m.fit(Rtr)),
        ("MF(16)", MatrixFactorization(16, 0.01, 0.05, 50, 0), lambda m: m.fit(Rtr)),
        ("Popularity", Popularity(), lambda m: m.fit(Rtr)),
    ]
    print(f"\n{'模型':12} | {'Recall@10':>9} | {'NDCG@10':>8} | {'RMSE':>6} | {'耗时(ms)':>8}")
    print("-" * 58)
    for name, m, fit in models:
        t0 = time.perf_counter()
        fit(m)
        dt = (time.perf_counter() - t0) * 1000
        rec, ndcg = recall_ndcg(m, R, train, test, 10)
        rmse = m.rmse(test, R) if hasattr(m, "rmse") else float("nan")
        print(f"{name:12} | {rec:9.3f} | {ndcg:8.3f} | {rmse:6.3f} | {dt:8.1f}")

    mf = models[1][1]
    print(f"\nMF loss：{mf.loss_history[0]:.3f} → {mf.loss_history[-1]:.3f}")
    print(f"用户 0 推荐：{mf.recommend(0, 5).tolist()}")


if __name__ == "__main__":
    main()
