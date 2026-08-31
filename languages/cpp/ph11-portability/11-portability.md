# C++ 标准、编译器与可移植性阶段

> 面向高性能系统、存储引擎方向，本阶段能看懂 C++ 标准演进（C++11~C++23）与三大编译器（GCC/Clang/MSVC）的差异，会用平台宏与条件编译隔离平台相关代码，能识别 ABI 与标准库实现差异带来的二进制兼容风险，让"能编译"升级为"同一份代码多编译器多平台都能构建"。

## 1. 概述

本阶段定位：**能用 `__cplusplus` 与特性测试宏判断编译器支持的语言标准边界，说清 C++11/14/17/20/23 各代的代表性特性；能用 `#if defined(_WIN32)` 等平台宏与条件编译隔离平台相关代码，写出 GCC/Clang/MSVC 三套编译器、Windows/Linux/macOS 三类平台都能构建的跨平台代码；能识别名字修饰、标准库实现与内联命名空间带来的 ABI 二进制兼容风险**。学完本阶段，面对"Linux 上好好的、Windows 上编译不过"或"换了个编译器就报一堆错"这类问题，能按"标准边界 → 编译器差异 → 标准库差异 → ABI 风险"的顺序排查，而不是到处堆 `#ifdef` 打补丁。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 标准演进 | C++11/14/17/20/23 特性边界、`__cplusplus`、特性测试宏 |
| 编译器差异 | GCC、Clang、MSVC 的支持度、预定义宏与告警差异 |
| 标准库实现 | libstdc++、libc++、MSVC STL 的差异与二进制兼容影响 |
| 平台宏与条件编译 | `_WIN32`/`__linux__`/`__APPLE__`/`_MSC_VER`、`#if/#ifdef` |
| 固定宽度与字节序 | `<cstdint>` 固定宽度类型、大小端与跨平台序列化 |
| ABI 与标准的关系 | 名字修饰、Itanium/MSVC ABI、内联命名空间、ABI 风险识别 |
| 跨平台工程 | 平台适配层、公共接口稳定、CI 多编译器矩阵 |

这个阶段只涉及 C++ 标准演进与编译器差异、平台宏与条件编译、固定宽度类型与字节序、以及 ABI 与二进制兼容的风险识别，**不涉及对象生命周期与值类别深入（ph12，roadmap 第 12 节，目录待建）、Rule of 0/3/5 与 RAII 进阶（ph13，目录待建）、UB 系统化梳理（ph15，目录待建）、动态库加载与插件机制深入（ph19，目录待建：dlopen/LoadLibrary、符号可见性、版本控制——本阶段只讲 ABI 概念与风险识别）、跨语言互操作（ph20，目录待建：pybind11、C ABI 包装层——本阶段 `extern "C"` 只做概念演示）** — 那些是后续阶段的内容。承接 ph10 构建调试与工具链阶段：ph10 把 `-std=c++20` 当"开关"用，本阶段把开关背后的东西讲透——标准边界在哪、各编译器支持到哪、跨平台构建的差异从何而来，把 CMake/工具链能力应用到"同一份代码多编译器多平台都能构建"上。

## 2. 来源与演变

C++ 标准由 ISO/IEC 14882 规定，节奏是"**标准先行、编译器跟进**"：1998 年 C++98 确立模板、STL、异常、RTTI 等核心能力，此后近十年几乎停滞（2003 年只有一次小修）；2011 年 C++11 带来语言史上最大的一次现代化——`auto`、lambda、移动语义、智能指针、`nullptr`；此后进入三年一版的节奏：C++14 小步改进（泛型 lambda、auto 返回类型推导）、C++17 补全实用特性（结构化绑定、if constexpr、std::filesystem、string_view）、C++20 大规模扩展（concepts、ranges、协程、modules、std::format）、C++23 收尾（std::print、std::expected、mdspan）。关键认知：**标准是"文档"先发布，编译器逐个特性实现，且三大编译器节奏不一**——查支持度要看特性表，查标准细节看权威参考。

| 标准 | 发布时间 | 标志性特性 | 支持现状（本机 Apple clang 21 实测；GCC/MSVC 未在本环境验证） |
|------|---------|-----------|-------------------------------------------------------------|
| C++98 | 1998 | 模板、STL、异常、RTTI | 全支持（后续标准的基线） |
| C++11 | 2011 | auto、lambda、移动语义、智能指针、nullptr | 全支持 |
| C++14 | 2014 | 泛型 lambda、auto 返回类型、std::make_unique | 全支持 |
| C++17 | 2017 | 结构化绑定、if constexpr、std::filesystem、string_view | 全支持 |
| C++20 | 2020 | concepts、ranges、协程、modules、std::format、`<=>` | 主要特性支持（本机 `__cpp_concepts=202002`、`__cpp_lib_format=202110` 实测）；modules 支持各家仍不一致 |
| C++23 | 2023 | std::print、std::expected、mdspan | 部分特性落地；mdspan 等仍有实现缺口 |

三年一版让 C++ 持续吸收现代语言特性，但也放大了"**编译器支持和语言标准不是完全同步**"：C++20 发布几年后，三大编译器仍没把全部特性实现完——modules 在 GCC 上支持不完整、MSVC 与 Clang 各有各的编译标志（ph10 已见）；C++23 的 mdspan 至今只有部分实现。可移植代码因此要以"**三套编译器共同支持的特性交集**"为基准，写之前查特性表而不是想当然。权威参考：cppreference（含各标准版本差异与跨编译器 Compiler support 特性表）、isocpp.org（标准委员会官网，含 FAQ 与提案）；编译器侧分别是 gcc.gnu.org/projects/cxx-status.html、clang.llvm.org/cxx_status.html、learn.microsoft.com 的 C++ 标准符合性表。

