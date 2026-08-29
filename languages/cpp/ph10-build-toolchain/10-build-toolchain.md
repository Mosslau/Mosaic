# C++ 构建、调试与工具链阶段

> 面向高性能系统、存储引擎方向，本阶段能把 C++ 工程项目管起来：用 CMake 组织多目标构建，用 GDB/LLDB 与 Sanitizer 定位段错误和内存泄漏，用 clang-tidy/clang-format 把质量关制度化，让"能编译"升级为"能工程化地构建、能系统性地定位复杂问题"。

## 1. 概述
本阶段定位：**能用 CMake 描述目标与依赖、构建多目标 C++ 项目，让 Debug/Release/RelWithDebInfo 三种构建类型各司其职；能用 GDB/LLDB 断点调试、分析 core dump，用 Valgrind 与 ASan/UBSan 定位内存泄漏、越界与未定义行为；能用 clang-tidy 做静态分析、clang-format 自动格式化、gcov/lcov 出覆盖率报告**。学完本阶段，面对"Debug 正常、Release 崩溃"或"线上段错误"，能按"构建类型 → 调试器 → Sanitizer → 静态分析"的顺序系统排查，而不是靠打印日志瞎猜。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 编译器与选项 | g++、clang++、-std、-g、-O0/-O2/-O3、-pg、-Wall/-Wextra |
| 构建工具 | Makefile 回顾、CMake（add_library/add_executable/target_link_libraries） |
| 构建类型 | Debug、Release、RelWithDebInfo 的分离使用与配置 |
| 模块化 | C++20 Modules（import/export module）与 BMI 编译模型 |
| 调试器 | GDB/LLDB 断点、单步、watch、backtrace、core dump 分析 |
| 内存检测 | Valgrind（memcheck）、ASan（AddressSanitizer）、UBSan |
| 静态分析 | clang-tidy（规则配置、运行、修复建议） |
| 格式化与覆盖率 | clang-format 自动格式化、gcov/lcov 覆盖率报告 |

**范围边界**：承接 ph09 文件网络系统编程——ph09 的单文件 `g++` 编译在本阶段升级为 CMake 多目标工程；**不涉及** C++ 标准演进与编译器差异（ph11：标准细节、GCC/Clang/MSVC 差异、ABI 稳定性）、对象生命周期与值类别深入（ph12）、UB 系统化梳理（ph15）、性能剖析深入（ph18：perf/火焰图——本阶段 `-pg`/gcov 只做覆盖率与基础计时）、vcpkg/conan 依赖管理深入（ph11，本阶段只了解）。

## 2. 来源与演变
构建工具的演化是"从命令序列到依赖图，再到工程描述"：早期工程用 shell 脚本逐条调用 g++，改一个文件就全量重编；1976 年贝尔实验室的 **Make** 用"目标-依赖-规则"按时间戳做增量构建，但语法原始、跨平台差、表达"库 A 依赖 B、B 又依赖 C"的传递关系很痛苦。2000 年 Kitware 推出 **CMake**：先用 CMakeLists.txt 描述"构建哪些目标、目标间什么关系"，再由生成器产出 Makefile 或 **Ninja** 脚本——配置与构建分离、一套描述跨平台，成为 C/C++ 工程事实标准；**Bazel/Meson** 在大型单体仓库与强缓存方向继续探索，但 CMake 的生态地位至今稳固。

C++20 给构建模型带来结构性变革：**Modules（模块）** 用 `import`/`export module` 取代 `#include`，编译器把模块编译成 **BMI**（Binary Module Interface）并缓存，不再逐文件展开头文件文本——编译速度提升、符号隔离成为 C++20 最受关注的构建特性。工具链同步成熟：1986 年 Stallman 写出 **GDB**，配合 `-g` 的 **DWARF** 调试信息实现符号化调试；Apple 主导的 **Clang/LLVM**（2009）带来可读错误信息与 **LLDB**，并孵化出 **ASan/UBSan**、**clang-tidy** 这一整套免费质量工具——Sanitizer 用编译期插桩抓运行时内存错误，比 Valgrind 的纯动态模拟快一个数量级，成为现代 C/C++ 工程的标准配置。

| 时间 | 工具 | 关键演变 |
|------|------|---------|
| 1976 | Make | 目标-依赖-规则成型，增量构建诞生 |
| 1986 | GDB | 符号化调试（DWARF）成为可能 |
| 2000 | CMake | 构建系统生成器，配置-构建分离，C/C++ 事实标准 |
| 2009 | Clang/LLVM | 可读错误信息、LLDB、libclang 工具链生态 |
| 2011 | ASan | GCC/Clang 内置地址消毒器，插桩式内存检测 |
| 2012 | clang-tidy | 基于 Clang AST 的静态分析，可自动修复 |
| 2020 | C++20 | Modules 入标准，import/export 取代 #include 的构建模型 |
| 近年 | Ninja/Bazel | 更快构建与增量缓存；CMake 可生成 Ninja 作为后端 |

