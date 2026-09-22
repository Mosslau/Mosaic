# examples —— C 语言 Sanitizer / 静态分析 / 单元测试阶段完整示例

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64）。安全示例统一 `-Wall -Wextra -std=c11` 零警告；Sanitizer 演示按各自「运行前提」编译。全部输出为本机实测。

## 关于故意出错的代码

本阶段的主题之一就是"故意写错再让工具抓"——每个 Sanitizer 演示文件都在**文件首行注释**写明了运行前提。请严格遵守：

- **ex01（越界 / use-after-free）**：必须用 `-fsanitize=address` 编译运行，否则裸跑会破坏相邻内存或读已归还的内存，行为不可预测。
- **ex02（整数溢出 / 非法移位）**：必须用 `-fsanitize=undefined` 编译运行；不带的裸跑输出只是"碰巧回绕"的垃圾值，无意义。
- **ex03（数据竞争）**：`race` 模式必须用 `-fsanitize=thread` 编译运行；裸跑的 `counter` 最终值不确定。
- **ex04（泄漏）**：不崩溃、裸跑"看不出问题"——这正是泄漏必须靠工具的原因；检测方式按平台选（见文件头与下方表格）。
- **ex05（组合）**：`safe` 是正确代码；`badmem`/`badlogic` 是故意出错演示，必须用 `-fsanitize=address,undefined` 编译运行。
- **ex06（自测模式）**：正常工程代码，可任意编译运行。
- 部分演示文件编译时**故意触发**编译期警告（如 ex01 的 `-Warray-bounds`）——这也是教学点：编译器在编译期就能拦下一部分错误。它们不是"零警告代码"，请勿当作规范样板。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-asan.c` | ASan 抓地址错误：`./ex01 oob` 越界写（`stack-buffer-overflow`），`./ex01 uaf` free 后读取（`heap-use-after-free`，附分配/释放两段栈） | `cc -Wall -Wextra -std=c11 -fsanitize=address -g ex01-asan.c -o ex01`（oob 演示另触发 `-Warray-bounds` 警告） | `./ex01 oob` / `./ex01 uaf`（均被 ASan 中止） | 已验证：oob 报 `ERROR: AddressSanitizer: stack-buffer-overflow` + `WRITE of size 4`；uaf 报 `heap-use-after-free` + `READ of size 4` + `freed by`/`previously allocated by`；均退出码 134 |
| `ex02-ubsan.c` | UBSan 抓逻辑错误：有符号溢出 + 非法移位（`1 << 31`），默认报错后继续 | `cc -Wall -Wextra -std=c11 -fsanitize=undefined -g ex02-ubsan.c -o ex02`；中止形态加 `-fno-sanitize-recover=undefined` | `./ex02`（两条 `runtime error` 后继续打印，退出码 0） | 已验证：报 `signed integer overflow: 2147483647 + 1 ...` 与 `left shift of 1 by 31 places ...`；中止形态在第一处 SIGABRT、退出码 134 |
| `ex03-tsan.c` | TSan 抓数据竞争：两线程无锁自增共享变量；`./ex03 race` 坏版、`./ex03 fixed` 加锁修复版 | `cc -Wall -Wextra -std=c11 -fsanitize=thread -g ex03-tsan.c -o ex03` | `./ex03 race` / `./ex03 fixed` | 已验证：race 报 `WARNING: ThreadSanitizer: data race`（`Location is global 'counter'`）+ `SUMMARY`，退出码 134，最终值不确定（实测一次 102147）；fixed 输出 `counter = 200000`、零报告、退出码 0 |
| `ex04-leak.c` | 泄漏检测（跨平台对照）：分配 64 字节后从不释放 | `cc -Wall -Wextra -std=c11 -g ex04-leak.c -o ex04`（普通构建即可，泄漏检测不需插桩） | 按平台：Linux `-fsanitize=address` 构建直接跑（LSan）；macOS `leaks --atExit -- ./ex04`；Linux/Intel macOS `valgrind --leak-check=full ./ex04` | 已验证（macOS）：普通运行退出码 0 无报告；ASan 构建 + `ASAN_OPTIONS=detect_leaks=1` 报 `AddressSanitizer: detect_leaks is not supported on this platform.`；`leaks --atExit` 报 `1 leak for 80 total leaked bytes.`（80 含 malloc 开销）；Valgrind 未在本环境验证（Apple Silicon 官方不支持） |
| `ex05-combo.c` | ASan+UBSan 组合一次编译双查：`safe` 正确动态数组零报告；`badmem` 越界写；`badlogic` 有符号溢出 | `cc -Wall -Wextra -std=c11 -fsanitize=address,undefined -g ex05-combo.c -o ex05` | `./ex05 safe` / `./ex05 badmem` / `./ex05 badlogic` | 已验证：safe 输出 `v[99]=99 len=100` + 越界被拦截、退出码 0；badmem 报 `ERROR: AddressSanitizer: heap-buffer-overflow` + `WRITE of size 4`、退出码 134；badlogic 报 `runtime error: signed integer overflow` 后继续、退出码 0 |
| `ex06-selftest.c` | 自测模式单元测试：零依赖断言宏框架，对带边界检查的 byte buffer 写 6 组用例（边界输入 + 错误路径） | `cc -Wall -Wextra -std=c11 -O1 -g ex06-selftest.c -o ex06` | `./ex06`（全过则退出码 0；CI 用法 `./ex06 && echo OK`） | 已验证：`-Wall -Wextra` 零警告；输出 23 个 `[PASS]` + `自测通过: 23 个断言全部通过`、退出码 0；加 `-fsanitize=address,undefined -fno-sanitize-recover=all` 复跑同样零报告 |

## 说明

- 六个示例与主文档第 6 章示例 1~6 一一对应；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以本目录为准）。
- 所有运行产物（`ex01`~`ex06*` 可执行文件）一律写 /tmp 或构建临时目录，验证后清理，不入仓库。
- 本机 ASan/TSan 无法启动外部符号器（llvm-symbolizer spawn 失败 errno 9），栈帧未符号化，但错误类型、读写大小、调用关系与 `SUMMARY` 完整——这与 ph10 相同，属本环境已知现象。
- Valgrind 面向 Linux（macOS Apple Silicon 官方不支持，本机未安装，未在本环境验证）；cppcheck 本机未安装（未在本环境验证）；clang-tidy 为 Homebrew LLVM 21.1.8（`/opt/homebrew/opt/llvm/bin/clang-tidy`），已在主文档 3.6 演示。
- 静态分析（cppcheck/clang-tidy）与单元测试框架（Unity/CMocka/Criterion）的工具级内容在主文档第 3 章；本目录聚焦"能编译能运行"的 Sanitizer 与自测模式示例。
