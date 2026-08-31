# C++ 构建、调试与工具链阶段

> 面向高性能系统、存储引擎方向，本阶段把"能编译"升级为"能工程化地构建、能系统性地定位复杂问题"：理解编译链接流水线，会用静态库/动态库与 Makefile/CMake 组织多目标工程，并用 GDB/LLDB、Sanitizer、clang-tidy 等把质量关制度化。

## 1. 概述

本阶段定位：**看懂并亲手走一遍"预处理 → 编译 → 汇编 → 链接"的完整流水线，能读目标文件与符号表（nm/objdump）；会用 ar 打包静态库、会构建和链接动态库；会用 Makefile 与 CMake 组织多目标工程并理解增量构建；能用 GDB/LLDB 断点调试与 core dump 分析，用 Valgrind 与 ASan/UBSan 定位内存泄漏、越界与未定义行为，用 clang-tidy/clang-format/gcov 把代码质量关制度化**。学完本阶段，面对"Debug 正常、Release 崩溃"或"链接报 undefined reference"，能按"编译阶段 → 链接阶段 → 构建系统 → 调试器 → Sanitizer → 静态分析"的顺序系统排查，而不是靠打印日志瞎猜。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 编译流水线 | 预处理（-E）、编译（-S）、汇编（-c）、链接四阶段与中间产物 |
| 目标文件与符号表 | nm/objdump 读 T/t/D/S/b/U、Mach-O 段、符号名 mangling |
| 静态库 | ar 打包、链接器按需抽取、-L/-l 链接顺序 |
| 动态库 | -dynamiclib/-shared 构建、@rpath/DYLD_LIBRARY_PATH、运行时解析 |
| 构建工具 | Makefile（目标-依赖-规则、增量构建）、CMake（target/依赖/构建类型/多目标） |
| 构建类型 | Debug、Release、RelWithDebInfo 的分离使用与配置 |
| 模块化 | C++20 Modules（import/export module）与 BMI 编译模型 |
| 调试器 | GDB/LLDB 断点、单步、watch、backtrace、core dump 分析 |
| 内存检测 | Valgrind（memcheck）、ASan（AddressSanitizer）、UBSan |
| 静态分析 | clang-tidy（规则配置、运行、自动修复） |
| 格式化与覆盖率 | clang-format 自动格式化、gcov/lcov 覆盖率报告 |

这个阶段只涉及 C++ 工程的构建工具链核心（编译链接流水线、目标文件与符号表、静态库、动态库、Makefile/CMake 构建系统）与配套的调试/质量工具（GDB/LLDB、Valgrind、ASan/UBSan、clang-tidy、clang-format、gcov/lcov），**不涉及 C++ 标准演进与编译器差异、ABI 稳定性与 vcpkg/conan 依赖管理（ph11）、对象生命周期与值类别深入（ph12，目录待建）、UB 与内存安全系统化（ph15，目录待建）、测试/静态分析/代码规范系统化（ph16，目录待建）、性能剖析深入（ph18，目录待建：perf/火焰图——本阶段 `-pg`/gcov 只做覆盖率与基础计时）和 ABI 与动态库插件机制深入（ph19，目录待建：符号可见性、版本控制、插件 ABI——本阶段只做动态库的构建与运行时链接）** — 那些是后续阶段的内容。承接 ph09 文件网络系统编程阶段：ph09 的单文件 `c++` 编译在本阶段升级为多目标工程化构建。

## 2. 来源与演变

构建工具的演化是"从命令序列到依赖图，再到工程描述"：早期工程用 shell 脚本逐条调用 g++，改一个文件就全量重编；1976 年贝尔实验室的 **Make** 用"目标-依赖-规则"按时间戳做增量构建，但语法原始、跨平台差、表达"库 A 依赖 B、B 又依赖 C"的传递关系很痛苦。2000 年 Kitware 推出 **CMake**：先用 CMakeLists.txt 描述"构建哪些目标、目标间什么关系"，再由生成器产出 Makefile 或 **Ninja** 脚本——配置与构建分离、一套描述跨平台，成为 C/C++ 工程事实标准；**Bazel/Meson** 在大型单体仓库与强缓存方向继续探索，但 CMake 的生态地位至今稳固。

编译流水线本身比构建工具更古老：**预处理与编译分离**可以追溯到 C 语言诞生（1972），宏、条件编译让"一份源码适配多平台"成为可能；汇编器与链接器则来自更早的系统软件传统——链接器把多个编译单元的目标文件合并、解析符号，这一模型从 1960 年代延续至今，是理解一切构建工具的底层心智。

C++20 给构建模型带来结构性变革：**Modules（模块）** 用 `import`/`export module` 取代 `#include`，编译器把模块编译成 **BMI**（Binary Module Interface）并缓存，不再逐文件展开头文件文本——编译速度提升、符号隔离成为 C++20 最受关注的构建特性。工具链同步成熟：1986 年 Stallman 写出 **GDB**，配合 `-g` 的 **DWARF** 调试信息实现符号化调试；Apple 主导的 **Clang/LLVM**（2009）带来可读错误信息与 **LLDB**，并孵化出 **ASan/UBSan**、**clang-tidy** 这一整套免费质量工具——Sanitizer 用编译期插桩抓运行时内存错误，比 Valgrind 的纯动态模拟快一个数量级，成为现代 C/C++ 工程的标准配置。

| 里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Make（贝尔实验室） | 1976 | 目标-依赖-规则成型，增量构建诞生 |
| GDB（Stallman） | 1986 | 符号化调试（DWARF）成为可能 |
| CMake（Kitware） | 2000 | 构建系统生成器，配置-构建分离，C/C++ 事实标准 |
| Clang/LLVM | 2009 | 可读错误信息、LLDB、libclang 工具链生态 |
| ASan（Chrome 团队） | 2011 | GCC/Clang 内置地址消毒器，插桩式内存检测 |
| clang-tidy | 2012 | 基于 Clang AST 的静态分析，可自动修复 |
| C++20 | 2020 | Modules 入标准，import/export 取代 #include 的构建模型 |
| 近年 | — | Ninja/Bazel 更快构建与增量缓存；CMake 可生成 Ninja 作为后端 |

本文示例以 **C++20** 为基线（roadmap 自第 6 节起主线使用 C++20 特性，`-std=c++20` 是当前稳定度与功能的平衡点），验证工具链为本机 Apple clang 21（`c++`，g++ 兼容）+ LLVM 版 `nm`/`objdump`/`ar`（Mach-O 格式）+ GNU Make 3.81 + CMake 4.2.3，全部示例已在本环境实际编译运行验证（已验证）。编译器对 C++20 各特性的支持差异、`-std` 开关之外的移植性细节属于 ph11 标准与可移植性阶段——本阶段把 `-std=c++20` 当开关用即可。这套构建工具链的语法与参数是 C/C++ 生态里**最稳定、最值得先掌握**的部分：二十多年没大改，学会后长期复用。

## 3. 语法与参数

### 3.1 编译流水线：预处理 → 编译 → 汇编 → 链接

**必会概念：一次 `c++ main.cpp -o app` 背后是四个可拆分的阶段，每阶段都有独立命令与中间产物**。用 `-E`/`-S`/`-c` 把流水线摊开看（完整示例见 `examples/ex01-pipeline.cpp`）：

