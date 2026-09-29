"""生成对抗网络 GAN — 手写实现（深度模型 · 生成式）

**形态与前面所有实验都不同**：没有单一的损失函数，而是**两个网络交替对抗训练**。
所以接口是 train(data) 而不是 fit(X, y)——GAN 的 fit(X, y) 本身就不成立（没有 y）。

    gan = GAN(latent_dim=64, lr_g=2e-4, lr_d=2e-4)
    gan.train(X_train, epochs=100)        # 交替训练，无标签
    samples = gan.sample(n=16)            # 从噪声生成
    scores = gan.discriminator(X_test)    # 判别器打分

手写纪律（按族细化）：允许 `torch.Tensor` / `torch.autograd`，
**禁止 PyTorch 的现成层与现成优化器**（本实现用 numpy，不依赖 torch）。

**必须处理的核心问题**（README「数学推导」段要写清）：
    1. 两个网络的梯度方向相反，训练不平衡会模式崩塌 / 判别器压倒
    2. 实践上用非饱和损失（-log D(G(z))）而非原始 min-max，否则早期梯度消失
"""

import numpy as np


def leaky_relu(z: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    # TODO: 手写
    raise NotImplementedError("TODO: 手写 LeakyReLU")


class GAN:
    """生成器 G 与判别器 D 交替训练；两者都在本类内部手写前向/反向。"""

    def __init__(self, latent_dim: int = 64, hidden: tuple[int, ...] = (128, 256),
                 lr_g: float = 2e-4, lr_d: float = 2e-4, random_state: int | None = None) -> None:
        self.latent_dim = latent_dim
        self.hidden = hidden
        self.lr_g = lr_g
        self.lr_d = lr_d
        self.random_state = random_state
        self.g_params: dict = {}
        self.d_params: dict = {}
        self.d_loss_history: list[float] = []
        self.g_loss_history: list[float] = []

    def generator(self, Z: np.ndarray) -> np.ndarray:
        # TODO: 手写 G 前向：噪声 → 隐层 → 生成样本
        raise NotImplementedError("TODO: 手写生成器前向")

    def discriminator(self, X: np.ndarray) -> np.ndarray:
        """返回 [0,1] 的真假概率——demo 用它看判别器是否压倒了生成器。"""
        # TODO: 手写 D 前向：样本 → 隐层 → sigmoid
        raise NotImplementedError("TODO: 手写判别器前向")

    def train(self, X: np.ndarray, epochs: int = 100, batch_size: int = 64) -> None:
        """交替训练：先更新 D（真样本 + 假样本各一批），再更新 G（经 D 反传，D 参数冻结）。"""
        # TODO: 手写
        #   更新 G 时**必须冻结 D 的参数**（只回传到 G，不更新 D）——这是最容易写错的地方
        #   分别记录 d_loss / g_loss 到 history，demo 用双曲线观察对抗平衡
        raise NotImplementedError("TODO: 手写交替对抗训练")

    def sample(self, n: int = 16) -> np.ndarray:
        # TODO: 手写——从标准正态采样噪声，过生成器
        raise NotImplementedError("TODO: 手写采样")


if __name__ == "__main__":
    raise SystemExit("请先完成 train/sample，再到 demo.py 跑实验")
