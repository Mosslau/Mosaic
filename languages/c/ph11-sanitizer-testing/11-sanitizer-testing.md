# C 语言 Sanitizer / 静态分析 / 单元测试阶段

> 面向系统底层、存储引擎方向，本阶段把"会写 C"升级为"能证明 C 代码质量"——用动态检测、静态分析与单元测试组成质量工具链，把运行时事故挡在发布之前。

## 1. 概述

Sanitizer / 静态分析 / 单元测试阶段是 C 学习路线中"从定位错误到系统性防错"的工程化转折点。目标：**建立 C 代码质量工具链，减少运行时事故**——ph10 把 ASan/UBSan/Valgrind 当"定位工具"临时使用，并留下"工具的系统化工程化使用留给 ph11"的伏笔；本阶段接住它：把 Sanitizer 写进构建配置与 CI 流程，补上静态分析（cppcheck/clang-tidy）与单元测试（自测模式与 Unity/CMocka/Criterion），再用 gcov/lcov 把"测了多少"变成可度量的报告。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 动态检测（地址类） | ASan 的构建选项、报告解读（错误类型 / READ·WRITE / 调用栈） |
| 动态检测（逻辑类） | UBSan 的 recover 与中止两种形态、报告解读 |
| 动态检测（并发类） | TSan 检测数据竞争（工具级使用，衔接 ph08 线程） |
| 动态检测（泄漏类） | LSan（Linux）、macOS leaks、Valgrind 的泄漏分类 |
| 静态分析 | cppcheck、clang-tidy 的检查类别与集成方式 |
| 单元测试 | 自测模式（断言宏）与 Unity/CMocka/Criterion 框架选型 |
| 覆盖率 | gcov/lcov 的计数插桩原理、报告解读与门槛设定 |
| 工程化 | Sanitizer 构建配置、make test 一键运行、CI 集成 |

本阶段承接 ph10：ph10 建立了"识别 10 类 UB + 用 Sanitizer 复现定位"的认知，示例里工具只是临时命令；本阶段把工具变成构建配置的一部分（`-fsanitize` 写进脚本而非每次手敲）、把测试变成代码的一部分（自测模式 / test 目录 + 断言框架）、把覆盖变成可度量的事实（gcov/lcov 报告），并给出"动态检测与静态分析互补"的选型逻辑。

这个阶段只涉及 Sanitizer（ASan/UBSan/TSan/LSan）的系统化使用、静态分析（cppcheck/clang-tidy）、单元测试（自测模式与 Unity/CMocka/Criterion）与覆盖率（gcov/lcov）及其构建与 CI 集成，**不涉及字节序与二进制格式的位级处理（ph12，roadmap 第 12 节）、mmap、Page Cache 与可靠文件 IO（ph13，roadmap 第 13 节）和跨语言互操作 ABI（ph14，roadmap 第 14 节，目录待建）** — 那些是 ph12 字节序、内存对齐与二进制格式解析阶段、ph13 mmap、Page Cache 与可靠文件 IO 阶段和 ph14 C 与 C++ / Python / Rust 互操作阶段的内容；并发部分 TSan 只做检测工具介绍，**锁设计与内存序分析不属于本阶段**（衔接 ph08 线程，深入分析属并发专题）。

## 2. 来源与演变

**质量工具链的两条主线：错误发现前置化、质量从度量开始**。早期 C 工程靠"发布后崩溃再修"，成本随系统变大而失控；工具链的演进本质是把错误发现不断左移——从运行期事故，到测试期报告，再到编译期警告。2002 年 **Valgrind** 用动态二进制插桩实现了"不需要重编译"的内存检查；2011 年 Google 开源 **AddressSanitizer（ASan）**，把开销从 Valgrind 的 20~50 倍压到约 2 倍，使内存检测能常驻每次构建与 CI——这是本阶段一切工程化的前提。同年 LLVM 启动 **ThreadSanitizer（TSan）** 原型，2013 年起随 LLVM 发布，把数据竞争检测同样压到约 5~15 倍开销、可进 CI；**LeakSanitizer（LSan）** 作为 ASan 的泄漏检测组件内建（仅 Linux 支持，macOS 上实测不可用，见 3.4）。

**静态分析走的是另一条路：不运行代码也能查**。1990 年代的 lint 用正则规则扫描源码，误报多；2009 年的 **cppcheck** 做源码级路径模拟，2016 年前后 **clang-tidy** 直接复用编译器前端 AST，把静态分析从"独立小工具"并入编译器生态。**测试与覆盖同源演进**：**gcov** 随 GCC 提供计数插桩；**Unity**（2007）、**CMocka 1.0**（2015）、**Criterion**（2015）先后把 C 单元测试从"自造断言宏"规范成框架；**lcov** 把 gcov 的文本报告汇总成 HTML，覆盖率才具备"CI 门禁"的形态。

| 时间 | 事件 | 对质量工具链的意义 |
|------|------|------------------|
| 1990s | gcov 随 GCC 提供计数插桩 | 最早的行覆盖率度量 |
| 2002 | Valgrind 发布 | 无需重编译的内存错误检测 |
| 2007 | Unity 发布 | C 单测从自造断言走向轻量框架 |
| 2009 | cppcheck 发布 | 开源 C/C++ 静态分析主流化 |
| 2011 | Google 开源 ASan；LLVM 启动 TSan 原型 | ~2x 开销，Sanitizer 可常驻开发与 CI；并发检测走向工程化 |
| 2012~2013 | UBSan 随 Clang 发布（GCC 4.9 跟进）；TSan 随 LLVM 发布 | 溢出/除零/移位等逻辑型 UB 的廉价检测；数据竞争检测可进 CI |
| 2015 | CMocka 1.0、Criterion 发布 | 带 mock 与参数化的现代测试框架 |
| 2016+ | clang-tidy 成熟 | 静态分析并入编译器生态 |

ph10 埋下的"Sanitizer 与调试工具链（ASan/UBSan/TSan 的使用）"伏笔，在此兑现为可复用的工程流程：**Sanitizer 负责每次改动，静态分析负责定期全量，单元测试负责行为回归，覆盖率负责暴露测试盲区**。

本文示例以 **C11** 为基线（C99 之后、C23 普及之前，GCC/Clang/MSVC 支持度最一致的公共子集；Sanitizer 的 `-fsanitize=` 系列选项自 2013 年起在 GCC/Clang 间保持一致，与 C 标准版本无关）。验证工具链：**Apple clang 21.0.0（`cc`，macOS arm64）+ Homebrew LLVM 21.1.8（`clang-tidy`，路径 `/opt/homebrew/opt/llvm/bin/clang-tidy`）**；gcov 为 Apple 自带 `/usr/bin/gcov`；cppcheck 与 Valgrind 本机未安装（Valgrind 官方不支持 macOS Apple Silicon），涉及两者的表述已如实标注。本阶段演示的 Sanitizer 行为与报告格式是工具链工程中最稳定的部分——`-fsanitize=address,undefined` 的组合写法与报告关键行（`ERROR: AddressSanitizer: ...`、`runtime error: ...`、`WARNING: ThreadSanitizer: ...`）多年不变，本阶段讲的内容短期内不会过时。