```bash
# 1. 预处理（-E）：宏展开、#include 头文件文本插入、条件编译——产物是纯文本源码
c++ -std=c++20 -Wall -Wextra -E ex01-pipeline.cpp -o /tmp/ex01.i
# 2. 编译（-S）：语法/语义检查 + 优化，产出汇编（模板实例化、constexpr 求值发生在此）
c++ -std=c++20 -Wall -Wextra -S ex01-pipeline.cpp -o /tmp/ex01.s
# 3. 汇编（-c）：汇编器把汇编翻译成机器码目标文件 .o（含符号表与重定位表）
c++ -std=c++20 -Wall -Wextra -c ex01-pipeline.cpp -o /tmp/ex01.o
# 4. 链接：把多个 .o 与库的符号解析配对、重定位地址，产出可执行文件
c++ -std=c++20 -Wall -Wextra ex01-pipeline.cpp -o /tmp/ex01-app
/tmp/ex01-app
```

本机实测的中间产物证据（已验证）：`-E` 输出里宏被原位展开为 `(sizeof(vals) / sizeof((vals)[0]))`；`-S` 输出里出现模板实例化符号 `__Z5twiceIiET_S0_`（`twice<int>`）；`nm` 目标文件能看到 `T __Z5clampiii`（全局函数）、`t __ZL13hidden_helperi`（static 函数）、`U _printf`（未定义，链接期从 libc 解析）。

要点：

- **编译单元（Translation Unit）** 是"一个 .cpp + 它 include 的所有头文件展开后的整体"，编译的最小单位；**头文件改 → 所有包含它的 .cpp 都要重编**，这正是后面 Makefile/CMake 增量构建要管理的依赖（见 3.5、4.2）
- **坑：`-Wall -Wextra` 只覆盖编译阶段**——语法、类型、未使用变量等前端诊断；链接期错误（undefined reference）与运行期错误（越界）它都管不到，各阶段错误要各阶段查
- 四个阶段可拆可合：交叉编译只需换编译器前缀（如 `aarch64-linux-gnu-g++`），流水线本身不变；单文件小项目可以一步到位，工程化项目才需要拆分管理（为什么拆分见 4.1）

### 3.2 目标文件与符号表：nm / objdump

**必会概念：目标文件是"符号 + 机器码 + 元数据"的容器，符号表是链接器的地图**。编译单元之间靠符号连接：函数名、全局变量名被 mangle 成唯一符号（如 `gcd` → `__Z3gcdii`），链接器靠符号配对跨文件引用。用 nm/objdump 读它（完整示例见 `examples/ex04-symbols.cpp`）：

```bash
c++ -std=c++20 -Wall -Wextra -c ex04-symbols.cpp -o /tmp/ex04-symbols.o
nm /tmp/ex04-symbols.o        # 符号表，字母 = 类型
objdump -t /tmp/ex04-symbols.o   # 带段信息的符号表
objdump -h /tmp/ex04-symbols.o   # 段表：__text（代码）/ __data / __common / __bss
```

本机实测符号表（已验证，Apple/LLVM nm、Mach-O）：

| 源 | 符号 | nm 字母 | 含义 |
|----|------|---------|------|
| `int global_add(int,int)` | `__Z10global_addii` | `T` | 已定义全局函数（__text 段） |
| `static int hidden_util(int)` | `__ZL11hidden_utili` | `t` | 静态函数，仅本翻译单元可见 |
| `int g_counter = 5` | `_g_counter` | `D` | 非零初始化全局（__data 段） |
| `int g_zero = 0` | `_g_zero` | `S` | 零初始化全局（__common；Linux ELF 上是 `B`） |
| `static int s_hits = 0` | `__ZL6s_hits` | `b` | 静态变量（__bss，局部） |
| `std::printf` 引用 | `_printf` | `U` | 未定义，链接期从 libc 解析 |

要点：

- **字母跨平台微调**：`T/t/U` 在 Apple 与 Linux 一致；零初始化全局本机是 `S`（__common），Linux ELF 是 `B`；符号名本机带前缀下划线（`__Z...` = 单下划线 + Itanium ABI 的 `_Z`）——ABI 与符号命名的深入属 ph19
- **undefined reference 是链接错误**：声明了但没定义（或库没链接上）的符号，在链接阶段报 `Undefined symbols for architecture arm64: "_foo"`——先 `nm` 确认符号在哪个 .o/库，再检查依赖是否声明（见 3.3/3.6）
- **duplicate symbol 同理**：两个 .o 定义了同名全局符号 → 链接冲突；`static`/匿名命名空间是"只在当前翻译单元可见"的隔离手段

### 3.3 静态库：ar 打包与按需抽取

**必会概念：静态库（`.a`/`.lib`）是目标文件的归档集合，链接时按"被引用到的成员"抽取并入可执行文件**。打包与验证（完整示例见 `examples/ex02-*`）：

```bash
c++ -std=c++20 -Wall -Wextra -c ex02-libstat.cpp  -o /tmp/ex02-libstat.o
c++ -std=c++20 -Wall -Wextra -c ex02-libmath.cpp -o /tmp/ex02-libmath.o
ar rcs /tmp/libex02.a /tmp/ex02-libstat.o /tmp/ex02-libmath.o   # r=插入 c=静默 s=索引
ar t /tmp/libex02.a          # 列出归档成员
nm /tmp/libex02.a            # 每个成员的符号表
c++ -std=c++20 -Wall -Wextra ex02-main.cpp -L/tmp -lex02 -o /tmp/ex02-app
/tmp/ex02-app
```

要点：

- **按需抽取（demand loading）**：链接器只把"被引用到的 .o 成员"并入可执行文件。本机实测：消费者只调用 gcd/lcm，链接后 `nm` 可执行文件里**没有** is_prime/factorial（它们所在的成员未被引用）——这就是"静态库体积大但可执行文件只带走用到的部分"的原理
- **链接顺序坑**：使用库的文件在前、`-l` 在后（`main.cpp lib.a` 或 `main.o -lfoo`），反了报 undefined reference；静态库只做一次向前扫描
- 静态库的代码在链接时**已并入可执行文件**，部署不用带 .a，但库更新要重新链接——与 3.4 动态库正好相反

### 3.4 动态库：构建与运行时解析

**必会概念：动态库（macOS `.dylib` / Linux `.so`）的符号解析推迟到运行时**——可执行文件只记录"依赖哪个动态库"（DT_NEEDED/@rpath 条目），加载器（dyld/ld.so）在启动时按查找路径解析（完整示例见 `examples/ex03-*`）：

```bash
# 1. 构建动态库（macOS 用 -dynamiclib；Linux 对应 -shared -fPIC，macOS 默认已 PIC）
c++ -std=c++20 -Wall -Wextra -dynamiclib -install_name @rpath/libex03.dylib \
    ex03-dynlib.cpp -o /tmp/libex03.dylib
nm -gU /tmp/libex03.dylib      # 导出符号
# 2. 消费者链接（记录依赖 @rpath/libex03.dylib）
c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L/tmp -lex03 -o /tmp/ex03-app
# 3. 直接运行 → 失败：找不到库（本机实测报错如下，这是教学点不是 bug）
/tmp/ex03-app
#    dyld[PID]: Library not loaded: @rpath/libex03.dylib
#      Referenced from: <...> /tmp/ex03-app
#    Reason: no LC_RPATH's found    （Linux 对应 error while loading shared libraries）
# 4. 运行时指定查找路径 → 成功（Linux 用 LD_LIBRARY_PATH）
DYLD_LIBRARY_PATH=/tmp /tmp/ex03-app
# 5. 或链接期写入 rpath → 直接运行
c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L/tmp -lex03 \
    -Wl,-rpath,@loader_path/. -o /tmp/ex03-rpath
/tmp/ex03-rpath
otool -L /tmp/ex03-app        # 查看依赖的动态库（Linux 用 readelf -d）
```

