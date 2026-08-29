# C 语言 Sanitizer / 静态分析 / 单元测试阶段

> 面向系统底层、存储引擎方向，本阶段把"会写 C"升级为"能证明 C 代码质量"——用动态检测、静态分析与单元测试组成质量工具链，把运行时事故挡在发布之前。

## 1. 概述
Sanitizer / 静态分析 / 单元测试阶段是 C 学习路线中"从定位错误到系统性防错"的工程化转折点。目标：**建立 C 代码质量工具链，减少运行时事故**——ph10 把 ASan/UBSan/Valgrind 当"定位工具"临时使用，并留下"工具的系统化工程化使用留给 ph11"的伏笔；本阶段接住它：把 Sanitizer 写进构建配置与 CI 流程，补上静态分析（cppcheck/clang-tidy）与单元测试（Unity/CMocka/Criterion），再用 gcov/lcov 把"测了多少"变成可度量的报告。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 动态检测 | ASan、UBSan、Valgrind 的构建选项、运行参数与报告解读 |
| 静态分析 | cppcheck、clang-tidy 的检查类别与集成方式 |
| 单元测试 | Unity/CMocka/Criterion 的断言、setUp/tearDown、mock |
| 覆盖率 | gcov/lcov 的计数插桩原理、报告解读与门槛设定 |
| 工程化 | Sanitizer 构建配置、make test 一键运行、CI 集成 |

本阶段承接 ph10：ph10 建立了"识别 10 类 UB + 用 Sanitizer 复现定位"的认知，示例里工具只是临时命令；本阶段把工具变成构建配置的一部分（`-fsanitize` 写进脚本而非每次手敲）、把测试变成代码的一部分（test 目录 + 断言框架）、把覆盖变成可度量的事实（gcov/lcov 报告），并给出"动态检测与静态分析互补"的选型逻辑。

**范围边界**：承接 ph10 未定义行为与防御性编程——ph10 解决"哪里有 UB、如何复现"，本阶段解决"如何系统化发现并守住"；**不涉及** 字节序与二进制格式位级处理（ph12）、mmap 与 Page Cache（ph13）、跨语言互操作 ABI（ph14）；本阶段重在"动态检测 + 静态分析 + 单元测试 + 覆盖率"的组合使用，并发数据竞争检测（TSan）只做工具级介绍，锁设计与内存序不展开。
## 2. 来源与演变
**质量工具链的两条主线：错误发现前置化、质量从度量开始**。早期 C 工程靠"发布后崩溃再修"，成本随系统变大而失控；工具链的演进本质是把错误发现不断左移——从运行期事故，到测试期报告，再到编译期警告。2002 年 **Valgrind** 用动态二进制插桩实现了"不需要重编译"的内存检查；2011 年 Google 开源 **AddressSanitizer（ASan）**，把开销从 Valgrind 的 20~50 倍压到约 2 倍，使内存检测能常驻每次构建与 CI——这是本阶段一切工程化的前提。

**静态分析走的是另一条路：不运行代码也能查**。1990 年代的 lint 用正则规则扫描源码，误报多；2009 年的 **cppcheck** 做源码级路径模拟，2016 年前后 **clang-tidy** 直接复用编译器前端 AST，把静态分析从"独立小工具"并入编译器生态。**测试与覆盖同源演进**：**gcov** 随 GCC 提供计数插桩；**Unity**（2007）、**CMocka 1.0**（2015）、**Criterion**（2015）先后把 C 单元测试从"自造断言宏"规范成框架；**lcov** 把 gcov 的文本报告汇总成 HTML，覆盖率才具备"CI 门禁"的形态。

| 时间 | 事件 | 对质量工具链的意义 |
|------|------|------------------|
| 1990s | gcov 随 GCC 提供计数插桩 | 最早的行覆盖率度量 |
| 2002 | Valgrind 发布 | 无需重编译的内存错误检测 |
| 2007 | Unity 发布 | C 单测从自造断言走向轻量框架 |
| 2009 | cppcheck 发布 | 开源 C/C++ 静态分析主流化 |
| 2011 | Google 开源 ASan | ~2x 开销，Sanitizer 可常驻开发与 CI |
| 2013 | UBSan 随 Clang 发布（GCC 4.9 跟进） | 溢出/除零/移位等逻辑型 UB 的廉价检测 |
| 2015 | CMocka 1.0、Criterion 发布 | 带 mock 与参数化的现代测试框架 |
| 2016+ | clang-tidy 成熟 | 静态分析并入编译器生态 |

ph09 埋下的"Sanitizer 与调试工具链（ASan/UBSan/TSan 的使用）"伏笔，在此兑现为可复用的工程流程：**Sanitizer 负责每次改动，静态分析负责定期全量，单元测试负责行为回归，覆盖率负责暴露测试盲区**。
## 3. 语法与参数
### 3.1 动态检测三件套：ASan / UBSan / Valgrind
**动态检测（Dynamic Analysis）** 是在"带检测代码的运行"中发现问题：编译器或运行时给程序加上检查逻辑，出错时打印报告。本阶段的三件套覆盖两类错误——**地址类**（越界、use-after-free、泄漏）与**逻辑类**（溢出、除零、非法移位）。

