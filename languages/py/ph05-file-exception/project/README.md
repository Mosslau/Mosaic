# ph05 阶段项目：日志分析工具

> 对应 Roadmap（python.md）ph05「推荐项目」第一个「日志分析工具」。读取车联网诊断日志，统计级别分布、时间分布与错误 Top-N，输出文本报告，可选导出「部件 × 级别」交叉表 CSV。

## 需求

用标准库实现一个命令行日志分析工具 `log_analyzer.py`：读取诊断日志文件，逐行用正则解析出时间戳、级别、部件、消息；统计日志级别分布、按小时的时间分布、按部件的 ERROR Top-N，生成文本分析报告；可选把「部件 × 级别」交叉表导出为 CSV。仓库自带样例数据 `sample_logs.log`，可直接运行验证。

## 功能清单

- [x] 读日志文件：`python3 log_analyzer.py <日志文件>`，非日志行（注释/空行/表头）自动跳过
- [x] 统计日志级别分布（INFO / WARN / ERROR 计数）
- [x] 统计时间分布（按小时聚合）
- [x] 统计错误 Top-N：按部件统计 ERROR 次数，`--top N` 控制条数（默认 5）
- [x] 输出文本报告：默认打印到 stdout，`-o report.txt` 同时写入文件
- [x] 导出交叉表：`--csv level_stats.csv` 输出「部件 × 级别」计数 CSV（含 total 列）
- [x] 错误处理：文件缺失/读取失败时抛自定义异常 `LogParseError`（`raise ... from e` 保留根因），CLI 层转退出码 1

## 验收标准

- [ ] `python3 log_analyzer.py sample_logs.log` 输出报告：24 条有效记录；级别分布 INFO=11 / WARN=6 / ERROR=7；时间分布 08 时 9 条 / 09 时 10 条 / 10 时 5 条；ERROR Top 为 BMS-001=3、MCU-003=3、VCU-002=1
- [ ] `python3 log_analyzer.py sample_logs.log -o report.txt` 后 `report.txt` 内容与 stdout 一致
- [ ] `python3 log_analyzer.py sample_logs.log --csv level_stats.csv` 生成 CSV，表头为 `component,INFO,WARN,ERROR,total`
- [ ] `python3 log_analyzer.py nonexistent.log` 输出错误信息并返回退出码 1
- [ ] `python3 log_analyzer.py`（无参数）打印用法并返回退出码 2

## 扩展方向

- 支持日志轮转（多文件合并分析），对齐生产环境按天分片日志
- 用 `datetime`/`collections.deque` 做滑动窗口告警（属于 ph06 标准库阶段内容）
- 对接 ph08 第三方库（pandas）做时序趋势分析
- 输出 HTML 报告，为 ph09 数据分析阶段的图表展示打底

## 验证环境

- Python 3.13.12，仅标准库，无第三方依赖
- 运行：`python3 log_analyzer.py sample_logs.log`
- 验证状态：已验证
