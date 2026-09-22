# ph15 阶段项目：电池健康预测（battery-health）

> 对应 roadmap 第 15 节「推荐项目」第一个「电池健康预测」——把本阶段的 ML 工作流（合成数据 → train/test 划分 → 双任务建模 → 指标评估 → 模型产物 → 命令行推理）完整落进一个最小可运行、可测试、产物不污染仓库的工程；另一个推荐项目「日志异常检测」作为扩展方向（见文末，且与练习 3 衔接）。

## 需求

电池是电动车最贵也最需要监控的部件。本项目预测两块内容：

- **SOH（State of Health，健康度 %）回归**：给定工作工况（累计循环次数、平均温度、放电深度、充电倍率），预测电池还剩多少健康度——退化曲线随工况非线性加速（高温/深放/大倍率），这是随机森林比线性回归强的天然场景（ex04 的过拟合/非线性主题）；
- **健康等级分类**：把 SOH 分箱成 健康（≥90）/ 退化（80~90）/ 临界（<80）三级，且标签带体检测量噪声——等级分类学到的不是「SOH 的确定性函数」，而是有噪声的真实标签（ex03 的指标与不平衡主题）。

数据为**合成数据**（`bhealth/data.py`，seed 固定、物理趋势可解释、离线可复现）；模型用 RandomForest（树模型对特征缩放不敏感——ex02 结论的直接复用）；评估带两个 baseline 对照（回归的「预测均值」、分类的「多数类」——roadmap 必会概念：先 baseline 再复杂化）；模型产物用 joblib 落盘到 `/tmp`（产物纪律），`--predict` 从另一个进程加载做单条推理——这就是「模型部署」的最小闭环（概念衔接：服务化/容器化部署见 [ph16 部署与 DevOps 阶段](../../ph16-deploy-devops/16-deploy-devops.md)，roadmap 第 16 节）。

## 功能清单

- [x] `bhealth/data.py`：合成电池老化数据（`FEATURES=[cycles, avg_temp, depth, c_rate]`；SOH = 100 − 循环数×每循环老化率 + 噪声；等级由带测量误差的 SOH 分箱）；同 seed 完全可复现；train/test 按等级分层划分
- [x] `bhealth/model.py`：`RandomForestRegressor`（SOH）+ `RandomForestClassifier`（等级）双模型 `BatteryHealthPipeline`；`save/load` joblib 产物
- [x] `bhealth/evaluate.py`：回归 RMSE/MAE/R²、分类 acc/macro-F1/混淆矩阵、两个 baseline 对照、`summary_metrics` 汇总成 JSON
- [x] `cli.py` 命令行入口：`--n/--seed/--test-size/--out` 训练 + `--predict CYCLES TEMP DEPTH CRATE` 加载推理 + `--demo` 离线自检（含指标断言）
- [x] `tests/` 14 个 pytest 用例：数据形状/范围/复现性/分层划分/物理单调性、模型复现性与优于 baseline、产物 save→load 闭环、CLI demo/训练/推理/错误路径
- [x] 质量门禁：`pyproject.toml` 统一配置；`ruff check .` 与 `ruff format --check .` 全绿

## 验收标准

- `python3 -m pytest` → **14 passed**（data 5 + model 5 + cli 4，本机实测）
- `ruff check .` → `All checks passed!`；`ruff format --check .` → 8 files already formatted（本机实测）
- `python3 cli.py`（默认 N=1500，seed=42）→ 本机实测：SOH 回归 **RMSE 2.692% / MAE 2.057% / R² 0.968**（baseline 预测均值 RMSE 15.13%——模型把误差压到 baseline 的 18%）；等级分类 **acc 0.896 / macro-F1 0.876**（baseline 多数类 acc 0.504）；测试集等级分布 [94, 92, 189]（健康 94 / 退化 92 / 临界 189），混淆矩阵 `[[82,12,0],[9,73,10],[0,8,181]]`（**数字随数据划分/随机种子波动**，±1~2 个百分点内）
- `python3 cli.py --predict 1500 25 80 1.0` → `预测 SOH: 79.5% → 健康等级: 临界`（1500 次循环 + 常温 + DoD 80% 已到退化临界线——与老化公式互相印证）
- `python3 cli.py --predict 3000 40 95 2.0` → `预测 SOH: 40.0% → 健康等级: 临界`（高温深放大倍率 3000 循环后逼近下限）
- `python3 cli.py --demo` → 自检通过：R² 0.944 > 0.85、acc 0.840 > 0.75（本机实测，n=400）
- **产物纪律**：模型产物默认写 `/tmp/bhealth-model/`（demo 写 `/tmp/bhealth-demo/`），不入库；运行后 `git status` 工作区干净

## 数据泄漏教学点（重要）

SOH 是**要预测的目标，不是特征**——把 SOH 喂进模型去预测 SOH 是教科书级泄漏（ex01 的泄漏演示）。真实场景里 SOH 靠定期体检实测、平时拿不到，模型要干的是「根据工况预测两次体检之间的 SOH 轨迹」；本项目特征只有工况，`tests/test_model.py::test_no_target_leakage_features` 把这个约束固化成测试。

## 扩展方向

- **日志异常检测**（roadmap 另一个推荐项目）：把目标从「电池健康」换成「文本/数值日志是否异常」——练习 3 的马氏距离/IsolationForest 思路 + 练习 4 的日志文本向量化都可复用，数据换成 [ph18 数据平台分析 / 自动化方向阶段](../../ph18-data-platform-automation/18-data-platform-automation.md)会遇到的平台日志/指标数据
- 模型换线性基线对照：`StandardScaler + Ridge`（需要缩放——树模型不需要）对比 RandomForest，观察非线性分段老化率让 RF 领先多少（示例 ex04 的方法直接可用）
- 服务化：把 `BatteryHealthPipeline.load + predict` 包成 FastAPI 端点（ph10 Web 后端阶段技能；异步推理入口见 ph14 的异步 FastAPI 示例），容器化部署衔接 [ph16 部署与 DevOps 阶段](../../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）
- 体检数据接入：用 ph09 的数据读取/清洗把真实体检记录读进来替换合成数据，特征工程（时间窗聚合）走本阶段 3.4 的方法