## 3. 语法与参数

### 3.1 ASan：地址类错误的运行时检测

**动态检测（Dynamic Analysis）** 是在"带检测代码的运行"中发现问题：编译器或运行时给程序加上检查逻辑，出错时打印报告。ASan（AddressSanitizer）管**地址类**错误——越界、use-after-free、double free、泄漏。启用方式 `-fsanitize=address`，典型开销约 2 倍时间，**需要重编译**。

| 工具 | 启用方式 | 检测对象 | 典型开销 | 需重编译 |
|------|---------|---------|---------|---------|
| ASan | `-fsanitize=address -g` | 越界、use-after-free、double free | ~2x 时间 | 是 |
| UBSan | `-fsanitize=undefined -g` | 有符号溢出、除零、非法移位、未对齐访问 | 几个百分点 | 是 |
| 组合 | `-fsanitize=address,undefined -g` | 两者叠加 | ~2x 时间 | 是 |
| TSan | `-fsanitize=thread -g` | 数据竞争（与 ASan 互斥，见 3.3） | 5~15x 时间 | 是 |
| Valgrind | `valgrind ./app` | 未初始化读、越界、泄漏 | 20~50x | 否 |

**报告三要素（阶段验收"能解释 ASan 报告中的栈信息"）**——以 `examples/ex01-asan.c` 的 oob 模式实测报告为例：

```text
ERROR: AddressSanitizer: stack-buffer-overflow on address 0x... at pc ... bp ... sp ...
WRITE of size 4 at 0x... thread T0
SUMMARY: AddressSanitizer: stack-buffer-overflow (...) in demo_oob+0x...
```

- **错误类型**：`stack-buffer-overflow` 说明对象在**栈**上（`arr` 是局部数组）；堆对象报 `heap-buffer-overflow`；`heap-use-after-free` 说明"释放后使用"；
- **操作**：`WRITE of size 4` 是写越界（读则显示 `READ`），`size 4` 对应 `int` 宽度；
- **位置**：`in demo_oob+0x...` 定位到出错的函数——完整报告里 `#0/#1` 栈帧逐层给出调用链，use-after-free 额外有 `freed by` 与 `previously allocated by` 两段栈（分配/释放位置对照，见示例 1）。

**要点**：`-g` 必须有（行号依赖调试信息，本机 ASan 的 llvm-symbolizer spawn 失败 errno 9、栈帧未符号化，但错误类型/读写大小/函数名完整，与 ph10 相同属本环境已知现象）；库与主程序要**统一**加开关（插桩与运行时链接须一致）；`ASAN_OPTIONS=abort_on_error=1` 可让 ASan 报错即中止（默认已中止）。

### 3.2 UBSan：逻辑型 UB 的廉价检测

UBSan（UndefinedBehaviorSanitizer）管**逻辑类**错误——有符号溢出、除零、非法移位、未对齐访问、空指针解引用。开销只有几个百分点，可以常驻所有构建。与 ASan 的分工：**ASan 管"地址对不对"，UBSan 管"运算本身合不合法"**——两者组合一次编译双管齐下（见 3.5）。

UBSan 默认**报错后继续**（recover 形态）：`examples/ex02-ubsan.c` 实测输出两条 `runtime error` 后仍打印 `b`/`s`、退出码 0：

```text
ex02-ubsan.c:18:15: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ex02-ubsan.c:18:15
ex02-ubsan.c:21:15: runtime error: left shift of 1 by 31 places cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ex02-ubsan.c:21:15
b = -2147483648
s = -2147483648
```

要让它中止（CI 里"报错即失败"），编译加 `-fno-sanitize-recover=undefined` 或运行时 `UBSAN_OPTIONS=halt_on_error=1`——本机实测中止形态退出码 134（SIGABRT），只在第一处错误中止。**修复思路**沿用 ph10 3.5：先判断再运算、`__builtin_add_overflow`、移位位数检查 + 位运算用无符号类型（exercises 练习 2 的完整闭环）。

### 3.3 TSan：数据竞争检测（工具级使用）

TSan（ThreadSanitizer，`-fsanitize=thread`）检测**数据竞争**：两个线程无锁访问同一内存、且至少一个是写、且两次访问之间没有 happens-before 关系。它是同一套 Sanitizer 思路在并发域的延伸（衔接 ph08 线程），开销 5~15 倍，适合开发与 CI 的并发模块。

`examples/ex03-tsan.c` 的 race 模式实测报告：

```text
WARNING: ThreadSanitizer: data race (pid=...)
  Location is global 'counter' at 0x... (ex03+0x...)
SUMMARY: ThreadSanitizer: data race (...) in worker_race+0x64
ThreadSanitizer: reported 1 warnings
```

- `WARNING: ThreadSanitizer: data race` 是竞争判定；`Location is global 'counter'` 指出被竞争的变量；
- `in worker_race+0x...` 给出参与竞争的函数；完整报告还列出两个线程各自的调用栈（谁在写、谁在读）；
- 竞争下 `counter` 最终值不确定（本机实测一次 102147），这是 UB 的表现；
- **修复→复跑闭环**：加互斥锁后（`fixed` 模式）零报告、稳定输出 `counter = 200000`、退出码 0——"检测→修复→复跑零报告"是本阶段对并发模块的标准流程。

**要点**：TSan **与 ASan 互斥**——`-fsanitize=address,thread` 编译直接被拒绝（实测 `clang: error: invalid argument '-fsanitize=address' not allowed with '-fsanitize=thread'`）；与 UBSan 可组合（实测 `-fsanitize=thread,undefined` 编译运行正常）。本阶段只把 TSan 当检测工具用，**锁设计与内存序分析不属于本阶段**（那是并发专题的内容），这里只需会用、能读报告、能验证修复。

### 3.4 LSan 与跨平台泄漏检测（macOS 局限实测）

泄漏（allocated 后 unreachable）ASan 不直接报——它由 **LeakSanitizer（LSan）** 检测，而 LSan 是 ASan 的一部分但**仅 Linux 支持**。本机（macOS）实测：ASan 构建 + `ASAN_OPTIONS=detect_leaks=1` 运行 `examples/ex04-leak.c`（故意泄漏 64 字节）：

```text
==96885==AddressSanitizer: detect_leaks is not supported on this platform.
```