| 工具 | 启用方式 | 检测对象 | 典型开销 | 需重编译 |
|------|---------|---------|---------|---------|
| ASan | `gcc -fsanitize=address -g` | 越界、use-after-free、double free、泄漏 | ~2x 时间 | 是 |
| UBSan | `gcc -fsanitize=undefined -g` | 有符号溢出、除零、非法移位、未对齐访问 | 几个百分点 | 是 |
| 组合 | `gcc -fsanitize=address,undefined -g` | 两者叠加 | ~2x 时间 | 是 |
| Valgrind | `valgrind ./app` | 未初始化读、越界、泄漏 | 20~50x | 否 |

roadmap 示例（组合开关是日常默认形态）：
```bash
gcc -fsanitize=address,undefined -g main.c -o app
./app
```
**要点**：
- `-g` 必须有，报告里的源码行号依赖调试信息（ph10 示例已反复强调）；
- UBSan 默认**报错后继续**（recover）；要让它中止，编译加 `-fno-sanitize-recover=undefined` 或运行时 `UBSAN_OPTIONS=halt_on_error=1`——本机实测中止形态退出码 134（SIGABRT），CI 里"报错即失败"就靠它；
- `ASAN_OPTIONS=detect_leaks=1` 默认开启泄漏检测，`abort_on_error=1` 可让 ASan 直接中止；
- 库与主程序要**统一**加开关（插桩与运行时链接须一致）；
- Valgrind 不需要重编译，适合接手没有 Sanitizer 的旧代码（见 4.3）。
### 3.2 静态分析：cppcheck 与 clang-tidy
**静态分析（Static Analysis）** 不运行程序，直接在源码或编译器 AST 上扫描全部路径。它与编译器警告（`-Wall`/`-Wextra`）的关系：警告只覆盖"当前翻译单元、可达路径"，静态分析能跨文件、能模拟未执行的分支——但它会**误报**，告警需要人工判定。

```bash
cppcheck --enable=all --inconclusive --std=c11 src/
clang-tidy src/*.c -checks='clang-analyzer-*,bugprone-*' -- -Iinclude
```

| 工具 | 原理 | 典型检查 | 误报倾向 |
|------|------|---------|---------|
| cppcheck | 源码解析 + 路径模拟 | 空指针解引用、越界、未初始化、资源泄漏 | 中（用 `--inconclusive` 开关控制） |
| clang-tidy | 编译器前端 AST | 与编译器同源，规则可自定义（clang-analyzer/bugprone 等组） | 低（基于真实语义） |

本机实测 clang-tidy（LLVM 21）对"整数除法赋给 double"的典型输出：
```text
tidy_demo.c:5:12: warning: result of integer division used in a floating point
        context; possible loss of precision [bugprone-integer-division]
```
**要点**：静态分析适合**定期全量扫描**（评审前、发版前），动态检测适合**每次改动**（开发循环、CI）；两者互补的机制见 4.5。clang 编译器本身也内建静态能力——示例 1 的越界代码在编译期就被 `-Warray-bounds` 警告（本机实测），先听编译器的，再上工具。
### 3.3 单元测试框架：Unity / CMocka / Criterion
**单元测试（Unit Testing）** 把每个函数当作可独立验证的单元：给定输入，断言输出与副作用符合预期。C 的主流框架都是"断言宏 + 测试注册 + 运行器"的结构，区别在重量级与附加能力。

| 框架 | 特点 | 断言风格 | mock 支持 | 依赖 |
|------|------|---------|----------|------|
| Unity | 单文件框架（unity.c/h），极轻量 | `TEST_ASSERT_EQUAL_INT` 等宏 | 无（可配 CMock） | 仅 C 编译器 |
| CMocka | 来自 Google，带 mock 与组测试 | `assert_int_equal` 等函数 | 内置 mock | libcmocka |
| Criterion | 现代风格，fixture/参数化 | `cr_assert` 宏 | 部分 | libcriterion |

Unity 最小骨架（三个要素：断言、setUp/tearDown、RUN_TEST 注册）：
```c
#include "unity.h"
void setUp(void)   {}
void tearDown(void) {}
void test_add(void) { TEST_ASSERT_EQUAL_INT(4, 2 + 2); }
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_add);
    return UNITY_END();
}
```
**要点**：setUp/tearDown 在每个用例前后自动调用，保证用例互不污染；测试文件与源码分离（`test/` 目录，命名 `test_xxx.c`）；**测试必须能一键运行**（阶段验收第一项），所以一定要进构建脚本：`make test` 或 CI 里的同一行命令；框架选型上，纯 C 数据结构库用 Unity 最省事，需要模拟外部依赖（如文件 IO）时选 CMocka。
### 3.4 覆盖率：gcov / lcov
**覆盖率（Coverage）** 回答"测试跑过哪些代码"。gcov 在编译期给每个基本块插入计数器，运行后把计数导出，lcov 再汇总成报告。roadmap 必会概念"单元测试应覆盖边界输入和错误路径"在这里变成可量化的事实：**没跑到的行和分支就是没测的路径**。