要点：

- **运行时报错的排查顺序**：`otool -L`（依赖什么）→ 确认库在不在 → 确认查找路径（DYLD_LIBRARY_PATH / rpath）→ 确认库与可执行文件架构一致（`file` 查看，arm64 vs x86_64）
- 动态库更新**无需重链接**消费者（只要接口不变），但部署必须带库文件并保证查找路径——静态库/动态库的取舍见第 5 章
- 本阶段只做动态库的构建与运行时链接：**符号可见性（visibility）、版本控制与插件 ABI 属于 ph19 ABI、动态库与插件机制阶段（目录待建）**，这里只需理解"编译期记录依赖、运行期解析地址"这条主线

### 3.5 Makefile：目标-依赖-规则与增量构建

**必会概念：Makefile 是"目标 → 依赖 → 规则"的声明，make 按时间戳决定重编谁**。1976 年的核心机制至今未变——目标比依赖旧就执行规则（完整示例见 `examples/ex05-make/`，工程化多目标版见 project/）：

```make
# examples/ex05-make/Makefile（节选）
CXX      := c++               # 用 := 而非 ?=：环境可能已导出 CC/CXX，?= 不会覆盖
CXXFLAGS := -std=c++20 -Wall -Wextra
OBJDIR   := build
TARGET   := $(OBJDIR)/calc
OBJS     := $(OBJDIR)/calc.o $(OBJDIR)/main.o

$(TARGET): $(OBJS)                       # 目标依赖两个 .o
	$(CXX) $(CXXFLAGS) $^ -o $@

$(OBJDIR)/calc.o: calc.cpp calc.h | $(OBJDIR)   # 头文件也写进依赖！
	$(CXX) $(CXXFLAGS) -c calc.cpp -o $@
```

```bash
make                # 全量构建（产物在 build/，源码目录不落 .o）
make run            # 构建并运行
make clean          # rm -rf build
```

增量实测（已验证，GNU Make 3.81，touch 前先 `sleep 1`——3.81 只比较秒级时间戳，同秒内 touch 会被当作"未更新"）：

- `sleep 1 && touch calc.cpp && make` → 只重编 `build/calc.o` 并重链接，`main.o` 未动；
- `sleep 1 && touch calc.h && make` → `calc.o` 与 `main.o` **都**重编（头文件依赖生效）；
- 无改动再 `make` → `make: Nothing to be done for 'all'.`

要点：

- **头文件必须写进依赖**：漏写头文件依赖是 Makefile 最常见的坑——头文件改了但依赖它的 .o 不重编，产物带旧声明，出现"明明改了却不变"的诡异行为；工程上可用 `g++ -MM` 自动生成依赖（见 project/README 扩展方向）
- **坑：make 只认时间戳**，不认内容；时钟回拨、同秒 touch 都会造成漏判/重编
- `.PHONY` 声明伪目标（all/clean/test 等不产出文件的"动作目标"）；`:=` vs `?=` 的取舍见示例注释

### 3.6 CMake 核心：target 与依赖

**必会概念：CMake 管目标和依赖，不只是生成 Makefile**。CMakeLists.txt 的最小单元是 **target**（add_library / add_executable），target 之间用 `target_link_libraries` 建立依赖并传递属性——这是 CMake 相比手写 Makefile 的核心价值：依赖关系写在描述里，生成器翻译成具体的编译/链接命令（完整示例见 `examples/ex06-cmake/`，工程化形态见 project/）。

```cmake
cmake_minimum_required(VERSION 3.16)
project(ph10_demo CXX)

add_library(math_utils STATIC math_utils.cpp)   # 静态库目标
add_executable(app main.cpp)                     # 可执行目标
target_link_libraries(app PRIVATE math_utils)    # 依赖：app 链接 math_utils
target_compile_options(app PRIVATE -Wall -Wextra)
```

```bash
cmake -B build          # 配置：读 CMakeLists.txt，生成 build/Makefile（或 Ninja）
cmake --build build     # 构建：实际编译链接
./build/app             # 运行
cmake --build build --target clean   # 清理；或 rm -rf build 彻底重来
```

要点：

- 库类型 `STATIC`（静态）/ `SHARED`（动态）/ `INTERFACE`（纯头文件接口库）；依赖可见性 `PRIVATE`（仅自己）/ `PUBLIC`（自己 + 下游）/ `INTERFACE`（仅下游）
- **坑：漏写 `target_link_libraries` 报 `undefined reference`**——CMake 不自动推断链接关系，依赖必须显式声明（同 3.3 的链接顺序教训，CMake 帮你把顺序写对）
- **坑：CMake 变量有目录作用域**——子目录/函数里 `set()` 的变量不影响父作用域，跨目录传值用 `target_*` 属性或 `PARENT_SCOPE`

### 3.7 CMake 配置：构建类型与 C++ 标准

**必会概念：Debug/Release/RelWithDebInfo 应分开使用**——三种构建类型是"三种产品"，不是同一个程序换个名字。

| 构建类型 | 优化 | 调试信息 | 断言 | 用途 |
|----------|------|---------|------|------|
| Debug | `-O0 -g` | 完整 | 保留 | 开发、断点调试 |
| Release | `-O3 -DNDEBUG` | 无 | 关闭 | 交付、线上 |
| RelWithDebInfo | `-O2 -g` | 完整 | 关闭 | 线上崩溃分析（可发布又可回放 core） |

```cmake
cmake_minimum_required(VERSION 3.16)
project(ph10_conf CXX)

set(CMAKE_CXX_STANDARD 20)                  # 要求 C++20
set(CMAKE_CXX_STANDARD_REQUIRED ON)         # 编译器不满足直接报错
set(CMAKE_CXX_EXTENSIONS OFF)               # 禁用 GNU 扩展，保持可移植
add_executable(app main.cpp)
```

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake -B build-rel -DCMAKE_BUILD_TYPE=Release   # 独立构建目录，两种产品并存
cmake --build build && cmake --build build-rel
```

要点：

- **坑：构建类型混用**——"Debug 正常、Release 崩"先怀疑 UB（见 3.12），也要确认是否 `-DNDEBUG` 关掉了 assert、`-O3` 改变了行为；**单目录反复切构建类型易踩缓存**，不同构建类型用不同 build 目录
- **坑：`CMAKE_CXX_STANDARD` 只是"最低要求"**——不配 `CMAKE_CXX_STANDARD_REQUIRED ON` 时编译器会悄悄 fallback，`#include <format>` 可能静默编译失败
- 多配置生成器（Visual Studio/Xcode）用 `--config Release` 选构建类型，不用 `-DCMAKE_BUILD_TYPE`

### 3.8 多目标项目组织：子目录与库

工程化项目按"库 + 可执行 + 测试"分层：业务逻辑放库，入口与测试放可执行目标，每个子目录一个 `add_subdirectory`。**目标名是全局的**，子目录间直接按名字引用（工程化完整实现见 project/）。

```text
project/
├── CMakeLists.txt          # 顶层：add_subdirectory 汇总
├── core/                   # add_library(core ...) 业务库
├── app/                    # add_executable(app ...) 入口
└── tests/                  # add_executable(tests ...) + enable_testing()
```

