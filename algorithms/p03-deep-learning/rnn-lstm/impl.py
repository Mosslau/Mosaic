"""RNN 与 LSTM — 手写实现（深度模型 · 判别式）

比其他深度实验多一个维度：**时间**。反向传播要沿时间轴展开（BPTT），
梯度要跨时间步累加——所以接口里会显式出现"时间步"。

    rnn = RNN(vocab_size=..., hidden_size=64, lr=0.01, epochs=20)
    rnn.fit(X_train, y_train)              # X: (N, T) 的序列
    logits = rnn.predict(X_test)           # (N, n_classes)
    text = rnn.generate(prompt_ids, n_steps=20)   # 序列生成

**本实验的核心结论**：朴素 RNN 的梯度会随 T 指数衰减/爆炸（README 要给出推导），
LSTM 用门控 + 细胞状态缓解。demo 要能观察到"T 变长时 RNN 学不动、LSTM 还能学"。
"""

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    # TODO: 手写数值稳定 sigmoid
    raise NotImplementedError("TODO: 手写 sigmoid")


class RNN:
    """朴素 RNN：h_t = tanh(W_xh x_t + W_hh h_{t-1} + b_h)，逐时间步手写 BPTT。"""

    def __init__(self, hidden_size: int = 64, lr: float = 0.01, epochs: int = 20) -> None:
        self.hidden_size = hidden_size
        self.lr = lr
        self.epochs = epochs
        self.params: dict = {}
        self.loss_history: list[float] = []

    def forward(self, X: np.ndarray, cache: dict | None = None) -> np.ndarray:
        """沿时间步循环；cache 需保存每个 t 的 h_t 与输入（BPTT 要用全部时间步）。"""
        # TODO: 手写
        raise NotImplementedError("TODO: 手写 RNN 前向（沿时间步）")

    def backward(self, grad_out: np.ndarray, cache: dict) -> dict:
        """BPTT：从 T 倒着回传，**每步的梯度要累加**（dh 有两路来源：输出与本步之后）。"""
        # TODO: 手写
        #   常见错误：忘记把"来自未来时间步的 dh"加到当前步——README 标为易错点
        raise NotImplementedError("TODO: 手写 BPTT")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RNN":
        # TODO: 手写训练循环；收敛判据与梯度裁剪（防爆炸）都要在 README 说明
        raise NotImplementedError("TODO: 手写训练循环")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 取最后一个时间步的隐状态接输出层
        raise NotImplementedError("TODO: 手写序列分类预测")

    def generate(self, prompt_ids: np.ndarray, n_steps: int = 20) -> np.ndarray:
        """自回归生成：把上一步的输出喂回输入（README「局限与延伸」对比后面 GPT 的做法）。"""
        # TODO: 手写
        raise NotImplementedError("TODO: 手写自回归生成")


class LSTM(RNN):
    """LSTM：在 RNN 上引入输入/遗忘/输出三门与细胞状态 c_t。"""

    def forward(self, X: np.ndarray, cache: dict | None = None) -> np.ndarray:
        # TODO: 手写四组权重（i/f/o/g）、c_t = f⊙c_{t-1} + i⊙g、h_t = o⊙tanh(c_t)
        #   门控的关键在于 c_t 的那条"高速公路"——README 要说明它为何缓解梯度消失
        raise NotImplementedError("TODO: 手写 LSTM 前向")

    def backward(self, grad_out: np.ndarray, cache: dict) -> dict:
        # TODO: 手写——细胞状态的梯度沿时间几乎是恒等传递，这是与 RNN 最本质的差异
        raise NotImplementedError("TODO: 手写 LSTM 反向")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
