# exercises —— C 语言 Sanitizer / 静态分析 / 单元测试阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。五题与 roadmap ph11「练习」的对齐：练习 1 对应「用 ASan 修复越界问题」，练习 4 对应「给动态数组库写单元测试」（自测模式版），练习 5 对应「生成覆盖率报告」；练习 2/3 覆盖学习内容 UBSan 与 TSan（衔接 ph08 线程的并发检测）；roadmap「用 cppcheck 检查一个项目」由主文档 3.6 与使用场景表给出命令与判读方法（本机未安装 cppcheck，未在本环境验证，建议在 Linux/CI 环境完成）。参考实现在 `sol-*` 文件中，做完再看。

> ⚠️ 练习 1/2/3 的"坏版本复现"必须用对应 Sanitizer 编译运行（`-fsanitize=address` / `-fsanitize=undefined` / `-fsanitize=thread`），**不要裸跑**坏版本——那是故意写错的代码（越界会破坏相邻内存、数据竞争结果不确定）。

## 练习 1：用 ASan 复现并修复越界（★）

- **目标**：写一个含越界写的程序，用 ASan 复现、读懂报告、修复，验证"修复后报告消失"
- **要求**：
  - 坏版本：`int arr[3] = {1,2,3}; arr[3] = 100;`，加行内注释说明"为什么这是 UB"
  - 用 `-fsanitize=address -g` 编译运行，记录报告中的**错误类型**与 **READ/WRITE 大小**（`-g` 才有行号）
  - 修复版：把裸下标访问收进"带边界检查的接口"（越界请求返回 -1），并演示一个被拦截的越界请求
- **验收**：坏版本 ASan 报 `stack-buffer-overflow`（`WRITE of size 4`，退出码 134）；修复版 `cc -Wall -Wextra -std=c11` 零警告、加 `-fsanitize=address` 重跑**零报告**、退出码 0

## 练习 2：用 UBSan 复现并修复整数类 UB（★）

- **目标**：写一个含 3 处整数 UB 的程序（有符号溢出、`INT_MIN / -1`、`1 << 31`），用 UBSan 复现并逐个修复
- **要求**：
  - 坏版本：同一 `main` 里依次触发 3 处 UB，每处加注释说明"为什么是 UB"
  - 用 `-fsanitize=undefined` 编译运行记录报告（默认报错后继续，3 条都能看到）；再用 `-fno-sanitize-recover=undefined` 确认中止形态（第一个错误处 SIGABRT、退出码 134）
  - 修复版：加法先判断或用 `__builtin_add_overflow`；除法检查 `d == -1 && m == INT_MIN`；移位位数检查 + 位运算改用无符号类型
- **验收**：坏版本报 `signed integer overflow` / `division of -2147483648 by -1` / `left shift of 1 by 31` 三条；修复版零警告、加 `-fsanitize=undefined` 重跑**零报告**、退出码 0

## 练习 3：用 TSan 检测并修复数据竞争（★★）

- **目标**：写一个两线程无锁自增共享变量的程序，用 TSan 复现数据竞争、加锁修复、复跑零报告
- **要求**：
  - 坏版本：两个线程各自 `for (i < 100000) counter++;`（`counter` 是全局变量），加注释说明"为什么这是数据竞争"
  - 用 `-fsanitize=thread -g` 编译运行，记录报告的 `WARNING` 与 `Location`（指向哪个全局变量）与最终 `counter` 值（竞争下不确定）
  - 修复版：用 `pthread_mutex_t` 串行化自增，解释为什么加锁后 `counter` 稳定为 200000
- **验收**：坏版本报 `WARNING: ThreadSanitizer: data race`、退出码 134；修复版零报告、输出 `counter = 200000`、退出码 0

## 练习 4：给函数写自测模式单元测试（★★）

- **目标**：用"断言宏 + 计数器"的自测模式（零依赖，参考 examples/ex06-selftest.c 思路但自己写）给两个函数写测试，覆盖边界输入与错误路径
- **要求**：
  - 被测函数：`is_leap(y)`（闰年判断，4 个分支）与 `check_len(len, max)`（长度校验，错误路径返回 -1）
  - 测试覆盖：`is_leap(2000/1900/2024/2023/1600/1700)` 六种输入走全部 4 个分支；`check_len` 的正常/等于上限/超上限/空 record
  - 自测壳：`CHECK(cond)` 宏统计 PASS/FAIL，`main` 返回 `failures == 0 ? 0 : 1`（可进 CI）
  - 反证：把 `is_leap` 的 `y % 400 == 0` 改成 `y % 400 != 0` 重编译，确认测试能抓住回归
- **验收**：`cc -Wall -Wextra -std=c11 -O1` 零警告；全过时退出码 0；故意引入 bug 后至少一个用例 `[FAIL]`、退出码非 0；加 `-fsanitize=address,undefined` 复跑零报告

## 练习 5：生成覆盖率报告并补测（★★★）

- **目标**：写一个含"从不调用的函数"与"未触发的错误分支"的程序，用 gcov 生成报告、读懂 `#####` 与 `taken 0%`、补测到 100%
- **要求**：
  - 源码：`is_leap` + `check_len(len, max)`（错误路径 `len > max` 返回 -1）+ `report_corrupt()`（**不要写 `static`**——未调用的 static 函数会被编译器剔除、不参与覆盖统计）
  - 第一版只走合法路径：`./程序` 后 `gcov` 记录行/分支覆盖，找出 `#####` 行与 `taken 0%` 分支（macOS 的 `.gcda` 名带可执行名前缀，如 `sol05-sol-05-coverage.gcda`；Linux 直接是源码名）
  - 补测版：触发错误分支（`check_len(20, 16)`）并调用 `report_corrupt()`，用 `gcov -b` 确认行覆盖与 `taken at least once` 都到 100%
- **验收**：第一版行覆盖 < 100% 且报告里有 `#####` 与 `taken 0%`；补测后 `Lines executed` / `Branches executed` / `Taken at least once` 全部 100%（本机实测 72.73% → 100%）

> **提示**：练习 1/2/3 对应主文档 3.1~3.4 的知识与实测报告，练习 4 对应 3.7 与 examples/ex06，练习 5 对应 3.8 与 examples/ex05 的补测思路——先独立完成，再对照 `sol-*` 复盘。所有 Sanitizer 报告请在 sol 文件注释里对照自己的实测输出。