`core/CMakeLists.txt`：

```cmake
add_library(core STATIC logger.cpp config.cpp)   # 头文件不必列出
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})  # 下游可见头文件
target_compile_features(core PUBLIC cxx_std_20)  # 传递"至少 C++20"
```

要点：

- **`target_include_directories` 可见性要匹配**：库对外头文件用 `PUBLIC`，下游才能 `#include <core/logger.h>`；纯内部头用 `PRIVATE`
- **坑：用 `include_directories()` 全局改 include 路径**——影响整个目录树、无法表达"谁需要谁"，多目标项目一律用 `target_*` 系列
- 测试用 `add_test` + `ctest` 注册（示例见 examples/ex06-cmake，深入属 ph16 测试阶段）；`INTERFACE` 库适合"纯头文件库"（如对 nlohmann/json 的封装层）

### 3.9 C++20 Modules 基础（import / export module）

**必会概念：Modules 替代 #include，提升编译速度和隔离性**。模块把声明与实现编译成二进制接口（BMI），调用方 `import` 时直接读 BMI，不再展开头文件文本——**未 export 的符号对调用方不可见**，隔离性天然成立。

```cpp
// math.cppm —— 模块单元（module unit）
export module math_utils;                       // 定义模块名
export int add(int a, int b) { return a + b; }  // export 的才对外可见
```

```cpp
// main.cpp —— 模块消费者
import math_utils;
int main() { return add(2, 3) == 5 ? 0 : 1; }
```

```bash
# clang++：先编译模块单元产出 BMI，再编译消费者
clang++ -std=c++20 --precompile math.cppm -o math_utils.pcm
clang++ -std=c++20 -fmodule-file=math_utils=math_utils.pcm main.cpp math_utils.pcm -o app
./app
```

要点：

- **坑：Modules 的编译器支持差异很大**——GCC 支持不完整、MSVC/Clang 各有各的 `-fmodule-*` 标志与扩展名约定，**标准发布至今工具链仍未完全收敛**；学概念用 clang++ 单文件演示，工程上保守用传统头文件
- `export module 名字` 定义模块、`export 符号` 控制可见性、`import` 顺序无关；模块名通常与文件路径对应
- 编译模型差异（BMI 缓存、按模块重编）见 4.4——**Modules 不解决依赖图问题**，工程依赖仍要 CMake 管理

### 3.10 g++ / clang++ 编译选项回顾与进阶

3.1 已用过 `-E/-S/-c`，ph02 已会用 `g++ main.cpp -o app`，本阶段把选项体系补齐并理解其组合：

```bash
c++ -std=c++20 -Wall -Wextra -g -O0 main.cpp -o app_debug       # Debug
c++ -std=c++20 -Wall -Wextra -O2 -DNDEBUG main.cpp -o app_rel   # Release
c++ -std=c++20 -O2 -pg main.cpp -o app_prof && ./app_prof        # -pg 配 gprof（ph18 深入）
gprof app_prof gmon.out
# 注：-pg/gprof 是 GNU/Linux 传统链路；本机（macOS）无 gprof、-pg 不产 gmon.out，
#     未在本环境验证——性能剖析实操到 Linux 环境或 ph18 阶段进行
clang++ -std=c++20 -Wall -Wextra -O2 main.cpp -o app_clang       # clang 与 gcc 基本兼容
```

| 选项 | 作用 |
|------|------|
| `-std=c++17/c++20/c++23` | 指定语言标准 |
| `-Wall -Wextra` | 常用警告 + 额外警告（`-Werror` 升级为错误） |
| `-g` | 生成 DWARF 调试信息，GDB/LLDB 必需 |
| `-O0/-O1/-O2/-O3` | 优化级别；`-O0` 便于调试、`-O2` 默认发布级 |
| `-DNDEBUG` | 关闭 `assert`（Release 标配） |
| `-pg` | 插入剖析代码，配合 gprof 输出 gmon.out |
| `-fsanitize=address,undefined` | 启用 ASan + UBSan 插桩（见 3.12） |

要点：

- **坑：`-Werror` 误用**——第三方头文件/未清理老代码触发一堆警告时，`-Werror` 让构建直接挂；CI 用前先确认依赖树零警告，或 `-Wno-error=具体警告` 局部豁免
- **坑：`-O2` 下变量可能被优化进寄存器甚至消除**——调试必须 `-g -O0` 搭配，`-O2 -g` 断点时变量值可能"看不到"
- 链接顺序规则依然成立：**使用库的文件在前、`-l` 在后**，反了报 `undefined reference`（见 3.3）

### 3.11 GDB / LLDB 调试：断点·watch·core dump

GDB（GNU）与 LLDB（LLVM 系，macOS 默认）命令高度对应，掌握 GDB 即掌握 LLDB：

| GDB | LLDB | 作用 |
|-----|------|------|
| `b main` / `b 12` | `breakpoint set -n main` | 函数/行号断点 |
| `r` / `n` / `s` | `run` / `next` / `step` | 运行 / 单步（不进入/进入函数） |
| `p 变量` | `p` / `frame variable` | 打印变量 |
| `bt` | `bt` | 调用栈（崩溃定位第一命令） |
| `watch i` | `watchpoint set variable i` | 变量变化即停 |
| `c` / `q` | `continue` / `quit` | 继续 / 退出 |

core dump 是进程崩溃瞬间的内存映像——**线上程序崩了，把 core 拿回来就能离线回放现场**：

```bash
ulimit -c unlimited      # 默认常为 0（禁止 core），先开启
./app                    # 段错误 → 生成 core 文件
gdb ./app core           # 离线分析，无需重跑
(gdb) bt                 # 直接看崩溃时调用栈
# 注：GDB/core dump 流程为 Linux 链路，本机（macOS）无 gdb、默认不产 core，
#     未在本环境验证；macOS 断点调试用系统自带 lldb（命令对照见上表）
```

要点：

- **没有 `-g` 就没有调试体验**——GDB 只剩裸地址；systemd 系统 core 由 `coredumpctl` 托管（`coredumpctl gdb app`）；**确认程序与 core 同一版本**，否则行号错位
- **坑：`watch` 被优化变量**——`-O0` 下最可靠；命中后先用 `bt` 确认是谁改的
- macOS 上 GDB 需要签名配置，直接 `lldb`（系统自带）即可，命令对照见上表

### 3.12 Valgrind 与 ASan / UBSan：内存与 UB 检测

**Valgrind（memcheck）** 是纯动态分析：模拟执行、跟踪每块内存的读写与释放，**不需要重新编译**，慢 20~50 倍但零改动：

```bash
c++ -std=c++20 -g leak.cpp -o leak
valgrind --leak-check=full ./leak      # 越界/未初始化/泄漏/double-free 全报
# 注：本机未安装 valgrind（macOS 支持滞后），未在本环境验证——内存检测在本阶段
#     以 ASan/UBSan 为主（见下），Valgrind 建议在 Linux 环境实操
```

**ASan（AddressSanitizer）** 是编译期插桩：编译器在每次内存访问前后插入检查，配合影子内存（见 4.5）抓越界、use-after-free、泄漏——比 Valgrind 快一个数量级，CI 标配：

```bash
c++ -std=c++20 -g -fsanitize=address,undefined -fno-omit-frame-pointer bug.cpp -o bug
./bug                                  # 崩在越界点，打印详细报告
ASAN_OPTIONS=detect_leaks=1 ./bug      # 打开泄漏检测
```

