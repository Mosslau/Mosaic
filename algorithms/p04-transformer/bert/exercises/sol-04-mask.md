# 参考解：第 4 题（实现）——15% mask

1. eligible = 非 pad/cls/sep/mask；
2. 每个句子取 15%（至少 1 个）；
3. 80% 设 `[MASK]`，10% 随机词，10% 保留；
4. target 始终保留原 token，mask_pos 记录选中位置。