即 macOS 上 LSan 不可用。**跨平台对照**（同一个"分配后不释放"的程序）：

| 平台/工具 | 命令 | 实测/预期报告 |
|----------|------|--------------|
| Linux LSan | `-fsanitize=address` 构建后直接运行 | `Direct leak of 64 byte(s) in 1 object(s)`（未在本环境验证，LSan 为 Linux 专属） |
| macOS leaks | `leaks --atExit -- ./ex04` | 实测 `Process ...: 1 leak for 80 total leaked bytes.`（80 含 malloc 开销） |
| Linux/Intel macOS Valgrind | `valgrind --leak-check=full ./ex04` | `64 bytes in 1 blocks are definitely lost`（本机无 Valgrind，未在本环境验证） |

**要点**：泄漏**不崩溃**、裸跑"看不出问题"——这正是它必须靠工具的原因；macOS 开发者的日常选择是系统自带 `leaks`（依赖 MallocStackLogging，`--atExit` 模式在进程退出时扫描）；Valgrind 不需要重编译、适合接手没有 Sanitizer 构建的旧代码，但 20~50 倍开销只适合定期深挖，且官方不支持 macOS Apple Silicon。

### 3.5 Sanitizer 组合与构建选项

**组合开关是日常默认形态**（roadmap 示例）：

```bash
cc -fsanitize=address,undefined -g main.c -o app
./app
```

一次编译 ASan（地址类）+ UBSan（逻辑类）双查。TSan 单独构建（与 ASan 互斥，见 3.3）。常用运行时环境变量：

| 变量 | 取值 | 效果 |
|------|------|------|
| `ASAN_OPTIONS` | `abort_on_error=1` | ASan 报错即中止（默认已中止）；`detect_leaks=1` 仅 Linux 有效 |
| `UBSAN_OPTIONS` | `halt_on_error=1` | UBSan 从"报错后继续"变"报错即中止"（等价于编译期 `-fno-sanitize-recover=undefined`） |
| `TSAN_OPTIONS` | `halt_on_error=1` | TSan 报错即中止 |

**优化级别**：Sanitizer 构建建议 `-O1`（`-O0` 可能让部分 UB 不暴露，`-O2` 的行号映射变差，ph10 4.2 已铺垫）；但**复现/演示** UB 用 `-O0` 更稳——`-O1` 下 clang 可能把被测试的内存访问常量折叠/死代码消除，ASan 因此漏报（ph10 project/ 的实测结论）。两类现象作用于**不同的 UB/代码路径**，并不矛盾：`-O1` 以上优化可能把"被测的越界访问"常量折叠或死代码消除、ASan 漏报——这类"优化消掉 UB"的漏报用 `-O0` 复现更稳；反向的另一类问题（如未初始化行为只在优化后的指令布局下显现）则 `-O0` 看不到——CI 构建取 `-O1` 正是为了贴近发布行为、多查这一类（与 ph10 3.6 同一口径）。发布构建**不带** `-fsanitize`：约 2 倍时间与内存开销、依赖 Sanitizer 运行时、且 ASan 会改变内存布局与分配器行为（可能掩盖或改变某些时序问题）。

### 3.6 静态分析：cppcheck 与 clang-tidy

**静态分析（Static Analysis）** 不运行程序，直接在源码或编译器 AST 上扫描全部路径。它与编译器警告（`-Wall`/`-Wextra`）的关系：警告只覆盖"当前翻译单元、可达路径"，静态分析能跨文件、能模拟未执行的分支——但它会**误报**，告警需要人工判定。

```bash
cppcheck --enable=all --inconclusive --std=c11 src/          # 源码级路径模拟
clang-tidy src/*.c -checks='clang-analyzer-*,bugprone-*' -- -Iinclude   # 编译器前端 AST
```

| 工具 | 原理 | 典型检查 | 误报倾向 |
|------|------|---------|---------|
| cppcheck | 源码解析 + 路径模拟 | 空指针解引用、越界、未初始化、资源泄漏 | 中（`--inconclusive` 是额外启用"不确定结论"检查，输出更多而非减少） |
| clang-tidy | 编译器前端 AST | 与编译器同源，规则可自定义（clang-analyzer/bugprone 等组） | 低（基于真实语义） |

本机实测 clang-tidy（Homebrew LLVM 21.1.8）对"整数除法赋给 double"的典型输出：

```text
tidy_demo.c:3:12: warning: result of integer division used in a floating point
        context; possible loss of precision [bugprone-integer-division]
```

**要点**：静态分析适合**定期全量扫描**（评审前、发版前），动态检测适合**每次改动**（开发循环、CI）；两者互补的机制见 4.6。clang 编译器本身也内建静态能力——`examples/ex01-asan.c` 的越界代码在编译期就被 `-Warray-bounds` 警告（本机实测），**先听编译器的，再上工具**。本机未安装 cppcheck（未在本环境验证其输出，命令与判读方法如上）。

### 3.7 单元测试：框架选型与自测模式

**单元测试（Unit Testing）** 把每个函数当作可独立验证的单元：给定输入，断言输出与副作用符合预期。C 的主流框架都是"断言宏 + 测试注册 + 运行器"的结构，区别在重量级与附加能力。

| 框架 | 特点 | 断言风格 | mock 支持 | 依赖 |
|------|------|---------|----------|------|
| Unity | 单文件框架（unity.c/h），极轻量 | `TEST_ASSERT_EQUAL_INT` 等宏 | 无（可配 CMock） | 仅 C 编译器（需下载 unity.c/h） |
| CMocka | 来自 Google，带 mock 与组测试 | `assert_int_equal` 等函数 | 内置 mock | libcmocka |
| Criterion | 现代风格，fixture/参数化 | `cr_assert` 宏 | 部分 | libcriterion |

三个框架都要下载/安装依赖，**本机未在本环境验证**（命令与骨架见各框架文档）。本阶段的可运行示例走**自测模式**（`examples/ex06-selftest.c`）：零依赖，4 行断言宏 + 一个计数器就够——

```c
#define CHECK(cond) do {                                          \
    if (cond) { g_passes++; printf("[PASS] %s\n", #cond); }       \
    else { g_failures++; printf("[FAIL] %s\n", #cond); }          \
} while (0)
```

`main` 返回 `g_failures == 0 ? 0 : 1`，退出码即测试结果——**可进 CI**（`./ex06 && echo OK`）。**要点**：setUp/tearDown 或"每次用例自建自毁"保证用例互不污染；测试文件与源码分离（`test/` 目录）；**测试必须能一键运行**（阶段验收第一项）——`make test` 或 CI 里的同一行命令；框架选型上，纯 C 数据结构库用 Unity 最省事，需要模拟外部依赖（如文件 IO）时选 CMocka，需要参数化用例时选 Criterion——"自测模式"永远是零依赖的兜底。