```bash
gcc --coverage -g app.c -o app        # 1. 编译期插入计数
./app                                 # 2. 运行, 退出时写 .gcda
gcov app.gcda                         # 3. 生成 app.c.gcov 文本报告
lcov --capture --directory . --output-file coverage.info   # 4. 汇总
genhtml coverage.info --output-directory html              # 5. HTML 报告
```

| 文件/命令 | 内容 | 生成时机 |
|----------|------|---------|
| `.gcno` | 静态插桩图（哪些行有计数） | 编译时 |
| `.gcda` | 运行时执行计数 | 程序退出时写入 |
| `.gcov` | 每行执行次数，未执行行标记 `#####` | `gcov` 命令 |
| `coverage.info` / `html/` | 汇总报告（函数/行/分支三级） | `lcov` / `genhtml` |

**要点**：覆盖率是**测试质量的度量而非目标**——100% 行覆盖 ≠ 无 bug，但"错误分支 taken 0%"能直接暴露测试盲区（示例 5）；行覆盖只看"这行跑没跑过"，**分支覆盖**（`gcov -b`）才看"每个分支取没取过"，错误路径的验证必须看分支；插桩有性能开销，所以覆盖率用单独构建（`--coverage`）而非发布构建；平台差异：Linux gcc 的产物是 `源文件名.gcno/.gcda`，macOS clang 会带可执行名前缀（`ex5_cov-ex5_cov.gcda`，示例 5 有实测注）。
### 3.5 Sanitizer 构建选项与 CI 集成
工具要"常驻"而不是"想起来才用"，必须固化进构建系统。一个工程至少三套配置：**Debug**（`-O0 -g`，调试）、**Sanitizer**（`-O1 -g -fsanitize=address,undefined`，开发与 CI）、**Release**（`-O2`，发布）。

```cmake
# CMakeLists.txt 片段: 单独的 Sanitizer 构建开关
option(ENABLE_SANITIZERS "Build with ASan/UBSan" OFF)
if(ENABLE_SANITIZERS)
  add_compile_options(-fsanitize=address,undefined -g -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
```
```makefile
# Makefile 片段: 一键测试与 Sanitizer 测试
test:
	./test_darray
asan:
	gcc -fsanitize=address,undefined -g test_darray.c darray.c unity/unity.c -o test_asan
	./test_asan
```
**要点（roadmap 必会概念"Sanitizer 适合开发和 CI，不一定适合生产发布"）**：发布版不带 `-fsanitize`——约 2 倍时间与内存开销、依赖 ASan 运行时、且 ASan 会改变内存布局与分配器行为（可能掩盖或改变某些时序问题）；开发与 CI 则**必须**带，CI 至少安排一个 job 用 ASan+UBSan 构建并跑完全部测试，**泄漏在 CI 里视为失败**；Sanitizer 构建建议 `-O1`（`-O0` 可能让部分 UB 不暴露，`-O2` 的行号映射变差，ph10 4.2 已铺垫）；"内存错误越早发现越便宜"（roadmap 必会概念）——编译期警告 < CI 报告 < 线上事故，成本差一个数量级以上。
## 4. 底层原理
### 4.1 ASan：shadow memory 与 redzone
ASan 由三部分组成：**编译期插桩**、**替换的 malloc/free**、**shadow memory 映射**。编译器在每个 load/store 前插入"查 shadow"的代码；每个栈/堆/全局对象四周铺设**redzone（红区）**——带特殊标记的守卫字节；malloc/free 被替换成带记录的版本：记录每块内存的地址、大小与调用栈，`free` 后内存进入 **quarantine（延迟回收区）**，期间再访问即判定 use-after-free。

