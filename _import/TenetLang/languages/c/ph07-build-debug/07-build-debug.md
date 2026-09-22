# C 语言编译、调试与工程化阶段

> 面向系统底层、存储引擎方向，本阶段像工程项目一样组织、构建和调试 C 代码：从"能编译"走向"能工程化地构建、能系统性地定位崩溃"。

## 1. 概述

编译、调试与工程化阶段是 C 学习路线中"从写代码到造产品"的节点。目标：**能用 gcc/clang 组织多文件项目，把 -Wall/-Wextra 的警告当质量信号处理，用 Makefile/CMake 描述依赖关系，用 GDB 与 core dump 把崩溃定位到具体代码行，并能用 ar 封装静态库、用 -fPIC -shared 制作动态库**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 编译器与选项 | gcc、clang、-std、-g、-O2、-I、-L、-l、-c、-o |
| 警告体系 | -Wall、-Wextra、-Werror、警告即质量信号 |
| 构建配置 | Debug 构建（-g -O0）与 Release 构建（-O2 -DNDEBUG） |
| 库的制作与链接 | 静态库 .a（ar 打包）、动态库 .so（-fPIC、-shared） |
| 构建工具 | Makefile（目标·依赖·规则、变量、伪目标）、CMakeLists.txt |
| 调试工具 | GDB 断点、单步、print、backtrace、watch |
| 崩溃分析 | core dump 生成、gdb 离线回放、bt 定位崩溃现场 |
| 预处理器 | #ifdef 条件编译、-D 宏定义、include guard |

本阶段承接 ph06 的文件操作实践：ph02 学过 `gcc main.c math_utils.c -o app` 这种"命令行手动编译"，本阶段把它升级为可重复、可增量、可配置的工程化构建；ph04 养成的"用 Valgrind/ASan 查内存错误"习惯，本阶段接上"用 GDB 与 core dump 定位崩溃"的调试器思维。

**范围边界**：承接 ph06 文件操作；**不涉及** Linux 系统编程与多线程（ph08：文件描述符、fork/exec、pthread、socket、epoll）、C 标准与可移植性细节（ph09）、未定义行为深入（ph10）、Sanitizer 工具链系统化（ph11）、性能剖析（perf/火焰图，后续阶段）。

## 2. 来源与演变

编译器的自由化是这一切的起点。1987 年 Richard Stallman 为 GNU 项目发布了 GCC（GNU Compiler Collection，最初叫 GNU C Compiler），让 Unix/Linux 世界摆脱了对商业编译器（如 AT&T 的 `cc`）的依赖，成为 Linux 生态的基石。2009 年，Apple 主导开发了 Clang/LLVM：模块化架构、更快的编译速度、**带高亮与修复提示的错误信息**，如今 macOS/Xcode 的默认编译器就是 clang——gcc 与 clang 的参数基本兼容，同一个命令行几乎可以互换。

构建工具的演化脉络是"从命令序列到依赖图"：早期工程用 shell 脚本逐条调用 gcc，改一个文件就要全量重编；1976 年 Stuart Feldman 在贝尔实验室为 Unix 编写了 **Make**，用"目标-依赖-规则"描述构建图，按时间戳只重编变化的文件——增量构建思想沿用至今。但 Make 语法原始、跨平台差，2000 年 Kitware 推出 **CMake**：先写 CMakeLists.txt，再生成 Makefile 或 Ninja 构建脚本，成为 C/C++ 跨平台的事实标准。

调试器与崩溃分析工具同步演进：1986 年 Stallman 又写出了 **GDB**（GNU Debugger），配合 `-g` 生成的调试信息（DWARF 格式）实现断点、单步、变量查看；**core dump**（核心转储）机制源于 Unix 早期——进程崩溃时内核把内存映像写入 core 文件，GDB 可离线回放崩溃现场，无需重跑程序。如今 lldb（LLVM 系）与 GDB 并立，但"符号化调试"的模型一脉相承。

本文示例以 **C99** 为基线（Makefile 语法与 GCC/Clang 通用，GDB 命令与版本无关），验证工具链 Apple clang 17 + CMake 3.31 + GDB。

| 时间 | 工具 | 关键演变 |
|------|------|---------|
| 1972 | Unix 汇编时代 | 手工编译，无标准工具链 |
| 1976 | Make | Stuart Feldman 编写，目标-依赖-规则成型，增量构建诞生 |
| 1986 | GDB | Stallman 编写，符号化调试成为可能 |
| 1987 | GCC | GNU C Compiler 发布，自由编译器基石 |
| 1990s | DWARF | 调试信息格式标准化，`-g` 选项背后的规范 |
| 2000 | CMake | 跨平台构建系统生成器，C/C++ 事实标准 |
| 2009 | Clang/LLVM | Apple 主导，错误信息可读性与编译速度的革命 |

