# 参考解：第 5 题（迁移）——[CLS] 探针

MLM 训练 200 轮后，取 `encode(tokens)` 的 `[CLS]`，训练逻辑回归。

**实测**：MLM loss 0.130、masked acc 0.958；探针 acc 0.933。

结论：MLM 好不代表表示一定适合分类；探针/微调是必要评估。