### 3.8 覆盖率：gcov / lcov

**覆盖率（Coverage）** 回答"测试跑过哪些代码"。gcov 在编译期给每个基本块插入计数器（`--coverage` = `-fprofile-arcs -ftest-coverage`），运行后把计数导出，lcov 再汇总成报告。roadmap 必会概念"单元测试应覆盖边界输入和错误路径"在这里变成可量化的事实：**没跑到的行和分支就是没测的路径**。

```bash
cc --coverage -g app.c -o app        # 1. 编译期插入计数
./app                                # 2. 运行, 退出时写 .gcda
gcov app.gcda                        # 3. 生成 app.c.gcov 文本报告（macOS 的 .gcda 名带可执行名前缀）
gcov -b app.gcda                     # 4. 加 -b 看分支
lcov --capture --directory . --output-file coverage.info   # 5. 汇总
genhtml coverage.info --output-directory html              # 6. HTML 报告
```

| 文件/命令 | 内容 | 生成时机 |
|----------|------|---------|
| `.gcno` | 静态插桩图（哪些行有计数） | 编译时 |
| `.gcda` | 运行时执行计数 | 程序退出时写入 |
| `.gcov` | 每行执行次数，未执行行标记 `#####` | `gcov` 命令 |
| `coverage.info` / `html/` | 汇总报告（函数/行/分支三级） | `lcov` / `genhtml` |

本机实测（exercises 练习 5 的 `sol-05-coverage.c`，Apple clang 21.0.0 + Apple gcov）：第一版只走合法路径 → `Lines executed:72.73% of 22`、`Taken at least once:70.00% of 10`，报告里 `report_corrupt` 的行是 `#####`、`check_len` 的错误分支是 `taken 0%`；补测版（触发错误分支 + 调用 `report_corrupt`）→ 三项全部 100%。**要点**：覆盖率是**测试质量的度量而非目标**——100% 行覆盖 ≠ 无 bug，但"错误分支 taken 0%"能直接暴露测试盲区；行覆盖只看"这行跑没跑过"，**分支覆盖**（`gcov -b`）才看"每个分支取没取过"，错误路径的验证必须看分支；插桩有性能开销，覆盖率用单独构建而非发布构建；macOS 的 `.gcda` 名带可执行名前缀（`sol05-sol-05-coverage.gcda`），Linux gcc 直接是源码名（`sol-05-coverage.gcda`）。

### 3.9 把工具固化进构建与 CI

工具要"常驻"而不是"想起来才用"，必须固化进构建系统。一个工程至少三套配置：**Debug**（`-O0 -g`，调试）、**Sanitizer**（`-O1 -g -fsanitize=address,undefined`，开发与 CI）、**Release**（`-O2`，发布）。本阶段 project/ 的 Makefile 就是样板（`make test` / `make asan` / `make coverage` / `make check`）：

```makefile
# Makefile 片段: 一键测试 + Sanitizer 测试（完整版见 project/Makefile）
SANFLAGS = -fsanitize=address,undefined -fno-sanitize-recover=all
test:
	./test_buffer
asan:
	cc -Wall -Wextra -std=c11 -O1 -g $(SANFLAGS) buffer.c test_buffer.c -o test_buffer_asan
	./test_buffer_asan
```

```cmake
# CMakeLists.txt 片段: 单独的 Sanitizer 构建开关
option(ENABLE_SANITIZERS "Build with ASan/UBSan" OFF)
if(ENABLE_SANITIZERS)
  add_compile_options(-fsanitize=address,undefined -g -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
```

**要点（roadmap 必会概念"Sanitizer 适合开发和 CI，不一定适合生产发布"）**：发布版不带 `-fsanitize`（见 3.5 开销与副作用）；开发与 CI 则**必须**带——CI 至少安排一个 job 用 ASan+UBSan 构建并跑完全部测试，**泄漏在 CI 里视为失败**；**"内存错误越早发现越便宜"**（roadmap 必会概念）——编译期警告 < CI 报告 < 线上事故，成本差一个数量级以上，这也是"先听编译器的，再上工具，最后靠流程"的分层逻辑。

## 4. 底层原理

### 4.1 ASan：shadow memory 与 redzone

ASan 由三部分组成：**编译期插桩**、**替换的 malloc/free**、**shadow memory 映射**。编译器在每个 load/store 前插入"查 shadow"的代码；每个栈/堆/全局对象四周铺设 **redzone（红区）**——带特殊标记的守卫字节；malloc/free 被替换成带记录的版本：记录每块内存的地址、大小与调用栈，`free` 后内存进入 **quarantine（延迟回收区）**，期间再访问即判定 use-after-free。

**shadow memory** 是 ASan 的核心机制：每 8 字节用户内存对应 1 字节 shadow（地址 = 用户地址 >> 3 + 固定偏移）。shadow 为 0 表示"8 字节全部可寻址"，非 0 表示"偏移量或红区标记"。一次越界访问命中红区 shadow 值，立即中止并打印报告（下图为 `examples/ex01-asan.c` 报告里 shadow 字节区的示意：`f1/f3` 是栈红区、`04` 是"该 8 字节粒内前 4 字节可寻址"的部分可寻址标记）：

```text
用户内存: [arr[0]|arr[1]|arr[2]|  REDZONE... ]   ← int arr[3] 共 12 字节
shadow  : [    00    |  04   |   f3... ]        ← 每 8 用户字节对应 1 shadow 字节
写 arr[3] → 命中第 2 粒的 poison 半区(shadow=04) → 立即报错并打印调用栈

示意 shadow 行（栈上 arr 附近的一段 shadow 字节区, f1/f3 是红区守卫）:
  f1 f1 f1 f1  00  04  f3 f3
  ├─ 左红区 ─┤            ├右红区┤
  00: 第 1 粒整粒可寻址（arr[0]/arr[1]）
  04: 第 2 粒前 4 字节可寻址（arr[2]）, 后 4 字节为 poison —— 越界写 arr[3]
      命中的正是这一半, ASan 据此报 stack-buffer-overflow
```

### 4.2 UBSan：编译期插桩

UBSan 是**纯编译期插桩**：编译器在可疑运算（有符号加减乘、除零、移位、对齐等）前插入 `__ubsan_handle_*` 检查函数，触发时打印 `runtime error: ...` 与源码位置。它不做 shadow memory，因此开销只有几个百分点，可以常驻所有构建。默认**报错后继续**执行；`-fno-sanitize-recover=undefined` 把检查从"打印"改成"abort"。注意编译器优化可能提前消除部分 UB 代码（ph10 4.1 的"无 UB 假设"），UBSan 的检查要在优化前提插好，所以 Sanitizer 构建用 `-O1` 而不是 `-O0` 更贴近发布行为（演示复现则相反，见 3.5）。

