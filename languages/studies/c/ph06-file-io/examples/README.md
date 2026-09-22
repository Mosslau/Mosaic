# examples —— 文件操作阶段完整示例

验证环境：Apple clang 17（gcc 兼容），编译命令统一 `gcc -Wall -Wextra -std=c99`。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-line-stats.c` | 文本逐行读取与统计（fgets + strtok + ferror） | `gcc -Wall -Wextra -std=c99 ex01-line-stats.c -o ex01-line-stats` | `./ex01-line-stats sample.txt` |
| `ex02-csv-parser.c` | CSV 解析：字段校验/跳过坏行/统计有效记录 | `gcc -Wall -Wextra -std=c99 ex02-csv-parser.c -o ex02-csv-parser` | `./ex02-csv-parser students.csv` |
| `ex03-config-reader.c` | 配置文件 key=value：注释/两种 = 写法/容忍坏行 | `gcc -Wall -Wextra -std=c99 ex03-config-reader.c -o ex03-config-reader` | `./ex03-config-reader app.conf` |
| `ex04-bin-record.c` | 二进制读写结构体：定长字段/短读写检查 | `gcc -Wall -Wextra -std=c99 ex04-bin-record.c -o ex04-bin-record` | `./ex04-bin-record` |
| `ex05-append-log.c` | append-only 日志：时间戳 + 追加 + fflush | `gcc -Wall -Wextra -std=c99 ex05-append-log.c -o ex05-append-log` | `./ex05-append-log` |

## 样例数据（输入文件，保留在仓库）

| 文件 | 用途 | 内容 |
|------|------|------|
| `students.csv` | ex02 输入 | 含空行、多余列、数字错误、名字超长——演示跳过逻辑 |
| `app.conf` | ex03 输入 | 含注释、空行、`key = value`/`key=value` 两种写法、错误行 |
| `sample.txt` | ex01 输入 | 普通文本（README 下方直接 `printf` 生成，或复用 students.csv） |

## 运行产物（验证后清理，不入仓库）

- `records.bin`（ex04 生成）、`app.log`（ex05 生成）——验证后 `rm` 清理

五个示例均已在 Apple clang 17（gcc 兼容）下编译零警告并运行验证（已验证）。