## 3. 语法与参数

### 3.1 gcc / clang 常用编译选项

```bash
# 一步到位: 预处理 + 编译 + 汇编 + 链接
gcc -std=c11 -Wall -Wextra -g -O0 main.c math_utils.c -o app
# 分步: 只编译不链接, 得到目标文件
gcc -std=c11 -Wall -Wextra -c math_utils.c     # → math_utils.o
gcc -std=c11 -Wall -Wextra -c main.c           # → main.o
gcc main.o math_utils.o -o app                 # 只链接
# 只有 main.o 变了 → 只需重编 main.c 再链接 → 这就是 Make 的用武之地
```

| 选项 | 作用 |
|------|------|
| `-std=c11` | 指定语言标准（c99/c11/c17/gnu11…） |
| `-Wall -Wextra` | 打开常用警告 + 额外警告 |
| `-Werror` | 把警告升级为错误，编译直接失败 |
| `-g` | 生成调试信息（DWARF），GDB 必需 |
| `-O0/-O1/-O2/-O3` | 优化级别；`-O0` 不优化、便于调试 |
| `-DNDEBUG` | 定义宏，关闭 `assert` 断言 |
| `-I<dir>` | 添加头文件搜索路径 |
| `-L<dir> -l<name>` | 链接库：在 `<dir>` 中找 `lib<name>.a`/`.so` |
| `-c` | 只编译不链接，产出 `.o` 目标文件 |
| `-o` | 指定输出文件名 |
| `-fPIC -shared` | 生成位置无关代码 / 制作动态库 |

**要点**：
- **gcc 与 clang 的命令行基本兼容**，同一份编译命令两个编译器都能跑；`-l` 后面的库名不带 `lib` 前缀与扩展名（`-lmath` 找 `libmath.a` 或 `libmath.so`）。
- `-L` 必须出现在 `-l` 之前；找不到库时链接器报 `cannot find -lmath`，先用 `ls` 确认库名与路径。

### 3.2 警告体系：-Wall -Wextra -Werror

```bash
gcc -Wall -Wextra -Werror main.c -o app
```
**`-Wall` 并不是"所有警告"**，只是一组最常用的警告；`-Wextra` 再补充一组；两者叠加是 C 项目的最低质量门槛。

| 常见警告 | 含义 | 典型原因 |
|----------|------|---------|
| `unused variable` | 变量定义了没用 | 拼写错、遗留代码 |
| `unused function` | 函数没被调用 | 忘了接进 main、声明与定义不一致 |
| `implicit declaration` | 隐式函数声明 | 漏 `#include` 头文件 |
| `sign-compare` | 有符号/无符号比较 | `int` 与 `size_t` 直接比较 |
| `maybe-uninitialized` | 可能未初始化就使用 | 分支漏赋值 |
| `return-type` | 函数声明返回类型但没 return | 忘记写返回值 |

**要点**：
- **警告要当成质量信号处理**：每条警告都是编译器免费送的行级诊断，修一个警告往往比修一个线上崩溃便宜一个数量级；ph06 的"检查每个 IO 返回值"与"检查每条警告"是同一件事。
- `-Werror` 把警告变成编译失败，适合 CI 强制零警告；**坑：老代码或第三方头文件可能触发警告导致构建失败**——按项目需要打开，必要时用 `#pragma GCC diagnostic ignored "-Wunused-parameter"` 局部豁免。

### 3.3 Debug 与 Release 构建

| 维度 | Debug 构建 | Release 构建 |
|------|-----------|--------------|
| 优化 | `-O0`（不优化，源码与指令一一对应） | `-O2`/`-O3`（激进优化） |
| 调试信息 | `-g` 完整符号 | 通常去掉或精简 |
| 断言 | 保留 `assert` | `-DNDEBUG` 关闭 |
| 目标 | 可断点、可单步、可 print | 体积小、速度快 |
| 典型用法 | 开发期、调试期 | 测试通过后的交付、线上 |

```bash
# Debug
gcc -std=c11 -Wall -Wextra -g -O0 main.c -o app_debug
# Release
gcc -std=c11 -Wall -Wextra -O2 -DNDEBUG main.c -o app_release
```
**坑（必背）**：**未定义行为在不同优化级别下表现完全不同**——同一段越界代码在 `-O0` 下"碰巧正常"，在 `-O2` 下可能崩溃或产生诡异结果。所以"Debug 正常、Release 崩溃"时，**先怀疑未定义行为（ph10 深入），而不是怀疑编译器有 bug**；Debug 与 Release 是两种不同目标的产品，不能互相替代（ph10 还会看到 Sanitizer 在 ph11 系统化）。

