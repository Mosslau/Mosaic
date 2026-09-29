"""变分自编码器 VAE — 手写实现（深度模型 · 生成式）

与同族的 AutoEncoder 关键差别：**中间是分布而不是点**。所以除了重构，
还多一项 KL 散度损失——这正是接口里出现 sample() 的原因（能采样才叫生成模型）。

    vae = VAE(latent_dim=16, lr=1e-3, epochs=50)
    vae.fit(X_train)                       # 无监督：目标是 X 自己 + KL 正则
    mu, logvar = vae.encode(X_test)        # 返回分布参数，不是点
    X_hat = vae.reconstruct(X_test)
    samples = vae.sample(n=16)             # 从先验 N(0, I) 采样再解码

三个必须手推的点（README「数学推导」段）：
    1. 证据下界 ELBO 的推导：重构项 + KL 项从何而来
    2. **重参数化技巧** z = mu + sigma * eps —— 没有它采样不可导，整个模型训不了
    3. KL 项对 mu / logvar 的闭式解（不必采样估计，README 要给出公式）
"""

import numpy as np


class VAE:
    """编码器输出 (mu, logvar)；重参数化采样 z；解码器重建。"""

    def __init__(self, latent_dim: int = 16, lr: float = 1e-3, epochs: int = 50,
                 beta: float = 1.0, random_state: int | None = None) -> None:
        self.latent_dim = latent_dim
        self.lr = lr
        self.epochs = epochs
        self.beta = beta              # beta-VAE 的权重，demo 可扫它看解耦效果
        self.random_state = random_state
        self.params: dict = {}
        self.loss_history: list[float] = []
        self.recon_history: list[float] = []
        self.kl_history: list[float] = []

    def encode(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """返回 (mu, logvar)——**用 logvar 而不是 sigma**，为了让 KL 项数值稳定（README 说明）。"""
        # TODO: 手写——共享隐层后接两个输出头
        raise NotImplementedError("TODO: 手写编码器（双头输出）")

    def reparameterize(self, mu: np.ndarray, logvar: np.ndarray,
                       rng: np.random.Generator) -> np.ndarray:
        """z = mu + exp(0.5 * logvar) * eps，eps ~ N(0, I)。"""
        # TODO: 手写——这一行是整个 VAE 可训练的关键，注释里要写清"为什么不能直接采样"
        raise NotImplementedError("TODO: 手写重参数化采样")

    def decode(self, Z: np.ndarray) -> np.ndarray:
        # TODO: 手写解码器前向
        raise NotImplementedError("TODO: 手写解码器前向")

    def reconstruct(self, X: np.ndarray) -> np.ndarray:
        """用分布均值重构（推理期不采样，保证输出可复现）。"""
        # TODO: 手写——encode 取 mu → decode
        raise NotImplementedError("TODO: 手写重构")

    def fit(self, X: np.ndarray) -> "VAE":
        """最小化 -ELBO = 重构误差 + beta * KL(q(z|x) || N(0,I))，两项分别记录。"""
        # TODO: 手写
        #   重构项：MSE 或 Bernoulli 交叉熵（二值图像用它，README 说明选哪个及理由）
        #   KL 项闭式：-0.5 * Σ(1 + logvar - mu^2 - exp(logvar))
        #   反向时 **KL 的梯度也要经 mu / logvar 回传到编码器**，别只反传重构项
        raise NotImplementedError("TODO: 手写 ELBO 训练循环")

    def sample(self, n: int = 16) -> np.ndarray:
        # TODO: 手写——从先验 N(0, I) 采样 Z，再 decode
        raise NotImplementedError("TODO: 手写先验采样")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/sample，再到 demo.py 跑实验")
