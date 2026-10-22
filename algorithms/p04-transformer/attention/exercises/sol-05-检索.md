# 参考解：第 5 题（迁移）——内容检索

构造 64 个随机 key、one-hot value；query=某个 key。
attention 权重应选中该 key，输出对应 value；mean pooling 只能返回平均 value。

**实测**：T=64、D=32、64 个 query 全量 top-1 1.000；mean pooling 0.000。