本文示例以 **C++20** 为基线（roadmap 自第 6 节起主线使用 C++20 特性，`-std=c++20` 是当前稳定度与功能的平衡点；特性边界演示同时用 `-std=c++14/17/20` 对照），验证工具链为 **Apple clang 21.0.0（`c++`/`g++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`）**，全部示例已在本环境实际编译运行验证（已验证）；GCC/MSVC 本机没有对应编译器，涉及这两家的内容如实标注「未在本环境验证」。`__cplusplus`/特性测试宏/平台宏这一套语法是 C++ 生态里**最稳定、最值得先掌握**的可移植性基础：二十多年没大变，学会后长期复用。

## 3. 语法与参数

### 3.1 `__cplusplus` 与特性测试宏

**必会概念：用 `__cplusplus` 判断"编译器当前按哪个标准编译"，用特性测试宏判断"某个具体特性/库到底可不可用"**。`__cplusplus` 是编译器预定义宏，值即标准版本号：

| 宏值 | 标准 | 宏值 | 标准 |
|------|------|------|------|
| 199711L | C++98 | 201703L | C++17 |
| 201103L | C++11 | 202002L | C++20 |
| 201402L | C++14 | 202302L | C++23 |

```cpp
#if __cplusplus >= 202002L
    // 编译器声称当前按 C++20 编译
#elif __cplusplus >= 201703L
    // 至少 C++17
#endif
```

要点：

- 本机实测（已验证）：`-std=c++14/17/20/23` 分别得到 `201402L/201703L/202002L/202302L`，Apple clang 与 Homebrew clang 一致
- **坑：MSVC 默认把 `__cplusplus` 报成 199711L**——除非加 `/Zc:__cplusplus`（微软文档值，未在本环境验证）
- **坑：不写 `-std=` 时默认标准各家不同**——本机实测 Apple clang 21 默认 `gnu++14`（`__cplusplus=201402L`），Homebrew clang 21 默认 `gnu++17`（`201703L`）；GCC 默认 `gnu++17`（据公开资料，未验证）、MSVC 默认 C++14（需 `/std:` 显式指定，据公开资料，未验证）。**判标准前先确认 `-std=` 真的生效了**
- **特性测试宏（Feature Test Macro）**：`__has_include(头文件)` 判断头文件是否存在（C++17 标准化）、`__has_cpp_attribute(属性)` 判断属性支持（见 3.4）、C++20 起标准化的 `__cpp_*`/`__cpp_lib_*` 系列（如 `__cpp_lib_filesystem`、`__cpp_concepts`）精确到单个特性
- 判断"能不能用某个特性"优先用特性测试宏：`#if __has_include(<optional>)` 回答"这个库在不在"，比 `#if __cplusplus >= 201703L` 回答"编译器声称什么标准"更贴近真相

**坑：`__cpp_lib_*` 必须先 include 对应头文件才会定义**。本机实测（已验证，完整版见 `exercises/sol-03-std-probe.cpp`；`__has_include` 的用法见 `examples/ex03-condcompile.cpp`）：

| 特性宏 | C++17 实测 | C++20 实测 | 含义 |
|--------|-----------|-----------|------|
| `__cpp_lib_filesystem` | 201703 | 201703 | `<filesystem>` 可用 |
| `__cpp_lib_optional` | 201606 | 202106 | `<optional>` 可用（C++20 升版） |
| `__cpp_lib_format` | 未定义 | 202110 | `<format>` 仅在 C++20 定义 |
| `__cpp_concepts` | 未定义 | 202002 | concepts 仅在 C++20 |

### 3.2 平台宏与条件编译

**必会概念：平台宏由编译器预定义，用来在源码里区分平台与编译器**。三大平台与编译器（含 Clang 兼容 GCC 宏）的核心宏：

| 宏 | 定义者 | 含义 |
|----|--------|------|
| `_WIN32` | MSVC/MinGW 等 Windows 编译器 | 32/64 位 Windows 都定义；判断"是 Windows"用这个 |
| `_WIN64` | 同上 | 仅 64 位 Windows |
| `__linux__` | GCC/Clang | Linux 平台 |
| `__APPLE__` | Apple clang/GCC | macOS/iOS 等 Apple 平台 |
| `__unix__` | GCC/Clang（Linux 等） | Unix 系（**本机实测：macOS 的 Apple clang 不定义它**，只在 Linux 等系统定义） |
| `_MSC_VER` | MSVC | MSVC 版本戳（如 1938 = VS2022 17.8，微软文档值，未在本环境验证） |
| `__GNUC__` | GCC（Clang 为兼容也定义） | GCC 主版本号（**Clang 下是兼容值，实测报 4.2.1，不代表真实 GCC 版本**） |
| `__clang__` | Clang | 1 = 正在用 Clang |
| `__VERSION__` | GCC/Clang | 编译器自我介绍字符串（本机实测 Apple = `"Apple LLVM 21.0.0 (clang-2100.1.1.101)"`，Homebrew = `"Homebrew Clang 21.1.8"`） |

```cpp
#if defined(_WIN32)
    // Windows path
#elif defined(__APPLE__)
    // macOS path
#elif defined(__linux__)
    // Linux path
#endif
```

要点：

- 条件编译四件套：`#if` / `#ifdef` / `#ifndef` / `#elif` / `#else` / `#endif`；组合条件用 `#if defined(A) && !defined(B)`，**`#ifdef` 只能判断单个宏**
- **坑：判平台和判编译器别混**——`_WIN32` 回答"是不是 Windows"，`_MSC_VER`/`__GNUC__`/`__clang__` 回答"用哪个编译器"；MinGW 在 Windows 上 `_WIN32` 与 `__GNUC__` 同时定义
- **坑：`__GNUC__` 不等于"真 GCC"**——本机实测两家 Clang 都定义 `__GNUC__=4`、`__GNUC_MINOR__=2`（兼容 GCC 4.2.1）。判编译器家族必须按 `_MSC_VER` → `__clang__` → `__GNUC__` 的顺序，先查 `__clang__` 才能区分"真 GCC"与"Clang 假装的 GCC"（完整版见 `examples/ex04-compilers.cpp`）
- **坑：宏可以来自命令行**——`g++ -DDEBUG`、CMake `target_compile_definitions` 都往源码注入宏，平台宏只是编译器内置的那一部分；`-D_WIN32` 是常用的"本机模拟 Windows 分支"验证技巧（见 6. 示例 1/5）

