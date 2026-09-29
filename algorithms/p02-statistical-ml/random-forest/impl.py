"""随机森林 — 手写实现（监督估计器）

随机森林 = 决策树的 bagging 集成。**本实验的前置依赖是同族的 decision-tree**：
impl 里应复用你已写好的 `DecisionTree`，而不是重写一遍划分逻辑——
要手写的是"随机性来自哪里"（样本自助采样 + 特征随机子集）与"如何汇总"。

    forest = RandomForest(n_trees=100, max_features="sqrt", random_state=42)
    forest.fit(X_train, y_train)
    label = forest.predict(X_test)

随机性的两个来源（README「数学推导」段要写出它为什么能降方差）：
    1. bootstrap：每棵树在同规模的自助采样集上训练（约 36.8% 样本未入袋）
    2. feature subsampling：每次划分只从随机特征子集里选最优
"""

import numpy as np

from decision_tree import DecisionTree


class RandomForest:
    """由 n_trees 棵决策树组成的 Bagging 集成，投票（分类）或平均（回归）。"""

    def __init__(
        self,
        n_trees: int = 100,
        max_features: str | int | None = "sqrt",
        max_depth: int | None = None,
        random_state: int | None = None,
    ) -> None:
        self.n_trees = n_trees
        self.max_features = max_features
        self.max_depth = max_depth
        self.random_state = random_state
        self.trees: list[DecisionTree] = []
        self.oob_indices: list[np.ndarray] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomForest":
        # TODO: 手写
        #   1. 用固定种子的 rng（np.random.default_rng）保证可复现
        #   2. 每棵树：bootstrap 采样（有放回）→ 记录未入袋样本索引（用于 OOB 估计）
        #      → 训练 DecisionTree（把特征子集策略传给单棵树）
        #   3. max_features="sqrt" 时取 sqrt(n_features)，留实现痕迹在注释里
        raise NotImplementedError("TODO: 手写 Bagging 训练循环")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 所有树预测后按多数投票；分类用众数，回归用均值
        raise NotImplementedError("TODO: 手写集成投票")

    def oob_score(self, X: np.ndarray, y: np.ndarray) -> float:
        """用未入袋样本估泛化精度——不用额外验证集就能看集成效果（README 要点明这个技巧）。"""
        # TODO: 手写——每条样本只交给"没见过它"的树投票
        raise NotImplementedError("TODO: 手写 OOB 估计")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
