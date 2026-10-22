# 参考解：第 4 题（实现）——字符 tokenizer

`fit`：统计频次，按 `(-freq, char)` 排序；`<unk>` 放 0。

`encode`：`stoi.get(c, 0)`；`decode`：查 `itos`。

要求：已知文本 roundtrip；未知字符 → 0。