### 3.3 `#pragma once` 与 include guard

**必会概念：头文件必须防重复包含**，两种主流机制：

| 方案 | 标准性 | 优点 | 风险 |
|------|--------|------|------|
| include guard | ISO C++ 标准机制 | 任何编译器都认 | 宏名唯一性靠人保证，拼错/撞名导致失效 |
| `#pragma once` | 非标准（事实标准） | 简洁、无宏名问题 | 极老旧编译器不支持（现代工程可忽略） |

```cpp
// guard 写法：标准、可移植性最好
#ifndef PH11_GUARD_STYLE_H
#define PH11_GUARD_STYLE_H
struct Guarded { int value = 1; };
#endif

// pragma once 写法：简洁，所有主流编译器都支持
#pragma once
struct Pragmatic { int value = 2; };
```

要点：

- 双保险写法（`#pragma once` + include guard 一起写）也常见，工程上二选一即可
- **坑：guard 宏名要带项目前缀**——`CONFIG_H` 这类通用名在大型工程里极易撞车，`PH11_*`/`项目名_*` 更安全
- 有保护时同一头文件被包含多次不会重复定义；**漏写保护**的后果是 `redefinition of 'NoGuard'` 编译错误

### 3.4 标准属性：`[[deprecated]]`、`[[nodiscard]]` 等

**必会概念：C++11 起有标准属性语法 `[[attr]]`，跨编译器可移植**；此前 GCC/Clang 用 `__attribute__((...))`、MSVC 用 `__declspec(...)`，各写各的：

| 属性 | 标准 | 用途 |
|------|------|------|
| `[[deprecated("提示语")]]` | C++14 | 标记弃用 API，使用处编译告警 |
| `[[nodiscard]]` | C++17 | 忽略返回值时告警 |
| `[[maybe_unused]]` / `[[fallthrough]]` | C++17 | 抑制未使用告警 / 声明 switch 落空是有意的 |
| `[[likely]]` / `[[unlikely]]` | C++20 | 分支概率提示，辅助优化 |

要点：

- 用 `__has_cpp_attribute(名字)` 判断属性支持度，返回值是引入版本。本机实测（已验证，Apple clang 21）：`deprecated` = 201309（C++14）、`nodiscard` = 201907、`likely` = 201803
- **公共 API 要退役时用 `[[deprecated("改用新接口")]]` 过渡**，比直接删掉/静默改掉安全；`[[nodiscard]]` 适合"忽略返回值必然出 bug"的函数（如打开资源类的接口）
- **坑：老代码里的 `__attribute__((deprecated))`/`__declspec(deprecated)` 是编译器私有写法**，新代码一律用标准属性；特性检测写法见 3.1

### 3.5 固定宽度整数类型：`<cstdint>`

**必会概念：跨平台代码不能假设 `int`/`long` 的宽度，固定宽度类型把"恰好 N 位"变成编译期承诺**。本机实测（已验证，完整版见 `examples/ex01-stdint.cpp`）：

```cpp
#include <cstdint>   // 固定宽度类型 + INT32_MAX 等宏
#include <cstdio>

static_assert(sizeof(int32_t) == 4, "int32_t must be exactly 4 bytes");

int main() {
    std::printf("int8_t=%zu  int16_t=%zu  int32_t=%zu  int64_t=%zu\n",
                sizeof(int8_t), sizeof(int16_t), sizeof(int32_t), sizeof(int64_t));
    std::printf("uint8_t=%zu  uint16_t=%zu  uint32_t=%zu  uint64_t=%zu\n",
                sizeof(uint8_t), sizeof(uint16_t), sizeof(uint32_t), sizeof(uint64_t));
    std::printf("INT32_MAX=%d  UINT32_MAX=%u\n", INT32_MAX, UINT32_MAX);
    std::printf("int_least8_t=%zu  int_fast32_t=%zu  intmax_t=%zu\n",
                sizeof(int_least8_t), sizeof(int_fast32_t), sizeof(intmax_t));
    std::printf("int=%zu  long=%zu  long long=%zu  void*=%zu\n",
                sizeof(int), sizeof(long), sizeof(long long), sizeof(void*));
    return 0;
}
```

本机实测输出（已验证，Apple clang 21 与 Homebrew clang 21 一致）：

```text
int8_t=1  int16_t=2  int32_t=4  int64_t=8
uint8_t=1  uint16_t=2  uint32_t=4  uint64_t=8
INT32_MAX=2147483647  UINT32_MAX=4294967295
int_least8_t=1  int_fast32_t=4  intmax_t=8
int=4  long=8  long long=8  void*=8
```

要点：

- **固定宽度类型在任何平台都是恰好 N 位**（`int32_t` 恒为 4 字节），`static_assert` 把关；`int`/`long` 宽度跨平台不同（本机 4/8，Windows 上是 4/4）——写二进制格式、跨平台协议必须用固定宽度
- `int_least8_t`/`int_fast32_t` 只保证**下限**（至少 8 位/最快），具体宽度平台定，别假设具体值；`intmax_t` 是能表示所有整数的最大宽度类型
- 边界值宏（`INT32_MAX`/`UINT64_MAX` 等）由 `<cstdint>` 提供，与类型宽度联动
- 典型用途：二进制协议头、文件格式字段（magic/version/length）、跨平台日志 ID——见 `exercises/sol-05-bin-header.cpp`