### 4.3 TSan：shadow memory 与 happens-before

TSan 的核心是**向量时钟 + shadow memory**：每条线程维护一个向量时钟（vector clock）记录"我已知的各线程时间"，每个内存单元有 shadow 槽记录"最近一次访问它的线程与时钟"。运行时判定规则：若两次访问同一地址（至少一次是写）**没有 happens-before 关系**，即数据竞争。happens-before 边来自：互斥锁的 acquire/release、线程创建与汇合（pthread_create/join）、原子操作、信号量等——TSan 拦截这些同步原语自动建立偏序。开销 5~15 倍主要来自时钟更新与 shadow 读写。

### 4.4 泄漏检测：LSan / Valgrind DBI / macOS leaks

**LSan** 是 ASan 的泄漏组件：维护"存活分配集"，进程退出时从根（全局/栈/寄存器可达的内存）做可达性扫描，**不可达的分配即泄漏**，报告里给出分配调用栈。它只在 Linux 可用（macOS 实测报 `detect_leaks is not supported on this platform.`，见 3.4）。**Valgrind** 采用**动态二进制插桩（DBI）**：不修改源程序，运行时把二进制翻译成中间表示（IR），逐条指令插桩后再执行；Memcheck 用 shadow 位记录每个字节"已定义/未定义"，泄漏在退出时把未释放块分成 **definitely lost / possibly lost / still reachable** 三类（`definitely lost` 必须修）。**macOS leaks** 依赖 `MallocStackLogging` 记录每次分配的调用栈，`--atExit` 在进程退出时对照扫描——三者机制不同（编译期插桩 / 运行时翻译 / 系统 malloc 钩子），共同点是"退出时做可达性分析"。

### 4.5 gcov：计数插桩

gcov 是**计数插桩（count instrumentation）**：编译期在每个基本块入口插入计数器并写出插桩图 `.gcno`；程序运行退出时把计数写进 `.gcda`；`gcov` 读取两者，按行输出执行次数（未执行行标 `#####`），`gcov -b` 额外输出分支比例。**行覆盖率** = 执行过的行 / 可执行行；**分支覆盖率** = 至少取过一次的分支 / 全部分支。lcov/genhtml 把这些文本汇总成按函数、行着色的 HTML 报告，覆盖率门槛（如"核心模块行覆盖 ≥ 80%"）才能在 CI 里自动卡关。

### 4.6 动态检测与静态分析为什么互补

roadmap 必会概念"**动态检测和静态分析互补**"：动态检测只在**运行经过的路径**上检查，准确但覆盖不全——没人触发的路径永远不会被查；静态分析扫描**全部代码路径**，全面但有误报，且看不到运行时值。两者是"深度"与"广度"的组合。

| 维度 | 动态检测（ASan/UBSan/TSan/Valgrind） | 静态分析（cppcheck/clang-tidy） |
|------|-------------------------------|-------------------------------|
| 检查范围 | 只查运行经过的路径 | 扫描全部代码路径 |
| 是否需要运行 | 需要 | 不需要 |
| 准确度 | 高（真实执行） | 有误报，需人工判定 |
| 发现的问题 | 内存错误、UB、数据竞争（带运行时值） | 空指针、越界、资源泄漏、可移植性/风格 |
| 开销 | 2~50x 时间 | 编译期/定期扫描 |
| 适合时机 | 每次改动、CI | 定期全量、评审前 |

组合拳：**动态检测保"走过的路没问题"，静态分析保"没走过的路没大坑"**。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| CI 质量门禁 | ASan/UBSan 构建、make test 一键运行、覆盖率阈值、cppcheck 检查（3.9） |
| 动态数组/buffer 库开发 | 边界输入单测、扩容失败路径、ASan 验证（示例 5/6，project/ 全流程） |
| 存储引擎与 WAL/buffer | record 编解码单测、截断/长度非法等错误路径、泄漏检测（示例 4，project/） |
| 遗留代码接手 | Valgrind 免重编译查泄漏、cppcheck 摸底、clang-tidy 补规则（3.4/3.6） |
| 数据结构与算法练习 | 自测模式单测 + gcov 覆盖率，用报告找未测分支（示例 6，练习 4/5） |
| 多线程模块 | TSan 检测数据竞争（衔接 ph08 线程；检测→修复→复跑闭环，示例 3） |
| 跨平台发布 | LSan（Linux）/ leaks（macOS）/ Valgrind 三选一的泄漏检测对照（3.4） |

**不适合**此阶段的事项：

- 字节序与二进制格式的位级处理（ph12 字节序、内存对齐与二进制格式解析阶段（roadmap 第 12 节）：大端/小端、varint、length-prefix frame、checksum）
- mmap、Page Cache 与可靠文件 IO（ph13 mmap、Page Cache 与可靠文件 IO 阶段（roadmap 第 13 节）：fsync、刷盘边界、崩溃恢复）
- 跨语言互操作 ABI（ph14 C 与 C++ / Python / Rust 互操作阶段（roadmap 第 14 节，目录待建）：C ABI、FFI、opaque pointer）
- 并发模型与内存序设计（本阶段 TSan 只做检测工具介绍，锁策略与 happens-before 分析不展开）
- 性能剖析与优化（perf/火焰图属于"找慢"而非"找错"，目的不同）

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令与验证状态见其 README）。**关于故意出错的代码**：示例 1~5 的"坏模式"是故意写错的演示，必须按各文件**首行注释的运行前提**用对应 Sanitizer 编译运行（`-fsanitize=address` / `-fsanitize=undefined` / `-fsanitize=thread` / 组合），裸跑有崩溃/数据损坏风险或输出无意义；示例 6 是正常工程代码，可任意编译运行。以下所有实测输出来自 Apple clang 21.0.0（macOS arm64）；本机 ASan/TSan 无法启动外部符号器（errno 9），栈帧未符号化但错误类型/读写大小/函数名完整。

### 示例 1：ASan 抓越界与 use-after-free

对应 roadmap 练习"用 ASan 修复越界问题"与学习内容 AddressSanitizer。

> 运行前提：必须用 `-fsanitize=address` 编译运行，否则勿运行。

```c
// examples/ex01-asan.c —— ASan 抓两类地址错误（UB 演示，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static void demo_oob(void) {
    int arr[3] = {1, 2, 3};
    printf("arr[0]=%d\n", arr[0]);
    arr[3] = 100;          /* 故意越界写 1 个元素 */
    printf("写完了(到不了这行)\n");
}

static void demo_uaf(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) return;
    *p = 7;
    free(p);
    printf("%d\n", *p);    /* 故意在 free 后读取 */
    free(p);               /* 故意 double free（第一个错误已中止, 到不了这里） */
}
```

