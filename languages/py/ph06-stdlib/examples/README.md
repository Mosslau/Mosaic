# examples —— 标准库阶段完整示例

> 每个示例是主文档 `06-stdlib.md` 第 6 章对应示例的完整可运行版。验证环境：Python 3.13.12，全部使用标准库，无第三方依赖。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-organize-files.py` | pathlib 批量整理文件：glob 遍历 + 正则提取日期 + 归档到子目录 + 统一加前缀 | `python3 ex01-organize-files.py` |
| `ex02-extract-log-fields.py` | 正则提取日志字段：命名分组 findall 提取时间/IP/错误码 + Counter 统计分布 | `python3 ex02-extract-log-fields.py` |
| `ex03-logging-config.py` | logging 模块化配置：控制台全级别 + RotatingFileHandler 按大小回滚 | `python3 ex03-logging-config.py` |
| `ex04-rename-tool.py` | argparse 命令行工具：`--dir`/`--ext`/`--prefix`/`--dry-run`，自动生成 `--help` | `python3 ex04-rename-tool.py --help` |
| `ex05-subprocess-call.py` | subprocess 调用外部命令：捕获输出、`check=True` 处理非零返回码、超时保护 | `python3 ex05-subprocess-call.py` |

说明：

- `ex04-rename-tool.py` 无参数时在临时目录演示「实际改名」与「`--dry-run`」两种模式；带参数时按命令行执行，如 `python3 ex04-rename-tool.py --dir /tmp/demo --ext .txt --prefix bak_`
- `ex03-logging-config.py` 把日志写入临时目录，日志级别 DEBUG 只进控制台、INFO 以上进文件（超 1KB 回滚保留 2 个备份）
- 全部示例在临时目录内生成/消费数据，运行后不残留文件

全部已在本环境用 python3（3.13.12）运行验证，输出与文件内注释期望值一致（已验证）。
