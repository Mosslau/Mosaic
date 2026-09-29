"""PCA 主成分分析 — 框架对照调用

用手写实现同样的数据和指标，调 sklearn 跑一遍。目的：
1. 验证手写实现的正确性（explained_variance_ratio_ 应对齐）
2. 感受框架封装的便利与隐藏的细节
3. 记录框架内部额外做的优化（写回 README「框架对照」一节）

注意：**无监督，签名没有 y**。
"""


def run_framework(X_train, n_components: int = 2):
    """用框架接口完成降维，返回与手写版对齐的指标字典。

    返回示例：{"explained_variance_ratio": [...], "time_sec": ...}
    """
    # TODO: 例：from sklearn.decomposition import PCA -> PCA(n_components).fit_transform(X)
    #   README「框架对照」要回答：sklearn 默认用 SVD 而不是协方差特征分解——
    #   两者在数值稳定性与复杂度上差在哪（这是本章最有价值的对照结论）
    raise NotImplementedError("TODO: 调框架接口，返回 {'explained_variance_ratio': ..., 'time_sec': ...}")


if __name__ == "__main__":
    raise SystemExit("请先完成 run_framework，由 demo.py 统一调用对比")