### 3.4 静态库 .a 与动态库 .so 的制作与链接

```bash
# 静态库: 先编译成 .o, 再用 ar 打包 (名字来自 "archiver")
gcc -c math_utils.c -o math_utils.o
ar rcs libmath.a math_utils.o        # r=插入 c=创建 s=符号索引
ar t libmath.a                       # 查看库里的成员
# 链接: 库代码被直接拷进可执行文件
gcc main.c -L. -lmath -o app_static

# 动态库: 编译必须加 -fPIC, 链接时 -shared
gcc -fPIC -c math_utils.c -o math_utils_pic.o
gcc -shared math_utils_pic.o -o libmath.so
gcc main.c -L. -lmath -o app_dynamic
```
| 对比 | 静态库 .a | 动态库 .so |
|------|----------|-----------|
| 链接时 | 需要的 .o 代码拷入可执行文件 | 只记录库名与所需符号 |
| 运行时 | 不需要 .a 文件 | 由动态链接器 `ld.so` 按 `DT_NEEDED` 加载 |
| 更新 | 要重新链接 | 换一个 .so 即生效（ABI 兼容时） |
| 体积/内存 | 每进程一份拷贝 | 多进程共享同一份代码段 |

**要点**：
- **`-l` 库必须放在使用它的源文件/目标文件之后**（`gcc main.c -lmath` 正确，`gcc -lmath main.c` 报 `undefined reference`），因为链接器从左到右扫描、符号只向后解析——这是最经典的链接坑。
- 动态库启动时找不到：用 `ldd app_dynamic` 查看依赖，`LD_LIBRARY_PATH=. ./app_dynamic` 临时指定搜索路径；正式部署应装进 `/usr/lib` 或用 rpath。

### 3.5 Makefile 基础

```makefile
CC     = gcc
CFLAGS = -std=c11 -Wall -Wextra -g
TARGET = app
OBJS   = main.o math_utils.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c main.c

math_utils.o: math_utils.c math_utils.h
	$(CC) $(CFLAGS) -c math_utils.c

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
```
一条 Make 规则 = **目标（target）: 依赖（prerequisites）** + 换行缩进的命令（recipe）。Make 的工作方式：比较目标与依赖的时间戳，**只有依赖比目标新（或目标不存在）时才重跑命令**——这是"增量构建"的本质。

| 语法 | 含义 |
|------|------|
| `CC = gcc` | 变量赋值，用 `$(CC)` 引用 |
| `$@` / `$^` / `$<` | 自动变量：目标 / 所有依赖 / 第一个依赖 |
| `.PHONY: clean` | 伪目标声明：防止磁盘上恰好有名为 clean 的文件时跳过 |
| `#` 注释 | 注释行 |

**要点**：
- **Makefile 描述的是依赖关系，不只是命令集合**——写出正确的依赖，Make 才会帮你"只重编该重编的"，这是本阶段必会概念。
- **坑 1**：命令前必须是 **Tab**，空格会报 `missing separator`；**坑 2**：头文件必须写进依赖（`main.o: main.c math_utils.h`），否则改了头文件不触发重编，产生"改了没生效"的诡异 bug。

### 3.6 CMake 基础

```cmake
cmake_minimum_required(VERSION 3.10)
project(myapp C)

add_library(math_utils STATIC math_utils.c)      # 静态库 (SHARED → 动态库)
add_executable(app main.c)                        # 可执行文件
target_link_libraries(app PRIVATE math_utils)     # app 链接 math_utils
target_compile_options(app PRIVATE -Wall -Wextra)
```
```bash
cmake -B build          # 配置阶段: 读 CMakeLists.txt, 生成构建系统 (Makefile/Ninja)
cmake --build build     # 构建阶段: 实际编译链接
./build/app             # 运行
cmake --build build --target clean   # 清理
```
**要点**：
- CMake 不是编译器，而是"**构建系统生成器**"：CMakeLists.txt 描述"要构建什么"，具体怎么构建交给 Makefile/Ninja。
- `add_library` 的类型：`STATIC`（静态库）/ `SHARED`（动态库）/ `INTERFACE`（纯头文件接口库）；**坑：忘写 `target_link_libraries` 会报 `undefined reference`**——CMake 不会自动推断链接关系。
- 配置与构建分离（`-B build` 生成独立目录），`rm -rf build` 即可彻底重来，比手工 Makefile 更工程化。