### 3.6 字节序与跨平台序列化

**必会概念：多字节整数在内存中的字节排列因平台而异（大端/小端）；写文件或网络协议必须固定字节序，通常是"大端"（网络序）**。三种探测方式互相印证（完整版见 `examples/ex02-endian.cpp`）：

| 方式 | 可移植性 | 说明 |
|------|---------|------|
| `__BYTE_ORDER__` 宏 | GCC/Clang | 与 `__ORDER_LITTLE_ENDIAN__`(1234)/`__ORDER_BIG_ENDIAN__`(4321) 比较；MSVC 不定义 |
| 运行期字节探测 | 全平台 | 看 0x0102 的首字节是 0x01（大端）还是 0x02（小端），任何编译器都行 |
| `std::endian::native` | C++20 `<bit>` | 标准库判据，最规范 |

本机实测输出（已验证）：

```text
macro __BYTE_ORDER__      : little
runtime byte probe        : little
std::endian::native       : little
value=0x01020304  big-endian bytes: 01 02 03 04
roundtrip=16909060 (OK)
```

要点：

- **坑：不要用 `reinterpret_cast` 直接把结构体当字节流**——结构体布局（padding/对齐）跨编译器、跨平台不同，序列化必须逐字节手动拼；`0x01020304` 序列化后字节应为 `01 02 03 04`（高位在前）
- **大端（网络序）是跨平台约定的默认**：TCP/IP 协议头、HTTP/2 帧头长度字段、不少二进制文件格式（如 PNG/JPEG/TIFF）都用大端，任何字节序机器读同一字节流结果一致；注意 HTTP/1.1 的 Content-Length 是 ASCII 十进制文本、不是二进制大端——字节序约定由协议/格式规范决定，写入前先查文档
- 手写 `to_big_endian` 在 little-endian 机器上做字节反转，读回再反转一次即还原——不依赖平台字节序（`exercises/sol-04-endian-serialize.cpp`、`sol-05-bin-header.cpp` 是完整练习）

### 3.7 三大编译器差异速览：GCC、Clang、MSVC

**必会概念：GCC、Clang、MSVC 是三个独立实现，标准支持、预定义宏、告警体系各有差异**（本机实测列；未实测列如实标注）：

| 维度 | Apple clang 21（本机实测） | Homebrew clang 21（本机实测） | GCC | MSVC |
|------|---------------------------|------------------------------|-----|------|
| 默认标准 | gnu++14（`__cplusplus=201402L`） | gnu++17（`201703L`） | gnu++17（据公开资料，未验证） | C++14（需 `/std:c++17` 等显式指定，据公开资料，未验证） |
| 常用警告 | `-Wall -Wextra -Wpedantic` | 同左 | 同左 | `/W4`、`/WX`（警告即错误） |
| 家族宏 | `__clang__=1` + `__GNUC__=4.2.1`（兼容值） | 同左，`__VERSION__` 不同 | `__GNUC__` 为主版本号（未验证） | `_MSC_VER`（未验证） |
| 标准实现节奏 | 跟随上游 LLVM | 快、新特性落地早 | 稳健、偏保守 | 跟随生态需求，Modules 落地早 |
| 平台 | Apple 生态为主 | 全平台 | Linux/Unix 为主 | Windows 为主 |
| 默认标准库 | libc++ | libc++（macOS）/ libstdc++（Linux） | libstdc++ | MSVC STL |

要点：

- **坑：依赖编译器扩展 = 放弃可移植**——GNU 扩展（`__int128`、`typeof`、语句表达式）在 MSVC 上直接编译失败；C++20 Modules 的编译标志三家各异（ph10 已见）
- 同一份代码多套编译器都"零警告"通过，才算可移植；CI 里开 GCC/Clang/MSVC 构建矩阵。本机可验证的是 Apple clang 与 Homebrew clang 双编译器对齐（见 6. 示例 2 与 `exercises` 练习 1）
- 告警名各家不同：同一告警 Clang 叫 `-Wtautological-constant-compare`（本机实测），GCC 叫 `-Wbool-compare`（据公开资料，未验证）——对齐警告靠"同一批代码多套都过"

## 4. 底层原理

### 4.1 ABI 与标准的关系

**必会概念：API 是源码契约，ABI 是二进制契约，标准只规定前者**。API（Application Programming Interface）：函数签名、类接口、语义——源码能编译就说明满足；ABI（Application Binary Interface）：函数在二进制里叫什么名字、参数怎么传（寄存器/栈）、对象怎么布局、异常怎么传播、虚表长什么样——二进制能链接、能运行才说明满足。

- ISO 标准对 ABI **几乎不做规定**：`struct S { int a; char b; };` 的布局、`int f(int)` 的符号名，都由编译器 + 平台决定
- 推论一：同一平台、同一 ABI 家族内（都走 Itanium C++ ABI 的 GCC/Clang）编出的 .o 通常可互链；跨 ABI 家族（Itanium vs MSVC）**不可能**互链
- 推论二：**标准库 ABI 是 ABI 的一部分**——同一编译器，如果链接的库是另一套标准库实现编的，`std::string` 布局不同，运行即崩
- C++ ABI 不如 C ABI 稳定：C 有平台级调用约定（System V AMD64 等），C++ 只有事实标准 Itanium C++ ABI（GCC/Clang 系）与 MSVC ABI（Windows）两家并存

### 4.2 名字修饰（Name Mangling）与 Itanium/MSVC ABI

**必会概念：C++ 重载要求函数名携带参数类型，编译器把源码名字"修饰"成二进制符号名**。`int f(int)` 与 `double f(double)` 必须编成两个不同的符号。本机实测（已验证，macOS Mach-O / Itanium C++ ABI）：