**shadow memory** 是 ASan 的核心机制：每 8 字节用户内存对应 1 字节 shadow（地址 = 用户地址 >> 3 + 固定偏移）。shadow 为 0 表示"8 字节全部可寻址"，非 0 表示"偏移量或红区标记"。一次越界访问命中红区 shadow 值，立即中止并打印报告：
```text
用户内存: [arr[0]|arr[1]|arr[2]| REDZONE | ...]
shadow  : [  0  |  0  |  0  |  0xfa   | ...]
读 arr[3] → 命中 shadow=0xfa(红区) → 立即报错并打印调用栈
```
报告结构（阶段验收"能解释 ASan 报告中的栈信息"）：`ERROR: AddressSanitizer: <类型> on address ...`（类型如 `stack-buffer-overflow`/`heap-use-after-free`）→ `READ/WRITE of size N` → `#0/#1 ... in <函数> <文件>:<行号>` 调用栈 → UAF 额外有 `freed by` 与 `previously allocated by` 两段栈（分配/释放位置对照，见示例 1）。
### 4.2 UBSan：编译期插桩
UBSan 是**纯编译期插桩**：编译器在可疑运算（有符号加减乘、除零、移位、对齐等）前插入 `__ubsan_handle_*` 检查函数，触发时打印 `runtime error: ...` 与源码位置。它不做 shadow memory，因此开销只有几个百分点，可以常驻所有构建。默认**报错后继续**执行；`-fno-sanitize-recover=undefined` 把检查从"打印"改成"abort"。与 ASan 的分工：**ASan 管"地址对不对"，UBSan 管"运算本身合不合法"**——两者组合一次编译双管齐下。注意编译器优化可能提前消除部分 UB 代码（ph10 4.1 的"无 UB 假设"），UBSan 的检查要在优化前提插好，所以 Sanitizer 构建用 `-O1` 而不是 `-O0` 更贴近发布行为。
### 4.3 Valgrind：动态二进制插桩（DBI）
**Valgrind** 采用**动态二进制插桩（Dynamic Binary Instrumentation, DBI）**：不修改源程序，运行时把二进制翻译成中间表示（IR），逐条指令插桩后再执行。Memcheck 工具用 shadow 位记录每个字节"已定义/未定义"，在条件跳转与系统调用处检查未初始化使用；越界靠分配块元数据比对；泄漏在进程退出时把未释放块分成 **definitely lost / possibly lost / still reachable** 三类。因为"不需要重编译"，Valgrind 对没有 Sanitizer 构建的旧代码仍是唯一选择；但 20~50 倍开销让它只适合深挖与定期检查，不适合每次构建。
### 4.4 gcov：计数插桩
gcov 是**计数插桩（count instrumentation）**：编译期（`--coverage` = `-fprofile-arcs -ftest-coverage`）在每个基本块入口插入计数器并写出插桩图 `.gcno`；程序运行退出时把计数写进 `.gcda`；`gcov` 读取两者，按行输出执行次数（未执行行标 `#####`），`gcov -b` 额外输出分支比例。**行覆盖率** = 执行过的行 / 可执行行；**分支覆盖率** = 至少取过一次的分支 / 全部分支。lcov/genhtml 把这些文本汇总成按函数、行着色的 HTML 报告，覆盖率门槛（如"核心模块行覆盖 ≥ 80%"）才能在 CI 里自动卡关。
### 4.5 动态检测与静态分析为什么互补
roadmap 必会概念"**动态检测和静态分析互补**"：动态检测只在**运行经过的路径**上检查，准确但覆盖不全——没人触发的路径永远不会被查；静态分析扫描**全部代码路径**，全面但有误报，且看不到运行时值。两者是"深度"与"广度"的组合。

| 维度 | 动态检测（ASan/UBSan/Valgrind） | 静态分析（cppcheck/clang-tidy） |
|------|-------------------------------|-------------------------------|
| 检查范围 | 只查运行经过的路径 | 扫描全部代码路径 |
| 是否需要运行 | 需要 | 不需要 |
| 准确度 | 高（真实执行） | 有误报，需人工判定 |
| 发现的问题 | 内存错误、UB（带运行时值） | 空指针、越界、资源泄漏、可移植性/风格 |
| 开销 | 2~50x 时间 | 编译期/定期扫描 |
| 适合时机 | 每次改动、CI | 定期全量、评审前 |

组合拳：**动态检测保"走过的路没问题"，静态分析保"没走过的路没大坑"**。TSan（ThreadSanitizer，`-fsanitize=thread`）是同一思路在并发域的延伸——检测数据竞争（衔接 ph08 线程），但锁设计与内存序分析不在本阶段范围。
## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| CI 质量门禁 | ASan/UBSan 构建、make test 一键运行、覆盖率阈值、cppcheck 检查 |
| 动态数组/字符串库开发 | 边界输入单测、扩容失败路径、ASan 验证（示例 4 全流程） |
| 存储引擎与 WAL/buffer | record 编解码单测、截断/长度非法等错误路径、泄漏检测 |
| 遗留代码接手 | Valgrind 免重编译查泄漏、cppcheck 摸底、clang-tidy 补规则 |
| 数据结构与算法练习 | Unity 单测 + gcov 覆盖率，用报告找未测分支 |
| 多线程模块 | TSan 检测数据竞争（衔接 ph08 线程） |

