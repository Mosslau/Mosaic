# 迁移项目：top-k 推荐

## 验收

- MF Recall@10 > 0.4；
- 推荐排除已评分；
- 给出可解释的基线对照。

运行：`uv run python recommend.py`

实测：Recall@10 0.516；NDCG@10 0.252。