## 3. 语法与参数
### 3.1 CMake 核心：target 与依赖
**必会概念：CMake 管目标和依赖，不只是生成 Makefile**。CMakeLists.txt 的最小单元是 **target**（add_library / add_executable），target 之间用 `target_link_libraries` 建立依赖并传递属性——这是 CMake 相比手写 Makefile 的核心价值：依赖关系写在描述里，生成器翻译成具体的编译/链接命令。
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
- 库类型 `STATIC`（静态）/ `SHARED`（动态）/ `INTERFACE`（纯头文件接口库）；依赖可见性 `PRIVATE`（仅自己）/ `PUBLIC`（自己+下游）/ `INTERFACE`（仅下游）
- **坑：漏写 `target_link_libraries` 报 `undefined reference`**——CMake 不自动推断链接关系，依赖必须显式声明
- **坑：CMake 变量有目录作用域**——子目录/函数里 `set()` 的变量不影响父作用域，跨目录传值用 `target_*` 属性或 `PARENT_SCOPE`
### 3.2 CMake 配置：构建类型与 C++ 标准
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
- **坑：构建类型混用**——"Debug 正常、Release 崩"先怀疑 UB（见 3.7），也要确认是否 `-DNDEBUG` 关掉了 assert、`-O3` 改变了行为；**单目录反复切构建类型易踩缓存**，不同构建类型用不同 build 目录
- **坑：`CMAKE_CXX_STANDARD` 只是"最低要求"**——不配 `CMAKE_CXX_STANDARD_REQUIRED ON` 时编译器会悄悄 fallback，`#include <format>` 可能静默编译失败
- 多配置生成器（Visual Studio/Xcode）用 `--config Release` 选构建类型，不用 `-DCMAKE_BUILD_TYPE`
### 3.3 多目标项目组织：子目录与库
工程化项目按"库 + 可执行 + 测试"分层：业务逻辑放库，入口与测试放可执行目标，每个子目录一个 `add_subdirectory`。**目标名是全局的**，子目录间直接按名字引用（完整代码见示例 1）。
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
target_compile_features(core PUBLIC cxx_std_17)  # 传递"至少 C++17"
```
要点：
- **`target_include_directories` 可见性要匹配**：库对外头文件用 `PUBLIC`，下游才能 `#include <core/logger.h>`；纯内部头用 `PRIVATE`
- **坑：用 `include_directories()` 全局改 include 路径**——影响整个目录树、无法表达"谁需要谁"，多目标项目一律用 `target_*` 系列
- 测试用 `add_test` + `ctest` 注册（ph16 深入）；`INTERFACE` 库适合"纯头文件库"（如对 nlohmann/json 的封装层）
### 3.4 C++20 Modules 基础（import / export module）
**必会概念：Modules 替代 #include，提升编译速度和隔离性**。模块把声明与实现编译成二进制接口（BMI），调用方 `import` 时直接读 BMI，不再展开头文件文本——**未 export 的符号对调用方不可见**，隔离性天然成立。
```cpp
// math.cppm —— 模块单元（module unit）
export module math_utils;                       // 定义模块名
export int add(int a, int b) { return a + b; }  // export 的才对外可见
export int multiply(int a, int b) { return a * b; }
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
- 编译模型差异（BMI 缓存、按模块重编）见 4.3——**Modules 不解决依赖图问题**，工程依赖仍要 CMake 管理
### 3.5 g++ / clang++ 编译选项回顾与进阶
ph02 已会用 `g++ main.cpp -o app`，本阶段把选项体系补齐并理解其组合：
```bash
g++ -std=c++17 -Wall -Wextra -g -O0 main.cpp -o app_debug       # Debug
g++ -std=c++17 -Wall -Wextra -O2 -DNDEBUG main.cpp -o app_rel   # Release
g++ -std=c++17 -O2 -pg main.cpp -o app_prof && ./app_prof        # -pg 配 gprof（ph18 深入）
gprof app_prof gmon.out
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
| `-fsanitize=address,undefined` | 启用 ASan + UBSan 插桩（见 3.7） |

