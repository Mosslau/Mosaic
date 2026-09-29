"""迷你 GPT 字符级语言模型 — 手写实现（深度模型 · 生成式）

**本目录没有 fit(X, y)**：语言模型的目标是"根据前文预测下一个字符"，
输入和目标来自**同一段文本的错位切分**，不存在独立的 y。所以接口是
train(text)/generate(prompt) 而不是估计器形态——这正是本目录与 p03 判别式
实验（mlp / cnn / rnn）在接口上的根本差别。

    gpt = MiniGPT(vocab_size=..., n_layers=2, d_model=64, n_heads=4, context=32)
    gpt.train(text, epochs=100)              # data = 原始文本，内部自己错位切分
    out = gpt.generate("he", n_steps=50)     # 自回归生成

要手写并串起来的完整链路（前面各实验的成果在这里合流）：
    1. 字符级 tokenizer（字符 ↔ id 双向映射，含未知字符处理）
    2. token embedding + **位置编码**（本实验用可学习的位置嵌入，README 说明与正弦版的差别）
    3. n_layers 个 Transformer Block（复用 ../mini-transformer/ 与 ../attention/ 的实现）
    4. 输出投影回词表 + 交叉熵损失 + 全链路反向传播
    5. 采样策略：贪心 / 温度 / top-k（temperature 与 top_k 的取舍写进 README）
"""

import numpy as np


class CharTokenizer:
    """字符级分词：按出现频次建表，提供 encode / decode。"""

    def __init__(self) -> None:
        self.stoi: dict[str, int] = {}
        self.itos: dict[int, str] = {}

    def fit(self, text: str) -> "CharTokenizer":
        # TODO: 手写——统计字符集，按频次排序建 id（排序保证跨运行可复现）
        raise NotImplementedError("TODO: 手写字符表构建")

    def encode(self, text: str) -> np.ndarray:
        # TODO: 手写——未知字符映射到预留的 <unk> id
        raise NotImplementedError("TODO: 手写 encode")

    def decode(self, ids: np.ndarray) -> str:
        # TODO: 手写
        raise NotImplementedError("TODO: 手写 decode")


class MiniGPT:
    """字符级 GPT：embedding + 位置嵌入 + N 个 Block + 语言模型头。"""

    def __init__(self, vocab_size: int, context: int = 32, d_model: int = 64,
                 n_heads: int = 4, n_layers: int = 2, random_state: int | None = None) -> None:
        self.vocab_size = vocab_size
        self.context = context
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.random_state = random_state
        self.token_emb: np.ndarray | None = None
        self.pos_emb: np.ndarray | None = None
        self.blocks: list = []
        self.lm_head: dict = {}
        self.loss_history: list[float] = []

    def forward(self, idx: np.ndarray) -> tuple[np.ndarray, dict]:
        """idx: (B, T) 的 token id → 返回 (B, T, vocab) 的 logits 与反向所需缓存。"""
        # TODO: 手写——token_emb[idx] + pos_emb[:T]，逐个 Block 前向（causal mask 必开），
        #   最后经 lm_head 投到词表维度；缓存每层中间量供反向
        raise NotImplementedError("TODO: 手写 GPT 前向")

    def backward(self, d_logits: np.ndarray, cache: dict) -> dict:
        # TODO: 手写——lm_head 反向 → 逐 Block 反向（**逆序！**）→ embedding 反向
        #   逆序遍历 Block 是最容易写错的地方；embedding 梯度要按 id 用 np.add.at 累加
        raise NotImplementedError("TODO: 手写 GPT 反向")

    def train(self, text: str, epochs: int = 100, lr: float = 3e-3,
              batch_size: int = 16) -> list[float]:
        """text 是原始文本；内部按 context 窗口错位切分成 (输入, 目标) 对。"""
        # TODO: 手写
        #   1. tokenize → 按 context 切窗口；输入 = 窗口[:-1]，目标 = 窗口[1:]
        #   2. 交叉熵损失 + 反向 + 参数更新
        #   3. 记录 loss_history（demo 画 loss 曲线，观察是否真的在学）
        raise NotImplementedError("TODO: 手写训练循环（错位切分 + 交叉熵）")

    def generate(self, prompt: str, n_steps: int = 50, temperature: float = 1.0,
                 top_k: int | None = None) -> str:
        """自回归生成：每步取最后一个位置的 logits，采样后拼回输入。"""
        # TODO: 手写
        #   可做增量解码（每步只前向最后一个 token），并把这与全序列重算的耗时写进「实验结果」
        #   temperature 与 top_k 对输出的影响也要写进「实验结果」
        raise NotImplementedError("TODO: 手写自回归采样生成")


if __name__ == "__main__":
    raise SystemExit("请先完成 train/generate，再到 demo.py 跑实验")
