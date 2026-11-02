"""文本主题模型 — sklearn NMF / LDA 对照。"""

from sklearn.decomposition import NMF as SkNMF
from sklearn.decomposition import LatentDirichletAllocation


def fit_nmf(X, n_topics=3):
    return SkNMF(n_components=n_topics, init="random", random_state=0,
                 max_iter=500).fit(X)


def fit_lda(X, n_topics=3):
    """不同模型族的公平基线：概率生成式 LDA，同 TF-IDF 矩阵、同主题数。"""
    return LatentDirichletAllocation(
        n_components=n_topics, random_state=0, max_iter=200,
        learning_method="batch").fit(X)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