要点：
- **坑：`-Werror` 误用**——第三方头文件/未清理老代码触发一堆警告时，`-Werror` 让构建直接挂；CI 用前先确认依赖树零警告，或 `-Wno-error=具体警告` 局部豁免
- **坑：`-O2` 下变量可能被优化进寄存器甚至消除**——调试必须 `-g -O0` 搭配，`-O2 -g` 断点时变量值可能"看不到"
- 链接顺序规则依然成立：**使用库的文件在前、`-l` 在后**，反了报 `undefined reference`
### 3.6 GDB / LLDB 调试：断点·watch·core dump
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
```
要点：
- **没有 `-g` 就没有调试体验**——GDB 只剩裸地址；systemd 系统 core 由 `coredumpctl` 托管（`coredumpctl gdb app`）；**确认程序与 core 同一版本**，否则行号错位
- **坑：`watch` 被优化变量**——`-O0` 下最可靠；命中后先用 `bt` 确认是谁改的（示例 3 实战）
### 3.7 Valgrind 与 ASan / UBSan：内存与 UB 检测
**Valgrind（memcheck）** 是纯动态分析：模拟执行、跟踪每块内存的读写与释放，**不需要重新编译**，慢 20~50 倍但零改动：
```bash
g++ -std=c++17 -g leak.cpp -o leak
valgrind --leak-check=full ./leak      # 越界/未初始化/泄漏/double-free 全报
```
**ASan（AddressSanitizer）** 是编译期插桩：编译器在每次内存访问前后插入检查，配合影子内存（见 4.4）抓越界、use-after-free、泄漏——比 Valgrind 快一个数量级，CI 标配：
```bash
g++ -std=c++17 -g -fsanitize=address,undefined -fno-omit-frame-pointer bug.cpp -o bug
./bug                                  # 崩在越界点，打印详细报告（见示例 2）
ASAN_OPTIONS=detect_leaks=1 ./bug      # 打开泄漏检测
```
要点：
- **坑：ASan 与 Release 混用**——`-fsanitize=address` 要配 `-O0/-O1`，与 `-O2` 混用会误报/漏报；ASan 只检测"编译进插桩的代码"，第三方 .so 不插桩就检不到
- **UBSan 抓未定义行为**：整数溢出、空指针解引用、移位越界等，与 ASan 可同时开；`-fno-sanitize-recover=all` 让 UB 直接终止而非继续
- 分工：**快速定位用 ASan（要重编译），快速验证已有二进制用 Valgrind（不重编译）**；Valgrind 对未初始化读取更敏感，ASan 对越界/释放更精准
### 3.8 clang-tidy 静态分析
**必会概念：静态分析能提前发现大量低级错误**。clang-tidy 基于 Clang 的 AST 在**编译期**检查代码、不运行程序——能抓编译器警告抓不到的问题：`std::move` 误用、生命周期悬垂、性能反模式：
```bash
clang-tidy main.cpp -checks='-*,clang-analyzer-*,bugprone-*,performance-*' -- -std=c++17
clang-tidy main.cpp -checks='-*,modernize-*' --fix -- -std=c++17   # 自动修复安全部分
```
| 规则组 | 抓什么 | 典型例子 |
|--------|--------|---------|
| `clang-analyzer-*` | 内存/空指针/逻辑错误 | null 解引用、泄漏路径 |
| `bugprone-*` | 易错写法 | 拷贝粘贴错误、可疑比较 |
| `performance-*` | 性能反模式 | 不该拷贝的拷贝、慢循环 |
| `modernize-*` | 现代 C++ 风格 | auto/智能指针替换裸 new |
| `readability-*` | 可读性 | 命名、复杂度过高 |

要点：
- **clang-tidy 需要编译参数**（`--` 后的 `-std`、include 路径），真实项目配 `compile_commands.json`（CMake 生成，见 4.1）自动获得——**坑：不给编译参数时按默认 C++98 分析，误报一堆**
- 先跑默认 `clang-analyzer-*` 抓真 bug，再按项目增补规则组，**别一次性全开**（误报率爆炸）
- **坑：clang-tidy 与编译器警告不同源**——`-Wall` 是前端诊断，clang-tidy 是 AST 独立分析，两者互补、不能互相替代
### 3.9 clang-format 格式化自动化
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
### 3.10 gcov / lcov 覆盖率
覆盖率回答"测试跑到了多少代码"：**gcov** 是 GCC 的覆盖率工具（`--coverage` 插桩，运行时写 `.gcda`），**lcov** 把 gcov 原始数据转成 HTML 报告：
```bash
g++ -std=c++17 --coverage main.cpp -o app
./app                                  # 生成 main.gcda
gcov main.cpp                          # 文本报告：每行命中次数
lcov --capture --directory . --output-file coverage.info
genhtml coverage.info --output-directory html
# 浏览器打开 html/index.html：红=未覆盖 绿=覆盖
```
要点：
- **覆盖率是"证据"不是"目标"**——100% 行覆盖也可能漏掉关键分支；先看核心逻辑（解析、协议、边界处理）有没有测试跑到
- **坑：`--coverage` 与 `-O2` 混用**——优化合并/重排代码行，行号对不上源码，覆盖率失真；覆盖率构建用 `-O0 -g`
- 工程化：CMake 对测试目标单独开 `--coverage`（见示例 5），CI 生成报告并设核心文件覆盖率阈值

## 4. 底层原理
### 4.1 CMake 生成器与构建系统三阶段
CMake 不是编译器，是"**构建系统生成器**"，一次构建分三个阶段：
1. **configure（配置）**：`cmake -B build` 读 CMakeLists.txt，解析 target 与依赖、探测编译器、展开变量，生成 `build/CMakeCache.txt`（缓存配置）与构建脚本；
2. **generate（生成）**：按所选生成器（Unix Makefiles / Ninja / Visual Studio）产出具体构建脚本；
3. **build（构建）**：`cmake --build build` 调用 make/ninja 按依赖图增量编译链接。

关键推论：**改 CMakeLists.txt 后必须重新 configure**（`cmake -B build` 检测到变更会自动重跑）；`compile_commands.json`（`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`）是 configure 的副产品，供 clang-tidy 与编辑器索引使用；`CMakeCache.txt` 记录上次探测结果，**换编译器/构建类型建议删掉 build 目录重来**。生成器可插拔：Ninja 并行度更高、增量更快，**"CMake 生成 Ninja"是大型 C++ 项目标配**（`cmake -B build -G Ninja`）。
### 4.2 链接与依赖图：target 的传递性
C++ 编译单元（.cpp → .o）靠**符号**连接：每个 .o 有符号表（`nm app.o` 查看），链接器把"未定义引用"与"其它文件的定义"配对并做重定位。CMake 的 target 图正是这张符号依赖图的高层描述，**`target_link_libraries(app PRIVATE core)` 不只是"链接时加 -lcore"，而是建立属性传递**：
| 属性 | PRIVATE | PUBLIC | INTERFACE |
|------|---------|--------|-----------|
| 链接库（-l） | 仅 app | app + 下游 | 仅下游 |
| include 目录 | 仅 app | app + 下游 | 仅下游 |
| 编译选项/特性 | 仅 app | app + 下游 | 仅下游 |

由此理解两个经典现象：**静态库按需抽取**——链接器只把被引用到的 .o 成员并入可执行文件，库内 .o 的依赖顺序有讲究；**动态库（SHARED）符号解析推迟到运行时**，由 `ld.so` 按 `DT_NEEDED` 加载（ph19 深入）。"头文件互相 include 却漏了链接关系"报 `undefined reference`，就是依赖图没建全的典型症状——**CMake 的价值在于把这张图声明出来并翻译成正确的命令行**。
### 4.3 Modules 的 BMI 编译模型 vs 头文件包含模型
头文件模型是**文本复制**：每个 .cpp 编译时都要把 include 的头文件全文展开进翻译单元——同一头文件被 100 个 .cpp include 就要解析 100 次，且头文件里的宏、`using` 会**污染**所有包含者。Modules 模型是**二进制接口 + 缓存**：
```
#include 模型: 每个 .cpp ──(文本展开头文件)──▶ 独立编译 ──▶ .o    头文件改 → 所有包含者重编
Modules 模型:  math.cppm ──▶ math_utils.pcm (BMI, 只编译一次) ──▶ import 方直接读 BMI
```
- **BMI（Binary Module Interface）**：模块单元编译产物，含声明、类型布局、导出符号的完整描述；import 方**不重新解析源码**，只读 BMI——这是编译速度提升的来源；
- **隔离性**：模块内未 `export` 的符号（辅助函数、内部类型）对 import 方完全不可见，不可能像头文件那样泄漏宏到调用方；
- **依赖图更陡**：import 关系必须**先编译被 import 的模块**，BMI 变化会级联重编——CMake 对 Modules 的构建支持仍在演进（`CXX_MODULES` 等属性），**这也是工程上 Modules 落地慢于标准发布的原因**。

一句话：Modules 把"头文件 = 文本展开"改成"模块 = 预编译接口"，换来编译速度与隔离性，代价是构建系统要理解新的依赖关系。
### 4.4 Sanitizer 的插桩与运行时
ASan 的威力来自**编译期插桩 + 影子内存**。插桩：编译器在每个 load/store 前后插入对目标地址的合法性检查；**shadow memory（影子内存）**：ASan 启动时申请一块按固定比例映射的"影子区"，**每 8 字节用户内存对应 1 字节影子**，记录状态（可寻址/不可寻址/红区）。一次访问 = 查影子（O(1)）+ 比对状态，命中红区（越界）或已释放区（use-after-free）立即报错并打印栈回溯。**红区（redzone）**是每次分配前后垫的不可访问字节，让"越界一点点"也被逮住；`detect_leaks` 在退出时扫描无引用的存活分配，报泄漏点。

UBSan 走另一条路：**检查点插桩**——在可能触发 UB 的操作（有符号溢出、除零、移位越界）前插入条件检查，命中即打印 `file:line: runtime error: signed integer overflow`，`-fno-sanitize-recover=all` 改为终止。共同原理：**把"编译期猜不到、运行期才发生"的错误，变成编译期显式插入的运行时检查**——这是它们比 Valgrind 快一个数量级的原因（插桩在编译期完成、运行时开销小），也是"Release 崩、Debug 不崩"时开 ASan/UBSan 能一击命中的原因。

## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| 多目标工程构建 | CMake target、add_library/add_executable、target_link_libraries |
| 开发/发布双轨 | Debug/Release/RelWithDebInfo 构建类型分离 |
| 库 + 可执行 + 测试分层 | 子目录、add_subdirectory、INTERFACE 库、ctest |
| 崩溃定位 | GDB/LLDB 断点、bt、core dump 离线分析 |
| 内存泄漏与越界排查 | Valgrind、ASan/UBSan 插桩与报告解读 |
| 代码质量把关 | clang-tidy 规则集、-Wall/-Wextra、-Werror |
| 格式与风格统一 | clang-format 自动化、.clang-format 配置 |
| 测试覆盖度量 | gcov/lcov、--coverage、HTML 报告 |
| CI 质量门禁 | compile_commands.json、--dry-run -Werror、覆盖率阈值 |

**不适合**此阶段的事项：
- **C++ 标准与可移植性深入**（ph11）：标准演进细节、GCC/Clang/MSVC 差异、ABI 稳定性——本阶段只把 `-std=c++20` 当开关用
- **vcpkg/conan 依赖管理深入**（ph11）：包管理、版本解析、私有仓库——本阶段依赖用 `find_package`/系统库即可
- **性能剖析深入**（ph18）：perf、火焰图、热点优化——本阶段 `-pg`/gcov 只做覆盖率与基础计时
- **UB 与内存安全系统化**（ph15）：本阶段用 Sanitizer"发现"问题，系统归类与规避留到 ph15

## 6. 代码示例
> 说明：示例均可在 Linux/macOS 上原样运行；示例 2 是故意写错的程序，用于演示 ASan 定位越界。

### 示例 1：CMake 多目标项目（库 + 可执行 + 测试）
对应 roadmap 练习"给项目写 CMake"与推荐项目"C++ 工程模板"的最小形态：把 ph09 的日志工具拆成 core 库 + app 可执行 + tests 测试三个目标，含构建类型配置。
```text
ph10_demo/
├── CMakeLists.txt          # 顶层
├── core/                   # logger.h / logger.cpp + CMakeLists.txt
├── app/                    # main.cpp + CMakeLists.txt
└── tests/                  # test_logger.cpp + CMakeLists.txt
```
`CMakeLists.txt`：
```cmake
cmake_minimum_required(VERSION 3.16)
project(ph10_demo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)      # 未指定时默认 Debug
endif()
add_subdirectory(core)
add_subdirectory(app)
add_subdirectory(tests)
```
`core/CMakeLists.txt`：
```cmake
add_library(core STATIC logger.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
```
`app/CMakeLists.txt`：
```cmake
add_executable(app main.cpp)
target_link_libraries(app PRIVATE core)
target_compile_options(app PRIVATE -Wall -Wextra)
```
`tests/CMakeLists.txt`：
```cmake
enable_testing()
add_executable(tests test_logger.cpp)
target_link_libraries(tests PRIVATE core)
add_test(NAME test_logger COMMAND tests)
```
`core/logger.h`：
```cpp
#pragma once
#include <string>
namespace core { void log(const std::string& msg); }
```
`core/logger.cpp`：
```cpp
#include "logger.h"
#include <iostream>
namespace core { void log(const std::string& msg) { std::cout << "[log] " << msg << "\n"; } }
```
`app/main.cpp`：
```cpp
#include "logger.h"
int main() { core::log("hello ph10"); return 0; }
```
`tests/test_logger.cpp`：
```cpp
#include "logger.h"
int main() { core::log("from test"); return 0; }  // 真实项目用断言框架（ph16）
```
```bash
cmake -B build && cmake --build build
./build/app                         # [log] hello ph10
ctest --test-dir build --output-on-failure
cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel   # 双轨验证
```
要点：**目标分层**（core 库 / app / tests）是工程模板的核心骨架；`PRIVATE` 依赖与 `PUBLIC` include 的可见性组合让"改库内部不影响下游"成立；不同构建类型用独立 build 目录。

### 示例 2：用 ASan 定位越界（故意 bug + 编译运行 + 解读报告）
对应 roadmap 练习"用 ASan 查越界"：`fill` 的循环条件写错（`<=` 应为 `<`），越界写 stack 数组。这个 bug 在 `-O0` 下可能"碰巧不崩"，ASan 一定抓住。
```cpp
// bug.cpp —— 故意越界：i <= size 应为 i < size
#include <iostream>
void fill(int* arr, int size) {
    for (int i = 0; i <= size; ++i)   // 越界：i == size 时写 arr[size]
        arr[i] = i * i;
}
int main() {
    int nums[4] = {0};
    fill(nums, 4);
    std::cout << nums[3] << "\n";
    return 0;
}
```
```bash
g++ -std=c++17 -g -fsanitize=address -fno-omit-frame-pointer bug.cpp -o bug
./bug
```
```
==12345==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ff... at pc ...
WRITE of size 4 at 0x7ff... thread T0
    #0 fill(int*, int) bug.cpp:5          ← 越界发生在第 5 行 arr[i] = i * i
    #1 main bug.cpp:10
Address 0x7ff... is located in stack of thread T0 at offset 32 in frame
    #0 main bug.cpp:7
  This frame has 1 object(s):
    [32, 48) 'nums'                        ← 数组 nums 只占 16 字节 [32,48)
```
解读：报告给出**错误类型**（`stack-buffer-overflow`，栈越界）、**操作**（`WRITE of size 4`）、**位置**（bug.cpp:5）与**对象区间**（`nums`）——不需要猜，直接改第 5 行为 `i < size` 再编译即消失。同一程序用 Valgrind 验证（不重编译）：
```bash
g++ -std=c++17 -g bug.cpp -o bug_vg
valgrind --leak-check=full ./bug_vg      # Invalid write of size 4 ... at fill (bug.cpp:5)
```
要点：越界分**堆越界（heap-buffer-overflow）与栈越界（stack-buffer-overflow）**，报告明确区分；`-fno-omit-frame-pointer` 保证回溯带行号；**坑：ASan 构建用 `-O0/-O1`**，与 `-O2` 混用会误报/漏报。

### 示例 3：GDB 调试段错误（bt/断点/变量查看）
对应 roadmap 验收"能定位段错误"：写一个空指针解引用程序，完整走"运行 → 崩溃 → bt → 查看变量 → 定位修复"。
```cpp
// crash.cpp —— 故意崩溃：解引用空指针
#include <iostream>
struct Config { int port; };
Config* load_config(const char* path) {   // 假装加载失败返回 nullptr
    (void)path;
    return nullptr;
}
int main() {
    Config* cfg = load_config("/tmp/x.conf");
    std::cout << cfg->port << "\n";       // 崩在这里：空指针解引用
    return 0;
}
```
```bash
g++ -std=c++17 -g -O0 crash.cpp -o crash
gdb ./crash
```
```text
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x00005555555551f5 in main () at crash.cpp:11
11          std::cout << cfg->port << "\n";
(gdb) bt
#0  main () at crash.cpp:11
(gdb) print cfg
$1 = (Config *) 0x0            ← 证据：cfg 是空指针
(gdb) break crash.cpp:11
(gdb) run
(gdb) print load_config("/tmp/x.conf")
$2 = (Config *) 0x0            ← 确认返回值就是空指针
```
修复：`load_config` 失败应返回错误（RAII + 异常或 `std::optional<Config>`，见 ph12），或调用方先判空。再看 core dump 流程：
```bash
ulimit -c unlimited && ./crash && gdb ./crash core
(gdb) bt                       # 不重跑程序，直接回放崩溃现场
```
要点：**bt 永远先看**（告诉你在哪层崩），再用 `print` 找证据（空指针、越界索引）；**core dump 让线上崩溃可离线分析**——但要求程序带 `-g` 且与 core 同一版本。

### 示例 4：clang-tidy 静态检查（配置 + 运行 + 修复建议）
对应 roadmap 练习"用 clang-tidy 做静态检查"：一段"能编译、能运行"但藏着问题的代码，clang-tidy 一跑就现形。
```cpp
// sloppy.cpp —— 能编译但有问题
#include <string>
#include <vector>
int main() {
    std::vector<int> v{1, 2, 3};
    for (size_t i = 0; i < v.size(); ++i) {
        std::string s = std::to_string(v[i]);   // 循环内每次拷贝构造
        (void)s;
    }
    int* p = new int(42);                        // 裸 new：没人 delete
    (void)p;
    return 0;
}
```
`.clang-tidy`：
```yaml
Checks: 'clang-analyzer-*,bugprone-*,performance-*,modernize-*'
```
```bash
# 方式 A：命令行直接指定规则
clang-tidy sloppy.cpp -checks='-*,clang-analyzer-*,bugprone-*,performance-*,modernize-*' -- -std=c++17
# 方式 B：工程化——CMake 生成 compile_commands.json，clang-tidy 自动拿编译参数
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
clang-tidy sloppy.cpp -p build
```
输出摘录：
```
warning: use a range-based for loop instead [modernize-loop-convert]
warning: 'new' used to allocate memory; use std::make_unique instead [modernize-make-unique]
warning: the parameter 'p' is unused [clang-analyzer-deadcode.DeadStores]
```
自动修复与复检：
```bash
clang-tidy sloppy.cpp -checks='-*,modernize-*' --fix -- -std=c++17
clang-tidy sloppy.cpp -checks='-*,clang-analyzer-*' -- -std=c++17   # 复检：警告清零
```
要点：静态分析是**编译期白盒检查**——不运行、不插桩，直接看 AST，能抓"编译器警告 + 运行时错误"之外的风格/生命周期/性能问题；**坑：不给编译参数时按旧标准分析，误报一片**；规则集从 `clang-analyzer-*` 起步逐步增补。

### 示例 5：gcov/lcov 覆盖率报告（构建 + 测试 + 生成报告）
对应 roadmap 练习"生成覆盖率报告"：对示例 1 的 core 库开覆盖率插桩，跑测试后用 lcov 生成 HTML 报告。
```bash
# 1. 覆盖率构建：-O0 -g --coverage（勿与 -O2 混用，行号会失真）
g++ -std=c++17 -O0 -g --coverage -c core/logger.cpp -o logger_cov.o
g++ -std=c++17 -O0 -g --coverage tests/test_logger.cpp logger_cov.o -o test_logger
# 2. 运行测试 → 生成 .gcda 数据文件
./test_logger
# 3. 文本报告：每行命中次数
gcov logger.cpp
# 4. HTML 报告
lcov --capture --directory . --output-file coverage.info --rc lcov_branch_coverage=1
genhtml coverage.info --output-directory html
# 浏览器打开 html/index.html：绿=命中 红=未覆盖，汇总行/分支覆盖率
```
输出摘录（gcov）：
```
        -:    0:Source:core/logger.cpp
        1:    5:namespace core { void log(const std::string& msg) {
        #####:    6:    std::cout << "[log] " << msg << "\n";   ← ##### 表示未执行
```
要点：覆盖率报告回答"测试跑到哪"——`#####` 行 = 从未执行，优先补核心逻辑（错误分支、边界值）的测试；lcov 把 gcov 原始数据变成可读的 HTML（行/分支/函数覆盖三张表）；CI 用法：`lcov --remove coverage.info '*/tests/*' -o filtered.info` 排除测试自身后，按核心文件设覆盖率阈值，不达标构建失败（本示例 + 示例 1 的 ctest 即"带 CI 的小型库"推荐项目的最小闭环）。

## 7. 总结
### 关键要点
1. **CMake 管目标和依赖，不只是生成 Makefile**：target + target_link_libraries 声明依赖图，PRIVATE/PUBLIC/INTERFACE 控制属性传递——与手写 Makefile 的本质区别
2. **Debug/Release/RelWithDebInfo 应分开使用**：`-O0 -g`（开发）/ `-O3 -DNDEBUG`（交付）/ `-O2 -g`（线上可分析），独立 build 目录，混用是坑
3. **Modules 替代 #include，提升编译速度和隔离性**：import/export module 编译成 BMI 缓存复用，未 export 符号不泄漏——但工具链支持差异大，工程落地谨慎
4. **静态分析能提前发现大量低级错误**：clang-tidy 基于 AST 白盒检查，抓 `-Wall` 抓不到的现代 C++ 反模式，配 compile_commands.json 才准确
5. **格式化应自动化**：clang-format + .clang-format 提交前统一排版，CI 用 `--dry-run -Werror` 强制，diff 只含业务改动
6. **调试器比打印日志更适合定位崩溃**：GDB/LLDB 即时提问，bt → print → 断点/watch 是标准流程；core dump 让线上崩溃离线可回放
7. **ASan/UBSan 是内存与 UB 的第一响应工具**：编译期插桩 + 影子内存，`-fsanitize=address,undefined` 一跑即中；Valgrind 不重编译、对未初始化更敏感
8. **覆盖率是证据不是目标**：gcov/lcov 回答"测试跑到哪"，核心逻辑优先补测，`--coverage` 必须配 `-O0 -g` 才不失真
9. **"Debug 正常、Release 崩"先怀疑 UB**：构建类型、优化级别、NDEBUG 三者的差异是排查起点，Sanitizer 一击命中
10. **工具链的价值是让工程可重复**：configure→generate→build 三阶段、compile_commands.json、CI 质量门禁——"一键构建、一键测试、一键报告"是工程化成熟的标志
### 跨语言对比：构建与质量工具链
| 维度 | C++/CMake | C/Makefile | Go | Java/Maven | Rust/Cargo |
|------|-----------|-----------|-----|-----------|-----------|
| 构建描述 | CMakeLists.txt（target + 依赖） | Makefile（目标-依赖-规则） | go.mod + go build（隐式） | pom.xml | Cargo.toml（内建） |
| 构建类型 | Debug/Release/RelWithDebInfo | 手动 -g -O0 / -O2 -DNDEBUG | 无传统概念 | Maven profile | --debug / --release |
| 依赖管理 | find_package/FetchContent | 手写 -L -l 链接 | go mod | Maven 中央仓库 | crates.io |
| 调试与内存检测 | GDB/LLDB + ASan/Valgrind | GDB + Valgrind/ASan | delve + go test -race | jdb（JVM 管内存） | rust-gdb/Miri（所有权编译期保证） |
| 静态分析与格式化 | clang-tidy + clang-format | cppcheck + clang-format | go vet + gofmt（官方强制） | SpotBugs + 插件生态 | clippy + rustfmt（官方强制） |
| 覆盖率 | gcov/lcov | gcov/lcov | go test -cover | JaCoCo | tarpaulin/grcov |

一句话：**Go 与 Rust 把构建、格式化、测试内置进官方工具链（gofmt/rustfmt、go test/cargo test），开箱即用；C/C++ 是"自由拼装"的工程传统**——CMake + clang-tidy + clang-format + gcov 各自独立、靠约定组合，这正是大型系统软件的现实：每一层都可见、可控、可配置。
### 阶段验收标准
- 能构建**多目标项目**：库 + 可执行 + 测试分层，CMake 声明 target 与依赖，Debug/Release 双目录构建
- 能定位**段错误**：GDB/LLDB 断点、bt、变量查看，或 core dump 离线分析崩溃现场
- 能定位**内存泄漏和越界**：ASan/UBSan 报告解读，Valgrind 不重编译验证
- 能配置**基础质量工具链**：clang-tidy 规则集 + compile_commands.json、clang-format 自动格式化、gcov/lcov 覆盖率报告
- 能完成四个练习：给项目写 CMake、用 ASan 查越界、用 clang-tidy 做静态检查、生成覆盖率报告
### 进入下一阶段前
确保能完成以下练习：
- **给项目写 CMake**：任选 ph07-ph09 的项目（如 ph09 的 TCP echo server），按示例 1 拆成"库 + 可执行"并用 CMake 构建（提示：`add_subdirectory` 分层、`target_link_libraries(app PRIVATE core)`、`-DCMAKE_BUILD_TYPE=Release` 验证双构建）
- **用 ASan 查越界**：故意写一个堆/栈越界程序，参考示例 2，完整走"编译 `-fsanitize=address` → 运行 → 读报告（类型/行号/对象区间）→ 修复"（提示：堆越界用 `new[]` 后越界写；对比 `-O0` 与 ASan 的行为差异）
- **用 clang-tidy 做静态检查**：对示例 4 的 sloppy.cpp 或自己的项目跑 `clang-analyzer-*`，至少修 3 条警告（提示：`-p build` 用 compile_commands.json；先 `-checks='-*,clang-analyzer-*'` 抓真 bug，再增补规则组）
- **生成覆盖率报告**：对示例 1 的 core 库开 `--coverage`，跑测试后 lcov/genhtml 出 HTML 报告（提示：`-O0 -g --coverage`；找到 `#####` 未覆盖行并补一个测试用例）
- 进阶（可选）：给 CMake 工程加 ctest 注册；用 `-G Ninja` 对比构建速度；把 clang-format 接进 git pre-commit hook
### 推荐项目
- **C++ 工程模板**：示例 1 的完整形态——core 库 + app + tests 三层骨架、Debug/Release/RelWithDebInfo 构建类型、`-Wall -Wextra` 零警告、clang-format + .clang-format 格式化门禁、clang-tidy 规则集、ctest 测试注册、README 写清"怎么配置/构建/测试"——roadmap 指定项目，后续所有阶段项目都从它起步，是"能构建多目标项目"验收的直接产物
- **带 CI 的小型库**：在工程模板上挑一个 ph07-ph09 的模块（如日志库）做成可复用库，GitHub Actions/GitLab CI 里跑"cmake 配置构建 → ctest → clang-tidy 静态检查 → clang-format 校验 → gcov/lcov 覆盖率报告（设阈值）"，任一环节失败即红灯——把本阶段全部工具链串成一条流水线，正是"能配置基础质量工具链"验收的完整答案，也是未来存储引擎等系统软件质量的雏形
### 下一阶段
**C++ 标准、编译器与可移植性**（ph11-portability，文档规划中）—— 标准演进（C++11~C++23）、编译器差异（GCC/Clang/MSVC）、ABI 稳定性、跨平台构建；届时把本阶段的 CMake/工具链能力应用到"同一份代码多编译器多平台都能构建"上。
