# 阶段项目：多模块命令行工具 —— 文件统计工具

对应 roadmap ph07 推荐项目第一个「多模块命令行工具」。拆成 io/parse/report 三模块，Makefile 构建，验证增量构建与 GDB 调试能力。

## 需求

- `io.c`/`io.h` —— 文件读取：打开、逐行读、关闭、错误处理
- `parse.c`/`parse.h` —— 行解析：统计行数/单词/字符（复用 ph06 的 strtok 思路）
- `report.c`/`report.h` —— 结果输出：格式化打印统计（行/词/字符/最长行）
- `main.c` —— 命令行入口：支持 `-v`（verbose 输出每个文件明细）+ 多个文件参数
- `Makefile` —— 管理全部模块构建（增量构建生效）

## 功能清单

| 功能 | 说明 |
|------|------|
| 多模块 | io/parse/report 三分层，`.h` 只暴露必要接口 |
| 多文件 | 支持一次统计多个文件（逐个处理 + 汇总） |
| 增量构建 | Makefile 依赖正确，改一个 `.c` 只重编它 |
| GDB 验证 | 用 `gdb ./app` 断点验证 parse 边界（超长行截断） |
| 零警告 | `-Wall -Wextra -std=c11` 编译零警告 |

## 验收标准

- [ ] `make` 构建成功、`./app file1.txt file2.txt` 正确输出统计
- [ ] `touch io.c && make` 只重编 io.o（增量构建生效）
- [ ] `./app missing.txt` 优雅报错（perror + 跳过，不中断其他文件）
- [ ] `-Wall -Wextra -std=c11` 编译零警告
- [ ] 用 `gdb ./app` 断点验证 parse 处理超长行

## 扩展方向

- 加 `-r` 递归统计目录（用 `readdir`，为 ph08 系统编程打底）
- 加 `-o report.txt` 输出到文件（复用 ph06 文件写）
- 加 `--json` 输出 JSON 格式（结构化数据的严谨编码，为 ph16 存储引擎的记录格式/校验打底）

## 验证环境

- Apple clang 17（gcc 兼容），`-Wall -Wextra -std=c11`
- 构建：`make`
- 运行：`./app main.c` / `./app -v main.c io.c`
- 验证状态：已验证
