# 参考解：第 5 题（迁移）——alpha 与 top 词

在短信语料上对 `α ∈ {0.01,0.1,1,10}` 做 5 折 CV，选最优；再用最优 α 训练，
按 `log P(w|spam) − log P(w|ham)` 排序，列 top 5。

**预期**：测试 ≥0.9；top 词基本是 `free/win/prize/click/...` 这些 spam 词；
这份语料对 α 不敏感（CV 接近持平）。
