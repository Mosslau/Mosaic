# exercises —— C 语言未定义行为 UB 与常见坑阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。练习 2/5 分别对应 roadmap ph10「练习」小节的「用 ASan 检查越界和 use-after-free」「给字符串处理函数补边界检查」；练习 1/3/4 覆盖「有符号整数溢出」「未初始化变量」与必会概念「UB 可能在优化级别变化后暴露」（roadmap「收集 10 个常见 UB 示例并修复」由本阶段 project/ C 常见坑示例库整体落地）。参考实现在 `sol-*` 文件中，做完再看。

> ⚠️ 练习 1/2 的"坏版本复现"必须用 Sanitizer 编译运行（`-fsanitize=undefined -fno-sanitize-recover=all` / `-fsanitize=address`），**不要裸跑**坏版本——那是故意写错的 UB 代码。

## 练习 1：用 UBSan 复现并修复整数溢出（★）

- **目标**：写一个含 3 处整数类 UB 的程序（有符号溢出、`INT_MIN / -1`、`1 << 31`），用 UBSan 复现并逐个修复
- **要求**：
  - 坏版本：同一 `main` 里依次触发 3 处 UB，每处加行内注释说明"为什么这是 UB"
  - 用 `-fsanitize=undefined -fno-sanitize-recover=all` 编译运行，记录报告（注意：程序在第一个 UB 处中止，想看到 3 条报告要"逐个修复、逐个复现"或逐个注释）
  - 修复版：先判断再运算（加法用 `INT_MAX - 1` 边界检查或 `__builtin_add_overflow`；除法检查 `d == -1 && m == INT_MIN`；移位位数检查 + 改用无符号类型 `1u << n`）
- **验收**：坏版本 UBSan 报 `signed integer overflow`/`division of -2147483648 by -1`/`left shift of 1 by 31`；修复版 `cc -Wall -Wextra -std=c11` 零警告，加 UBSan 重跑**零报告**，退出码 0

## 练习 2：用 ASan 定位并修复越界与 use-after-free（★★）

- **目标**：写一个同时含"越界写"和"free 后访问（+重复 free）"的程序，用 ASan 复现、读懂报告、修复
- **要求**：
  - 坏版本：数组越界写 1 个元素 + `free(p)` 后读 `*p` + 再 `free(p)`，每处加注释
  - 用 `-fsanitize=address -g` 编译运行，记录报告中的**错误类型**与 **READ/WRITE 大小**（有 `-g` 的环境还应看到源码行号）
  - 修复版：索引先检查（`size_t` 与长度比较）；`free` 后立即置 `NULL`（解释为什么置 NULL 后"重复 free"也安全）
- **验收**：坏版本 ASan 报 `stack-buffer-overflow`（WRITE of size 4）与 `heap-use-after-free`（READ of size 4）；修复版零警告、ASan 重跑零报告、退出码 0

## 练习 3：定位并修复未初始化变量（★★）

- **目标**：写一个条件依赖未初始化局部变量的程序，用"编译期警告 + 运行时工具"两条路定位，再修复
- **要求**：
  - 坏版本：`int x; if (x > 0) ... else ...`，加注释说明"为什么读 x 是 UB（不确定值）"
  - 先用 `cc -Wall -Wextra -O1` 编译观察 `-Wuninitialized` 警告（编译器先于运行时发现）；再用 Valgrind 复现（本机没有就如实记录"未在本环境验证"，不要假装跑过）
  - 修复版：声明即初始化
- **验收**：坏版本触发 `-Wuninitialized` 警告；修复版零警告、输出稳定（`x = 0` 或等价）、退出码 0

## 练习 4：观察优化级别改变 UB 表现（★）

- **目标**：用 `-O0` 与 `-O2` 编译同一段溢出代码，对比两次输出，解释差异来源
- **要求**：
  - 用 `(a + 1) > a` 判 `INT_MAX` 的程序（参考 examples/ex06-opt-levels.c 的思路，自己重写一遍，别直接复制）
  - 分别用 `-O0` 和 `-O2` 编译运行，记录两个输出；再用 UBSan 编译，确认"两种输出都是 UB 的合法表现"
  - 用一段话解释：为什么优化级别能改变 UB 代码的输出（编译器对"无溢出"做了什么假设）
- **验收**：`-O0` 与 `-O2` 输出不同（本环境实测 0 vs 1）；UBSan 报告 `signed integer overflow`；能写出假设与折叠的解释

## 练习 5：给字符串处理函数补边界检查（★★）

- **目标**：把 ph03 手写的 `strcpy`/`strcat` 升级为带容量的字符串类型，超长输入截断而非溢出
- **要求**：
  - 定义 `sstr_t { char *buf; size_t cap; size_t len; }` 与 `sstr_init`/`sstr_copy`/`sstr_append`（参考 examples/ex05-safe-str.c，但自己写）
  - `sstr_copy` 返回"是否截断"（0=完整，1=截断）；`sstr_append` 先算剩余容量再写
  - 演示三次写入：一次完整、两次超长（覆盖 copy 与 append 两个路径），打印 `[内容] len cap 截断标志`
  - 用一句话说明 `strncpy` 与 `strncat` 的 `\0` 语义差异（必背点）
- **验收**：`cc -Wall -Wextra -std=c11` 零警告；加 `-fsanitize=address,undefined` 运行零报告；三次写入输出与注释预期一致，超长输入被截断、始终以 `\0` 结尾

> **提示**：练习 1/2/3 分别对应主文档 3.5/3.2+3.4/3.6 的知识，练习 4 对应 4.1/4.2，练习 5 对应 3.10——先独立完成，再对照 `sol-*` 复盘。所有 Sanitizer 报告请在 sol 文件注释里对照自己的实测输出。