### 3.7 GDB 调试：断点·单步·print·backtrace·watch

```bash
gcc -g -Wall -Wextra crash.c -o crash    # 必须加 -g, 否则 GDB 看不到源码
gdb ./crash
```
| 命令 | 简写 | 作用 |
|------|------|------|
| `break 行号/函数` | `b` | 设断点，如 `b 8`、`b fill` |
| `run [参数]` | `r` | 运行程序（可带命令行参数） |
| `next` | `n` | 单步执行，不进入函数 |
| `step` | `s` | 单步执行，进入函数 |
| `print 表达式` | `p` | 打印变量/表达式，如 `p i`、`p arr[0]` |
| `backtrace` | `bt` | 查看调用栈（谁调了谁） |
| `list` | `l` | 查看当前位置附近源码 |
| `watch 变量` | — | 变量每次变化都停下 |
| `continue` | `c` | 继续运行到下一个断点 |
| `quit` | `q` | 退出 |

一个典型会话（崩溃后定位）：
```text
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401163 in fill (arr=0x7fffffffdde0, len=3) at crash.c:5
5               arr[i] = i * i;
(gdb) bt
#0  fill (arr=0x7fffffffdde0, len=3) at crash.c:5
#1  0x00000000004011a5 in main () at crash.c:11
(gdb) p i
$1 = 3
(gdb) p len
$2 = 3
```
**要点**：
- **调试器比打印日志更适合定位崩溃**：printf 要改代码、重编译、重跑，GDB 是对**正在运行的程序**直接提问——设断点、查变量、看调用栈，全部即时完成，这是本阶段必会概念。
- 单步前先 `b main` + `r` 把程序停在入口，再用 `n`/`s` 逐行走；`bt` 永远先看——它直接告诉你崩溃发生在哪一层调用。

### 3.8 core dump 生成与分析

```bash
ulimit -c unlimited     # 允许生成 core 文件 (默认常为 0, 即禁止)
./crash                 # 段错误 → 当前目录生成 core 文件
gdb ./crash core        # 离线回放崩溃现场, 不需要重跑程序
(gdb) bt                # 直接看到崩溃时的调用栈
```
**core dump（核心转储）**是进程崩溃瞬间的**内存映像**，由内核写入磁盘（Linux 默认 `core` 或 `core.<pid>`）。它是"崩溃现场的快照"：线上程序崩了，把 core 文件拿回来就能离线分析。

**要点**：
- **坑 1**：core 默认被 `ulimit -c` 限制为 0（不生成），要 `ulimit -c unlimited` 开启；**坑 2**：systemd 系统会把 core 转给 `coredumpctl`（`coredumpctl gdb <程序名>` 可直接进入 GDB）；**坑 3**：core 文件可能很大，注意磁盘空间。
- 分析 core 同样要求可执行文件带 `-g`；**先确认崩溃程序与 core 是同一版本**，否则行号错位。

### 3.9 预处理器与条件编译

```c
#ifdef DEBUG
    fprintf(stderr, "debug: x=%d\n", x);   /* 只在 DEBUG 定义时编译 */
#endif

#ifndef NDEBUG
    assert(x > 0);                          /* NDEBUG 定义时整行消失 */
#endif
```
```bash
gcc -DDEBUG main.c -o app        # 命令行定义宏, 等价于 #define DEBUG
gcc -DNDEBUG main.c -o app       # 关闭 assert 的工程化方式
```
**要点**：
- 条件编译（`#ifdef`/`#ifndef`/`#if`/`#endif`）与 include guard（ph02）同源，都是预处理阶段按宏展开或删除代码。
- 典型用途：调试开关（`-DDEBUG`）、平台差异（`#ifdef __linux__`）、特性开关、`-DNDEBUG` 关断言——这正是 Debug/Release 构建差异的底层机制。
- **坑：条件编译宏过多会让代码可读性急剧下降**；能用普通 `if` 判断的运行时分支，不要滥用预处理。

## 4. 底层原理

### 4.1 编译流程回顾

