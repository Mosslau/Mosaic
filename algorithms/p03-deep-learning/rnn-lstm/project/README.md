# 迁移项目：8×8 数字的行序列分类 —— RNN vs LSTM

## 需求

把循环网络用到非文本序列上。与 parity 的差别是三个**新约束**：

1. **输入是 8 行像素**：`(N,8,8)`，每行 8 个特征，T=8；
2. **10 分类**：不是二分类；
3. **真实数据**：sklearn `digits`，不是合成序列。

## 功能清单

- [x] RNN / LSTM 处理 `(N,T,input_size)` 序列
- [x] 10 类 softmax
- [x] 测试 acc / macro F1 / 耗时
- [x] 4 条验收断言

## 验收标准

1. LSTM 测试 acc **≥ 0.98**；
2. RNN 测试 acc **≥ 0.95**；
3. LSTM 比 RNN 高；
4. LSTM macro F1 **≥ 0.98**。

脚本 `digits.py` 内逐条断言。

## 运行方式

```bash
cd algorithms/p03-deep-learning/rnn-lstm/project
uv run python digits.py
```

依赖：numpy + scikit-learn；运行约 2 秒。

## 实测结果（已验证）

环境：uv（Python 3.13.15 / numpy 2.5.4），`seed = 0`；样本 1797（训练 1200 / 测试 597）。

| 模型 | 测试 acc | macro F1 | 耗时（s） |
|---|---|---|---|
| RNN | 0.9765 | 0.9766 | 0.34 |
| LSTM | **0.9916** | **0.9916** | 1.83 |

**三条结论**：

1. **8 步序列上两者都不错**：数字的“行顺序”信息有限，RNN 已能到 0.977。
2. **LSTM 略优**：0.9916 vs 0.9765；门控在稍长依赖上更稳。
3. **序列模型可用于非文本**：图像按行/块切开就是序列；但 CNN 仍更适合空间结构。

## 扩展方向

- 把图像按 **patch 序列** 输入（ViT 思路），对比 CNN；
- 试 **GRU / 双向 LSTM / mean pooling**；
- 换 **真实文本**（IMDB/字符级语料），需要词嵌入；
- 做 **序列生成**（字符级语言模型），对比 p04 的 mini-GPT。
