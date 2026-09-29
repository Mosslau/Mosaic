"""迷你 Transformer Block — 手写实现（深度模型 · 生成式）

注意力（见 ../attention/）的上一层组装：把「多头注意力 + 前馈网络 + 残差 + LayerNorm」
按 pre-LN 结构拼成一个可堆叠的 Block。接口是 Block 形态（forward/backward），
并额外提供 `train(tokens)` 让 Block 能在语言建模任务上真的训起来。

    block = TransformerBlock(d_model=64, n_heads=4, d_ff=256)
    out = block.forward(X, mask)              # 自回归：causal mask 必须开
    losses = block.train(tokens, epochs=20)   # 语言建模目标（next-token）

必须自己实现的四件套（README「数学推导」段要分别写出推导）：
    1. LayerNorm 的前向与反向（均值方差归一化 + 仿射）
    2. 残差连接的梯度"高速公路"（为什么它让深层可训）
    3. pre-LN vs post-LN 的差别（本实验选 pre-LN，理由写进 README）
    4. 前馈网络是逐位置独立的两层 MLP
"""

import numpy as np


class LayerNorm:
    """LayerNorm：对最后一维归一化再仿射；反向要同时回传 d_gamma/d_beta/d_x。"""

    def __init__(self, d_model: int, eps: float = 1e-5) -> None:
        self.d_model = d_model
        self.eps = eps
        self.gamma = np.ones(d_model)
        self.beta = np.zeros(d_model)

    def forward(self, X: np.ndarray) -> np.ndarray:
        # TODO: 手写——mean/var 沿最后一维；缓存归一化后的值与标准差供反向
        raise NotImplementedError("TODO: 手写 LayerNorm 前向")

    def backward(self, d_out: np.ndarray) -> np.ndarray:
        # TODO: 手写——LayerNorm 反向有三项（含方差项的间接梯度），别漏
        raise NotImplementedError("TODO: 手写 LayerNorm 反向")


class TransformerBlock:
    """pre-LN Block：x = x + Attn(LN(x))；x = x + FFN(LN(x))。"""

    def __init__(self, d_model: int = 64, n_heads: int = 4, d_ff: int = 256,
                 causal: bool = True, random_state: int | None = None) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.causal = causal
        self.random_state = random_state
        self.ln1 = LayerNorm(d_model)
        self.ln2 = LayerNorm(d_model)
        self.params: dict = {}

    def forward(self, X: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        # TODO: pre-LN 结构：先 LN 再进子层，残差加在最外层（顺序写反是常见错误）
        raise NotImplementedError("TODO: 手写 Block 前向")

    def backward(self, d_out: np.ndarray) -> dict:
        # TODO: 手写——残差会把梯度**分两路**回传（直连 + 经子层），两条都要加
        raise NotImplementedError("TODO: 手写 Block 反向")

    def train(self, tokens: np.ndarray, epochs: int = 20, lr: float = 1e-3) -> list[float]:
        """在 next-token 语言建模目标上训练本 Block，返回每轮 loss。"""
        # TODO: 手写——构造（输入 = 前 n-1，目标 = 后 n-1）的错位样本，交叉熵 + 反向更新
        raise NotImplementedError("TODO: 手写语言建模训练循环")


if __name__ == "__main__":
    raise SystemExit("请先完成 forward/backward，再到 demo.py 跑实验")
