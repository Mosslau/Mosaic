"""K-Means 聚类 — 框架对照调用

用手写实现同样的数据和指标，调 sklearn 跑一遍。目的：
1. 验证手写实现的正确性（inertia 应对齐）
2. 感受框架封装的便利与隐藏的细节
3. 记录框架内部额外做的优化（写回 README「框架对照」一节）

注意：**无监督，签名没有 y**。
"""


def run_framework(X_train, n_clusters: int = 3, random_state: int | None = None):
    """用框架接口完成聚类，返回与手写版对齐的指标字典。

    返回示例：{"inertia": ..., "n_iter": ..., "time_sec": ...}
    """
    # TODO: 例：from sklearn.cluster import KMeans -> KMeans(n_clusters, n_init=...).fit(X)
    #   README「框架对照」要回答：sklearn 的 n_init / init 策略默认值与手写版差在哪、
    #   它为什么比手写的快（Elkan 三角不等式加速 / 并行）
    raise NotImplementedError("TODO: 调框架接口，返回 {'inertia': ..., 'time_sec': ...}")


if __name__ == "__main__":
    raise SystemExit("请先完成 run_framework，由 demo.py 统一调用对比")
