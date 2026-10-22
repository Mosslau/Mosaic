# 参考解：第 5 题（迁移）——next-token 续写

训练 40 轮后，测试 next-token acc 约 0.806。

给定 prompt `"the cat"`，循环 `predict_next` 40 次，得到符合模板的续写。
注意：Block 只学局部转移，续写可能重复/跑偏；这不是“理解语义”。
