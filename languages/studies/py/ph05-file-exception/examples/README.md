# examples —— 文件操作与异常处理阶段完整示例

> 每个示例是主文档 `05-file-exception.md` 第 6 章对应示例的完整可运行版。验证环境：Python 3.13.12，全部使用标准库，无第三方依赖。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-read-config.py` | 读取设备配置文件：手动解析 INI + 四段式异常处理 | `python3 ex01-read-config.py` |
| `ex02-bus-log-csv.py` | BUS 日志 CSV 解析：`csv.DictReader` 按列名访问并筛选 | `python3 ex02-bus-log-csv.py` |
| `ex03-device-json.py` | 设备配置 JSON 读写：`json.dump`/`load` round-trip | `python3 ex03-device-json.py` |
| `ex04-diag-log.py` | 诊断日志分析：正则逐行解析 + 级别/部件统计 | `python3 ex04-diag-log.py` |
| `ex05-batch-rename.py` | 批量重命名：自定义异常 + `raise from` 保留异常链 | `python3 ex05-batch-rename.py` |

全部已在本环境用 python3（3.13.12）运行验证，输出与文件内注释期望值一致（已验证）。示例均在临时目录内生成/消费数据，运行后不残留文件。
