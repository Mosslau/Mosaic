# examples —— AI / 机器学习阶段完整示例

> 每个示例对应主文档 `15-ai-ml.md` 相关小节（3.2~3.10）的完整可运行版。验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（scipy 1.16.3 / pandas 2.3.3 / matplotlib 3.10.6 也已装，本示例只用到 numpy + sklearn）；**PyTorch / Transformers 未安装**——深度学习的认知示例不在本目录（见主文档 3.9，概念讲解 + 未在本环境验证标注）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-data-quality.py` | 数据质量与泄漏：干净基线 vs 标签噪声 vs 缺失值填充 vs 泄漏特征（主文档 3.3） | `python3 ex01-data-quality.py`（离线） |
| `ex02-feature-engineering.py` | 特征工程：量纲缩放对 kNN 的影响（树模型不敏感）、类别编码 label-encoding vs one-hot（主文档 3.4） | `python3 ex02-feature-engineering.py`（离线） |
| `ex03-classification-metrics.py` | 分类评估：多数类 baseline 的骗局、accuracy/precision/recall/F1/macro-F1、混淆矩阵（主文档 3.5） | `python3 ex03-classification-metrics.py`（离线） |
| `ex04-regression-overfit.py` | 回归过拟合：多项式复杂度扫描（欠拟合↔过拟合）、系数范数爆炸、Ridge 正则化修复（主文档 3.6） | `python3 ex04-regression-overfit.py`（离线） |
| `ex05-crossval-tuning.py` | 交叉验证：单次划分的运气 vs k 折稳定估计、用 CV 调决策树深度（主文档 3.7） | `python3 ex05-crossval-tuning.py`（离线） |
| `ex06-mini-rag.py` | 迷你 RAG：TF-IDF + 余弦检索、查询措辞与 top-k 对命中率的影响、检索质量决定回答质量（主文档 3.10） | `python3 ex06-mini-rag.py`（离线） |
| `pyproject.toml` | 本目录 ruff 校验基准（line-length 100、select E/F/I/UP/B） | 被 `ruff check` 命令自动读取 |

说明：

- **离线可跑**：所有示例只用 numpy + sklearn（ex06 连 sklearn 都不用），不下载数据集、不起服务、不落盘——运行后 `git status` 工作区干净
- **产物纪律**：不产生模型/图片产物；如需把训练好的模型/图表存下来，统一写 `/tmp`（主文档 3.11 与 project/ 演示模型产物写 /tmp 的做法）
- **复现**：全部示例固定随机种子（seed=42），数字可复现；**评估数字随数据划分/随机种子波动**（约 ±1~2 个百分点、RMSE ±5~10%）——对比方向稳定，绝对数值仅供参考
- **数据生成**：电池传感器故障（健康 88%/过压 8%/过热振动 4%）、多项式回归曲线（真实函数已知）、电动车手册语料均为内置合成数据——把「数据从哪来、噪声多大」写在明面上，是评估可信的前提

验证状态（全部在本环境实际运行，已验证；数字为本机实测）：

- `ex01`：干净 test acc **0.930**（但两类故障 recall 只有 0.458/0.500——准确率的骗局在 ex03 展开）→ 标签噪声 25%（**仅训练集**，评估标签干净）test **0.873**（换 flip seed 实测 0.870~0.900；若评估标签也污染会虚跌到 0.75 量级）→ 缺失两列 60% 均值填充 **0.917** → 泄漏特征 val **0.990**（虚高），换真实输入后 **0.897**
- `ex02`：kNN 未缩放 test **0.890** → 缩放后 **0.930**；RF 缩放前后完全一致（0.963/0.947）；LR 类别 label-encoding **0.917** → one-hot **0.927**（batch C 0.896→0.925）
- `ex03`：多数类 baseline acc **0.880**（全猜健康）；kNN acc **0.930** 但 macro-F1 仅 **0.728**；RF acc **0.947** / macro-F1 **0.793**；kNN 混淆矩阵 `[[262,2,0],[13,11,0],[3,3,6]]`
- `ex04`：degree 1 train/test RMSE 1.391/1.438（欠拟合）→ degree 6 0.693/0.686（最佳）→ degree 15 0.674/0.788（过拟合，‖w‖ 8.7→1858）；Ridge(α=0.1) test **0.693** 修复
- `ex05`：单次划分 val acc 跨 10 个 seed 波动 **0.920~0.973**；5 折 CV **0.941 ± 0.004**（3 折 0.945±0.005 / 10 折 0.941±0.011）；CV 调 depth 选中 4 → test **0.944**（对照过深示例 depth 12 → train 0.998 / test 0.936，明显更低）
- `ex06`：清晰措辞 6 问 hit@1 全中、模糊 2 问全 miss → hit@1 **6/8**、hit@3 **7/8**；停用词不移除时词频检索 5/8 vs TF-IDF 6/8；句子级分块 hit@1 同为 6/8