本机实测报告要点（已验证，故意越界程序）：`ERROR: AddressSanitizer: heap-buffer-overflow`、`WRITE of size 4`、地址落在 `0 bytes after 16-byte region`（越界点紧邻分配区末尾）——错误类型、操作、位置三要素齐全。本机验证环境的沙箱限制外部符号化器启动，报告退化为"函数 + 偏移"形式；常规环境（Linux CI 等）会带 `file:line` 精确定位。

要点：

- **坑：ASan 与 Release 混用**——`-fsanitize=address` 要配 `-O0/-O1`，与 `-O2` 混用会误报/漏报；ASan 只检测"编译进插桩的代码"，第三方 .so 不插桩就检不到
- **UBSan 抓未定义行为**：整数溢出、空指针解引用、移位越界等，与 ASan 可同时开；`-fno-sanitize-recover=all` 让 UB 直接终止而非继续
- 分工：**快速定位用 ASan（要重编译），快速验证已有二进制用 Valgrind（不重编译）**；Valgrind 对未初始化读取更敏感，ASan 对越界/释放更精准。动手练习见 exercises/ 练习 2

### 3.13 clang-tidy 静态分析

**必会概念：静态分析能提前发现大量低级错误**。clang-tidy 基于 Clang 的 AST 在**编译期**检查代码、不运行程序——能抓编译器警告抓不到的问题：`std::move` 误用、生命周期悬垂、性能反模式：

```bash
clang-tidy main.cpp -checks='-*,modernize-loop-convert,modernize-use-auto,modernize-use-nullptr,performance-for-range-copy' -- -std=c++20
clang-tidy main.cpp -checks='-*,modernize-*' --fix -- -std=c++20   # 自动修复安全部分
```

| 规则组 | 抓什么 | 典型例子 |
|--------|--------|---------|
| `clang-analyzer-*` | 内存/空指针/逻辑错误 | null 解引用、泄漏路径 |
| `bugprone-*` | 易错写法 | 拷贝粘贴错误、可疑比较 |
| `performance-*` | 性能反模式 | 循环里值拷贝、慢循环 |
| `modernize-*` | 现代 C++ 风格 | auto、range-based for、智能指针替换裸 new |
| `readability-*` | 可读性 | 命名、复杂度过高 |

本机实测（已验证，Homebrew LLVM 21 的 clang-tidy）：对含 4 类反模式的代码一次报出 `modernize-loop-convert`（下标循环）、`modernize-use-auto`（冗长迭代器）、`modernize-use-nullptr`（NULL）、`performance-for-range-copy`（值拷贝循环）四条警告；`--fix` 自动改写后复检零警告。

要点：

- **clang-tidy 需要编译参数**（`--` 后的 `-std`、include 路径），真实项目配 `compile_commands.json`（CMake 生成，见 4.3）自动获得——**坑：不给编译参数时按默认旧标准分析，误报一堆**
- 先跑少量规则组（几类 modernize/performance）抓真问题，再按项目增补，**别一次性全开**（误报率爆炸）
- **坑：clang-tidy 与编译器警告不同源**——`-Wall` 是前端诊断，clang-tidy 是 AST 独立分析，两者互补、不能互相替代；规则配置的系统化深入属 ph16 测试、静态分析与代码规范阶段（目录待建）

### 3.14 clang-format 格式化自动化

**必会概念：格式化应自动化**——格式是机器的事，不是人肉审美；clang-format 按 `.clang-format` 配置统一排版：

```bash
clang-format -style=llvm -i main.cpp            # 按 LLVM 风格直接改文件
clang-format --dry-run -Werror main.cpp         # 只检查不改：CI 里"格式不过就失败"
clang-format -style=file -i src/*.cpp src/*.h   # 读项目根目录 .clang-format
```

`.clang-format`（提交进仓库）：

```yaml
BasedOnStyle: Google          # 以 Google 风格为基础
IndentWidth: 4                # 覆盖为 4 空格
ColumnLimit: 100              # 行宽 100
SortIncludes: true            # 自动排序 #include
```

要点：

- 风格之争没有标准答案（Google/LLVM/WebKit…），**选一个进仓库全员统一**，比"哪个更好"重要；`// clang-format off/on` 保护手排的表格/对齐代码
- **自动化落地**：编辑器保存时格式化、git pre-commit hook、CI 里 `--dry-run -Werror`——diff 只含业务改动
- **坑：clang-format 只管排版**——命名、语义、逻辑仍要人工与 clang-tidy 把关

### 3.15 gcov / lcov 覆盖率

覆盖率回答"测试跑到了多少代码"：**gcov** 是 GCC 的覆盖率工具（`--coverage` 插桩，运行时写 `.gcda`），**lcov** 把 gcov 原始数据转成 HTML 报告：

```bash
c++ -std=c++20 -O0 -g --coverage main.cpp -o main
./main                                  # 生成 .gcda 数据
gcov main-main.gcno                     # 文本报告：每行命中次数（文件名见下）
lcov --capture --directory . --output-file coverage.info
genhtml coverage.info --output-directory html
# 浏览器打开 html/index.html：红=未覆盖 绿=覆盖
```

要点：

- **覆盖率是"证据"不是"目标"**——100% 行覆盖也可能漏掉关键分支；先看核心逻辑（解析、协议、边界处理）有没有测试跑到
- **坑：`--coverage` 与 `-O2` 混用**——优化合并/重排代码行，行号对不上源码，覆盖率失真；覆盖率构建用 `-O0 -g`
- **产物文件名随工具链不同**：本机 Apple clang 的 `.gcno/.gcda` 命名为"可执行名-源文件名"（如 `main-main.gcno`），`gcov` 要显式传该文件名；Linux GCC 是"源文件名.gcno"（`gcov main.cpp` 即可）——命令差异如实记录，见 exercises/ 练习 4
- **lcov/genhtml 本机未安装、未在本环境验证**：安装 `brew install lcov` 后按上面命令执行；工程化 CI 用法：`lcov --remove coverage.info '*/tests/*' -o filtered.info` 排除测试自身后设覆盖率阈值，不达标构建失败

## 4. 底层原理

### 4.1 编译流水线与翻译单元：为什么分四阶段

```text
源文件.cpp ──(-E)──▶ 纯净源码.i ──(-S)──▶ 汇编.s ──(-c)──▶ 目标文件.o ──链接──▶ 可执行文件
```

每个箭头对应一个阶段与产物：`-E` 展开宏与头文件、`-S` 做语义检查与优化并产出汇编、`-c` 产出带符号表/重定位表的目标文件、链接解析符号并绑定地址。四阶段分离不是历史包袱，而是三个现实需求的产物：

1. **增量编译**：头文件/依赖改了只重编受影响单元，链接器负责合并——没有"目标文件"这个中间层，每次小改都要全量重编译；
2. **交叉编译**：换目标平台只换汇编器/链接器（或整个编译器前缀），流水线形状不变；
3. **工具复用**：预处理（宏/条件编译）、优化（-O2）、插桩（ASan）是独立可插拔阶段，编译器可以"编译一半"停下给其他工具用（如 `-S` 看汇编、`--coverage` 插桩）。

每个 `.o` 携带**符号表**（对外提供/需要的符号）与**重定位表**（代码里待填的地址坑位），链接器据此把多个翻译单元"拼"成一个地址空间连续的进程映像——这就是 3.2 里 nm 能看到的一切的物理基础。