```bash
# 1. 编译（必须带 -fsanitize=address; oob 演示另触发 -Warray-bounds 警告）
cc -Wall -Wextra -std=c11 -fsanitize=address -g examples/ex01-asan.c -o ex01
# 2. 运行（用 argv 选模式: oob 或 uaf）
./ex01 oob
./ex01 uaf
```

实测报告关键行（oob 模式）：

```text
ERROR: AddressSanitizer: stack-buffer-overflow on address ... at pc ... bp ... sp ...
WRITE of size 4 at ... thread T0
SUMMARY: AddressSanitizer: stack-buffer-overflow (...) in demo_oob+0x...
```

uaf 模式的关键行——与越界报告的最大区别是多了两段栈，**分配/释放位置对照**即可确认完整链条：

```text
ERROR: AddressSanitizer: heap-use-after-free on address ... at pc ...
READ of size 4 at ... thread T0
freed by thread T0 here:                ← free 的位置
previously allocated by thread T0 here: ← malloc 的位置
SUMMARY: AddressSanitizer: heap-use-after-free (...) in demo_uaf+0x...
```

解读：`stack-buffer-overflow` 说明对象在栈上（`arr` 是局部数组），堆对象报 `heap-buffer-overflow`；`WRITE/READ of size 4` 说明读写宽度；UAF 的 `freed by` 与 `previously allocated by` 两段栈对照分配/释放位置（ph10 示例 3 已见过，本阶段重点是把它变成门禁——CI 里出现即失败）。本机编译时 clang 还直接给出 `-Warray-bounds` 警告——**编译器已内建静态越界检测**，ASan 负责它抓不到的（use-after-free、运行时计算出的越界）。修复方式（free 后置 NULL、所有权文档化、索引先检查）已在 ph10 3.4 给出，exercises 练习 1 走完整闭环。

### 示例 2：UBSan 抓整数溢出与非法移位

对应 roadmap 学习内容 UndefinedBehaviorSanitizer 与 ph10 3.5 的溢出修复练习。

> 运行前提：必须用 `-fsanitize=undefined` 编译运行，否则勿运行（裸跑的 b/s 只是"碰巧回绕"的垃圾值）。

```c
// examples/ex02-ubsan.c —— UBSan 抓逻辑型 UB（UB 演示，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
#include <limits.h>
#include <stdio.h>

int main(void) {
    int a = INT_MAX;
    int b = a + 1;        /* 故意有符号溢出 */
    printf("b = %d\n", b);

    int s = 1 << 31;      /* 故意非法移位: 位数 == int 位宽 */
    printf("s = %d\n", s);
    return 0;
}
```

```bash
# 1. 编译（默认形态: 报错后继续）
cc -Wall -Wextra -std=c11 -fsanitize=undefined -g examples/ex02-ubsan.c -o ex02
# 2. 运行
./ex02
# 3. 中止形态（CI 里"报错即失败"靠它）
cc -Wall -Wextra -std=c11 -fsanitize=undefined -fno-sanitize-recover=undefined -g examples/ex02-ubsan.c -o ex02halt && ./ex02halt
```

实测输出（默认形态，两条 `runtime error` 后程序继续、退出码 0）：

```text
ex02-ubsan.c:18:15: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ex02-ubsan.c:18:15
ex02-ubsan.c:21:15: runtime error: left shift of 1 by 31 places cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ex02-ubsan.c:21:15
b = -2147483648
s = -2147483648
```

中止形态实测：第一个错误处 SIGABRT、退出码 134，`b`/`s` 不再打印。修复练习沿用 ph10 3.5：`__builtin_add_overflow`、除法前检查 `d == -1 && m == INT_MIN`、移位位数先检查（exercises 练习 2）。

### 示例 3：TSan 抓数据竞争（含修复闭环）

对应学习内容 TSan（衔接 ph08 线程）与练习 3 的"检测→修复→复跑"。

> 运行前提：必须用 `-fsanitize=thread` 编译运行，否则勿运行（race 模式裸跑的 counter 最终值不确定）。

```c
// examples/ex03-tsan.c —— TSan 抓数据竞争（UB 演示 + 修复闭环，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int counter = 0;                    /* 两个线程共享的全局变量 */
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;

/* 坏版本: 无锁自增 —— counter++ 是读-改-写三步, 两线程并发执行即竞争 */
static void *worker_race(void *arg) {
    (void)arg;
    for (int i = 0; i < NITER; i++)
        counter++;
    return NULL;
}
```

```bash
# 1. 编译（必须带 -fsanitize=thread; TSan 与 ASan 互斥, 单独构建）
cc -Wall -Wextra -std=c11 -fsanitize=thread -g examples/ex03-tsan.c -o ex03
# 2. 运行（race 坏版 / fixed 加锁修复版）
./ex03 race
./ex03 fixed
```

实测报告关键行（race 模式，退出码 134）：

```text
WARNING: ThreadSanitizer: data race (pid=...)
  Location is global 'counter' at ... (ex03+0x...)
SUMMARY: ThreadSanitizer: data race (...) in worker_race+0x64
ThreadSanitizer: reported 1 warnings
```

实测 fixed 模式：零报告、稳定输出 `counter = 200000 (加锁后稳定)`、退出码 0——**加锁后复跑零报告，闭环完成**。竞争下 `counter` 最终值不确定（实测一次 102147），这正是"数据竞争是 UB"的运行时表现。

### 示例 4：泄漏检测（LSan / leaks / Valgrind 三选一）

对应 roadmap 学习内容 Valgrind 与 ph04 的"用 Valgrind 检查内存问题"。价值：泄漏不崩溃，**必须靠工具**；且 Valgrind 不需要重编译，任何没开 Sanitizer 的构建都能直接查。

> 运行前提：这是"故意泄漏"的演示——裸跑看不出问题（不崩溃），"看不出问题"正是泄漏要工具才能发现的原因。

```c
// examples/ex04-leak.c —— 泄漏检测（故意泄漏演示，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 检测命令见下方命令块
int main(void) {
    int *p = malloc(16 * sizeof(int));   /* 64 字节: 分配后从不释放 */
    if (p == NULL) return 1;
    p[0] = 1;
    printf("p[0]=%d (程序正常退出, 但 64 字节泄漏)\n", p[0]);
    return 0;                            /* 没有 free(p) */
}
```

