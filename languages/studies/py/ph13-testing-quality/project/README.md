# ph13 阶段项目：带测试与质量门禁的遥测数据处理库（telemetry-stats）

> 对应 roadmap 第 13 节「推荐项目」第一个「带测试的数据处理库」——把本阶段的测试体系（pytest/fixture/参数化/覆盖率）与静态质量门禁（mypy/ruff/black/pre-commit/CI）完整落进一个真实的数据处理小库。

## 需求

设备遥测数据以 CSV 形式落盘（`ts,device,speed,component` 每行一条），行里混着无效记录（字段数不对、数值非法、越界）。做一个**带测试与质量门禁的数据处理库**：CSV 解析清洗 → 按设备分组统计 → 输出 CSV 报表 + 文本汇总，全程由 pytest 测试与 ruff/mypy/black 门禁保障——「能跑」之外，还要「证明它一直对、改不坏」。

## 功能清单

- [x] `telemetry_stats.parser`：`parse_row` / `parse_csv` 逐行校验清洗，无效行单独计数（不静默吞掉、不崩溃），跳过表头与空行
- [x] `telemetry_stats.stats`：`per_device_stats` 按设备分组统计速度/电量的 min / max / avg（保留两位小数，按设备名排序）；`filter_device` 只保留指定设备
- [x] `telemetry_stats.report`：`write_csv_report` 确定性覆盖写 CSV 报表（可安全重跑）；`write_summary` 文本汇总（带来源与生成时间，可审计）
- [x] `cli.py` 命令行入口：`--demo` 离线演示 + 自检断言、`--input/--output-dir/--filter-device/--log-level` 参数化
- [x] `tests/` 24 个 pytest 用例（fixture 落地：conftest 共享样本数据与临时 CSV；参数化覆盖非法输入枚举）
- [x] 质量门禁：`pyproject.toml` 统一配置 ruff / mypy / black / pytest；`ruff check .`、`mypy telemetry_stats cli.py`、`black --check .` 全绿
- [x] 门禁自动化：`.pre-commit-config.yaml`（ruff + ruff-format + mypy 钩子示例）、`.github/workflows/ci.yml`（GitHub Actions 多版本矩阵流水线）

## 验收标准

- `python3 -m pytest` → **24 passed**（解析 10 + 统计 5 + 报表 4 + CLI 5，本机实测）
- `ruff check .` → `All checks passed!`；`ruff format --check .` → 10 files already formatted（本机实测）
- `mypy telemetry_stats cli.py` → `Success: no issues found in 5 source files`（本机实测；tests/ 因需 pytest 类型桩而按 pyproject 配置排除）
- `black --check .` → 10 files would be left unchanged（本机实测）
- `python3 cli.py --demo` → 自检通过：解析 `4` 有效 + `1` 无效、统计 `2` 台设备、报表 3 行（本机实测）
- 覆盖率：标准库 `trace` 实测各源码模块 **100%**（cli 75 行 / report 42 / stats 38；parser 22 行由 test_parser 全量覆盖）——CI 里换成 `pytest-cov`（见 pyproject dev 依赖）体验更好

> **依赖状态如实标注**：pytest 8.4.2、ruff 0.12.0、mypy 1.17.1、black 25.9.0 本环境已装并实测；**pytest-cov 与 pre-commit 本环境未安装**（pyproject 的 dev 依赖已列、CI 里 `pip install -e ".[dev]"` 一次装齐）；`.pre-commit-config.yaml` 与 `.github/workflows/ci.yml` 为配置示例，**未在本环境验证**（本机无 CI 平台、未装 pre-commit），本地等价验证命令即上方 pytest/ruff/mypy/black 四条。

## 扩展方向

- 装 `pytest-cov` 后跑 `pytest --cov=telemetry_stats --cov-report=term-missing`，把覆盖率报告换成正式工具（CI 已按此写）
- 装 `pre-commit` 后 `pre-commit install && pre-commit run --all-files`，让门禁真正挂在提交前（配置已备好）
- roadmap 另一个推荐项目「FastAPI 测试模板」：把本库的统计能力包成 FastAPI 接口，用 TestClient 写接口测试（可结合 ph10 Web 后端阶段）
- 接入 ph12 自动化脚本阶段的定时任务：把「报表生成」变成定时任务（schedule/cron），质量门禁保证它每次输出都正确
