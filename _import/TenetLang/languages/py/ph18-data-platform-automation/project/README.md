# ph18 阶段项目：平台指标 Dashboard（platdash）

> 对应 roadmap 第 18 节「推荐项目」第一个「平台指标 Dashboard」（第二个「指标异常检测模型」由 [`../examples/ex07-anomaly-detection.py`](../examples/ex07-anomaly-detection.py) 落地）。流水线完全对应 roadmap §18 的示例骨架：`平台日志 → 清洗 → Pandas 分析 → 报表/API`。第二个推荐项目与 AI 通道可扩展接入，见「扩展方向」。

## 需求

平台一天产生百万行服务与节点指标，业务方要的不只是一张「今天平均延迟」的纸，而是**能下钻到单个服务实例的可阅读产物**。`platdash` 是一条可复用的清洗→分析→可视化流水线，输出两类交付物：

- **自包含 HTML Dashboard**：图表内嵌（base64），单文件可分发、可邮件、可归档；
- **结构化 JSON 摘要**：平台/单实例统计（`dashboard.json`），供 FastAPI/BI 直接消费。

项目刻意做成 **ph17 的 streamlog 风格**：一个可 import 的包 + 薄 CLI + pytest 测试，分析函数与展示层分离（可单测、可换展示）。

```text
platform.csv ──▶ clean（排序/去重/量程/尖峰）──▶ analyze（传输量/耗电/延迟分位/过热秒）
                          │                                  │
                          └────────────  report：HTML + PNG + JSON ──┘
```

## 指标口径

全阶段共用一份 schema（`examples/ex02` 与主文档 3.2 同源）：

| 列 | 含义 | 量程（清洗用） |
|---|---|---|
| `latency_ms` | 请求延迟（毫秒） | 0 ~ 2000 |
| `cpu_pct` | CPU 使用率（%） | 0 ~ 100 |
| `mem_used_gb` | 内存占用（GB） | 0 ~ 256 |
| `disk_temp_c` | 磁盘温度（℃） | 10 ~ 90 |
| `net_io_mb_s` | 网络入出速率（MB/s） | 0 ~ 2000 |
| `power_w` | 整机功率（W） | 20 ~ 600 |

派生口径（`analyze.py`，纯函数）：**数据传输量** = ∫ `net_io_mb_s` dt ÷ 1024（GB）；**耗电量** = ∫ `power_w` dt ÷ 3600（kWh）；**过热秒数** = `disk_temp_c > 75℃` 的行数。

## 功能清单

- [x] `platdash/data.py`：确定性平台样例生成器（3 个服务实例 × 20 分钟，含刻意埋的量程越界/尖峰/过热段/掉点），输出 /tmp；`read_platform` 读回 DataFrame
- [x] `platdash/clean.py`：清洗流水线（排序/去重/物理量程/孤立尖峰），与 ex02 同一套量程与跳变阈值语义，逐步骤可审计计数
- [x] `platdash/analyze.py`：`platform_summary`（总传输量/总耗电量/过热秒数等）+ `service_summary`（单实例维度，含 p95 延迟），纯函数可单测
- [x] `platdash/report.py`：Matplotlib（Agg 后端 + 中文字体回退）出图 + 自包含 HTML Dashboard + `dashboard.json`
- [x] `platdash/cli.py`：`argparse` 两个子命令——`build-dashboard --platform raw.csv --out dir` 与 `summary --platform raw.csv`
- [x] `pyproject.toml`：ruff + pytest 配置（`pythonpath=["."]`）
- [x] `tests/test_platdash.py`：9 个 pytest 用例（清洗计数/传输量估算/过热检测/延迟分位/报告产物/CLI 冒烟/缺列校验）

## 验收标准

- 验证环境（目标）：Python 3.13 + pandas 2.x/3.x + matplotlib + pytest + ruff
- `python3 -m pytest` → **全部通过**（project 目录内；`tests/` 9 个用例）
- `ruff check .` → 全绿；`ruff format --check .` → 全绿
- CLI 冒烟（产物写 /tmp，仓库不落数据）：
  ```bash
  # 1.（可选）装依赖
  python3 -m pip install "pandas>=2.2" "matplotlib>=3.9" "pytest>=8" "ruff>=0.4"
  # 2. 直接对内置样例造数据并出 Dashboard（默认走 /tmp）
  python3 -m platdash.cli build-dashboard
  # 3. 指定输入/输出目录
  python3 -m platdash.cli build-dashboard --platform /tmp/ph18-project/platform_raw.csv --out /tmp/ph18-project
  # 4. 只出摘要表格
  python3 -m platdash.cli summary --platform /tmp/ph18-project/platform_raw.csv
  ```
  预期产物：`dashboard.html`（自包含）、`dashboard.json`、若干 PNG 在输出目录
- 正确性抽查：总数据传输量与「平均速率 × 时长」的估算在同一量级；过热段服务实例 V002 的过热秒数 > 0 且健康实例 V001/V003 为 0；清洗报告计数与埋点一致
- **验证状态：已验证**（Python 3.13.9 + pandas + matplotlib 本机实测：`python3 -m pytest` 9 用例全绿、CLI 冒烟通过、内置样例端到端跑通）

## 运行手册

```bash
cd project
python3 -m platdash.cli build-dashboard      # 产物写 /tmp/ph18-project/
python3 -m platdash.cli summary              # 终端打印平台摘要表
python3 -m pytest                            # 测试（受限环境设 TMPDIR=/tmp）
ruff check . && ruff format --check .       # lint
```

## 目录结构

```text
project/
├── README.md
├── pyproject.toml
├── platdash/
│   ├── __init__.py      # 包导出
│   ├── data.py          # 样例生成 / CSV 读取
│   ├── clean.py         # 清洗流水线
│   ├── analyze.py       # 平台/单实例分析（纯函数）
│   ├── report.py        # Matplotlib + HTML Dashboard + JSON
│   └── cli.py           # argparse 入口
└── tests/
    └── test_platdash.py
```

## 扩展方向

- **接 FastAPI 出 API**：`dashboard.json` 已是结构化数据——包一层 [`../examples/ex06-fastapi-service.py`](../examples/ex06-fastapi-service.py) 的路由即得 `GET /services/{id}/summary`；实时场景把 CSV 源换成 ex08 的 MQTT 采集 sink
- **接 AI 异常检测**：把 `report.py` 的过热规则替换/叠加 [`../examples/ex07-anomaly-detection.py`](../examples/ex07-anomaly-detection.py) 的 Isolation Forest 分数列，Dashboard 增加「异常评分」区块——规则负责已知故障、模型负责未知模式（主文档 3.7）
- **按日/按实例分桶**：数据量大时按 `data-YYYYMMDD`（练习 4 的日桶思路）出增量 Dashboard，避免每次全量重算
- **资源健康度视角**：把 [`../examples/ex03-resource-health.py`](../examples/ex03-resource-health.py) 的容量标定估计接到 Dashboard 的节点卡片（`service_summary` 可扩展 `health_hint` 字段）
