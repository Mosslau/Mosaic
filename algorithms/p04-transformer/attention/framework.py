"""注意力机制 — 对照校验（模块族：对照的是数值梯度，不是框架实现）

**本目录没有"框架对照"**：注意力是一个组件，PyTorch 的现成注意力实现与手写版
不在同一抽象层级（它含融合 kernel、dropout、因果掩码等额外语义），直接比指标
得不出"框架多做了什么"的结论。所以本文件的对照物是**数值梯度**：

  用手写 forward 得到的标量损失，对每个输入做中心差分，得到数值梯度；
  与手写 backward 返回的解析梯度逐元素比对——相对误差应 < 1e-5。

这是反向传播最标准的自检手段，也是本实验"数学推导"段的实证：
**解析梯度推错了，数值梯度会当场揭穿**。同样不受手写纪律约束。
"""

import numpy as np


def numeric_grad(f, X: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """中心差分数值梯度：对 X 的每个元素分别做 +eps / -eps 两次前向。"""
    # TODO: 手写——注意别原地修改 X（要复制），否则会把有限差分算错
    raise NotImplementedError("TODO: 手写中心差分数值梯度")


def check_attention_grad(attn, Q: np.ndarray, K: np.ndarray, V: np.ndarray,
                         tol: float = 1e-5) -> dict:
    """比对解析梯度与数值梯度的相对误差，返回 {q: ratio, k: ratio, v: ratio}。

    返回示例：{"dQ": 3.2e-08, "dK": ..., "dV": ..., "passed": True}
    """
    # TODO: 手写
    #   1. 定义一个把 (Q, K, V) 映射到标量损失的函数（如输出平方和，简单可导）
    #   2. 用 numeric_grad 求数值梯度；用 attn.forward + attn.backward 求解析梯度
    #   3. 按相对误差 ||a - n|| / (||a|| + ||n|| + eps) 比较，超过 tol 记为不通过
    #   4. demo.py 会把三个比值打印出来，作为本实验「实验结果」段的实数证据
    raise NotImplementedError("TODO: 比对解析梯度与数值梯度")


if __name__ == "__main__":
    raise SystemExit("请先完成 check_attention_grad，由 demo.py 统一调用")