```text
# 源码：int f(int); double f(double); extern "C" int plain(int);
# 本机 nm 实测：int f(int) → __Z1fi，double f(double) → __Z1fd，extern "C" plain → _plain，main → _main
# macOS Mach-O 在 Itanium 符号前额外加一个下划线；Linux ELF 是 _Z1fi（无前导下划线）
# MSVC ABI：int f(int) → ?f@@YAHH@Z（? 开头、@ 分隔、YAH 编码"返回 int、参数 int"）——未在本环境验证
```

```bash
c++ -std=c++20 -c mangle.cpp -o mangle.o   # 1. 编译（mangle.cpp：int f(int); double f(double); extern "C" int plain(int);）
nm mangle.o | grep " T "                   # 2. 看符号：__Z1fi __Z1fd _plain _main
c++filt __Z1fi                             # 3. 还原：f(int)
```

要点：

- **`extern "C"` 关闭名字修饰**：`extern "C" int plain(int)` 的符号就是 `_plain`（本机实测）——跨语言、跨 ABI 边界（插件、C 库、pybind11）全靠它（ph19/ph20 深入）
- 推论：**"换编译器就链接失败"的第一嫌疑是名字修饰不兼容**——GCC 编的 .o 拿给 MSVC 链接，符号对不上；同编译器换标准库实现同理
- 永远别手写符号名、别在 C++ 侧绕过修饰；动态库导出/插件接口一律 `extern "C"` 或稳定包装层

### 4.3 标准库实现差异与二进制兼容

**必会概念：三大标准库实现各有各的内存布局与 ABI 版本策略，直接影响二进制兼容**：

| 实现 | 默认使用方 | 特点 |
|------|-----------|------|
| libstdc++ | GCC（Linux 默认） | `std::string` 64 位下 32 字节、SSO 15 字符；C++11 后 ABI 用 `std::__cxx11::` 内联命名空间标记（未在本环境验证，需 GCC） |
| libc++ | Clang（macOS 默认） | `std::string` 64 位下 **24 字节**、SSO **22 字符**（本机实测：`sizeof(std::string)=24`，22 字符在栈内、23 字符才堆分配）；用 `std::__1::` 内联命名空间做 ABI 版本化 |
| MSVC STL | MSVC | `std::string` 32 字节；与前两者布局完全不同（未在本环境验证） |

要点：

- **内联命名空间（Inline Namespace）**：`namespace std { inline namespace __cxx11 { class string {...}; } }`——符号名带上 `__cxx11`，新旧 ABI 的 `string` 是不同的符号、可共存
- 经典现场：libstdc++ 的 `_GLIBCXX_USE_CXX11_ABI`（GCC 5 起默认 1）切换新旧 ABI——**同一编译器，一个库用旧 ABI 编、程序用新 ABI 编，链接报 `undefined reference to std::__cxx11::basic_string<...>`**（未在本环境验证，需 GCC）
- 推论：**"标准库 ABI 可能影响二进制兼容"**——换编译器版本、换标准库、动 `_GLIBCXX_USE_CXX11_ABI`，都可能让"昨天还好的二进制"今天链接失败
- 必会概念落地：**不要在公共接口暴露不稳定细节**——公共头文件只放稳定 API，内部类型、实现宏、平台细节一律收进实现（`examples/ex05-path.*` 的适配层就是最小示范，`project/` 是完整形态）

### 4.4 编译器差异的根源与"标准≠支持"

三个编译器是**独立实现**，各自选择实现顺序与优先级：

- **Clang** 激进：新特性落地快、诊断质量高（带 fix-it 修复建议），常被当作"新标准探路者"
- **GCC** 稳健：实现保守但成熟，是 Linux 服务器默认选择，长尾平台支持最好
- **MSVC** 跟随生态需求：Windows 生态优先，Modules 支持落地早，但 `__cplusplus` 等宏行为与 GCC/Clang 不一致
- 标准三年一版、编译器按季度/年度发版 → **特性表上"部分支持/待实现"长期存在**（C++20 发布几年后 modules 仍未三家完全一致，见 3.7）
- 同一特性在不同编译器下的"宽容度"不同：旧标准模式下新特性会被当**扩展**接受并告警。本机实测（已验证，Apple clang 21）：`-std=c++14` 下结构化绑定只是 `-Wc++17-extensions` 警告（报 `decomposition declarations are a C++17 extension`），而 `-pedantic-errors` 才把它升级为错误；concepts 在 C++14/17 下直接报 `unknown type name 'concept'` 编译错误（见 6. 示例 3）
- 实践结论：**写可移植代码 = 以多套编译器共同支持的交集为准 + 特性测试宏探测 + CI 矩阵验证 + `-Wpedantic` 抓非标准扩展**；把"换编译器报错"当常态演练，而不是最后一刻的惊吓

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 同一份代码多套编译器构建 | 标准边界、特性测试宏、警告级别对齐（`-Wall -Wextra` / `/W4`） |
| Linux/Windows/macOS 跨平台发布 | 平台宏、条件编译、平台适配层 |
| 二进制文件/网络协议格式 | 固定宽度类型（`<cstdint>`）、大端序列化 |
| 动态库发布与升级 | ABI 稳定性、内联命名空间、`_GLIBCXX_USE_CXX11_ABI` |
| 第三方库接入 | 标准库实现差异、编译器扩展差异、ABI 匹配检查 |
| CI 多编译器矩阵 | GCC/Clang/MSVC 多套构建、特性表核对、`-Wpedantic` |
| 老代码/老库维护 | `__cplusplus` 判断、`[[deprecated]]` 弃用过渡、新老 ABI 切换 |

**不适合**此阶段的事项：

