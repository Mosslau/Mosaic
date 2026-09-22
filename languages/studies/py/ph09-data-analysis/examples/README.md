# examples —— 数据分析阶段完整示例

> 每个示例对应主文档 `09-data-analysis.md` 第 6 章（及 3.1 节）的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：numpy 2.3.5、pandas 2.3.3、matplotlib 3.10.6（openpyxl 3.1.5 / tabulate 0.9.0 仅 ex06 用到）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-numpy-basics.py` | NumPy 数组基础：构造 / 形状 / 索引 / 广播 / 向量化（主文档 3.1） | `python3 ex01-numpy-basics.py`（离线） |
| `ex02-sales-analysis.py` | 销售数据分析：造 CSV → read_csv → 清洗（缺失/去重）→ groupby + 透视 → 柱状图（第 6 章示例 1） | `python3 ex02-sales-analysis.py`（离线） |
| `ex03-latency-trend.py` | 服务延迟趋势：时间序列 + 过滤量程越界延迟 + resample/rolling + 折线趋势图（第 6 章示例 2） | `python3 ex03-latency-trend.py`（离线） |
| `ex04-resource-usage.py` | 资源用量分析：缺失值分组插值 + CPU/内存分组统计与透视 + 关联散点图（第 6 章示例 3） | `python3 ex04-resource-usage.py`（离线） |
| `ex05-log-stats.py` | 平台服务日志统计：正则解析 + 按来源/级别分组频次 + 分布柱状图（第 6 章示例 4） | `python3 ex05-log-stats.py`（离线） |
| `ex06-report-export.py` | 多表 join + 分组汇总 + pivot_table + Excel（多 Sheet）/ Markdown 报告导出（第 6 章示例 5） | `python3 ex06-report-export.py`（离线） |

说明：

- 全部示例**离线可跑**：数据均为脚本内自造（销售数据 / 平台指标 / 资源用量 / 服务日志），不依赖网络。
- **指标口径与 ph18 全阶段一致**：平台指标列为 `ts, service_id, latency_ms, cpu_pct, mem_used_gb, disk_temp_c, net_io_mb_s, power_w`；量程 latency 0~2000 ms（典型 40~90）、cpu 0~100%、mem 0~256 GB、disk_temp -10~90℃、net_io 0~2000 MB/s、power 10~800 W。
- 图表示例统一用 `matplotlib.use("Agg")` 后端 + `savefig()`，不弹 GUI，无显示环境（服务器 / CI）也能跑。
- **产物纪律**：示例生成的 CSV/PNG/XLSX/MD 一律写到**系统临时目录**（`tempfile.mkdtemp`，脚本会打印实际路径），不在仓库残留任何产物文件。
- 图表含中文标题/标签：脚本内置中文字体回退链（macOS PingFang/Hiragino → Linux Noto Sans CJK → Windows 微软雅黑/黑体），缺失字体时回退 DejaVu 出方块，但不会中断运行。
- lint / 格式：本目录暂无 `pyproject.toml`，按全仓库口径执行 `ruff check --line-length 100 . && ruff format --check --line-length 100 .`。

验证状态：全部示例均已在本环境（Python 3.13.9 + numpy 2.3.5 + pandas 2.3.3 + matplotlib 3.10.6）实际运行通过（已验证）。实测关键输出：

- `ex01`：`mean: 3.0 std: 1.4142`；`m.shape: (3, 4) m.dtype: int64`；`m[1, 2]: 6`、`m[:, 1]: [1 5 9]`；广播成 (3,3)；`normal(70,10,1000): mean = 69.71, std = 9.89`
- `ex02`：缺失 1 处、无重复；月均销售额降序 `西区店 118.8 / 东区店 117.5 / 南区店 92.0`（万元）；透视表东区店 2024-01 = 112.5、2024-02 = 122.5；PNG 约 23 KB
- `ex03`：原始 200 行 → 过滤后 199 行（剔除 1 个 5000 ms 越界延迟）；平均延迟 64.6 ms；PNG 约 154 KB
- `ex04`：缺失 3 处 → 插值后 0；S001/S002/S003 内存峰值利用率 45.23% / 47.55% / 50.55%；CPU 与内存相关系数 0.9874；PNG 约 54 KB
- `ex05`：解析 8 行、3 个不同来源；来源频次 `svc-001 = 4、svc-002 = 2、svc-003 = 2`；级别分布 INFO 4 / ERROR 2 / WARN 2；PNG 约 26 KB
- `ex06`：每实例汇总 S001 25500 请求 / 错误率 0.08%、S002 9800 / 0.41%、S003 38300 / 0.09%；请求量透视表（周一/周二/周三 × S001/S002/S003，空组合填 0）；Excel 与 Markdown 报告均生成