**不适合**此阶段的事项：
- 字节序与二进制格式的位级处理（ph12：大端/小端、varint、length-prefix frame、checksum）
- mmap、Page Cache 与可靠文件 IO（ph13：fsync、刷盘边界、崩溃恢复）
- 跨语言互操作 ABI（ph14：C ABI、FFI、opaque pointer）
- 并发模型与内存序设计（本阶段 TSan 只做检测工具介绍，锁策略与 happens-before 分析不展开）
- 性能剖析与优化（perf/火焰图属于"找慢"而非"找错"，目的不同）
## 6. 代码示例
> 说明：示例 1、2 是"故意出错"的演示，必须加 `-fsanitize` 编译运行（Sanitizer 会在出错处中止并打印报告），裸跑有崩溃/数据损坏风险；示例 3 用 Valgrind（面向 Linux，macOS Apple Silicon 官方不支持 Valgrind）；示例 4、5 是正常工程代码，可任意编译运行。示例 2、4、5 的编译与运行在本机（macOS + clang 17 / LLVM 21）实测，输出为真实产物；示例 1 的 ASan 报告为标准格式。
### 示例 1：ASan 检测越界与 use-after-free
对应 roadmap 练习"用 ASan 修复越界问题"与学习内容 AddressSanitizer。
```c
/* 故意越界写: 必须用 -fsanitize=address 编译运行, 否则勿运行 */
#include <stdio.h>
int main(void) {
    int arr[3] = {1, 2, 3};
    printf("arr[0]=%d\n", arr[0]);
    arr[3] = 100;   /* 故意越界写: ASan 应报 stack-buffer-overflow */
    printf("写完了\n");
    return 0;
}
```
```bash
gcc -fsanitize=address -g oob.c -o oob && ./oob
```
报告关键行（标准格式，`-g` 才有行号）：
```text
ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ff... at pc ...
WRITE of size 4 at ...
    #0 0x... in main oob.c:6
```
解读三要素（阶段验收"能解释 ASan 报告中的栈信息"）：**错误类型**——`stack-buffer-overflow` 说明对象在栈上（`arr` 是局部数组），堆对象则报 `heap-buffer-overflow`；**操作**——`WRITE of size 4` 是写越界（读则显示 `READ`）；**位置**——`#0 main oob.c:6` 给出越界源码行号。本机编译时 clang 还直接给出 `-Warray-bounds` 警告——编译器已内建静态越界检测，ASan 负责它抓不到的（use-after-free、运行时计算出的越界）。修复练习：把 `arr[3]` 改成 `arr[0]` 重编译，报告消失。