- **动态库加载与插件机制深入**（ph19，目录待建）：dlopen/LoadLibrary、插件生命周期、符号解析——本阶段只讲 ABI 概念与风险识别
- **跨语言互操作**（ph20，目录待建）：pybind11、C ABI 包装层、异常跨边界——本阶段 `extern "C"` 只做概念演示
- **对象生命周期与值类别深入**（ph12，目录待建）：本阶段不讨论移动语义、值类别细节
- **UB 系统化梳理**（ph15，目录待建）：本阶段只识别"扩展/非标准"带来的可移植风险，不展开 UB 分类

## 6. 代码示例

> 说明：示例均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8）实际编译运行验证（已验证），编译命令一律 `-std=c++20 -Wall -Wextra` 零警告；Windows 分支用 `-D_WIN32` 在本机交叉验证。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。

### 示例 1：平台分支 + 特性检测（examples/ex03-condcompile.cpp）

一段代码同时回答"我在哪个平台"、"用哪个编译器"、"某个头在不在"：

```cpp
// examples/ex03-condcompile.cpp —— 平台宏与条件编译（节选）
const char* platform_name() {
#if defined(_WIN32)
    return "Windows";
#elif defined(__APPLE__)
    return "macOS";
#elif defined(__linux__)
    return "Linux";
#else
    return "unknown";
#endif
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-condcompile && /tmp/ex03-condcompile
c++ -D_WIN32 -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-win && /tmp/ex03-win   # 模拟 Windows 分支
```

实测输出（已验证）：原生编译输出 `platform = macOS` / `compiler = Clang` / `has <optional> = yes`；`-D_WIN32` 变体输出 `platform = Windows`。要点：**`-D_WIN32` 模拟技巧让"Windows 分支"在本机也能验证**——分支代码是否可编译、逻辑是否正确，不必真上 Windows；平台分支只进一个，`#elif` 顺序决定优先级。

### 示例 2：同一份代码，双编译器编译，对比告警（练习 1 的题目代码）

对应练习"同项目用 GCC/Clang/MSVC 编译"（题目代码在 `exercises/README.md` 练习 1，修复版见 `exercises/sol-01-fix-warnings.cpp`）：同一份代码藏着两个常见笔误，两家编译器各自报自己的告警（本机两家都是 clang，措辞一致；GCC/MSVC 命名不同需对应机器实测）：

```cpp
// warn.cpp —— 同一份代码，分别用 c++ 与 clang++ 编译，对比告警
#include <cstdio>
int check(int x) {
    if (x = 42) {          // 笔误：赋值被当条件用
        return x;
    }
    return 0;
}
int main() {
    int a = 3, b = 4;
    if (a < b < 0) {       // 链式比较：数学意义与直觉不同
        std::printf("yes\n");
    }
    return check(a);
}
```

```bash
c++      -std=c++20 -Wall -c warn.cpp -o /dev/null
clang++  -std=c++20 -Wall -c warn.cpp -o /dev/null
```

实测输出（已验证，Apple clang 21 与 Homebrew clang 21 完全一致）：

```text
warn.cpp:3:11: warning: using the result of an assignment as a condition without parentheses [-Wparentheses]
warn.cpp:3:11: note: place parentheses around the assignment to silence this warning
warn.cpp:10:15: error: chained comparison 'X < Y < Z' does not behave the same as a mathematical expression [-Wparentheses]
warn.cpp:10:15: warning: result of comparison of constant 0 with expression of type 'bool' is always false [-Wtautological-constant-compare]
2 warnings and 1 error generated.
```

要点：**clang 21 把链式比较当 error（不是 warning）**，而赋值当条件只是 `-Wparentheses` 警告 + fix-it 修复建议；同一告警的命名各家不同（Clang `-Wtautological-constant-compare` 本机实测，GCC `-Wbool-compare` 据公开资料未验证）。**坑：只依赖某一个编译器的告警会漏报另一家的视角**——跨编译器项目在 CI 矩阵里多套都开，`-Werror`/`/WX` 把告警升级为错误。修复版（`==` + 显式 `&&`）双编译器零警告，见 `exercises/sol-01-fix-warnings.cpp`。

### 示例 3：C++14 → C++17 → C++20 特性边界（文档内嵌演示）

同一个文件分别按 C++14/17/20 编译，报错位置就是特性边界（完整可运行文件见 `exercises/sol-03-std-probe.cpp` 的特性宏探测；边界观察为文档内嵌演示，编译命令照抄即可复现）：

```cpp
// features.cpp —— 同一文件，分别用 -std=c++14 / c++17 / c++20 编译，观察报错边界
#include <cstdio>
#include <string>
#include <utility>

template <typename T>
concept Addable = requires(T a, T b) { a + b; };   // C++20 concepts

int main() {
    auto [id, name] = std::pair<int, std::string>{1, "one"};   // C++17 结构化绑定
    std::printf("%d=%s\n", id, name.c_str());
    return 0;
}
```

```bash
c++ -std=c++14 features.cpp -o /dev/null   # 期望报错
c++ -std=c++17 features.cpp -o /dev/null   # 期望报错（只剩 concepts）
c++ -std=c++20 features.cpp -o feat && ./feat
```

实测输出（已验证，Apple clang 21，行号随文件内容略有出入）：

```text
# -std=c++14（摘录）：
features.cpp: error: unknown type name 'concept'               # concepts 在 C++14 直接编译失败
features.cpp: warning: decomposition declarations are a C++17 extension [-Wc++17-extensions]
# -std=c++17：只剩 concept 的 error，结构化绑定告警消失
# -std=c++20：编译通过，运行输出 1=one
```

