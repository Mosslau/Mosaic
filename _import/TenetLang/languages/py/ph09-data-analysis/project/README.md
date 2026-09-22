# ph09 阶段项目：平台指标分析脚本

> 对应 Roadmap（python.md）ph09「推荐项目」第一个「平台指标分析脚本」。读取平台指标 CSV → 清洗（缺失/物理量程/重复）→ 按服务实例分组统计（延迟、CPU、内存峰值、磁盘温度、功率）→ 折线趋势 + 柱状对比图 → 导出 Excel/Markdown 报表。指标口径与 ph18「全阶段指标口径」一致。

## 需求

实现一个命令行平台指标分析工具：输入一份平台指标 CSV（列：`ts, service_id, latency_ms, cpu_pct, mem_used_gb, disk_temp_c, net_io_mb_s, power_w`），清洗缺失延迟与物理量程越界值、去重，按服务实例分组统计（样本数、平均/峰值延迟、平均 CPU、内存峰值与利用率、磁盘温度峰值、平均功率），产出折线趋势图 + 柱状对比图，并导出 Excel（多 Sheet）与 Markdown 摘要报告。要求解析/清洗/统计/导出为纯函数（可离线测试），CLI 支持 `--demo` 模式用内置模拟数据离线演示完整链路。

## 功能清单

- [x] 取数：`generate_demo_data()` 内置模拟数据（3 个服务实例 × 240 行，含 3 个缺失延迟 + 2 个越界延迟）；`load_metrics(path)` 读 CSV（`dtype` 保 service_id 字符串、`parse_dates` 解析 ts、校验列齐全）
- [x] 清洗：`clean(df)` —— 缺失值组内中位数填充 → 按常量表 `RANGES` 逐列物理量程过滤 → 去重 → 重置索引（复制语义，不改入参，呼应主文档 4.3）
- [x] 统计：`analyze(df)` —— 按服务实例分组：samples / avg_latency_ms / max_latency_ms / avg_cpu_pct / max_mem_used_gb / max_disk_temp_c / avg_power_w / mem_peak_pct
- [x] 图表：`make_charts(df, outdir)` —— 各实例延迟趋势折线（5 分钟均值降采样）+ 各实例平均延迟柱状对比，Agg 后端 `savefig`
- [x] 导出：`export_report(stats, df, outdir)` —— Excel 多 Sheet（汇总 + 清洗后数据）+ Markdown 报告（`to_markdown`）
- [x] CLI：argparse 支持 `--demo` / `--input` / `-o` 输出目录（默认系统临时目录）
- [x] 测试：`tests/test_metrics.py` 离线覆盖清洗/统计/导出/CLI 演示（pytest 5 用例）
- [x] 质量：`pyproject.toml` 内置 ruff 配置（line-length 100），`ruff check . && ruff format --check . && pytest -q` 一键门禁

## 验收标准

- [ ] `python3 metrics_analyzer.py --demo` 离线跑通：打印清洗前后行数（剔除数与注入的越界值一致）与按实例统计表，写出图表与报告
- [ ] `python3 metrics_analyzer.py --input metrics.csv -o out/` 跑通：统计表与产物齐全
- [ ] 数据含缺失延迟时被组内中位数填充，含 >2000 ms 的越界延迟时被剔除（`clean()` 的断言）
- [ ] `python3 -m pytest tests -q` 全部通过（离线，不依赖网络）
- [ ] `ruff check .` 与 `ruff format --check .` 零告警
- [ ] 说清为什么清洗/统计要设计成纯函数（可离线测试、与 CLI/文件 IO 解耦）

## 扩展方向（可选）

- 报表加时序维度：`pivot_table` 出「服务实例 × 日期」的延迟/请求量透视，`resample("1h")` 出每小时汇总（主文档 3.7）
- 图表加箱线图/直方图看每实例延迟分布，或按 `disk_temp_c > 75` 标出过热段（主文档 3.8，深入见 ph15 AI/ML 的分布分析）
- 把分析结果暴露成 HTTP 接口（主文档 5 使用场景 → ph10 Web 后端阶段；ph18 的 platdash 是完整形态）
- 数据量大时用 `chunksize` 分块读取 + 逐块聚合（主文档 4.4）；超内存换 polars/数据库（ph11）

## 验证环境

- Python 3.13.9；依赖：numpy 2.3.5、pandas 2.3.3、matplotlib 3.10.6、openpyxl 3.1.5、tabulate 0.9.0、pytest 8.4.2、ruff 0.12.0
- 安装：`pip install numpy pandas matplotlib openpyxl tabulate pytest ruff`（建议先在 venv 中安装，见 ph07）
- 运行 / 测试命令见「验收标准」各条
- 验证状态：已验证（`--demo` 离线链路、pytest 5 用例全过、ruff check/format 零告警均在本环境实际执行通过）

`--demo` 实测输出（节选）：

```text
演示模式：生成平台指标 720 行（含 3 个缺失延迟、2 个越界延迟）
清洗后 718 行（剔除 2 行）

按服务实例分组统计:
service_id  samples  avg_latency_ms  max_latency_ms  avg_cpu_pct  max_mem_used_gb  max_disk_temp_c  avg_power_w  mem_peak_pct
      S001      239           64.63           99.97        72.16           111.30            44.36       318.85         43.48
      S002      239           66.85          102.97        72.73           117.14            44.63       334.69         45.76
      S003      240           71.93          100.66        76.12           120.89            45.69       354.71         47.22
```
