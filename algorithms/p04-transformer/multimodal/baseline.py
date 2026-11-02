"""多模态对照：随机线性双塔（下界）+ 岭回归跨模态对齐（训练过的基线）。"""

import numpy as np


def ridge_retrieval(Xi_tr, Xt_tr, Xi_te, Xt_te, y_te, alpha=1.0):
    """训练过的线性基线：用岭回归把图像映射到文本空间，再做检索。

    这是"有监督对齐"的强基线：同训练对、同一个检索口径；
    CLIP 的对比损失如果赢不了它，就说明收益不是来自跨模态对齐。
    """
    Xi_tr = np.asarray(Xi_tr, float)
    Xt_tr = np.asarray(Xt_tr, float)
    Xi_te = np.asarray(Xi_te, float)
    Xt_te = np.asarray(Xt_te, float)
    W = np.linalg.solve(Xi_tr.T @ Xi_tr + alpha * np.eye(Xi_tr.shape[1]),
                        Xi_tr.T @ Xt_tr)
    Ie = Xi_te @ W
    T = Xt_te
    Ie /= np.maximum(np.linalg.norm(Ie, axis=1, keepdims=True), 1e-12)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    pred = (Ie @ T.T).argmax(1)
    return float((np.asarray(y_te)[pred] == np.asarray(y_te)).mean())


def random_retrieval(Xi, Xt, y, d=16, seed=0):
    rng = np.random.default_rng(seed)
    Wi = rng.normal(0, .1, (Xi.shape[1], d))
    Wt = rng.normal(0, .1, (Xt.shape[1], d))
    Ie = Xi @ Wi
    T = Xt @ Wt
    Ie /= np.maximum(np.linalg.norm(Ie, axis=1, keepdims=True), 1e-12)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    pred = (Ie @ T.T).argmax(1)
    return float((np.asarray(y)[pred] == np.asarray(y)).mean())


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，由 demo.py 调用")
