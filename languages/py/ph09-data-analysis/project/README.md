# ph09 阶段项目：车辆遥测分析脚本

> 对应 Roadmap（python.md）ph09「推荐项目」第一个「车辆遥测分析脚本」。读取遥测 CSV → 清洗（缺失/异常值）→ 按车辆分组统计（均速、里程、能耗）→ 折线趋势 + 柱状对比图 → 导出 Excel/Markdown 报表。

## 需求

实现一个命令行车辆遥测分析工具：输入一份遥测 CSV（列：`vehicle_id, time, speed, mileage, energy`），清洗缺失值与 GPS 跳变异常值，按车辆分组统计（出车段数、总里程、总能耗、平均速度、百公里能耗），产出折线趋势图 + 柱状对比图，并导出 Excel（多 Sheet）与 Markdown 摘要报告。要求解析/清洗/统计/导出为纯函数（可离线测试），CLI 支持 `--demo` 模式用内置模拟数据离线演示完整链路。

## 功能清单

- [x] 取数：`generate_demo_data()` 内置模拟数据（3 车 × 240 行，含 3 个缺失速度 + 2 个异常速度）；`load_telemetry(path)` 读 CSV（`dtype` 保 vehicle_id 字符串、`parse_dates` 解析时间）
- [x] 清洗：`clean(df)` —— 缺失值组内中位数填充 → 速度物理范围（0~200 km/h）过滤异常值 → 去重 → 重置索引（复制语义，不改入参，呼应主文档 4.3）
- [x] 统计：`analyze(df)` —— 按车分组：trips / total_mileage / total_energy / avg_speed / energy_per_100km
- [x] 图表：`make_charts(df, outdir)` —— 各车速度趋势折线（5 分钟均值降采样）+ 各车平均速度柱状对比，Agg 后端 `savefig`
- [x] 导出：`export_report(stats, df, outdir)` —— Excel 多 Sheet（汇总 + 清洗后数据）+ Markdown 报告（`to_markdown`）
- [x] CLI：argparse 支持 `--demo` / `--input` / `-o` 输出目录（默认系统临时目录）
- [x] 测试：`tests/test_telemetry.py` 离线覆盖清洗/统计/导出/CLI 演示（pytest 5 用例）
- [x] 质量：`pyproject.toml` 内置 ruff 配置，`ruff check . && pytest -q` 一键门禁

## 验收标准

- [ ] `python3 telemetry_analyzer.py --demo` 离线跑通：打印清洗前后行数（剔除数与注入的异常值一致）与按车统计表，写出图表与报告
- [ ] `python3 telemetry_analyzer.py --input telemetry.csv -o out/` 跑通：统计表与产物齐全
- [ ] 数据含缺失速度时被组内中位数填充，含 >200 km/h 的 GPS 跳变时被剔除（`clean()` 的断言）
- [ ] `pytest -q` 全部通过（离线，不依赖网络）
- [ ] `ruff check .` 零告警
- [ ] 说清为什么清洗/统计要设计成纯函数（可离线测试、与 CLI/文件 IO 解耦）

## 扩展方向（可选）

- 报表加时序维度：`pivot_table` 出「车辆 × 日期」里程透视，`resample("1D")` 出每日汇总（主文档 3.7）
- 图表加箱线图/直方图看每车速度分布（主文档 3.8，深入见 ph15 AI/ML 的分布分析）
- 把分析结果暴露成 HTTP 接口（主文档 5 使用场景 → ph10 Web 后端阶段）
- 数据量大时用 `chunksize` 分块读取 + 逐块聚合（主文档 4.4）；超内存换 polars/数据库（ph11）

## 验证环境

- Python 3.13.9；依赖：numpy 2.3.5、pandas 2.3.3、matplotlib 3.10.6、openpyxl 3.1.5、tabulate 0.9.0、pytest 8.4.2、ruff 0.12.0
- 安装：`pip install numpy pandas matplotlib openpyxl tabulate pytest ruff`（建议先在 venv 中安装，见 ph07）
- 运行 / 测试命令见「验收标准」各条
- 验证状态：已验证（`--demo` 离线链路、pytest 5 用例全过、ruff 零告警均在本环境实际执行通过）

`--demo` 实测输出（节选）：

```text
演示模式：生成模拟遥测 720 行（含 3 个缺失速度、2 个异常速度）
清洗后 718 行（剔除 2 行）

按车辆分组统计:
vehicle_id  trips  total_mileage  total_energy  avg_speed  energy_per_100km
      V001    239         118.78         20.15      59.54             16.96
      V002    239         119.81         21.36      59.85             17.83
      V003    240         113.23         19.77      58.55             17.46
```