```text
main.c ──预处理──▶ main.i ──编译──▶ main.s ──汇编──▶ main.o ──┐
   (cpp: 展开宏/头文件)  (cc1: 生成汇编)  (as: 生成机器码)      ├─链接(ld)──▶ app
math_utils.c ───────────────────────────────────────────▶ math_utils.o ──┘
```
| 阶段 | 手段 | 诊断什么 |
|------|------|---------|
| 预处理 | `gcc -E main.c` | 宏展开是否正确、头文件是否包含 |
| 编译 | `gcc -S main.c` | 语法错误、类型错误、警告（带精确行号） |
| 汇编 | `gcc -c`、`objdump -d main.o` | 反汇编核对机器码 |
| 链接 | `gcc`、`nm main.o` | `undefined reference`、`multiple definition` |
| 全流程 | `gcc -v` | 查看编译器内部的完整调用链 |

理解这条流水线，就理解了 ph02 的结论：**每个 `.c` 独立编译**，编译期只看到声明，定义是否齐全要等链接期才见分晓——所以"编译过了却链接失败"是常态，二者是不同的错误类别。

### 4.2 链接器如何解析符号

每个目标文件 `.o` 都带一张**符号表（symbol table）**，记录两类符号：本文件**定义**的符号、本文件**引用**但未定义的符号。
```bash
nm math_utils.o        # T=本文件定义的函数, U=引用了但未定义的符号
nm app                 # 链接完成后, 所有引用都变成了具体地址
```
链接器（`ld`）的工作：把命令行里所有 `.o`/`.a`/`.so` 的符号表合并，**把每个"未定义引用"与其它文件中的"定义"配对，并执行重定位（relocation）——把引用处占位的地址改写为真实地址**。由此产生两类经典报错：
- `undefined reference to 'foo'`：没人定义 foo——漏编译了某 `.c`、漏链接了某个库、或 `-l` 顺序写反。
- `multiple definition of 'bar'`：两个 `.o` 都定义了 bar——重复定义；函数加 `static`（内部链接，ph02）可规避，或用 `inline`。
**要点**：静态库 `.a` 的链接语义特殊——**链接器只从库中抽取"被引用到"的 `.o` 成员**，所以库内文件的依赖顺序也有讲究；动态库的符号解析推迟到运行时（见 4.3）。

### 4.3 动态库与静态库的运行时差异

| 维度 | 静态库 .a | 动态库 .so |
|------|-----------|-----------|
| 链接时 | 代码拷入可执行文件 | 只写入依赖记录（`DT_NEEDED`）与符号版本 |
| 运行时 | 无外部依赖 | `ld.so` 先加载库再启动程序 |
| 内存占用 | 每进程一份代码拷贝 | **多进程共享同一份代码段**（节省内存） |
| 更新部署 | 必须重新链接 | 换 .so 文件即生效（ABI 兼容时） |
| 启动速度 | 快 | 多一次库加载与符号解析 |

**`-fPIC`（Position Independent Code，位置无关代码）**是共享库的必需品：普通可执行文件被装载到固定地址，指令里的地址直接写死；而共享库可能被映射到任意进程的任意虚拟地址，所以代码里的所有地址必须写成"**相对当前指令的偏移**"，装载到哪都能运行。实现上，全局数据与外部函数地址经 **GOT**（Global Offset Table）间接访问，函数调用经 **PLT**（Procedure Linkage Table）做首次调用的延迟绑定（lazy binding）——这是"换 .so 即生效"与"多进程共享"的底层前提。

### 4.4 调试信息格式（DWARF）与 GDB 如何映射回源码行

`-g` 生成的调试信息遵循 **DWARF**（Debugging With Attributed Record Formats）规范，它记录了三种关键映射：
- **源码行 ↔ 指令地址**（`.debug_line` 节）：让 GDB 知道"地址 0x401163 对应 crash.c 第 5 行"；
- **变量 ↔ 寄存器/栈位置**（`.debug_info` 节）：让 GDB 能 `print i` 找到变量存哪；
- **类型与函数信息**：让 `bt` 打印出带参数名的调用栈。

```bash
readelf --debug-dump=decodedline app   # 查看行号与地址的映射表
```
GDB 的机制由此可解：**断点 = 在目标行对应的指令地址写入陷阱指令（trap）**，CPU 执行到即陷入调试器；**单步 = 执行一条指令后立即停下，再把指令地址映射回源码行**；`print` 则按 DWARF 记录的位置去寄存器/栈里取当前值。

**要点**：
- **没有 `-g`，GDB 只剩裸地址**——看不到源码、变量、函数名，这是"GDB 不好用"的最常见原因；`-O2` 下变量可能被优化进寄存器甚至消除、行号错位，所以 **Debug 构建必须 `-g -O0` 搭配**（见 3.3）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 多文件项目构建 | gcc 多文件编译、Makefile、CMake |
| 代码质量把关 | -Wall、-Wextra、-Werror、警告即质量信号 |
| 崩溃定位 | GDB 断点/单步/print/backtrace、core dump |
| 发布性能版本 | Release 构建 `-O2 -DNDEBUG` |
| 代码复用封装 | 静态库 ar、动态库 -fPIC -shared、头文件接口 |
| 条件编译与多平台 | 预处理器、`-D` 宏、`#ifdef __linux__` |
| 自动化构建 / CI | Makefile 伪目标、CMake 配置-构建分离 |