### 4.2 链接与依赖图：符号解析、按需抽取、target 传递性

C++ 编译单元（.cpp → .o）靠**符号**连接：链接器把"未定义引用"（U）与"其它文件的定义"（T/D）配对并做重定位；配对不上的报 undefined reference，配到两个报 duplicate symbol。静态库（.a）是 .o 的集合，链接器按"被引用"逐成员抽取（3.3 已实测）；动态库则只记录依赖、地址留到运行时由加载器解析（3.4）。

CMake 的 target 图正是这张符号依赖图的高层描述——**`target_link_libraries(app PRIVATE core)` 不只是"链接时加 -lcore"，而是建立属性传递**：

| 属性 | PRIVATE | PUBLIC | INTERFACE |
|------|---------|--------|-----------|
| 链接库（-l） | 仅 app | app + 下游 | 仅下游 |
| include 目录 | 仅 app | app + 下游 | 仅下游 |
| 编译选项/特性 | 仅 app | app + 下游 | 仅下游 |

"头文件互相 include 却漏了链接关系"报 `undefined reference`，就是依赖图没建全的典型症状——**Makefile/CMake 的价值在于把这张图声明出来并翻译成正确的命令行**（Makefile 用手写依赖，CMake 用 target 属性，见 3.5/3.6）。

### 4.3 CMake 生成器与构建系统三阶段

CMake 不是编译器，是"**构建系统生成器**"，一次构建分三个阶段：

1. **configure（配置）**：`cmake -B build` 读 CMakeLists.txt，解析 target 与依赖、探测编译器、展开变量，生成 `build/CMakeCache.txt`（缓存配置）与构建脚本；
2. **generate（生成）**：按所选生成器（Unix Makefiles / Ninja / Visual Studio）产出具体构建脚本；
3. **build（构建）**：`cmake --build build` 调用 make/ninja 按依赖图增量编译链接。

关键推论：**改 CMakeLists.txt 后必须重新 configure**（`cmake -B build` 检测到变更会自动重跑）；`compile_commands.json`（`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`）是 configure 的副产品，供 clang-tidy 与编辑器索引使用（见 3.13）；`CMakeCache.txt` 记录上次探测结果，**换编译器/构建类型建议删掉 build 目录重来**。生成器可插拔：Ninja 并行度更高、增量更快，**"CMake 生成 Ninja"是大型 C++ 项目标配**（`cmake -B build -G Ninja`）。

### 4.4 Modules 的 BMI 编译模型 vs 头文件包含模型

头文件模型是**文本复制**：每个 .cpp 编译时都要把 include 的头文件全文展开进翻译单元——同一头文件被 100 个 .cpp include 就要解析 100 次，且头文件里的宏、`using` 会**污染**所有包含者。Modules 模型是**二进制接口 + 缓存**：

```text
#include 模型: 每个 .cpp ──(文本展开头文件)──▶ 独立编译 ──▶ .o    ← 头文件改 → 所有包含者重编
Modules 模型:  math.cppm ──▶ math_utils.pcm (BMI, 只编译一次) ──▶ import 方直接读 BMI
```

- **BMI（Binary Module Interface）**：模块单元编译产物，含声明、类型布局、导出符号的完整描述；import 方**不重新解析源码**，只读 BMI——这是编译速度提升的来源；
- **隔离性**：模块内未 `export` 的符号（辅助函数、内部类型）对 import 方完全不可见，不可能像头文件那样泄漏宏到调用方；
- **依赖图更陡**：import 关系必须**先编译被 import 的模块**，BMI 变化会级联重编——CMake 对 Modules 的构建支持仍在演进（`CXX_MODULES` 等属性），**这也是工程上 Modules 落地慢于标准发布的原因**。

一句话：Modules 把"头文件 = 文本展开"改成"模块 = 预编译接口"，换来编译速度与隔离性，代价是构建系统要理解新的依赖关系。

### 4.5 Sanitizer 的插桩与运行时

ASan 的威力来自**编译期插桩 + 影子内存**。插桩：编译器在每个 load/store 前后插入对目标地址的合法性检查；**shadow memory（影子内存）**：ASan 启动时申请一块按固定比例映射的"影子区"，**每 8 字节用户内存对应 1 字节影子**，记录状态（可寻址/不可寻址/红区）。一次访问 = 查影子（O(1)）+ 比对状态，命中红区（越界）或已释放区（use-after-free）立即报错并打印栈回溯。**红区（redzone）**是每次分配前后垫的不可访问字节，让"越界一点点"也被逮住；`detect_leaks` 在退出时扫描无引用的存活分配，报泄漏点。

UBSan 走另一条路：**检查点插桩**——在可能触发 UB 的操作（有符号溢出、除零、移位越界）前插入条件检查，命中即打印 `file:line: runtime error: signed integer overflow`，`-fno-sanitize-recover=all` 改为终止。共同原理：**把"编译期猜不到、运行期才发生"的错误，变成编译期显式插入的运行时检查**——这是它们比 Valgrind 快一个数量级的原因（插桩在编译期完成、运行时开销小），也是"Release 崩、Debug 不崩"时开 ASan/UBSan 能一击命中的原因（UB 系统化梳理属 ph15 未定义行为与内存安全阶段，目录待建）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 看懂/排查编译问题 | 编译流水线四阶段、-E/-S/-c 中间产物、-Wall -Wextra 诊断归属 |
| 链接报错排查 | nm/objdump 读符号表、undefined reference/duplicate symbol、链接顺序 |
| 代码复用与交付 | 静态库（ar 打包、按需抽取）vs 动态库（运行时解析、更新不重链）的取舍 |
| 多目标工程构建 | Makefile 目标-依赖-规则、CMake target、target_link_libraries、增量构建 |
| 开发/发布双轨 | Debug/Release/RelWithDebInfo 构建类型分离 |
| 库 + 可执行 + 测试分层 | 子目录、add_subdirectory、INTERFACE 库、ctest |
| 崩溃定位 | GDB/LLDB 断点、bt、core dump 离线分析 |
| 内存泄漏与越界排查 | Valgrind、ASan/UBSan 插桩与报告解读 |
| 代码质量把关 | clang-tidy 规则集、-Wall/-Wextra、-Werror |
| 格式与风格统一 | clang-format 自动化、.clang-format 配置 |
| 测试覆盖度量 | gcov/lcov、--coverage、HTML 报告 |
| CI 质量门禁 | compile_commands.json、--dry-run -Werror、覆盖率阈值 |

**静态库 vs 动态库怎么选**：静态库——部署只需一个可执行文件（无运行时查找问题）、版本锁定在链接时，但库更新要重链、可执行文件体积大；动态库——多个程序共享一份、库更新无需重链消费者（接口不变时），但引入"找不到库/版本不匹配"的运行时风险（见 3.4）。系统软件常见组合：**核心逻辑静态链接保证部署确定性，插件/可选模块动态加载**（插件机制深入属 ph19）。

**不适合**此阶段的事项：

