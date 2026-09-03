# ph18 阶段项目：车辆遥测 Dashboard（vehdash）

> 对应 roadmap 第 18 节「推荐项目」第一个「车辆遥测 Dashboard」（第二个「传感器异常检测模型」由 [`../examples/ex07-anomaly-detection.py`](../examples/ex07-anomaly-detection.py) 落地）。流水线完全对应 roadmap §18 的示例骨架：`车辆日志 → 清洗 → Pandas 分析 → 报表/API`。第二个推荐项目与 AI 通道可扩展接入，见「扩展方向」。

## 需求

车队一天产生百万行遥测，业务方要的不只是一张「今天平均车速」的纸，而是**能下钻到单车的可阅读产物**。`vehdash` 是一条可复用的清洗→分析→可视化流水线，输出两类交付物：

- **自包含 HTML Dashboard**：图表内嵌（base64），单文件可分发、可邮件、可归档；
- **结构化 JSON 摘要**：车队/单车统计（`dashboard.json`），供 FastAPI/BI 直接消费。

项目刻意做成 **ph17 的 streamlog 风格**：一个可 import 的包 + 薄 CLI + pytest 测试，分析函数与展示层分离（可单测、可换展示）。

```text
fleet.csv ──▶ clean（排序/去重/物理范围/尖峰）──▶ analyze（距离/能耗/SOH 段/温度）
                        │                                  │
                        └────────────  report：HTML + PNG + JSON ──┘
```

## 功能清单

- [x] `vehdash/data.py`：确定性车队样例生成器（3 车 × 20 分钟，含刻意埋的脏点与过热段），输出 /tmp；`read_fleet` 读回 DataFrame
- [x] `vehdash/clean.py`：清洗流水线（排序/去重/物理量程/孤立尖峰），与 ex02 同一套量程与跳变阈值语义，逐步骤可审计计数
- [x] `vehdash/analyze.py`：`fleet_summary`（总里程/总能耗/过热秒数等）+ `vehicle_summary`（单车维度），纯函数可单测
- [x] `vehdash/report.py`：Matplotlib（Agg 后端 + 中文字体回退）出图 + 自包含 HTML Dashboard + `dashboard.json`
- [x] `vehdash/cli.py`：`argparse` 两个子命令——`build-dashboard --fleet raw.csv --out dir` 与 `summary --fleet raw.csv`
- [x] `pyproject.toml`：ruff + pytest 配置（`pythonpath=["."]`）
- [x] `tests/test_vehdash.py`：9 个 pytest 用例（清洗计数/距离估算/过热检测/SOH 提示/报告产物/CLI 冒烟/缺列校验）

## 验收标准

- 验证环境（目标）：Python 3.13 + pandas 2.x/3.x + matplotlib + pytest + ruff；本机实测 Python 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1 + pytest 9.1.1 + ruff 0.16.5
- `python3 -m pytest` → **全部通过**（project 目录内；`tests/` 9 个用例）
- `ruff check .` → 全绿；`ruff format --check .` → 全绿
- CLI 冒烟（产物写 /tmp，仓库不落数据）：
  ```bash
  # 1.（可选）装依赖
  python3 -m pip install "pandas>=2.2" "matplotlib>=3.9" "pytest>=8" "ruff>=0.4"
  # 2. 直接对内置样例造数据并出 Dashboard（默认走 /tmp）
  python3 -m vehdash.cli build-dashboard
  # 3. 指定输入/输出目录
  python3 -m vehdash.cli build-dashboard --fleet /tmp/ph18-project/fleet_raw.csv --out /tmp/ph18-project
  # 4. 只出摘要 JSON/表格
  python3 -m vehdash.cli summary --fleet /tmp/ph18-project/fleet_raw.csv
  ```
  预期产物：`dashboard.html`（自包含）、`dashboard.json`、若干 PNG 在输出目录
- 正确性抽查：总里程与「以平均速度 × 时长」的估算在同一量级；过热段车辆 V002 的过热秒数 > 0 且健康车 V001/V003 为 0；清洗报告计数与埋点一致
- **验证状态：已验证**（Python 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1 本机实测：`python3 -m pytest` 9 用例全绿、CLI 冒烟通过、ruff check/format 全绿）

## 运行手册

```bash
cd project
python3 -m vehdash.cli build-dashboard      # 产物写 /tmp/ph18-project/
python3 -m vehdash.cli summary              # 终端打印车队摘要表
python3 -m pytest                            # 测试（受限环境设 TMPDIR=/tmp）
ruff check . && ruff format --check .       # lint
```

## 目录结构

```text
project/
├── README.md
├── pyproject.toml
├── vehdash/
│   ├── __init__.py      # 包导出
│   ├── data.py          # 样例生成 / CSV 读取
│   ├── clean.py         # 清洗流水线
│   ├── analyze.py       # 车队/单车分析（纯函数）
│   ├── report.py        # Matplotlib + HTML Dashboard + JSON
│   └── cli.py           # argparse 入口
└── tests/
    └── test_vehdash.py
```

## 扩展方向

- **接 FastAPI 出 API**：`dashboard.json` 已是结构化数据——包一层 [`../examples/ex06-fastapi-service.py`](../examples/ex06-fastapi-service.py) 的路由即得 `GET /vehicles/{id}/summary`；实时场景把 CSV 源换成 ex08 的 MQTT 采集 sink
- **接 AI 异常检测**：把 `report.py` 的过热规则替换/叠加 [`../examples/ex07-anomaly-detection.py`](../examples/ex07-anomaly-detection.py) 的 Isolation Forest 分数列，Dashboard 增加「异常评分」区块——规则负责已知故障、模型负责未知模式（主文档 3.7）
- **按日/按车分桶**：数据量大时按 `data-YYYYMMDD`（exer4 的日桶思路）出增量 Dashboard，避免每次全量重算
- **电池 SOH 视角**：把 [`../examples/ex03-battery-soh.py`](../examples/ex03-battery-soh.py) 的充电段估计接到 Dashboard 的电池卡片（project 的 `vehicle_summary` 预留了 `soh_hint` 字段）