要点：三代特性边界一目了然——**结构化绑定（C++17）在 C++14 下被当扩展接受并告警（`-pedantic-errors` 才升级为错误）；concepts（C++20）在 C++20 之前直接编译失败**。Clang 报错措辞与 GCC 不同（`unknown type name` vs GCC 的 `'concept' does not name a type`），但边界一致——这正是"编译器支持和语言标准不是完全同步"的现场。

### 示例 4：编译器差异宏实测（examples/ex04-compilers.cpp）

同一段代码分别用 Apple clang 与 Homebrew clang 编译，宏值如实打印：

```cpp
// examples/ex04-compilers.cpp —— 编译器家族与版本宏（节选）
const char* family() {
#if defined(_MSC_VER)
    return "MSVC";
#elif defined(__clang__)
    return "Clang";
#elif defined(__GNUC__)
    return "GCC";
#else
    return "unknown";
#endif
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex04-compilers.cpp -o /tmp/ex04-apple && /tmp/ex04-apple
clang++ -std=c++20 -Wall -Wextra ex04-compilers.cpp -o /tmp/ex04-hb && /tmp/ex04-hb
```

实测输出（已验证，节选）：

```text
# Apple clang 21.0.0（c++）:
compiler family: Clang
  __clang_major__ = 21, __clang_minor__ = 0
  __GNUC__        = 4.2.1 (GCC 主版本号；Clang 下是兼容值)
  __cplusplus     = 202002
  __VERSION__     = "Apple LLVM 21.0.0 (clang-2100.1.1.101)"

# Homebrew clang 21.1.8（clang++）:
compiler family: Clang
  __clang_major__ = 21, __clang_minor__ = 1
  __GNUC__        = 4.2.1 (GCC 主版本号；Clang 下是兼容值)
  __cplusplus     = 202002
  __VERSION__     = "Homebrew Clang 21.1.8"
```

要点：**判编译器家族必须 `_MSC_VER` → `__clang__` → `__GNUC__`**——两家 Clang 的 `__GNUC__` 都是 4.2.1（兼容值），用 `__GNUC__` 判断"是不是 GCC"会误判；`__VERSION__` 是编译器自我介绍，可精确区分 Apple 版与上游版。MSVC 的 `_MSC_VER`（如 1938 = VS2022 17.8）为微软文档值，未在本环境验证。

### 示例 5：简单跨平台路径适配层（examples/ex05-path.*）