- **C++ 标准与可移植性深入**（ph11）：标准演进细节、GCC/Clang/MSVC 差异、ABI 稳定性——本阶段只把 `-std=c++20` 当开关用
- **vcpkg/conan 依赖管理深入**（ph11）：包管理、版本解析、私有仓库——本阶段依赖用 `find_package`/系统库即可
- **性能剖析深入**（ph18，目录待建）：perf、火焰图、热点优化——本阶段 `-pg`/gcov 只做覆盖率与基础计时
- **UB 与内存安全系统化**（ph15，目录待建）：本阶段用 Sanitizer"发现"问题，系统归类与规避留到 ph15
- **测试/静态分析/代码规范系统化**（ph16，目录待建）：本阶段 clang-tidy/gcov 是入门用法，测试框架、规则配置、覆盖率阈值工程化属 ph16
- **ABI 与动态库插件机制深入**（ph19，目录待建）：符号可见性、版本控制、插件 ABI——本阶段只做动态库的构建与运行时链接

## 6. 代码示例

> 每个示例的完整文件在 [`examples/`](./examples/) 目录（ex01~ex06），验证环境 Apple clang 21（g++ 兼容），编译命令统一 `c++ -std=c++20 -Wall -Wextra`，构建产物全部输出到 /tmp 或 build/ 目录，验证后清理。全部示例已在本环境实际编译运行验证（已验证）；示例 2/3/4 是故意构造的观察对象（符号、按需抽取、运行时库查找），不是"错误代码"。调试与质量工具（ASan/tidy/coverage）的实操练习见 [`exercises/`](./exercises/) 练习 2~4（GDB/LLDB 未配练习，可对照 3.11 命令对照表自行实验），本节只放构建工具链核心的 6 个示例。

### 示例 1：编译流水线四阶段（ex01-pipeline.cpp）

完整文件：`examples/ex01-pipeline.cpp` —— 一段含宏/constexpr/模板/static 函数/外部符号引用的源码。四步观察：`-E` 看宏展开与头文件插入、`-S` 看模板实例化符号、`-c` 产出目标文件并用 `nm` 读符号、链接成可执行文件。

```cpp
// examples/ex01-pipeline.cpp —— 编译流水线四阶段演示源文件
#define ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))   // 宏在预处理期展开
constexpr int clamp(int v, int lo, int hi) { ... }  // constexpr 在编译期求值
template <typename T> T twice(T x) { return x * SCALE; }  // 模板在编译期实例化
static int hidden_helper(int x) { return x + 1; }   // static → 链接后是局部符号 t
```

```bash
# 1. 预处理 → 2. 编译 → 3. 汇编 → 4. 链接（产物全部输出到 /tmp）
c++ -std=c++20 -Wall -Wextra -E ex01-pipeline.cpp -o /tmp/ex01.i
c++ -std=c++20 -Wall -Wextra -S ex01-pipeline.cpp -o /tmp/ex01.s
c++ -std=c++20 -Wall -Wextra -c ex01-pipeline.cpp -o /tmp/ex01.o && nm /tmp/ex01.o
c++ -std=c++20 -Wall -Wextra ex01-pipeline.cpp -o /tmp/ex01-app && /tmp/ex01-app
```

### 示例 2：静态库（ex02 系列，ar + 按需抽取）

完整文件：`examples/ex02-math.h` + `ex02-libstat.cpp`（gcd/lcm）+ `ex02-libmath.cpp`（is_prime/factorial）+ `ex02-main.cpp`（消费者）。两个库成员打包进 `libex02.a`，消费者只引用 gcd/lcm——链接后 `nm` 可执行文件确认 is_prime/factorial 未并入，实证"按需抽取"。

```cpp
// examples/ex02-libstat.cpp —— 静态库成员 1：gcd / lcm
int gcd(int a, int b) {
    while (b != 0) { const int t = a % b; a = b; b = t; }
    return a < 0 ? -a : a;
}
int lcm(int a, int b) { return a / gcd(a, b) * b; }
```

```bash
c++ -std=c++20 -Wall -Wextra -c ex02-libstat.cpp  -o /tmp/ex02-libstat.o
c++ -std=c++20 -Wall -Wextra -c ex02-libmath.cpp -o /tmp/ex02-libmath.o
ar rcs /tmp/libex02.a /tmp/ex02-libstat.o /tmp/ex02-libmath.o
c++ -std=c++20 -Wall -Wextra ex02-main.cpp -L/tmp -lex02 -o /tmp/ex02-app
/tmp/ex02-app && nm /tmp/ex02-app | grep -i prime   # 无输出 = 按需抽取生效
```

### 示例 3：动态库（ex03 系列，构建 + 运行时解析）

完整文件：`examples/ex03-text.h` + `ex03-dynlib.cpp`（to_upper/count_vowels）+ `ex03-main.cpp`（消费者）。完整走"构建 dylib → 链接 → 直接运行失败 → DYLD_LIBRARY_PATH/rpath 成功"的教学路线。

```cpp
// examples/ex03-dynlib.cpp —— 动态库源码
std::string to_upper(const std::string& s) {
    std::string out = s;
    for (char& c : out) {
        c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
    return out;
}
```

```bash
c++ -std=c++20 -Wall -Wextra -dynamiclib -install_name @rpath/libex03.dylib \
    ex03-dynlib.cpp -o /tmp/libex03.dylib
c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L/tmp -lex03 -o /tmp/ex03-app
DYLD_LIBRARY_PATH=/tmp /tmp/ex03-app     # 直接运行会报 dyld: Library not loaded（教学点）
```

### 示例 4：符号表（ex04-symbols.cpp，nm / objdump）

完整文件：`examples/ex04-symbols.cpp` —— 放置"全局函数/静态函数/非零初始化全局/零初始化全局/静态变量"各一种，`nm` 读出 `T/t/D/S/b`、`nm -u` 读出未定义的 `U`、`objdump -h` 看 `__text/__data/__common/__bss` 段。

```cpp
// examples/ex04-symbols.cpp —— 符号表观察：nm / objdump 视角
int g_counter = 5;          // 非零初始化全局 → nm: D（__data 段）
int g_zero = 0;             // 零初始化全局   → nm: S（__common；Linux ELF 上是 B）
static int s_hits = 0;      // 静态变量       → nm: b（__bss，局部）
int global_add(int a, int b) { ++s_hits; return a + b + g_counter; }   // → T
```

```bash
c++ -std=c++20 -Wall -Wextra -c ex04-symbols.cpp -o /tmp/ex04-symbols.o
nm /tmp/ex04-symbols.o && objdump -t /tmp/ex04-symbols.o && objdump -h /tmp/ex04-symbols.o
```

### 示例 5：Makefile 增量构建（ex05-make/）

完整文件：`examples/ex05-make/`（Makefile + calc.h/calc.cpp/main.cpp）—— 目标-依赖-规则完整、头文件依赖显式声明、产物隔离到 `build/`。`touch` 实测增量：改 calc.cpp 只重编 calc.o、改 calc.h 两个 .o 都重编、无改动时 `Nothing to be done`（注意 GNU Make 3.81 秒级时间戳，先 `sleep 1`）。

```make
# examples/ex05-make/Makefile（节选）
$(OBJDIR)/calc.o: calc.cpp calc.h | $(OBJDIR)   # 头文件写进依赖是关键
	$(CXX) $(CXXFLAGS) -c calc.cpp -o $@
$(OBJDIR)/main.o: main.cpp calc.h | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c main.cpp -o $@
```

```bash
cd ex05-make && make && make run && make clean
```

### 示例 6：CMake 多目标（ex06-cmake/）

