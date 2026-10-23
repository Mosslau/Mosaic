"""多模态对照：随机线性双塔（无对比训练）。"""

import numpy as np


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