```bash
# 1. 普通构建（泄漏检测不需要编译期插桩）
cc -Wall -Wextra -std=c11 -g examples/ex04-leak.c -o ex04
# 2. macOS: 用系统自带 leaks（实测报告见下）
leaks --atExit -- ./ex04
# 3. Linux: ASan 构建后直接运行, 内建 LSan 退出时报告
cc -Wall -Wextra -std=c11 -fsanitize=address -g examples/ex04-leak.c -o ex04asan && ./ex04asan
# 4. Linux/Intel macOS: Valgrind（本机 Apple Silicon 官方不支持, 未在本环境验证）
valgrind --leak-check=full ./ex04
```

本机（macOS）实测：

```text
# macOS: LSan 不可用
==96885==AddressSanitizer: detect_leaks is not supported on this platform.
# macOS: leaks 可用
Process 96527: 189 nodes malloced for 32 KB
Process 96527: 1 leak for 80 total leaked bytes.
```

解读：macOS 上 ASan 内建 LSan 不可用（实测报错如上），改用系统自带 `leaks --atExit`（报 1 leak，80 字节含 malloc 开销）；Linux 上 LSan 随 ASan 构建自动启用，报 `Direct leak of 64 byte(s)`；Valgrind 报 `definitely lost`（必须修，另有 `possibly lost`/`still reachable` 两类）——本机无 Valgrind，后两者未在本环境验证。

### 示例 5：ASan+UBSan 组合一次编译双查

对应 roadmap 示例（组合开关是日常默认形态）与练习 4 的 CI 标准组合：**测试证明行为正确，Sanitizer 证明内存无错**。

> 运行前提：三个模式都要用 `-fsanitize=address,undefined` 编译运行；`badmem`/`badlogic` 是故意出错演示，裸跑无意义。

```c
// examples/ex05-combo.c —— ASan+UBSan 组合（safe 安全示例 + 两个坏模式，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int vec_push(IntVec *v, int val) {
    if (v == NULL) return -1;
    if (v->len == v->cap) {                    /* 满了: 2 倍扩容 */
        if (v->cap > SIZE_MAX / 2) return -1;  /* 扩容溢出防护(防御性) */
        size_t new_cap = v->cap * 2;
        int *tmp = realloc(v->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;            /* 扩容失败: 原数据不丢 */
        v->data = tmp;
        v->cap = new_cap;
    }
    v->data[v->len++] = val;
    return 0;
}

static int vec_get(const IntVec *v, size_t idx, int *out) {
    if (v == NULL || out == NULL) return -1;
    if (idx >= v->len) return -1;              /* 边界检查: 越界返回 -1 */
    *out = v->data[idx];
    return 0;
}
```

```bash
# 1. 编译（一次编译 ASan + UBSan 双查）
cc -Wall -Wextra -std=c11 -fsanitize=address,undefined -g examples/ex05-combo.c -o ex05
# 2. 运行（safe 正确代码 / badmem 越界写 / badlogic 有符号溢出）
./ex05 safe
./ex05 badmem
./ex05 badlogic
```

实测输出（safe 模式，退出码 0、零报告）：

```text
v[99]=99 len=100 (组合 Sanitizer 零报告)
v[100] 越界被拦截
```

badmem 模式实测（ASan 抓堆越界写，退出码 134）：

```text
ERROR: AddressSanitizer: heap-buffer-overflow on address ... at pc ... bp ... sp ...
WRITE of size 4 at ... thread T0
SUMMARY: AddressSanitizer: heap-buffer-overflow (...) in demo_badmem+0x...
```

badlogic 模式实测（UBSan 抓逻辑错误；默认 recover 报错后继续、退出码 0，加 `-fno-sanitize-recover=undefined` 则中止）：

```text
ex05-combo.c:92:15: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ex05-combo.c:92:15
b = -2147483648
```

解读：同一个构建开关下，地址类（`heap-buffer-overflow`）与逻辑类（`signed integer overflow`）都能被抓到——`-fsanitize=address,undefined` 就是 CI 的标准组合；`safe` 模式零报告证明**正确代码不会误报**，这正是"Sanitizer 构建跑测试"能作为门禁的前提。

### 示例 6：自测模式单元测试

对应 roadmap 练习"给动态数组库写单元测试"与必会概念"单元测试应覆盖边界输入和错误路径"。零依赖的自测模式（断言宏 + 计数器）对带边界检查的 byte buffer 写 6 组用例：空 buffer、边界内取值、扩容后边界、越界（`idx == len` 与远界）、NULL 参数、追加到需要多次翻倍扩容。

> 运行前提：无（正常工程代码，可任意编译运行；建议再加 `-fsanitize` 复跑）。

```c
// examples/ex06-selftest.c —— 自测模式单元测试（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int g_failures = 0;
#define CHECK(cond) do {                                                   \
    if (cond) {                                                            \
        printf("[PASS] %s\n", #cond);                                      \
    } else {                                                               \
        g_failures++;                                                      \
        printf("[FAIL] %s  (%s:%d)\n", #cond, __FILE__, __LINE__);         \
    }                                                                      \
} while (0)

static void test_out_of_bounds_returns_error(void) {
    Buf b;
    CHECK(buf_init(&b, 4) == 0);
    CHECK(buf_append(&b, "xy", 2) == 0);
    unsigned char c = 0;
    CHECK(buf_get(&b, 2, &c) == -1);           /* 越界: idx == len */
    CHECK(buf_get(&b, 100, &c) == -1);         /* 越界: 远界 */
    buf_destroy(&b);
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 -O1 -g examples/ex06-selftest.c -o ex06
# 2. 运行（CI 用法: ./ex06 && echo "测试通过"）
./ex06
# 3. Sanitizer 复跑（组合构建零报告 = 行为正确 + 内存无错）
cc -Wall -Wextra -std=c11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all examples/ex06-selftest.c -o ex06san && ./ex06san
```

实测输出（尾行；完整输出 23 个 `[PASS]`）：

```text
[PASS] buf_get(&b, 2, &c) == -1
[PASS] buf_get(&b, 100, &c) == -1
...
自测通过: 23 个断言全部通过 (退出码 0 = CI 通过)
```

解读：错误路径（越界请求）在这里是**可断言的行为**（返回 -1）而不是 UB——测试的价值在于把"会错"变成"可验证"；退出码即测试结果，`make test`/CI 一条命令复现。验证练习：故意把 `buf_get` 里的 `idx >= b->len` 改成 `idx > b->len`（留 off-by-one），越界用例应失败并定位到 `test_out_of_bounds_returns_error`——**测试能抓住回归**。补测练习（对应练习 5）：对本文件跑 `--coverage` + `gcov -b`，找出 `#####` 行与 taken 0% 的分支并补用例，覆盖率的用途是**指引补测**，不是数字本身。

## 7. 总结

### 关键要点

