# ph06 阶段项目：批量重命名工具

> 对应 Roadmap（python.md）ph06「推荐项目」第一个「批量重命名工具」。用 pathlib + argparse + logging 实现可配置的批量重命名工具，支持扩展名过滤、前缀/后缀、正则匹配、递归目录与 `--dry-run` 预览，输出统计报告。

## 需求

用标准库实现命令行工具 `rename_tool.py`：遍历目标目录（可递归），按扩展名与正则过滤出要处理的文件，统一加前缀/后缀重命名；支持 `--dry-run` 预览、冲突检测（目标已存在则跳过）、logging 分级日志与统计报告。仓库源码自带样例文件生成（`--make-samples`）与自测（`--selftest`），开箱即验。

## 功能清单

- [x] 目录参数：位置参数 `dir`（默认 `.`），非目录时报错并退出码 1
- [x] 扩展名过滤：`--ext .log`（未带 `.` 自动补全，默认 `.log`）
- [x] 前缀/后缀：`--prefix` / `--suffix`（后缀插在扩展名前，如 `a.txt` + `_bak` → `a_bak.txt`）
- [x] 正则匹配：`--pattern` 用 `re.search` 按文件名过滤（如 `--pattern "^can_"`）
- [x] 递归目录：`--recursive`/`-r`（`rglob` 遍历子目录）
- [x] dry-run：`--dry-run` 只预览不实际改名
- [x] 冲突检测：目标文件已存在时跳过并告警，不覆盖
- [x] 兜底移动：`Path.rename` 失败（如跨设备）时 `shutil.move` 兜底
- [x] 统计报告：logging 输出「计划 / 已改名 / 冲突跳过 / 其他跳过」四维统计
- [x] 样例生成：`--make-samples <DIR>` 生成含嵌套子目录的样例文件
- [x] 自测：`--selftest` 在临时目录断言 dry-run 不变、实际改名、冲突跳过

## 验收标准

- [ ] `python3 rename_tool.py --selftest` 输出「自测全部通过」（dry-run 计划 6 个不落地 → 实际改名 6 个 → 冲突跳过 1 个）
- [ ] `python3 rename_tool.py --make-samples demo` 后 `demo/` 出现 7 个样例文件（含 `archive/2024-06-01/` 嵌套目录）
- [ ] `python3 rename_tool.py demo --ext .log --prefix bak_ --pattern "can_" -r --dry-run` 只预览 3 个 `can_*` 文件，`demo/` 内容不变
- [ ] 去掉 `--dry-run` 实际执行后，6 个 `.log` 全部变为 `bak_*.log`（含嵌套目录 1 个），统计报告「已改名 6 个」
- [ ] `python3 rename_tool.py nonexistent_dir` 输出「目录不存在」并返回退出码 1
- [ ] `python3 rename_tool.py --help` 显示全部参数与说明

## 扩展方向

- 冲突时自动追加序号（`a.txt` → `a_1.txt` → `a_2.txt`）而不是跳过
- 按日期归档：解析文件名中的日期移动到 `archive/YYYY-MM-DD/`（主文档示例 1 的主题）
- 多规则重命名：支持从 JSON 配置文件读入批量规则（结合 `json` 序列化）
- 日志输出到文件：用 `RotatingFileHandler` 记录操作审计（结合示例 3）

## 验证环境

- Python 3.13.12，仅标准库（argparse/pathlib/shutil/re/logging），无第三方依赖
- 运行：`python3 rename_tool.py --selftest` / `python3 rename_tool.py --make-samples demo` / `python3 rename_tool.py demo --prefix bak_ --dry-run`
- 验证状态：已验证
