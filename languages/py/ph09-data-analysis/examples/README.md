# examples —— 数据分析阶段完整示例

> 每个示例对应主文档 `09-data-analysis.md` 第 6 章（及 3.1 节）的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：numpy 2.3.5、pandas 2.3.3、matplotlib 3.10.6（openpyxl 3.1.5 / tabulate 0.9.0 仅 ex06 用到）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-numpy-basics.py` | NumPy 数组基础：构造 / 形状 / 索引 / 广播 / 向量化（主文档 3.1） | `python3 ex01-numpy-basics.py`（离线） |
| `ex02-sales-analysis.py` | 销售数据分析：造 CSV → read_csv → 清洗（缺失/去重）→ groupby + 透视 → 柱状图（第 6 章示例 1） | `python3 ex02-sales-analysis.py`（离线） |
| `ex03-vehicle-speed.py` | 车辆速度分析：时间序列 + 过滤 GPS 跳变异常值 + resample/rolling + 折线趋势图（第 6 章示例 2） | `python3 ex03-vehicle-speed.py`（离线） |
| `ex04-battery-analysis.py` | 电池数据分析：缺失值线性插值 + SOC/电压相关系数 + 散点图与拟合线（第 6 章示例 3） | `python3 ex04-battery-analysis.py`（离线） |
| `ex05-can-log-stats.py` | CAN 日志统计：正则解析日志 + 按报文 ID 分组频次 + 分布柱状图（第 6 章示例 4） | `python3 ex05-can-log-stats.py`（离线） |
| `ex06-report-export.py` | 数据合并与透视：merge 多表 join + pivot_table + Excel（多 Sheet）/ Markdown 报告导出（第 6 章示例 5） | `python3 ex06-report-export.py`（离线） |

说明：

- 全部示例**离线可跑**：数据均为脚本内自造（模拟销售 / 遥测 / 电池 / CAN 日志），不依赖网络。
- 图表示例统一用 `matplotlib.use("Agg")` 后端 + `savefig()`，不弹 GUI，无显示环境（服务器 / CI）也能跑。
- **产物纪律**：示例生成的 CSV/PNG/XLSX/MD 一律写到**系统临时目录**（`tempfile.mkdtemp`，脚本会打印实际路径），不在仓库残留任何产物文件。
- 图表含中文标题/标签：脚本内置中文字体回退链（macOS PingFang/Hiragino → Linux Noto Sans CJK → Windows 微软雅黑/黑体），缺失字体时回退 DejaVu 出方块，但不会中断运行。

验证状态：全部示例均已在本环境（Python 3.13.9 + numpy 2.3.5 + pandas 2.3.3 + matplotlib 3.10.6）实际运行通过（已验证）。实测关键输出：

- `ex01`：`mean: 3.0 std: 1.4142`；`m.shape: (3, 4) m.dtype: int64`；`m[1, 2]: 6`、`m[:, 1]: [1 5 9]`；广播成 (3,3)；`normal(70,10,1000): mean = 69.71, std = 9.89`
- `ex02`：缺失 1 处、无重复；月均销售额降序 `西区店 118.8 / 东区店 117.5 / 南区店 92.0`（万元）；透视表东区店 2024-01 = 112.5、2024-02 = 122.5；PNG 约 23 KB
- `ex03`：原始 200 行 → 过滤后 199 行（剔除 1 个 320 km/h 异常值）；平均速度 59.5 km/h；PNG 约 156 KB
- `ex04`：插值后缺失 0；SOC 与电压相关系数 0.9974；PNG 约 66 KB
- `ex05`：频次 `0x123 = 4、0x456 = 2、0x789 = 2`；总报文 8、不同 ID 3；PNG 约 26 KB
- `ex06`：每车汇总 V001 255.5 km / 38.3 kWh / 14.99 kWh/100km、V002 98.0 / 15.5 / 15.82、V003 384.4 / 57.3 / 14.91；Excel 与 Markdown 报告均生成