**不适合**此阶段的事项：
- 线程并发调试（ph08：pthread 数据竞争、TSan、死锁分析）
- ASan/UBSan 等 Sanitizer 工具链系统化（ph11 专项）
- 性能剖析与热点优化（perf、gprof、火焰图，后续阶段）
- 内核模块 / 交叉编译与目标板调试（超出本阶段范围）

## 6. 代码示例

> 说明：示例均可在 Linux/macOS 上原样运行；示例 4 是故意写错的程序，用于演示 GDB 调试流程。每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 Apple clang 17（gcc 兼容）/ CMake 3.31，编译命令统一 `gcc -Wall -Wextra -std=c11`（命令见 examples/README.md）。

### 示例 1：多文件项目 + Makefile

对应 roadmap 练习"写一个多文件 C 项目"与"给前面项目写 Makefile"：复用 ph02 的 math_utils，用 Makefile 管理增量构建。

目录结构：
```text
project/
├── Makefile
├── math_utils.h
├── math_utils.c
└── main.c
```
`math_utils.h`：
```c
#ifndef MATH_UTILS_H
#define MATH_UTILS_H
int add(int a, int b);
int multiply(int a, int b);
int power(int base, int exp);
#endif
```
`math_utils.c`：
```c
#include "math_utils.h"
int add(int a, int b)      { return a + b; }
int multiply(int a, int b) { return a * b; }
int power(int base, int exp) {
    int r = 1;
    for (int i = 0; i < exp; i++) r *= base;
    return r;
}
```
`main.c`：
```c
#include <stdio.h>
#include "math_utils.h"
int main(void) {
    printf("add(2,3)=%d multiply(4,5)=%d power(2,10)=%d\n",
           add(2, 3), multiply(4, 5), power(2, 10));
    return 0;
}
```
`Makefile`：
```makefile
CC     = gcc
CFLAGS = -std=c11 -Wall -Wextra -g
TARGET = app
OBJS   = main.o math_utils.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c main.c

math_utils.o: math_utils.c math_utils.h
	$(CC) $(CFLAGS) -c math_utils.c

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
```
```bash
make && ./app
# 输出: add(2,3)=5 multiply(4,5)=20 power(2,10)=1024
make              # 再执行一次: 全部最新, 什么都不做 (增量构建生效)
touch main.c; make  # 只重编 main.o 并重新链接
make clean        # 清理产物
```

完整文件：`examples/ex01-makefile-project/`（Makefile + math_utils.h/c + main.c，4 个文件）

要点：头文件 `math_utils.h` 写进两个 `.o` 的依赖——改了接口声明，两个文件都会重编；`-Wall -Wextra` 保持零警告。

### 示例 2：静态库封装

对应 roadmap 练习"封装静态库"：把 math_utils 打成 `libmath.a`，另写一个调用方程序链接使用——这是"静态库形式的数据结构库"推荐项目的最小原型。

```bash
gcc -std=c11 -Wall -Wextra -c math_utils.c -o math_utils.o
ar rcs libmath.a math_utils.o      # 打包并生成符号索引
ar t libmath.a                     # 查看: math_utils.o
nm libmath.a                       # 查看库内符号: T add, T multiply, T power
```
`user.c`：
```c
#include <stdio.h>
#include "math_utils.h"            /* 接口: 只依赖头文件, 不依赖 .c */
int main(void) {
    printf("3 + 4 = %d\n", add(3, 4));
    printf("2^8 = %d\n", power(2, 8));
    return 0;
}
```
```bash
gcc -std=c11 -Wall -Wextra -c user.c -o user.o
gcc user.o -L. -lmath -o user      # 链接静态库
./user                             # 输出: 3 + 4 = 7 / 2^8 = 256
# 验证: 运行时不再需要 .a
mv libmath.a /tmp/ && ./user       # 仍正常运行
```

完整文件：`examples/ex02-static-lib/`（math_utils.h/c + user.c，3 个文件）

要点：静态库的链接语义是"按需抽取"——`ar rcs` 时按 `s` 生成符号索引，链接器只把被引用到的成员并入可执行文件；`-L.` 告诉链接器"当前目录找库"，`-lmath` 对应 `libmath.a`。