完整文件：`examples/ex06-cmake/`（CMakeLists.txt + math.h/cpp + main.cpp + test_math.cpp）—— 最小"静态库 + 可执行 + 测试"三目标，Debug/Release 双轨构建，ctest 注册。工程化的三层骨架（core/app/tests 子目录版）见 [`project/`](./project/)。

```cmake
# examples/ex06-cmake/CMakeLists.txt（节选）
add_library(math STATIC math.cpp)
target_include_directories(math PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(app main.cpp)
target_link_libraries(app PRIVATE math)
enable_testing()
add_test(NAME test_math COMMAND test_math)
```

```bash
cmake -B build && cmake --build build && ./build/app
ctest --test-dir build --output-on-failure
cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel
rm -rf build build-rel
```

## 7. 总结

### 关键要点

1. **一次编译是四阶段流水线**：预处理（-E，宏/头文件）→ 编译（-S，模板实例化/优化）→ 汇编（-c，目标文件）→ 链接（符号解析/重定位）——各阶段错误各阶段查
2. **目标文件是"符号 + 机器码"的容器**：nm 读 T/t/D/S/b/U，objdump 读段；undefined reference 是链接错误，先 nm 再查依赖
3. **静态库按成员按需抽取**：ar rcs 打包，链接器只并入被引用的 .o；**动态库符号解析推迟到运行时**，可执行文件只记依赖、启动时按 DYLD_LIBRARY_PATH/rpath 解析
4. **Makefile 是"目标-依赖-规则"的声明**：时间戳决定增量重编，头文件必须写进依赖；CMake 管目标和依赖（target + target_link_libraries），不只是生成 Makefile
5. **Debug/Release/RelWithDebInfo 应分开使用**：`-O0 -g`（开发）/ `-O3 -DNDEBUG`（交付）/ `-O2 -g`（线上可分析），独立 build 目录，混用是坑
6. **Modules 替代 #include，提升编译速度和隔离性**：import/export module 编译成 BMI 缓存复用，未 export 符号不泄漏——但工具链支持差异大，工程落地谨慎
7. **静态分析能提前发现大量低级错误**：clang-tidy 基于 AST 白盒检查，抓 `-Wall` 抓不到的现代 C++ 反模式，配 compile_commands.json 才准确
8. **格式化应自动化**：clang-format + .clang-format 提交前统一排版，CI 用 `--dry-run -Werror` 强制，diff 只含业务改动
9. **调试器比打印日志更适合定位崩溃**：GDB/LLDB 即时提问，bt → print → 断点/watch 是标准流程；core dump 让线上崩溃离线可回放
10. **ASan/UBSan 是内存与 UB 的第一响应工具**：编译期插桩 + 影子内存，`-fsanitize=address,undefined` 一跑即中；Valgrind 不重编译、对未初始化更敏感
11. **覆盖率是证据不是目标**：gcov/lcov 回答"测试跑到哪"，核心逻辑优先补测，`--coverage` 必须配 `-O0 -g` 才不失真
12. **"Debug 正常、Release 崩"先怀疑 UB**：构建类型、优化级别、NDEBUG 三者的差异是排查起点，Sanitizer 一击命中
13. **工具链的价值是让工程可重复**：configure→generate→build 三阶段、compile_commands.json、CI 质量门禁——"一键构建、一键测试、一键报告"是工程化成熟的标志

### 阶段验收清单

- [ ] 能说出编译流水线四阶段及各自产物（.i/.s/.o/可执行），会用 -E/-S/-c 观察中间产物
- [ ] 能用 nm/objdump 读符号表，解释 T/t/D/S/b/U 的含义；能排查 undefined reference 与 duplicate symbol
- [ ] 能用 ar 打包静态库并链接，能解释"按需抽取"并用 nm 验证
- [ ] 能构建动态库并用 DYLD_LIBRARY_PATH/rpath 解决运行时查找
- [ ] 能写 Makefile（目标-依赖-规则、头文件依赖、.PHONY），touch 实测增量只重编对应目标
- [ ] 能构建**多目标项目**：CMake 声明 target 与依赖，Debug/Release 双目录构建
- [ ] 能定位**段错误**：GDB/LLDB 断点、bt、变量查看，或 core dump 离线分析崩溃现场
- [ ] 能定位**内存泄漏和越界**：ASan/UBSan 报告解读，Valgrind 不重编译验证
- [ ] 能配置**基础质量工具链**：clang-tidy 规则集 + compile_commands.json、clang-format 自动格式化、gcov/lcov 覆盖率报告

### 跨语言对比：构建与质量工具链

| 维度 | C++/CMake | C/Makefile | Go | Java/Maven | Rust/Cargo |
|------|-----------|-----------|-----|-----------|-----------|
| 构建描述 | CMakeLists.txt（target + 依赖） | Makefile（目标-依赖-规则） | go.mod + go build（隐式） | pom.xml | Cargo.toml（内建） |
| 构建类型 | Debug/Release/RelWithDebInfo | 手动 -g -O0 / -O2 -DNDEBUG | 无传统概念 | Maven profile | --debug / --release |
| 依赖管理 | find_package/FetchContent | 手写 -L -l 链接 | go mod | Maven 中央仓库 | crates.io |
| 调试与内存检测 | GDB/LLDB + ASan/Valgrind | GDB + Valgrind/ASan | delve + go test -race | jdb（JVM 管内存） | rust-gdb/Miri（所有权编译期保证） |
| 静态分析与格式化 | clang-tidy + clang-format | cppcheck + clang-format | go vet + gofmt（官方强制） | SpotBugs + 插件生态 | clippy + rustfmt（官方强制） |
| 覆盖率 | gcov/lcov | gcov/lcov | go test -cover | JaCoCo | tarpaulin/grcov |

一句话：**Go 与 Rust 把构建、格式化、测试内置进官方工具链（gofmt/rustfmt、go test/cargo test），开箱即用；C/C++ 是"自由拼装"的工程传统**——CMake + clang-tidy + clang-format + gcov 各自独立、靠约定组合，这正是大型系统软件的现实：每一层都可见、可控、可配置（为 analysis/ 与 Tenet 合成积累素材）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：给项目写 CMake、用 ASan 查越界、用 clang-tidy 做静态检查、生成覆盖率报告、Makefile 增量构建，共 5 题——其中练习 1~4 与 roadmap ph10「练习」小节的四项承诺一一对应，练习 5（Makefile 增量构建）对应 roadmap「学习内容」中的 g++/Makefile。完成 5 题后继续。进阶（可选）：给练习 1 的 CMake 工程加 ctest 注册；用 `-G Ninja` 对比构建速度；把 clang-format 接进 git pre-commit hook。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**C++ 工程模板（Makefile 版）**——core 库 + app 可执行 + tests 测试三层骨架、显式源/头依赖、产物隔离 build/（Release 独立 build-release/）、`make`/`make test`/`make release`/`make clean`、增量与头文件依赖 touch 实测——roadmap 推荐项目，也是"能构建多目标项目"验收的直接产物，后续所有阶段项目都可以从它起步。roadmap 的另一个推荐项目「带 CI 的小型库」依赖远程 CI 平台（GitHub Actions/GitLab CI），本机无法验证未在 project/ 落地，作为扩展方向（见 project/README.md 扩展方向）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[C++ 标准、编译器与可移植性](../ph11-portability/11-portability.md) —— 标准演进（C++11~C++23）、编译器差异（GCC/Clang/MSVC）、ABI 稳定性、跨平台构建；届时把本阶段的构建工具链能力应用到"同一份代码多编译器多平台都能构建"上。
