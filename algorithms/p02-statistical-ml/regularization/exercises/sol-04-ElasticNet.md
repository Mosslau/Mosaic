# 参考解：第 4 题（实现）——ElasticNet

目标：

$$J(w)=\frac{1}{2n}\lVert Xw+b-y\rVert^2+\lambda_1\lVert w\rVert_1+\frac{\lambda_2}{2}\lVert w\rVert^2$$

坐标下降的更新式（固定其他系数）：

$$\rho_j=\frac{x_j^\top r}{n},\qquad
w_j=\frac{\text{soft}(\rho_j,\lambda_1)}{d_j+\lambda_2},\qquad
d_j=\frac{\lVert x_j\rVert^2}{n}$$

**两个极限**：

- `λ₂ = 0`：退化为 Lasso（更新式里的分母只剩 `d_j`）；
- `λ₁ = 0`：退化为 Ridge。注意 Ridge 的目标是 `(1/n)‖·‖² + λ‖w‖²`，
  与这里 `(1/(2n))‖·‖² + (λ₂/2)‖w‖²` 只差一个整体因子 2，所以 **λ₂ = λ_ridge**。

**为什么它在相关特征上比 Lasso 稳**：L1 的菱形约束在相关方向上会让解"跳"到某一个坐标轴上
（只留一个特征）；L2 的圆形约束把两个相关特征的系数一起缩小，倾向于"两个都留"。

运行 `sol-04-ElasticNet.py` 可以看到两个极限的对拍与相关特征上的系数差异。