### 示例 3：动态库（-fPIC -shared）

在示例 2 基础上制作共享库，演示运行时链接与装载。

```bash
gcc -std=c11 -Wall -Wextra -fPIC -c math_utils.c -o math_utils_pic.o
gcc -shared math_utils_pic.o -o libmath.so
gcc user.o -L. -lmath -o user_so
ldd user_so        # 显示: libmath.so => not found (还没告诉系统去哪找)
LD_LIBRARY_PATH=. ./user_so   # 输出同示例 2
```
要点：
- 编译必须 `-fPIC`（位置无关代码，见 4.3），链接用 `-shared`；没有 `-fPIC` 时 `-shared` 会报"重定位需修改只读段"类错误。
- **运行时动态链接器按 `DT_NEEDED` 找库**：默认路径找不到就报 `error while loading shared libraries`；`LD_LIBRARY_PATH=.` 临时指定，正式部署放 `/usr/local/lib` 并执行 `ldconfig`。
- 动态库版本迭代只需替换 `.so` 文件（保持 ABI 兼容时），进程重启即生效，无需重新链接——这是线上热更依赖的基础。

完整文件：`examples/ex03-dynamic-lib/`（复用 ex02 的 math_utils + user.c，`-fPIC -shared` 编译）

### 示例 4：GDB 调试段错误

对应 roadmap 练习"用 GDB 调试段错误"：写一个故意越界的程序，完整走一遍"运行 → 崩溃 → bt → 查看变量 → 定位行号"。

`crash.c`：
```c
#include <stdio.h>

void fill(int *arr, int len) {
    for (int i = 0; i <= len; i++) {   /* 应为 i < len: 越界 */
        arr[i] = i * i;
    }
}

int main(void) {
    int nums[3] = {0};
    fill(nums, 3);
    for (int i = 0; i < 3; i++)
        printf("%d\n", nums[i]);
    return 0;
}
```
```bash
gcc -g -Wall -Wextra crash.c -o crash
./crash        # 段错误 (Segmentation fault)
gdb ./crash
```
```text
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401163 in fill (arr=0x7fffffffdde0, len=3) at crash.c:5
5               arr[i] = i * i;
(gdb) bt
#0  fill (arr=0x7fffffffdde0, len=3) at crash.c:5
#1  0x00000000004011a5 in main () at crash.c:11
(gdb) print i
$1 = 3
(gdb) print len
$2 = 3
(gdb) list 3,7
3       void fill(int *arr, int len) {
4           for (int i = 0; i <= len; i++) {
5               arr[i] = i * i;
6           }
7       }
(gdb) quit
```
再看"主动设断点 + 单步 + watch"的定位方式：
```text
(gdb) break crash.c:4        # 在循环条件处设断点
(gdb) run
(gdb) watch i                # i 每次变化都停下
(gdb) continue
# ... 观察 i 从 0,1,2 走到 3, 越过数组边界 nums[0..2] 时即可确认
```
要点：
- 崩溃信息直接给出**函数、参数、行号**（`fill at crash.c:5`）；`bt` 给出完整调用链（main → fill），`print i/len` 证实 `i=3` 越过了 `len=3` 的数组——`i <= len` 的 off-by-one 立刻现形。
- 调试完修正为 `i < len`，重新 `make`/`gcc` 后崩溃消失；**修 bug 的顺序永远是"先定位再修改"**，这正是调试器优于 printf 之处。

完整文件：`examples/ex04-gdb-debug.c`（故意越界示例，必须用 `-g` 编译后用 gdb 运行）

### 示例 5：CMake 最小项目

对应 roadmap 练习"能编写基础 CMakeLists.txt"：同一份 math_utils，用 CMake 组织"可执行文件 + 静态库"。

```text
cmake_demo/
├── CMakeLists.txt
├── math_utils.c
└── main.c
```
`CMakeLists.txt`：
```cmake
cmake_minimum_required(VERSION 3.10)
project(cmake_demo C)

add_library(math_utils STATIC math_utils.c)        # 静态库
add_executable(app main.c)                          # 可执行文件
target_link_libraries(app PRIVATE math_utils)       # 关键: 建立链接关系
target_compile_options(app PRIVATE -Wall -Wextra -g)
```
```bash
cmake -B build                # 配置: 生成 build/Makefile
cmake --build build           # 构建: 实际编译
./build/app                   # 运行
cmake --build build --target clean   # 或 rm -rf build 彻底重来
```
要点：
- 把 `STATIC` 改成 `SHARED` 即得到动态库版本（CMake 自动加 `-fPIC -shared`）——**同一种描述，两种产物**，这是 CMake 相比手写 Makefile 的主要收益。
- **坑：漏写 `target_link_libraries(app PRIVATE math_utils)` 会报 `undefined reference to 'add'`**——CMake 不自动推断链接，链接关系必须显式声明。