同一个构建开关下的 use-after-free（`-fsanitize=address` 不变）：
```c
/* 故意 use-after-free: 必须用 -fsanitize=address 编译运行, 否则勿运行 */
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) return 1;
    *p = 7;
    free(p);
    printf("%d\n", *p);   /* 故意在 free 后读取 */
    return 0;
}
```
报告关键行与越界报告的最大区别：多了两段栈，**分配/释放位置对照**即可确认完整链条：
```text
ERROR: AddressSanitizer: heap-use-after-free on address ...
READ of size 4 at ...
    #0 ... in main uaf.c:8
freed by thread T0 here:
    #0 ... in main uaf.c:6        ← free 的位置
previously allocated by thread T0 here:
    #0 ... in main uaf.c:5        ← malloc 的位置
```
ph10 示例 3 已见过这个报告；本阶段的重点是把它**变成门禁**：CI 里出现即失败，修复方式（free 后置 NULL、所有权文档化）已在 ph10 3.4 给出。
### 示例 2：UBSan 检测整数溢出与非法移位
对应 roadmap 学习内容 UndefinedBehaviorSanitizer 与 ph10 3.5 的溢出修复练习。
```c
/* 故意溢出/非法移位: 必须用 -fsanitize=undefined 编译运行, 否则勿运行 */
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
gcc -fsanitize=undefined -g overflow.c -o overflow && ./overflow
```
本机实测输出（clang 17）：
```text
overflow.c:6:15: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior overflow.c:6:15
overflow.c:8:15: runtime error: left shift of 1 by 31 places cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior overflow.c:8:15
b = -2147483648
s = -2147483648
```
解读：UBSan 默认**报错后继续**，所以 `b`/`s` 仍打印；把编译命令改成 `-fno-sanitize-recover=undefined` 后，第一个错误处直接 SIGABRT（本机实测退出码 134）——CI 里"报错即失败"靠它。修复练习沿用 ph10 3.5：`__builtin_add_overflow(a, 1, &b)` 把溢出变成可处理的返回值；移位前先检查 `n >= 0 && n < 32`。
### 示例 3：Valgrind memcheck 检测内存泄漏（不依赖 sanitizer）
对应 roadmap 学习内容 Valgrind 与 ph04 的"用 Valgrind 检查内存问题"。价值在于**不需要重编译**：任何没开 Sanitizer 的构建都能直接查。
```c
/* 故意泄漏: 用 Valgrind memcheck 检测, 不依赖 sanitizer */
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    int *p = malloc(16 * sizeof(int));   /* 分配后从不释放 */
    if (p == NULL) return 1;
    p[0] = 1;
    printf("p[0]=%d\n", p[0]);
    return 0;                            /* 没有 free(p): 64 字节泄漏 */
}
```
```bash
gcc -g -Wall leak.c -o leak
valgrind --leak-check=full ./leak
```
报告关键行：
```text
==12345== HEAP SUMMARY:
==12345==     in use at exit: 64 bytes in 1 blocks
==12345==   total heap usage: 1 allocs, 0 frees, 64 bytes allocated
==12345== 64 bytes in 1 blocks are definitely lost in loss record 1 of 1
==12345==    at 0x...: malloc (vg_replace_malloc.c:...)
==12345==    by 0x...: main (leak.c:4)
```
解读：`definitely lost` 是**确定泄漏**（必须修），另有 `possibly lost`（可能泄漏）与 `still reachable`（退出时仍可达，多数场景不算泄漏）；`leak.c:4` 定位到 malloc 那一行。要点：**不重编译、不加 `-g` 也能报**（加 `-g` 才有行号）；开销 20~50 倍，适合定期深挖与接手旧代码，不适合进每次构建。平台提示：Valgrind 官方不支持 macOS Apple Silicon，本示例面向 Linux（roadmap 与多数 CI 环境）。
### 示例 4：用 Unity 给动态数组库写单元测试
对应 roadmap 练习"给动态数组库写单元测试"与推荐项目"带测试的数据结构库"。把 ph04 的动态数组补一个**边界检查的读接口** `da_get`（越界返回 -1），错误路径变成可断言的行为；然后写 5 个用例覆盖：空数组、边界内取值、扩容后边界、越界（`idx == len` 与远界）、NULL 参数。Unity 是单文件框架，把 `unity.c`/`unity.h`/`unity_internals.h` 三个文件下载到工程里即可（ThrowTheSwitch/Unity 仓库）。
```c
/* darray.h: ph04 动态数组 + 边界检查的读接口 */
#ifndef DARRAY_H
#define DARRAY_H
#include <stddef.h>

typedef struct {
    int   *data;
    size_t len;   /* 已用元素数 */
    size_t cap;   /* 容量（元素数） */
} DynArray;

int      da_init(DynArray *da);
void     da_destroy(DynArray *da);
int      da_push(DynArray *da, int val);
int      da_get(const DynArray *da, size_t idx, int *out);  /* 越界/空指针返回 -1 */
size_t   da_len(const DynArray *da);
#endif
```
```c
/* darray.c: 实现 (da_get 是新增的错误路径) */
#include <stdlib.h>
#include "darray.h"

int da_init(DynArray *da) {
    if (da == NULL) return -1;
    da->data = malloc(4 * sizeof(int));
    if (da->data == NULL) return -1;
    da->len = 0;
    da->cap = 4;
    return 0;
}

void da_destroy(DynArray *da) {
    if (da == NULL) return;
    free(da->data);
    da->data = NULL;
    da->len = da->cap = 0;
}

int da_push(DynArray *da, int val) {
    if (da == NULL) return -1;
    if (da->len == da->cap) {
        size_t new_cap = da->cap * 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;   /* 扩容失败, 原数据不丢 */
        da->data = tmp;
        da->cap  = new_cap;
    }
    da->data[da->len++] = val;
    return 0;
}

int da_get(const DynArray *da, size_t idx, int *out) {
    if (da == NULL || out == NULL) return -1;
    if (idx >= da->len) return -1;    /* 边界检查: 错误路径 */
    *out = da->data[idx];
    return 0;
}

size_t da_len(const DynArray *da) {
    return da == NULL ? 0 : da->len;
}
```
```c
/* test_darray.c: 覆盖边界输入与错误路径 */
#include "unity.h"
#include "darray.h"

static DynArray da;

void setUp(void)    { TEST_ASSERT_EQUAL_INT(0, da_init(&da)); }
void tearDown(void) { da_destroy(&da); }

void test_new_array_is_empty(void) {
    TEST_ASSERT_EQUAL_size_t(0, da_len(&da));
}

void test_push_then_get_in_bounds(void) {
    TEST_ASSERT_EQUAL_INT(0, da_push(&da, 42));
    int v = -1;
    TEST_ASSERT_EQUAL_INT(0, da_get(&da, 0, &v));
    TEST_ASSERT_EQUAL_INT(42, v);
}

void test_push_past_capacity_grows(void) {
    for (int i = 0; i < 100; i++)          /* 越过初始容量 4, 触发 2x 扩容 */
        TEST_ASSERT_EQUAL_INT(0, da_push(&da, i));
    TEST_ASSERT_EQUAL_size_t(100, da_len(&da));
    int v = -1;
    TEST_ASSERT_EQUAL_INT(0, da_get(&da, 99, &v));  /* 边界内最后一个 */
    TEST_ASSERT_EQUAL_INT(99, v);
}

void test_get_out_of_bounds_returns_error(void) {
    int v = -1;
    TEST_ASSERT_EQUAL_INT(-1, da_get(&da, 0, &v));   /* 空数组越界 */
    TEST_ASSERT_EQUAL_INT(0, da_push(&da, 1));
    TEST_ASSERT_EQUAL_INT(-1, da_get(&da, 1, &v));   /* 越界: idx == len */
    TEST_ASSERT_EQUAL_INT(-1, da_get(&da, 100, &v)); /* 越界: 远界 */
}

void test_null_arguments_rejected(void) {
    TEST_ASSERT_EQUAL_INT(-1, da_push(NULL, 1));     /* 错误路径 */
    int v = -1;
    TEST_ASSERT_EQUAL_INT(-1, da_get(NULL, 0, &v));
    TEST_ASSERT_EQUAL_size_t(0, da_len(NULL));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_new_array_is_empty);
    RUN_TEST(test_push_then_get_in_bounds);
    RUN_TEST(test_push_past_capacity_grows);
    RUN_TEST(test_get_out_of_bounds_returns_error);
    RUN_TEST(test_null_arguments_rejected);
    return UNITY_END();
}
```
```bash
gcc -I. -Iunity darray.c test_darray.c unity/unity.c -o test_darray && ./test_darray
```
本机实测输出：
```text
test_darray.c:47:test_new_array_is_empty:PASS
test_darray.c:48:test_push_then_get_in_bounds:PASS
test_darray.c:49:test_push_past_capacity_grows:PASS
test_darray.c:50:test_get_out_of_bounds_returns_error:PASS
test_darray.c:51:test_null_arguments_rejected:PASS
-----------------------
5 Tests 0 Failures 0 Ignored
OK
```
再把同一套测试用 Sanitizer 构建跑一遍（本机实测 UBSan 构建同样 5/5 通过）——这就是 CI 的标准组合：**测试证明行为正确，Sanitizer 证明内存无错**：
```bash
gcc -fsanitize=address,undefined -g -I. -Iunity darray.c test_darray.c unity/unity.c -o test_asan && ./test_asan
```
验证练习：故意把 `da_get` 里的 `idx >= da->len` 改成 `idx > da->len`（留 off-by-one），测试应失败并定位到 `test_get_out_of_bounds_returns_error`——**测试的价值在于能抓住回归**。
### 示例 5：gcov/lcov 生成覆盖率报告
对应 roadmap 练习"生成覆盖率报告"。故意留一个**从不调用的函数**（`report_corrupt`）和一个**未触发的错误分支**（`check_len` 的 `len > max`），让报告有 `#####` 行与 0% 分支可看。
```c
/* ex5_cov.c: 故意留未执行代码, 让覆盖率 < 100% 可见 */
#include <stdio.h>

static int is_leap(int y) {
    if (y % 400 == 0) return 1;
    if (y % 100 == 0) return 0;
    return y % 4 == 0;
}

/* 模拟 record 长度校验(衔接 ph12): len > max 是错误路径 */
static int check_len(size_t len, size_t max) {
    if (len > max) return -1;   /* 错误路径: 测试故意不触发 */
    return 0;
}

/* 损坏处理函数: 测试从不调用, 行覆盖率会出现 ##### */
void report_corrupt(void) {
    fprintf(stderr, "record corrupt\n");
}

int main(void) {
    printf("2000:%d 1900:%d 2024:%d 2023:%d\n",
           is_leap(2000), is_leap(1900), is_leap(2024), is_leap(2023));
    printf("check_len ok=%d\n", check_len(4, 16));   /* 只走合法路径 */
    return 0;
}
```
```bash
gcc --coverage -g ex5_cov.c -o ex5_cov   # 1. 编译期插入计数
./ex5_cov                                # 2. 运行, 生成 .gcda
gcov ex5_cov.gcda                        # 3. 文本报告
```
本机实测汇总（clang 17 + Apple gcov；macOS 的 `.gcda` 名带可执行名前缀 `ex5_cov-ex5_cov.gcda`，Linux gcc 直接是 `ex5_cov.gcda`）：
```text
File 'ex5_cov.c'
Lines executed:82.35% of 17
```
加 `-b` 看分支：
```text
Branches executed:100.00% of 6
Taken at least once:83.33% of 6
```
报告关键行：
```text
    #####:   17:void report_corrupt(void) {   ← 从不执行的行
    #####:   18:    fprintf(stderr, "record corrupt\n");
        1:   12:    if (len > max) return -1;   ← 行执行过…
branch  0 taken 0%                            ← …但错误分支从未被取
```
解读：行覆盖 82.35% 来自 `report_corrupt` 的 `#####` 行；而 `check_len` 的错误分支 **taken 0%** 用行覆盖根本看不出来，必须 `gcov -b` 看分支——这正是"单元测试应覆盖错误路径"的量化证据。HTML 报告用 lcov 汇总：
```bash
lcov --capture --directory . --output-file coverage.info
genhtml coverage.info --output-directory html
```
补测练习：给 `check_len(20, 16)` 与 `report_corrupt()` 各加一个用例后重跑，行覆盖与分支覆盖应趋近 100%——覆盖率的用途是**指引补测**，不是数字本身。另注：本机实测发现未调用的 `static` 函数会被编译器剔除、不参与覆盖统计，所以演示函数故意不写 `static`。
## 7. 总结
### 关键要点
1. **动态检测和静态分析互补**（roadmap 必会概念）：动态只查走过的路径、零误报；静态扫全部路径、有误报——组合使用，动态进 CI、静态定期全量
2. **Sanitizer 适合开发和 CI，不一定适合生产发布**（roadmap 必会概念）：约 2x 开销 + 运行时依赖 + 内存布局改变；发布版不带，开发/CI 必须带，泄漏在 CI 视为失败
3. **单元测试应覆盖边界输入和错误路径**（roadmap 必会概念）：空数组、满容量、`idx == len` 与远界、NULL 参数、扩容失败——每个错误路径一个用例
4. **内存错误越早发现越便宜**（roadmap 必会概念）：编译期警告 < CI 报告 < 线上事故，成本差一个数量级以上
5. **ASan 报告三要素**（阶段验收）：错误类型（stack/heap-buffer-overflow、use-after-free）、`READ/WRITE of size N`、`#0` 源码行号；UAF 另有分配/释放两段栈
6. **UBSan 管运算合法性，ASan 管地址合法性**：`-fsanitize=address,undefined` 一次编译两样都查；UBSan 默认报错后继续，`-fno-sanitize-recover` 转中止
7. **Valgrind 免重编译**：旧代码接手的唯一选择；开销 20~50 倍，别进每次构建；`definitely lost` 必须修
8. **覆盖率是度量不是目标**：100% 行覆盖 ≠ 无 bug；用 `gcov -b` 的分支覆盖盯错误路径，用 lcov 报告找 `#####`
9. **测试要能一键运行**：make test / CI 脚本把测试、Sanitizer、覆盖率串成一条命令，别人（和未来的你）一条命令就能复现
10. **工具要固化进构建**：Debug / Sanitizer / Release 三套配置，选项写进 CMake/Makefile 而非每次手敲
### 跨语言对比：测试与内存检测
| 维度 | C | C++ | Java | Python | Rust |
|------|---|-----|------|--------|------|
| 动态内存检测 | ASan/UBSan/Valgrind | 同 C，工具更丰富 | JVM 自管，无 UAF/泄漏 | GC + faulthandler | miri / nightly sanitizer |
| 静态分析 | cppcheck、clang-tidy | clang-tidy 最成熟 | SpotBugs、Error Prone | pylint、mypy、ruff | cargo clippy（官方集成） |
| 单元测试框架 | Unity、CMocka、Criterion | GoogleTest、Catch2 | JUnit、TestNG | pytest、unittest | cargo test（内置） |
| 覆盖率 | gcov/lcov | gcov/lcov | JaCoCo | coverage.py、pytest-cov | tarpaulin、llvm-cov |
| 内存安全兜底 | 无，全靠工具链 | 部分（RAII/智能指针） | GC | GC/引用计数 | 编译期保证（unsafe 除外） |

