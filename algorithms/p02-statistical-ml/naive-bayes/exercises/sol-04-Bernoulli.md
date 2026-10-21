# 参考解：第 4 题（实现）——Bernoulli NB

**模型**：只看词是否出现，`x_j ∈ {0,1}`：

$$P(x\mid c)=\prod_j p_{jc}^{x_j}(1-p_{jc})^{1-x_j},\qquad
p_{jc}=\frac{\text{出现 }w_j\text{ 的类 c 文档数}+\alpha}{n_c+2\alpha}$$

**与 Multinomial 的区别**：

- Multinomial 用词频（出现几次），适合长文档；
- Bernoulli 只用 0/1，且显式惩罚"没出现"（`(1−p)` 项），适合短文本。

**预期**：Bernoulli 在短信语料上测试 ≥0.9；两者都强，差异取决于文档长度与词频信息。
