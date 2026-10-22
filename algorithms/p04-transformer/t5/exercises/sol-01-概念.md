# 参考解：第 1 题（说清）

1. encoder 全 1（双向）。
2. decoder self-attn 下三角（causal）。
3. cross-attn：Q 来自 decoder，K/V 来自 encoder memory。
4. decoder 输入 `[BOS]+tgt[:-1]`，目标 `tgt`（含 EOS）。
