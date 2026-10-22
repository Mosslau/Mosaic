# 参考解：第 1 题（说清）

1. `Attention(Q,K,V)=softmax(QKᵀ/√d_k)V`。
2. `q·k` 的方差随 `d_k` 增长；除以 `√d_k` 把方差拉回 O(1)，避免 softmax 饱和。
3. padding mask 屏蔽填充位；causal mask 屏蔽未来位置。
4. `-inf` 在整行被 mask 时会出现 `-inf - -inf = nan`；`-1e9` 是有限大负数。
