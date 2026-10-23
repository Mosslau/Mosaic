"""迁移项目：给用户做 top-k 推荐"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import MatrixFactorization, make_data, recall_ndcg, train_test_mask  # noqa: E402


def main() -> None:
    R = make_data(120, 60, seed=0)
    tr, te = train_test_mask(R, .2, 0)
    m = MatrixFactorization(16, .01, .05, 50, 0).fit(R * tr)
    rec, ndcg = recall_ndcg(m, R, tr, te, 10)
    print(f"Recall@10 {rec:.3f}；NDCG@10 {ndcg:.3f}")
    print(f"用户 0 推荐：{m.recommend(0, 10).tolist()}")
    assert rec > 0.4


if __name__ == "__main__":
    main()