完整文件：`examples/ex05-cmake-project/`（CMakeLists.txt + math_utils.h/c + main.c，4 个文件）

## 7. 总结

### 关键要点

1. **警告是质量信号**：-Wall -Wextra 的每条警告都是编译器免费送的行级诊断，修警告比修崩溃便宜一个数量级
2. **Debug 与 Release 是两种产品**：`-g -O0`（可调试）vs `-O2 -DNDEBUG`（高性能），目标不同，不可混用
3. **Makefile 描述依赖关系，不只是命令集合**：正确写出依赖，Make 按时间戳只重编该重编的
4. **`-l` 库链接顺序有讲究**：使用库的文件在前、`-l` 在后，否则 `undefined reference`
5. **静态库拷代码，动态库记名字**：.a 链接时并入可执行文件；.so 运行时由 ld.so 加载、多进程共享
6. **`-fPIC` 是共享库的必需品**：位置无关代码保证 .so 装载到任意地址都能运行
7. **调试器比打印日志更适合定位崩溃**：断点/单步/print/bt 是对运行中程序的即时提问，无需改代码重编
8. **core dump 是崩溃现场快照**：`ulimit -c unlimited` 开启，`gdb ./app core` 离线分析线上崩溃
9. **错误信息本身指明阶段**：编译错误带行号、`undefined reference` 是链接问题、`SIGSEGV` 是运行期内存问题——先分类再动手
10. **没有 `-g` 就没有调试体验**：调试符号缺失时 GDB 只剩裸地址；`-O2` 下变量可能被优化消失

### 跨语言对比：构建与调试工具链

| 维度 | C/GCC | C++/CMake | Go | Java/Maven | Rust/Cargo |
|------|-------|-----------|-----|-----------|-----------|
| 编译器 | gcc、clang | g++、clang++ | go build（内建） | javac | rustc |
| 构建工具 | Makefile、CMake | CMake、Make | go build/go test（内建） | Maven、Gradle | cargo（内建） |
| 调试器 | GDB、lldb | GDB、lldb | delve | jdb | rust-gdb / lldb |
| 依赖管理 | 手写 `-L -l` 链接 | find_package / FetchContent | go mod | Maven 中央仓库 | crates.io |
| 构建描述 | 目标-依赖-规则 | CMakeLists.txt | go.mod（隐式） | pom.xml | Cargo.toml |
| 配置与发布 | `-D` 宏 / `-O2` / NDEBUG | CMake 构建类型 | 无传统概念 | Maven profile | --release / --debug |

C 的工具链最"手工"：没有内建包管理、没有统一的构建 DSL，Makefile/CMake/链接器每个环节都要自己掌握——但这正是存储引擎等系统软件的工程现实：**每一层都可见、可控、可调试**。

### 阶段验收清单

- [ ] 能从编译错误（带行号的语法/类型错误）与链接错误（`undefined reference`、`multiple definition`）中定位问题
- [ ] 能用 GDB（断点、单步、print、backtrace、watch）找到崩溃位置
- [ ] 能编写基础 Makefile（目标·依赖·规则、变量、伪目标）或 CMakeLists.txt（add_executable/add_library）
- [ ] 能用 -Wall -Wextra 把警告当质量信号处理，并理解 -Werror 的作用与代价
- [ ] 能用 ar 封装静态库、用 -fPIC -shared 制作动态库并正确链接
- [ ] 能生成并分析 core dump（ulimit -c unlimited + gdb ./app core）

### 动手练习

本阶段练习见 [exercises/](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：给前面项目写 Makefile、用 GDB 调试段错误、封装静态库、写一个多文件 C 项目共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [project/](./project/)：**多模块命令行工具**（文件统计工具，拆成 io/parse/report 三模块，Makefile 构建，验证增量构建与 GDB 调试）。

- [ ] 完成 exercises 全部练习并复盘
- [ ] 独立完成 project（通过 README 验收标准）

### 下一阶段

[Linux 系统编程阶段](../ph08-linux-sysprog/08-linux-sysprog.md) —— 文件描述符、open/read/write/close、fork/exec/wait、pthread、socket、epoll；届时把本阶段的 Makefile/GDB 能力应用到系统级程序上。