1. **动态检测和静态分析互补**（roadmap 必会概念）：动态只查走过的路径、零误报；静态扫全部路径、有误报——组合使用，动态进 CI、静态定期全量
2. **Sanitizer 适合开发和 CI，不一定适合生产发布**（roadmap 必会概念）：约 2x 开销 + 运行时依赖 + 内存布局改变；发布版不带，开发/CI 必须带，泄漏在 CI 视为失败
3. **单元测试应覆盖边界输入和错误路径**（roadmap 必会概念）：空 buffer、恰好填满、`idx == len` 与远界、NULL 参数、扩容失败——每个错误路径一个用例
4. **内存错误越早发现越便宜**（roadmap 必会概念）：编译期警告 < CI 报告 < 线上事故，成本差一个数量级以上
5. **ASan 报告三要素**（阶段验收）：错误类型（stack/heap-buffer-overflow、heap-use-after-free）、`READ/WRITE of size N`、调用栈；UAF 另有分配/释放两段栈
6. **UBSan 管运算合法性，ASan 管地址合法性**：`-fsanitize=address,undefined` 一次编译两样都查；UBSan 默认报错后继续，`-fno-sanitize-recover` 转中止
7. **TSan 抓数据竞争，与 ASan 互斥**：`WARNING: ThreadSanitizer: data race` + `Location` + 两线程栈；修复后复跑零报告才是闭环；锁设计与内存序不属本阶段
8. **泄漏必须靠工具**：不崩溃、裸跑看不出问题；Linux 用 LSan、macOS 用 `leaks --atExit`（LSan 实测不可用）、旧代码用 Valgrind（`definitely lost` 必须修）
9. **覆盖率是度量不是目标**：100% 行覆盖 ≠ 无 bug；用 `gcov -b` 的分支覆盖盯错误路径，用报告里的 `#####` 与 taken 0% 指引补测
10. **工具要固化进构建**：Debug / Sanitizer / Release 三套配置，选项写进 Makefile/CMake 而非每次手敲；`make test` / `make check` 一条命令复现

### 跨语言对比：测试与内存检测

| 维度 | C | C++ | Java | Python | Rust |
|------|---|-----|------|--------|------|
| 动态内存检测 | ASan/UBSan/TSan/Valgrind | 同 C，工具更丰富 | JVM 自管，无 UAF/泄漏 | GC + faulthandler | miri / nightly sanitizer |
| 静态分析 | cppcheck、clang-tidy | clang-tidy 最成熟 | SpotBugs、Error Prone | pylint、mypy、ruff | cargo clippy（官方集成） |
| 单元测试框架 | 自测模式、Unity、CMocka、Criterion | GoogleTest、Catch2 | JUnit、TestNG | pytest、unittest | cargo test（内置） |
| 覆盖率 | gcov/lcov | gcov/lcov | JaCoCo | coverage.py、pytest-cov | tarpaulin、llvm-cov |
| 内存安全兜底 | 无，全靠工具链 | 部分（RAII/智能指针） | GC | GC/引用计数 | 编译期保证（unsafe 除外） |

C 是所有对比项里最"裸露"的：**没有语言机制兜底**，内存安全只能外包给工具链与流程——Java/Python 靠 GC 免去 UAF 与泄漏，Rust 在编译期排除，而 C 必须把 ASan+单测+覆盖率变成 CI 的固定环节。存储引擎需要零成本控制，本阶段就是为这份控制权补上的"质量保险"。

### 阶段验收清单

- [ ] 能在 CI 或本地一键运行测试：`make test` / CI 脚本把测试、ASan+UBSan 构建、覆盖率命令串成一条命令（project/ 的 Makefile 直接可复用）
- [ ] 能解释 ASan 报告中的栈信息：错误类型、READ/WRITE 大小、调用栈、UAF 的分配/释放两段栈（示例 1）
- [ ] 能用测试覆盖核心边界条件：空、恰好填满、越界（`idx == len` 与远界）、NULL 参数、扩容失败路径（示例 6 / project/ 的用例即样板）
- [ ] 能区分 UBSan 的 recover 与中止两种形态，并知道 CI 里用 `-fno-sanitize-recover=undefined`（示例 2）
- [ ] 能用 TSan 检测数据竞争并验证修复（race 报 `data race`、fixed 零报告，示例 3）
- [ ] 能按平台选择泄漏检测：Linux LSan / macOS `leaks` / Valgrind，并解读报告（示例 4）
- [ ] 能读懂 gcov 报告的 `#####` 与 taken 0% 并用它指引补测（练习 5 / project 的 make coverage）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。五题与 roadmap ph11「练习」的对齐：练习 1 对应「用 ASan 修复越界问题」，练习 4 对应「给动态数组库写单元测试」（自测模式版），练习 5 对应「生成覆盖率报告」；练习 2/3 覆盖学习内容 UBSan 与 TSan（衔接 ph08 线程的并发检测）；roadmap「用 cppcheck 检查一个项目」由 3.6 与使用场景表给出命令与判读方法（本机未安装 cppcheck，未在本环境验证，建议在 Linux/CI 环境完成）。

- 用 ASan 复现并修复越界（★）
- 用 UBSan 复现并修复整数类 UB（★）
- 用 TSan 检测并修复数据竞争（★★）
- 给函数写自测模式单元测试（★★）
- 生成覆盖率报告并补测（★★★）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**带测试的 append-only buffer 库**——对应 roadmap 推荐项目「带测试的 WAL / buffer 库」，一个 append-only 字节 buffer（全部接口带边界检查与错误路径）+ 自测套件（30 个断言）+ Makefile（`make test` / `make asan` / `make coverage` / `make check`），把"测试证明行为正确、Sanitizer 证明内存无错、覆盖率暴露盲区"三件事固化成三条命令。roadmap 的另两个推荐项目：「带测试的数据结构库」由示例 5/6 与练习 4 覆盖，「带 Sanitizer 构建选项的 CMake 模板」由 3.9 的 CMake 片段给出骨架。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make check` 退出码 0、`make coverage` 报告可读、`make clean` 零残留）

### 下一阶段

[字节序、内存对齐与二进制格式解析阶段](../ph12-endian-binary/12-endian-binary.md) — 本阶段工具链将直接用于 record 解析器：长度先校验再读字段的边界逻辑用单元测试钉死（练习 4 的 check_len 思路 / project/ buffer 库的边界检查 get），解析越界与未对齐访问靠 ASan/UBSan 兜底，覆盖率报告会告诉你哪些损坏路径还没测。再往后是 [mmap、Page Cache 与可靠文件 IO 阶段](../ph13-mmap-page-cache/13-mmap-page-cache.md)（roadmap 第 13 节）的 fsync/刷盘边界与 ph16 数据库存储引擎基础阶段的 WAL/MemTable——本阶段 buffer 库的 append-only 语义正是为它们做的铺垫。