对应练习"为平台 API 写适配层"与推荐项目"跨平台文件工具库"的最小形态：路径拼接的 POSIX `/` 与 Windows `\` 差异，全部收进一个 `.cpp`，接口层零平台宏：

```cpp
// examples/ex05-path.h —— 平台适配层：对外只暴露统一接口
#pragma once
#include <string>
namespace path {
    char separator();
    std::string join(const std::string& base, const std::string& rel);
}
```

```cpp
// examples/ex05-path.cpp —— 用平台宏隔离实现（节选）
namespace path {
#if defined(_WIN32)
    const char kSep = '\\';     // Windows 路径分隔符
#else
    const char kSep = '/';      // POSIX 路径分隔符
#endif
    std::string join(const std::string& base, const std::string& rel) {
        if (base.empty()) return rel;
        if (base.back() == kSep) return base + rel;
        return base + kSep + rel;
    }
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-path && /tmp/ex05-path
c++ -D_WIN32 -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-win && /tmp/ex05-win
```

实测输出（已验证）：POSIX 分支输出 `data/config.json` / `data/config.json` / `separator: /`；`-D_WIN32` 分支输出 `data\config.json` / `data/\config.json` / `separator: \`。要点：**平台差异全部隔离在 `path.cpp` 一个翻译单元**，头文件没有任何平台宏——调用方、测试、其它模块永远只面对统一接口，这就是"跨平台代码应隔离平台相关层"的最小示范。**坑：能用 `std::filesystem`（C++17）就别手写路径**——标准库已替你跨平台，适配层留给 filesystem 管不到的 API（socket、动态库、线程名等）。

## 7. 总结

### 关键要点

1. **标准是文档先行，编译器逐个特性实现**：C++ 三年一版（11/14/17/20/23），编译器支持总是滞后，"编译器支持和语言标准不是完全同步"是常态不是意外
2. **`__cplusplus` 是标准边界的第一道判据**：199711L/201103L/201402L/201703L/202002L/202302L；MSVC 需 `/Zc:__cplusplus`；**不写 `-std=` 时各家默认标准不同**（本机实测 Apple clang 默认 gnu++14、Homebrew clang 默认 gnu++17）
3. **判断具体特性用特性测试宏**：`__has_include`/`__has_cpp_attribute`/`__cpp_lib_*`；**`__cpp_lib_*` 必须先 include 对应头文件才定义**（本机实测：`__cpp_lib_format` 仅在 C++20 定义为 202110）
4. **平台宏与条件编译是跨平台的语法基础**：`_WIN32`/`__linux__`/`__APPLE__` 判平台，`_MSC_VER`/`__clang__`/`__GNUC__` 判编译器（判序：`_MSC_VER` → `__clang__` → `__GNUC__`，因为 Clang 的 `__GNUC__` 实测报 4.2.1 兼容值）；`__unix__` 在 macOS 实测不定义
5. **固定宽度类型与固定字节序是二进制格式的地基**：`<cstdint>` 保证"恰好 N 位"（`static_assert` 把关），跨平台序列化固定用大端（网络序），别用 `reinterpret_cast` 把结构体当字节流
6. **跨平台代码应隔离平台相关层**：平台差异收进适配层（一个 .cpp + 一个头文件），接口层零平台宏，调用方无感知；能用 `std::filesystem` 就别手写路径
7. **`#pragma once` 与 include guard 二选一或双保险**：guard 是标准机制但宏名靠人，`#pragma once` 简洁但非标准（现代编译器全支持）
8. **公共接口用标准属性表达意图**：`[[deprecated]]`/`[[nodiscard]]` 可移植，`__has_cpp_attribute` 判断支持度（本机实测 deprecated=201309、nodiscard=201907）；编译器私有写法（`__attribute__`/`__declspec`）留给老代码
9. **ABI 是二进制契约，标准不规定**：名字修饰（Itanium `_Z1fi` vs MSVC `?f@@YAHH@Z`）是"换编译器就链接失败"的根源；`extern "C"` 关闭修饰（本机实测符号 `_plain`）
10. **标准库 ABI 影响二进制兼容**：libstdc++/libc++/MSVC STL 布局不同（本机实测 libc++ `std::string` 24 字节、SSO 22 字符），内联命名空间（`__cxx11`/`__1`）做 ABI 版本化；混用新老 ABI 的库会链接失败
11. **不要在公共接口暴露不稳定细节**：内部类型、实现宏、平台细节一律不进公共头文件
12. **可移植以多套编译器最保守者为准**：CI 矩阵（GCC/Clang/MSVC）+ 警告对齐 + `-Wpedantic` 抓非标准扩展；同一告警命名各家不同（Clang `-Wtautological-constant-compare` 实测，GCC `-Wbool-compare` 未验证）

### 阶段验收清单

- [ ] 能说明 **C++17 和 C++20 的主要差异**：结构化绑定/if constexpr/std::filesystem vs concepts/ranges/协程/modules/std::format，并能用 `-std=` 切换验证（6. 示例 3）
- [ ] 能解释 `__cplusplus` 的六个版本值，知道 MSVC 默认报 199711L 的坑，会用 `__has_include`/`__cpp_lib_*` 探测特性（3.1）
- [ ] 能说清平台宏与编译器宏的区别与判序（`_WIN32` vs `_MSC_VER`/`__clang__`/`__GNUC__`），知道 Clang 的 `__GNUC__` 是兼容值（3.2、6. 示例 4）
- [ ] 能用 `<cstdint>` 固定宽度类型与"大端序列化"写跨平台二进制格式，并解释为什么不能 `reinterpret_cast` 结构体（3.5/3.6、练习 4/5）
- [ ] 能处理**跨平台编译问题**：平台宏分支、条件编译、适配层隔离，同一份代码在双编译器零警告通过（6. 示例 1/2/5）
- [ ] 能识别 **ABI 风险**：名字修饰差异、标准库 ABI（内联命名空间、`_GLIBCXX_USE_CXX11_ABI`）、"换编译器/换标准库就链接失败"的原因（4.2/4.3）

### 跨语言对比：标准演进与可移植性

| 维度 | C++ | C | Java | Python | Rust |
|------|-----|---|------|--------|------|
| 标准节奏 | 三年一版（11/14/17/20/23），编译器逐个实现 | C11/C17/C23，实现碎片化 | 大版本演进（8/11/17/21 LTS），向后兼容承诺强 | 无 ISO 标准，PEP 演进，解释器版本差异 | 六年大版本（2015/2018/2021/2024），edition 机制 |
| 编译器/实现 | GCC/Clang/MSVC 三家鼎立 | GCC/Clang/MSVC + 大量嵌入式编译器 | javac + 多厂商 JVM | CPython 为事实标准 | rustc 一家，跨平台行为一致 |
| 可移植性保障 | 平台宏 + 条件编译 + 适配层（手工） | 同 C++，宏更原始 | 字节码 + JVM，"一次编译到处跑" | 解释执行，源码即分发 | 标准库平台抽象（std::fs 等）内置 |
| ABI 稳定性 | 无标准 ABI，Itanium/MSVC 分裂 | 平台级 C ABI 相对稳定 | 有 JVM 规范 ABI，但主要靠字节码分发 | 无 ABI 概念 | 官方明示不承诺稳定 ABI |
| 公共接口稳定性 | 标准属性 + 工程纪律 | 同上，更弱 | 语言级保证 | 约定（PEP + 文档） | edition + RFC 稳定性保证 |

一句话：**Java 用"字节码 + JVM"把可移植性做成平台承诺，Python 用"解释器"绕开编译期差异，Rust 用"单一编译器 + edition"压缩差异面；C/C++ 是唯一把可移植性留给开发者手工管理的系统语言**——平台宏、条件编译、适配层、ABI 意识是 C++ 工程师的必修课，这正是本阶段训练的能力。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：同一份代码双编译器编译对齐告警（★）、为平台 API 写适配层（★★）、检查项目使用的 C++ 标准特性（★★）、字节序无关的二进制序列化（★★）、跨平台二进制文件头（★★★）——练习 1~3 与 roadmap ph11「练习」小节的三个承诺一一对应，练习 4/5 覆盖「学习内容」中的固定宽度类型与字节序。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**跨平台文件工具库**——路径适配层（join/normalize/extension，平台宏隔离 + `-D_WIN32` 双分支自测）+ 基于 `std::filesystem` 的文件信息/目录遍历 + CLI（join/normalize/ext/info/ls）+ Makefile，是 roadmap 推荐项目①「跨平台文件工具库」的落地，也是"能处理跨平台编译问题"验收的直接产物。roadmap 推荐项目②「编译器兼容性实验项目」作为扩展方向（见 project/README.md 扩展方向）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

**ph12+（roadmap 第 12 节，目录待建）：对象生命周期、值类别与所有权深入** — 本阶段是当前最后一个有目录的阶段（roadmap 第 12~23 节均为规划中，目录待建）。ph11 讲清了"同一份代码在不同编译器/平台上的边界"，后续可深入 ph12 回到语言内部：对象何时创建、移动、销毁，prvalue/xvalue/lvalue 值类别，RVO/NRVO 与所有权转移；届时用本阶段的 `-std` 与多编译器意识去验证"移动语义是 C++11 起的标准特性"这类边界问题，标准与可移植性的功底会直接复用。
