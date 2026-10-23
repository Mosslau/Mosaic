"""ViT 对照：展平像素 + 逻辑回归（无注意力）。"""

from sklearn.linear_model import LogisticRegression


def fit_baseline(X, y, Xte, yte):
    clf = LogisticRegression(max_iter=2000, random_state=0)
    clf.fit(X.reshape(len(X), -1), y)
    return float((clf.predict(Xte.reshape(len(Xte), -1)) == yte).mean())


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，由 demo.py 调用")
