# ph12 阶段项目：BUS 日志批处理工具

> 对应 Roadmap（python.md）ph12「推荐项目」第二个「BUS 日志批处理工具」。解析 candump 风格 BUS 日志 → 按 ID 统计信号值 → 生成 CSV 报表 + 文本汇总；argparse 参数化、logging 审计、可安全重跑、输出可审计——四个必会概念在一个工具里全部落地，同时为 ph18 的平台日志解析打底。

## 需求

设备研发/运维场景里，BUS 总线日志（candump 导出）动辄几十 MB 纯文本，人工翻看效率极低。本工具把「读日志 → 按 ID 分组统计 → 出报表」固化成一条命令：解析 `(秒.微秒) 接口 ID#负载HEX` 格式的每一行，按 BUS ID 统计帧数与信号值（简化约定：**负载首字节即信号值**；带格式规约的深度日志解析属 [ph18 数据平台分析 / 自动化方向阶段](../../ph18-data-platform-automation/18-data-platform-automation.md)，roadmap 第 18 节，目录已建），支持按 ID 过滤，输出确定性覆盖写的 CSV 报表与带时间戳的文本汇总。

## 功能清单

- [x] 解析：正则逐行解析 candump 格式（空负载、大小写 ID、乱行容错），无效行单独计数
- [x] 统计：按 ID 分组——条数 / 首字节 min / max / avg（`round(..., 2)`），ID→信号名映射（0x123 运行速度、0x245 部件电压、0x301 电机温度）
- [x] 过滤：`--filter-id 0x123` 只统计指定 ID（其余 ID 不计入报表）
- [x] 报表：`bus_report.csv`（bus_id/信号/条数/min/max/avg）+ `summary.txt`（输入文件、生成时间、过滤条件、总帧数/无效行、逐 ID 明细）——**可审计**
- [x] 参数化：argparse CLI（`--input` / `--output-dir` / `--filter-id` / `--log-level` / `--log-file` / `--demo`）
- [x] 日志与错误处理：logging 到 stderr（可选 `--log-file` 落审计文件）；输入文件不存在返回退出码 2 并给友好提示
- [x] 安全重跑：报表内容确定性（仅 summary.txt 的生成时间随运行时刻变化），重复运行覆盖写、无副作用、不留多余文件
- [x] 离线演示：`--demo` 在临时目录生成确定性样本（12 有效帧 + 1 乱行）→ 全流程分析 → 自检断言 → 退出码 0
- [x] 测试：`tests/test_bus_log_tool.py` 覆盖解析/统计/过滤/报表内容/幂等/CLI（pytest 12 用例）
- [x] 质量：`pyproject.toml` 内置 ruff 配置，`ruff check . && pytest -q` 一键门禁（本环境实测：ruff 零告警、pytest 12 用例全过）

## 验收标准

- [ ] `python3 bus_log_tool.py --demo` 离线跑通：总帧数 `12`、无效行 `1`、3 个 ID 统计正确（0x123 运行速度 6 条 `[30, 60] avg 45.0`、0x245 部件电压 3 条 `[95, 112] avg 103.67`、0x301 电机温度 3 条 `[90, 110] avg 100.0`）、CSV 报表 `4` 行（含表头）、自检通过、退出码 0
- [ ] `pytest -q` 全部通过（12 用例，离线、不依赖网络与第三方库）；`ruff check .` 零告警
- [ ] `--filter-id 0x123` 只输出 0x123 一行统计（6 条）；输入文件不存在时退出码 2 且 stderr 有友好提示
- [ ] 报表文件只出现在 `--output-dir`（演示模式在系统临时目录），运行后 `git status` 工作区干净
- [ ] 能说清：正则解析为什么用「匹配整行 + 分组」而不是 `split()`（主文档 3.3/3.10）；报表确定性覆盖写为什么让脚本可安全重跑（主文档 3.9）；审计日志 + summary.txt 各承担什么可审计角色（主文档 3.9）

## 扩展方向（可选）

- **多字节信号 + 字节序**：负载首字节是简化约定，真实信号常跨字节（如 `int.from_bytes(data[2:4], "big")`），可扩展为按 (ID, 起始字节, 长度, 缩放) 配置的信号矩阵
- **接入 DBC 文件**：用 python-can / cantools 解析标准 DBC，信号定义从文件加载而非硬编码（本工具自身的延伸方向）
- **批量目录**：`--input` 支持目录时用 pathlib `rglob` 遍历（复用 ex01 的文件批处理思路），一个命令处理整个采集目录
- **定时 + 邮件**：配合 schedule（examples/ex06）定时跑，结果用 smtplib（examples/ex05）发日报——三个示例的合体
- **性能**：百万行级日志逐行 `read_text().splitlines()` 已可用，更大可换 `for line in f` 流式读取（主文档 3.3）

## 验证环境

- Python 3.13.9；核心零第三方依赖（标准库 `re`/`csv`/`argparse`/`logging`；测试：pytest 8.4.2、ruff 0.12.0）
- 安装：`pip install pytest ruff`（建议先在 venv 中安装，见 ph07）
- 运行：`python3 bus_log_tool.py --demo`；真实使用：`python3 bus_log_tool.py --input can.log --output-dir reports/ [--filter-id 0x123]`
- 测试：`pytest -q`；门禁：`ruff check . && pytest -q`
- 验证状态：已验证（`--demo` 退出码 0、pytest 12 用例全过、ruff 零告警、CLI 过滤与审计日志均在本环境实际执行通过）

`--demo` 实测输出（节选，样本与报表在系统临时目录）：

```text
样本: /var/folders/.../ph12-can-xxxxxx/sample-can.log
总帧数: 12 | 无效行: 1 | ID 类数: 3
  0x123 运行速度: 6 条 [30, 60] avg 45.0
  0x245 部件电压: 3 条 [95, 112] avg 103.67
  0x301 电机温度: 3 条 [90, 110] avg 100.0
报表: /var/folders/.../ph12-can-xxxxxx/reports/bus_report.csv（4 行，含表头）
自检通过：帧数 / 无效行 / 各 ID 统计 / 报表行数全部正确
```

CLI 实测输出（`--input sample.log --output-dir out/ --filter-id 0x123 --log-file out/audit.log`）：

```text
完成: 6 帧, 1 个 ID -> out/
# out/bus_report.csv
bus_id,信号,条数,min,max,avg
0x123,运行速度,6,30,60,45.0
# out/audit.log（每个动作一行，可审计）
2026-09-01 11:22:27 INFO 解析 sample.log -> 12 帧, 1 无效行
2026-09-01 11:22:27 INFO 按 ID 0x123 过滤 -> 6 帧
2026-09-01 11:22:27 INFO 报表已写入 out/（bus_report.csv + summary.txt）
```