C 是所有对比项里最"裸露"的：**没有语言机制兜底**，内存安全只能外包给工具链与流程——Java/Python 靠 GC 免去 UAF 与泄漏，Rust 在编译期排除，而 C 必须把 ASan+单测+覆盖率变成 CI 的固定环节。存储引擎需要零成本控制，本阶段就是为这份控制权补上的"质量保险"。
### 阶段验收标准
- 能在 CI 或本地一键运行测试：make test / CI 脚本把 Unity 测试、ASan+UBSan 构建、覆盖率命令串成一条命令（示例 4 的流程直接可复用）
- 能解释 ASan 报告中的栈信息：错误类型、READ/WRITE、`#0` 行号、UAF 的分配/释放栈（示例 1）
- 能用测试覆盖核心边界条件：空数组、满容量、越界（`idx == len` 与远界）、NULL 参数、扩容失败路径（示例 4 的 5 个用例即样板）
### 进入下一阶段前
- 给动态数组库写单元测试：用 Unity 覆盖 push/get 的边界输入与错误路径（参考示例 4），跑通后故意引入一个 off-by-one 确认测试能抓住回归
- 用 ASan 修复越界问题：写一个越界程序 → 读报告 → 修复 → 报告消失，走完示例 1 的完整闭环；提示：务必加 `-g`，否则没有行号
- 用 cppcheck 检查一个项目：对 ph07 的多文件项目跑 `cppcheck --enable=all --std=c11`，把每条告警分类为"真问题/误报"，修掉真问题；提示：静态分析告警要带上下文判定，别全信也别全忽略
- 生成覆盖率报告：对示例 4 的测试跑 gcov/lcov，找出 `#####` 行与 taken 0% 的分支并补测试；提示：先用 `gcov -b` 看分支，错误路径的缺口都在那里
### 推荐项目
- **带测试的数据结构库**（roadmap 推荐）：把 ph04/ph05 的动态数组、链表、HashMap 的每个 API 配 Unity 测试，错误路径全覆盖；Makefile 提供 `make test` / `make asan` 两档，`make test` 一键跑通全部用例
- **带 Sanitizer 构建选项的 CMake 模板**（roadmap 推荐）：Debug / Sanitizer / Release 三套配置（3.5 的骨架），CI 用 Sanitizer 档跑测试、Release 档发布；模板本身可作为后续所有 C 工程的起点
- **带测试的 WAL / buffer 库**（roadmap 推荐）：一个 append-only 字节 buffer + 长度校验函数，测试覆盖"正常写读 / 写满 / 截断 / 长度非法"四类路径（示例 5 的 check_len 思路），全部测试在 ASan 构建下跑——为 ph12 二进制格式与 ph17 WAL 预演
### 下一阶段
**字节序、内存对齐与二进制格式解析**（ph12-endian-alignment，文档规划中）—— 大端/小端、结构体 padding、length-prefix frame 与 checksum；ph12 的 record 解析器正是本阶段工具链的主场：长度先校验再读字段的边界逻辑要用单元测试钉死（示例 5 的 check_len 思路），解析越界与未对齐访问靠 ASan/UBSan 兜底，覆盖率报告会告诉你哪些损坏路径还没测。
