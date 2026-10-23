"""文本主题模型 — sklearn NMF 对照。"""

from sklearn.decomposition import NMF as SkNMF


def fit_nmf(X, n_topics=3):
    return SkNMF(n_components=n_topics, init="random", random_state=0,
                 max_iter=500).fit(X)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
