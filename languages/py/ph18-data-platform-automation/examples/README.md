# examples —— 数据平台分析 / 自动化方向阶段完整示例

> 每个示例对应主文档 `18-data-platform-automation.md` 相关小节（3.1~3.8）的完整可运行版。数据一律脚本内自造并写 `/tmp`，全部**离线可跑**、不依赖网络。**验证状态**：ex01~ex08 已在本环境（Python 3.13.9 + numpy + pandas + matplotlib + scikit-learn + fastapi + httpx + pytest + ruff）实际运行与 pytest 全绿（已验证）；ex08 的 **paho-mqtt 真实 broker 通道未在本环境验证**（本机无运行中的 MQTT broker），离线 Fake 通道已验证。

| 文件 | 说明（对应主文档小节） | 运行 / 测试 |
|------|------|------------|
| `ex01-log-spec-parse.py` | 平台日志解析 + 极简格式规约（REC/FLD）字段解码 + 按来源流式统计（3.1） | `python3 ex01-log-spec-parse.py`；`python3 -m pytest ex01-log-spec-parse.py -q` |
| `ex02-metrics-clean.py` | 指标清洗流水线：去重/量程/孤立尖峰/时间对齐补洞，逐步骤可审计计数（3.2） | `python3 ex02-metrics-clean.py`；`python3 -m pytest ex02-metrics-clean.py -q` |
| `ex03-resource-health.py` | 节点资源负载段计量积分反推可用容量与健康度，平台级滚动平滑（3.3） | `python3 ex03-resource-health.py`；`python3 -m pytest ex03-resource-health.py -q` |
| `ex04-fault-report.py` | 故障定位规则引擎（dataclass 规则库）+ Markdown/Matplotlib 报表（3.4） | `python3 ex04-fault-report.py`；`python3 -m pytest ex04-fault-report.py -q` |
| `ex05-test-platform.py` | 自动化测试平台：数据质量门禁 + pytest 基础设施（fixture/parametrize/marker/快照）（3.5） | `python3 ex05-test-platform.py`；`python3 -m pytest ex05-test-platform.py -q` |
| `ex06-fastapi-service.py` | 指标数据服务：平台摘要/时间序列/规则事件/指标上报，pydantic fail-fast 边界（3.6） | `python3 ex06-fastapi-service.py`；`--serve` 起 uvicorn；`python3 -m pytest ex06-fastapi-service.py -q` |
| `ex07-anomaly-detection.py` | AI 异常检测：Isolation Forest + 窗口形态特征，对照埋点评估召回/误报（3.7） | `python3 ex07-anomaly-detection.py`；`python3 -m pytest ex07-anomaly-detection.py -q` |
| `ex08-mqtt-collector.py` | MQTT 指标采集：主题路由 + 载荷校验 + 可替换 sink；离线 Fake 通道演示，paho 胶水给真实 broker 用（3.8） | `python3 ex08-mqtt-collector.py`；`python3 -m pytest ex08-mqtt-collector.py -q` |

## 全阶段指标口径（ex02~ex04/ex07/project 共用）

| 列 | 含义 | 量程（清洗用） | 典型值 |
|---|---|---|---|
| `latency_ms` | 请求延迟（毫秒） | 0 ~ 2000 | 40 ~ 90 |
| `cpu_pct` | CPU 使用率（%） | 0 ~ 100 | 55 ~ 90 |
| `mem_used_gb` | 内存占用（GB） | 0 ~ 256 | ~96 |
| `disk_temp_c` | 磁盘温度（℃） | -10 ~ 90 | ~38（>75 为过热） |
| `net_io_mb_s` | 网络入出速率（MB/s） | 0 ~ 2000 | 300 ~ 450 |
| `power_w` | 整机功率（W） | 10 ~ 800 | 200 ~ 450 |

说明：

- **依赖安装**（按需，装到 venv）：
  ```bash
  python3 -m pip install "pytest>=8" "ruff>=0.4" "numpy>=2" "pandas>=2.2" \
    "matplotlib>=3.9" "scikit-learn>=1.5" "fastapi>=0.115" "uvicorn>=0.30" \
    "httpx>=0.27" "paho-mqtt>=2"
  ```
  ex01 纯标准库零依赖；ex02~ex04/ex06 需要 pandas（ex03 另需 numpy、ex04 另需 matplotlib、ex06 另需 fastapi+httpx）；ex05 只需 pytest；ex07 需要 scikit-learn；ex08 离线路径零依赖、真实 broker 路径需要 paho-mqtt + 本机 MQTT broker
- **每个示例都是「main 自检 + pytest 断言」双形态**：`python3 ex0X-*.py` 打印教学输出并跑断言（失败退出码非 0）；`python3 -m pytest ex0X-*.py -q` 只收集文件内 `test_*` 跑断言。本机全部实测通过（已验证）
- **pytest 临时目录注意**：部分测试用 `tmp_path`，在受限环境（沙箱/容器）请设 `TMPDIR=/tmp` 再跑，否则 mkdir 权限可能被拒
- **产物纪律**：示例生成的数据与报表一律写系统临时目录（`/tmp/ph18-ex0X/`），仓库不残留数据/图片/CSV
- **图表示例**（ex04）用 `matplotlib.use("Agg")` 后端 + 内置中文字体回退链，无显示环境（服务器/CI）也能出图
- **lint**：本目录 `ruff check .` 与 `ruff format --check .`（配置见 [`pyproject.toml`](./pyproject.toml)，line-length 100）；本机全绿（已验证）
- ex01 的格式规约解析为教学子集：小端字段支持任意位宽，大端仅支持**字节对齐**字段（任意位级位序换算属完整解析工具库范畴，主文档 4.1 有边界说明）
