# 参考解：第 1 题（说清）

`text → tokenizer ids → E[id]+P[pos] → N 个 causal Block → hidden → Wlm → logits → softmax/采样`。

训练：所有位置并行算 next-token CE；生成：取最后位置，采样一个 token，拼回前缀重复。
