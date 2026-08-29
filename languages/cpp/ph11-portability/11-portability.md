# C++ C++ 标准、编译器与可移植性阶段

> 面向高性能系统、存储引擎方向，本阶段能看懂 C++ 标准演进（C++11~C++23）与三大编译器（GCC/Clang/MSVC）的差异，会用平台宏与条件编译隔离平台相关代码，能识别 ABI 与标准库实现差异带来的二进制兼容风险，让"能编译"升级为"同一份代码多编译器多平台都能构建"。

## 1. 概述
本阶段定位：**能用 `__cplusplus` 与特性测试宏判断编译器支持的语言标准边界，说清 C++11/14/17/20/23 各代的代表性特性；能用 `#if defined(_WIN32)` 等平台宏与条件编译隔离平台相关代码，写出 GCC/Clang/MSVC 三套编译器、Windows/Linux/macOS 三类平台都能构建的跨平台代码；能识别名字修饰、标准库实现与内联命名空间带来的 ABI 二进制兼容风险**。学完本阶段，面对"Linux 上好好的、Windows 上编译不过"或"换了个编译器就报一堆错"这类问题，能按"标准边界 → 编译器差异 → 标准库差异 → ABI 风险"的顺序排查，而不是到处堆 `#ifdef` 打补丁。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 标准演进 | C++11/14/17/20/23 特性边界、`__cplusplus`、特性测试宏 |
| 编译器差异 | GCC、Clang、MSVC 的支持度、警告体系与扩展差异 |
| 标准库实现 | libstdc++、libc++、MSVC STL 的差异与二进制兼容影响 |
| 平台宏与条件编译 | `_WIN32`/`__linux__`/`__APPLE__`/`_MSC_VER`、`#if/#ifdef` |
| ABI 与标准的关系 | 名字修饰、Itanium/MSVC ABI、内联命名空间、ABI 风险识别 |
| 跨平台工程 | 平台适配层、公共接口稳定、CI 多编译器矩阵 |

**范围边界**：承接 ph10 构建调试与工具链——ph10 把 `-std=c++20` 当"开关"用，本阶段把开关背后的东西讲透：标准边界在哪、各编译器支持到哪、跨平台构建的差异从何而来，把 CMake/工具链能力应用到"同一份代码多编译器多平台都能构建"上；**不涉及** 对象生命周期与值类别深入（ph12）、Rule of 0/3/5 与 RAII 进阶（ph13）、UB 系统化梳理（ph15）、动态库加载与插件机制深入（ph19，本阶段只讲 ABI 概念与风险识别）、跨语言互操作（ph20）；本阶段重在标准意识、平台隔离与二进制兼容风险判断。

## 2. 来源与演变
C++ 标准由 ISO/IEC 14882 规定，节奏是"**标准先行、编译器跟进**"：1998 年 C++98 确立模板、STL、异常、RTTI 等核心能力，此后近十年几乎停滞（2003 年只有一次小修）；2011 年 C++11 带来语言史上最大的一次现代化——`auto`、lambda、移动语义、智能指针、`nullptr`；此后进入三年一版的节奏：C++14 小步改进（泛型 lambda、auto 返回类型推导）、C++17 补全实用特性（结构化绑定、if constexpr、std::filesystem、string_view）、C++20 大规模扩展（concepts、ranges、协程、modules、std::format）、C++23 收尾（std::print、std::expected、mdspan）。关键认知：**标准是"文档"先发布，编译器逐个特性实现，且三大编译器节奏不一**——查支持度要看特性表，查标准细节看权威参考。

| 标准 | 发布时间 | 标志性特性 | 支持现状（GCC 15 / Clang 17 实测） |
|------|---------|-----------|-----------------------------------|
| C++98 | 1998 | 模板、STL、异常、RTTI | 全支持（后续标准的基线） |
| C++11 | 2011 | auto、lambda、移动语义、智能指针、nullptr | 全支持 |
| C++14 | 2014 | 泛型 lambda、auto 返回类型、std::make_unique | 全支持 |
| C++17 | 2017 | 结构化绑定、if constexpr、std::filesystem、string_view | 全支持 |
| C++20 | 2020 | concepts、ranges、协程、modules、std::format、`<=>` | 主要特性支持，modules 等仍未三家完全一致 |
| C++23 | 2023 | std::print、std::expected、mdspan | 本机已实测 std::print 可用，部分特性未落地 |

三年一版让 C++ 持续吸收现代语言特性，但也放大了"**编译器支持和语言标准不是完全同步**"：C++20 发布四年后，三大编译器仍没把全部特性实现完——modules 在 GCC 上支持不完整、MSVC 与 Clang 各有各的编译标志（ph10 已见）；C++23 的 mdspan 至今只有部分实现。可移植代码因此要以"**三套编译器共同支持的特性交集**"为基准，写之前查特性表而不是想当然。权威参考：cppreference（含各标准版本差异与跨编译器 Compiler support 特性表）、isocpp.org（标准委员会官网，含 FAQ 与提案）；编译器侧分别是 gcc.gnu.org/projects/cxx-status.html、clang.llvm.org/cxx_status.html、learn.microsoft.com 的 C++ 标准符合性表。

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
- **坑：MSVC 默认把 `__cplusplus` 报成 199711L**——除非加 `/Zc:__cplusplus`，跨编译器判断前先确认宏真值
- **特性测试宏（Feature Test Macro）**：`__has_include(头文件)` 判断头文件是否存在（C++17 标准化）、`__has_cpp_attribute(属性)` 判断属性支持（见 3.4）、C++20 起标准化的 `__cpp_*`/`__cpp_lib_*` 系列（如 `__cpp_lib_filesystem`、`__cpp_concepts`）精确到单个特性
- 判断"能不能用某个特性"优先用特性测试宏：`#if __has_include(<optional>)` 回答"这个库在不在"，比 `#if __cplusplus >= 201703L` 回答"编译器声称什么标准"更贴近真相
### 3.2 平台宏与条件编译
**必会概念：平台宏由编译器预定义，用来在源码里区分平台与编译器**。三大平台与两大编译器（含 Clang 兼容 GCC 宏）的核心宏：

| 宏 | 定义者 | 含义 |
|----|--------|------|
| `_WIN32` | MSVC/MinGW 等 Windows 编译器 | 32/64 位 Windows 都定义；判断"是 Windows"用这个 |
| `_WIN64` | 同上 | 仅 64 位 Windows |
| `__linux__` | GCC/Clang | Linux 平台 |
| `__APPLE__` | Apple Clang/GCC | macOS/iOS 等 Apple 平台 |
| `__unix__` | GCC/Clang | Unix 系（Linux/macOS 都命中） |
| `_MSC_VER` | MSVC | MSVC 版本号（如 1938 = VS2022 17.8） |
| `__GNUC__` | GCC（Clang 为兼容也定义） | GCC 主版本号 |
| `__clang__` | Clang | 1 = 正在用 Clang |

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
- **坑：宏可以来自命令行**——`g++ -DDEBUG`、CMake `target_compile_definitions` 都往源码注入宏，平台宏只是编译器内置的那一部分
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
- 有保护时同一头文件被包含多次不会重复定义（见示例 3）；**漏写保护**的后果是 `redefinition of 'NoGuard'` 编译错误
### 3.4 标准属性：`[[deprecated]]`、`[[nodiscard]]` 等
**必会概念：C++11 起有标准属性语法 `[[attr]]`，跨编译器可移植**；此前 GCC/Clang 用 `__attribute__((...))`、MSVC 用 `__declspec(...)`，各写各的：

| 属性 | 标准 | 用途 |
|------|------|------|
| `[[deprecated("提示语")]]` | C++14 | 标记弃用 API，使用处编译告警 |
| `[[nodiscard]]` | C++17 | 忽略返回值时告警 |
| `[[maybe_unused]]` / `[[fallthrough]]` | C++17 | 抑制未使用告警 / 声明 switch 落空是有意的 |
| `[[likely]]` / `[[unlikely]]` | C++20 | 分支概率提示，辅助优化 |

要点：
- 用 `__has_cpp_attribute(名字)` 判断属性支持度，返回值是引入版本（如 `deprecated` 为 201309L，即 C++14）
- **公共 API 要退役时用 `[[deprecated("改用新接口")]]` 过渡**，比直接删掉/静默改掉安全；`[[nodiscard]]` 适合"忽略返回值必然出 bug"的函数（如打开资源类的接口）
- **坑：老代码里的 `__attribute__((deprecated))`/`__declspec(deprecated)` 是编译器私有写法**，新代码一律用标准属性；特性检测写法见 3.1 与示例 1
### 3.5 三大编译器差异速览：GCC、Clang、MSVC
**必会概念：GCC、Clang、MSVC 是三个独立实现，标准支持、警告体系、扩展各有差异**：

| 维度 | GCC | Clang | MSVC |
|------|-----|-------|------|
| 默认标准 | gnu++17 | gnu++17 | C++14（需 `/std:c++17` 等显式指定） |
| 常用警告 | `-Wall -Wextra -Wpedantic` | 同左，另有 `-Weverything` | `/W4`、`/WX`（警告即错误） |
| 诊断风格 | 直接、简洁 | 详细、带修复建议（fix-it） | 详细、带文档链接 |
| 标准实现节奏 | 稳健、偏保守 | 快、新特性落地早 | 跟随生态需求，Modules 落地早 |
| 平台 | Linux/Unix 为主 | 全平台 | Windows 为主 |
| 默认标准库 | libstdc++ | libstdc++（Linux）/ libc++（macOS） | MSVC STL |

要点：
- **坑：依赖编译器扩展 = 放弃可移植**——GNU 扩展（`__int128`、`typeof`、语句表达式）在 MSVC 上直接编译失败；C++20 Modules 的编译标志三家各异（ph10 已见）
- 同一份代码三套编译器都"零警告"通过，才算可移植；CI 里开 GCC/Clang/MSVC 构建矩阵，方法见示例 2
- 告警名各家不同（GCC `-Wbool-compare` vs Clang `-Wtautological-constant-compare`，见示例 2 实测），对齐警告靠"同一批代码三套都过"

## 4. 底层原理
### 4.1 ABI 与标准的关系
**必会概念：API 是源码契约，ABI 是二进制契约，标准只规定前者**。API（Application Programming Interface）：函数签名、类接口、语义——源码能编译就说明满足；ABI（Application Binary Interface）：函数在二进制里叫什么名字、参数怎么传（寄存器/栈）、对象怎么布局、异常怎么传播、虚表长什么样——二进制能链接、能运行才说明满足。
- ISO 标准对 ABI **几乎不做规定**：`struct S { int a; char b; };` 的布局、`int f(int)` 的符号名，都由编译器 + 平台决定
- 推论一：同一平台、同一 ABI 家族内（都走 Itanium C++ ABI 的 GCC/Clang）编出的 .o 通常可互链；跨 ABI 家族（Itanium vs MSVC）**不可能**互链
- 推论二：**标准库 ABI 是 ABI 的一部分**——同一编译器，如果链接的库是另一套标准库实现编的，`std::string` 布局不同，运行即崩
- C++ ABI 不如 C ABI 稳定：C 有平台级调用约定（System V AMD64 等），C++ 只有事实标准 Itanium C++ ABI（GCC/Clang 系）与 MSVC ABI（Windows）两家并存
### 4.2 名字修饰（Name Mangling）与 Itanium/MSVC ABI
**必会概念：C++ 重载要求函数名携带参数类型，编译器把源码名字"修饰"成二进制符号名**。`int f(int)` 与 `double f(double)` 必须编成两个不同的符号：

```text
# Linux ELF / Itanium C++ ABI：int f(int) → _Z1fi，double f(double) → _Z1fd
# macOS Mach-O：额外加一个前导下划线 → __Z1fi（本机 nm 实测）
# MSVC ABI：int f(int) → ?f@@YAHH@Z（? 开头、@ 分隔、YAH 编码"返回 int、参数 int"）
```
```bash
nm mangle.o | grep " T "     # 看符号：__Z1fi __Z1fd _plain _main
c++filt __Z1fi               # 还原：f(int)
objdump -t mangle.o          # 更完整的符号表
```
要点：
- **`extern "C"` 关闭名字修饰**：`extern "C" int plain(int)` 的符号就是 `plain`——跨语言、跨 ABI 边界（插件、C 库、pybind11）全靠它（ph19/ph20 深入）
- 推论：**"换编译器就链接失败"的第一嫌疑是名字修饰不兼容**——GCC 编的 .o 拿给 MSVC 链接，符号对不上；同编译器换标准库实现同理
- 永远别手写符号名、别在 C++ 侧绕过修饰；动态库导出/插件接口一律 `extern "C"` 或稳定包装层
### 4.3 标准库实现差异与二进制兼容
**必会概念：三大标准库实现各有各的内存布局与 ABI 版本策略，直接影响二进制兼容**：

| 实现 | 默认使用方 | 特点 |
|------|-----------|------|
| libstdc++ | GCC（Linux 默认） | `std::string` 64 位下 32 字节、SSO 15 字符；C++11 后 ABI 用 `std::__cxx11::` 内联命名空间标记 |
| libc++ | Clang（macOS 默认） | `std::string` 64 位下 24 字节、SSO 22 字符；用 `std::__1::` 内联命名空间做 ABI 版本化 |
| MSVC STL | MSVC | `std::string` 32 字节；与前两者布局完全不同 |

要点：
- **内联命名空间（Inline Namespace）**：`namespace std { inline namespace __cxx11 { class string {...}; } }`——符号名带上 `__cxx11`，新旧 ABI 的 `string` 是不同的符号、可共存
- 经典现场：libstdc++ 的 `_GLIBCXX_USE_CXX11_ABI`（GCC 5 起默认 1）切换新旧 ABI——**同一编译器，一个库用旧 ABI 编、程序用新 ABI 编，链接报 `undefined reference to std::__cxx11::basic_string<...>`**
- 推论：**"标准库 ABI 可能影响二进制兼容"**——换编译器版本、换标准库、动 `_GLIBCXX_USE_CXX11_ABI`，都可能让"昨天还好的二进制"今天链接失败
- 必会概念落地：**不要在公共接口暴露不稳定细节**——公共头文件只放稳定 API，内部类型、实现宏、平台细节一律收进实现（示例 5 的适配层就是最小示范）
### 4.4 编译器差异的根源与"标准≠支持"
三个编译器是**独立实现**，各自选择实现顺序与优先级：
- **Clang** 激进：新特性落地快、诊断质量高（带 fix-it 修复建议），常被当作"新标准探路者"
- **GCC** 稳健：实现保守但成熟，是 Linux 服务器默认选择，长尾平台支持最好
- **MSVC** 跟随生态需求：Windows 生态优先，Modules 支持落地早，但 `__cplusplus` 等宏行为与 GCC/Clang 不一致
- 标准三年一版、编译器按季度/年度发版 → **特性表上"部分支持/待实现"长期存在**（C++20 发布四年后 modules 仍未三家完全一致，见 3.5）
- 同一特性在不同编译器下的"宽容度"不同：旧标准模式下新特性会被当**扩展**接受并告警（示例 4 实测：`-std=c++14` 下结构化绑定只是 `-Wc++17-extensions` 告警，`-pedantic-errors` 才升级为错误）——这正是"编译器支持和语言标准不是完全同步"的具体形态
- 实践结论：**写可移植代码 = 以三套编译器共同支持的交集为准 + 特性测试宏探测 + CI 矩阵验证 + `-Wpedantic` 抓非标准扩展**；把"换编译器报错"当常态演练，而不是最后一刻的惊吓

## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| 同一份代码三套编译器构建 | 标准边界、特性测试宏、警告级别对齐（`-Wall -Wextra` / `/W4`） |
| Linux/Windows/macOS 跨平台发布 | 平台宏、条件编译、平台适配层 |
| 动态库发布与升级 | ABI 稳定性、内联命名空间、`_GLIBCXX_USE_CXX11_ABI` |
| 第三方库接入 | 标准库实现差异、编译器扩展差异、ABI 匹配检查 |
| CI 多编译器矩阵 | GCC/Clang/MSVC 三套构建、特性表核对、`-Wpedantic` |
| 老代码/老库维护 | `__cplusplus` 判断、`[[deprecated]]` 弃用过渡、新老 ABI 切换 |

**不适合**此阶段的事项：
- **动态库加载与插件机制深入**（ph19）：dlopen/LoadLibrary、插件生命周期、符号解析——本阶段只讲 ABI 概念与风险识别
- **跨语言互操作**（ph20）：pybind11、C ABI 包装层、异常跨边界——本阶段 `extern "C"` 只做概念演示
- **对象生命周期与值类别深入**（ph12）：本阶段不讨论移动语义、值类别细节
- **UB 系统化梳理**（ph15）：本阶段只识别"扩展/非标准"带来的可移植风险，不展开 UB 分类

## 6. 代码示例
> 说明：示例均在本机（macOS，Apple Clang 17 + Homebrew GCC 15）实际编译运行验证；GCC 链接时 macOS 的 ld 可能额外打印一条与示例无关的 deployment version 提示，以下输出均已省略该噪音。Windows 分支用 `-D_WIN32` 在本机交叉验证。

### 示例 1：平台分支 + `__cplusplus` 特性检测
对应 roadmap 示例（`#if defined(_WIN32)` 平台分支）与练习"检查项目使用的 C++ 标准特性"：一段代码同时回答"我在哪个平台"与"编译器按哪个标准编译"。
```cpp
// platform.cpp —— 平台分支 + __cplusplus 标准检测
#include <cstdio>
int main() {
#if defined(_WIN32)
    std::printf("platform: Windows\n");
#elif defined(__APPLE__)
    std::printf("platform: macOS\n");
#elif defined(__linux__)
    std::printf("platform: Linux\n");
#else
    std::printf("platform: unknown\n");
#endif
#if __cplusplus >= 201703L
    std::printf("C++17 or newer: yes (__cplusplus = %ld)\n", (long)__cplusplus);
#else
    std::printf("C++17 or newer: no (__cplusplus = %ld)\n", (long)__cplusplus);
#endif
    return 0;
}
```
```bash
g++ -std=c++17 -Wall -Wextra platform.cpp -o platform && ./platform
```
```
platform: macOS
C++17 or newer: yes (__cplusplus = 201703)
```
```bash
g++ -D_WIN32 -std=c++17 platform.cpp -o platform_win && ./platform_win   # 模拟 Windows 分支
```
```
platform: Windows
C++17 or newer: yes (__cplusplus = 201703)
```
要点：**`-D_WIN32` 模拟技巧让"Windows 分支"在本机也能验证**——分支代码是否可编译、逻辑是否正确，不必真上 Windows；`__cplusplus` 是 `long`，打印要 `(long)` 强转配 `%ld`；平台分支只进一个，`#elif` 顺序决定优先级。
### 示例 2：同一份代码，GCC 与 Clang 分别编译，对比告警
对应练习"同项目用 GCC/Clang/MSVC 编译"：同一份代码藏着两个常见笔误，两个编译器各自报自己的告警，措辞与命名都不同。
```cpp
// warn.cpp —— 同一份代码，用 GCC 与 Clang 分别编译，对比告警
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
g++-15   -std=c++17 -Wall -c warn.cpp -o /dev/null
clang++  -std=c++17 -Wall -c warn.cpp -o /dev/null
```
GCC 输出：
```
warn.cpp: In function 'int check(int)':
warn.cpp:4:11: warning: suggest parentheses around assignment used as truth value [-Wparentheses]
warn.cpp: In function 'int main()':
warn.cpp:11:15: warning: comparison of constant '0' with boolean expression is always false [-Wbool-compare]
warn.cpp:11:11: warning: comparisons like 'X<=Y<=Z' do not have their mathematical meaning [-Wparentheses]
```
Clang 输出：
```
warn.cpp:4:11: warning: using the result of an assignment as a condition without parentheses [-Wparentheses]
warn.cpp:4:11: note: place parentheses around the assignment to silence this warning
warn.cpp:4:11: note: use '==' to turn this assignment into an equality comparison
warn.cpp:11:15: warning: comparisons like 'X<=Y<=Z' don't have their mathematical meaning [-Wparentheses]
warn.cpp:11:15: warning: result of comparison of constant 0 with expression of type 'bool' is always false [-Wtautological-constant-compare]
3 warnings generated.
```
要点：同样的问题，**GCC 与 Clang 的告警措辞、命名、详略全不一样**——GCC 说 "suggest parentheses..."、Clang 说 "using the result of an assignment as a condition" 且附 fix-it 修复建议；同一告警 GCC 叫 `-Wbool-compare`、Clang 叫 `-Wtautological-constant-compare`。**坑：只依赖某一个编译器的告警会漏报另一家的视角**——跨编译器项目在 CI 矩阵里三套都开，`-Werror`/`/WX` 把告警升级为错误。
### 示例 3：include guard 与 `#pragma once` 的实用头文件
对应必会概念"不要在公共接口暴露不稳定细节"的载体——头文件是公共接口的第一道关，防重复包含是基本功。
```cpp
// guard_style.h —— include guard 写法：可移植性最好，任何编译器都认识
#ifndef PH11_GUARD_STYLE_H
#define PH11_GUARD_STYLE_H
struct Guarded { int value = 1; };
#endif
```
```cpp
// pragma_style.h —— #pragma once 写法：简洁，但严格说是非标准扩展
#pragma once
struct Pragmatic { int value = 2; };
```
```cpp
// headermain.cpp —— 同一头文件被包含两次，不会重复定义
#include "guard_style.h"
#include "guard_style.h"     // 第二次包含：被 include guard 拦下
#include "pragma_style.h"
#include "pragma_style.h"    // 第二次包含：被 #pragma once 拦下
#include <cstdio>
int main() {
    Guarded g;
    Pragmatic p;
    std::printf("guarded=%d pragma=%d\n", g.value, p.value);
    return 0;
}
```
```bash
g++ -std=c++17 -Wall -Wextra headermain.cpp -o headermain && ./headermain
```
```
guarded=1 pragma=2
```
对照：漏写保护的头文件被包含两次直接编译失败：
```
In file included from noguard_main.cpp:2:
./no_guard.h:1:8: error: redefinition of 'NoGuard'
```
要点：**现代工程 `#pragma once` 可直接用，追求绝对可移植用 include guard**；guard 宏名带项目前缀防撞车；双保险写法两者都写也常见。
### 示例 4：C++14 → C++17 → C++20 特性边界（同一文件，三个 `-std`）
对应练习"检查项目使用的 C++ 标准特性"与验收"能说明 C++17 和 C++20 的主要差异"：同一个文件分别按 C++14/17/20 编译，报错位置就是特性边界。
```cpp
// features.cpp —— 同一文件，分别用 -std=c++14 / c++17 / c++20 编译，观察报错边界
#include <iostream>
#include <string>
#include <utility>
#include <vector>

// C++14：函数返回类型推导（auto 返回类型）
auto make_value() { return 42; }

// C++20：concepts（约束模板）
template <typename T>
concept Addable = requires(T a, T b) { a + b; };

template <Addable T>
T add(T a, T b) { return a + b; }

int main() {
    std::vector<std::pair<int, std::string>> items{{1, "one"}, {2, "two"}};
    for (auto [id, name] : items) {        // C++17：结构化绑定
        std::cout << id << "=" << name << "\n";
    }
    std::cout << "add=" << add(1, 2) << "\n";      // C++20：concepts
    std::cout << "v=" << make_value() << "\n";     // C++14：auto 返回
    return 0;
}
```
```bash
g++-15 -std=c++14 features.cpp -o /dev/null   # 期望报错
g++-15 -std=c++17 features.cpp -o /dev/null   # 期望报错（只剩 concepts）
g++-15 -std=c++20 features.cpp -o feat && ./feat
```
`-std=c++14` 的报错（摘录）：
```
features.cpp:12:1: error: 'concept' does not name a type; did you mean 'const'?
   12 | concept Addable = requires(T a, T b) { a + b; };
      | ^~~~~~~
      | const
features.cpp:12:1: note: 'concept' only available with '-std=c++20' or '-fconcepts'
features.cpp:14:11: error: 'Addable' has not been declared
features.cpp:19:15: warning: structured bindings only available with '-std=c++17' or '-std=gnu++17' [-Wc++17-extensions]
```
`-std=c++17` 的报错（摘录）：只剩 concepts 的错误，结构化绑定告警消失；`-std=c++20` 编译通过，运行输出：
```
1=one
2=two
add=3
v=42
```
要点：三代特性边界一目了然——**auto 返回类型（C++14）三档都能过；结构化绑定（C++17）在 C++14 下被当扩展接受并告警（`-pedantic-errors` 才升级为错误）；concepts（C++20）在 C++20 之前直接编译失败**。Clang 报错措辞不同（`unknown type name 'concept'`），但边界一致——这正是"编译器支持和语言标准不是完全同步"的现场：**新特性在旧标准下要么报错、要么降级为扩展告警**。
### 示例 5：简单跨平台路径适配层
对应练习"为平台 API 写适配层"与推荐项目"跨平台文件工具库"的最小形态：路径拼接的 POSIX `/` 与 Windows `\` 差异，全部收进一个 `.cpp`，接口层零平台宏。
```cpp
// path.h —— 平台适配层：对外只暴露统一接口，平台差异全部藏在实现里
#pragma once
#include <string>

namespace path {
    char separator();
    std::string join(const std::string& base, const std::string& rel);
}
```
```cpp
// path.cpp —— 用平台宏隔离实现：POSIX 用 '/', Windows 用 '\'
#include "path.h"

namespace path {
#if defined(_WIN32)
    const char kSep = '\\';     // Windows 路径分隔符
#else
    const char kSep = '/';      // POSIX 路径分隔符
#endif

    char separator() { return kSep; }

    std::string join(const std::string& base, const std::string& rel) {
        if (base.empty()) return rel;
        if (base.back() == kSep) return base + rel;   // 已带分隔符，不重复加
        return base + kSep + rel;
    }
}
```
```cpp
// pathmain.cpp —— 调用方只看到统一接口，不知道平台差异
#include "path.h"
#include <cstdio>
int main() {
    std::printf("%s\n", path::join("data", "config.json").c_str());
    std::printf("%s\n", path::join("data/", "config.json").c_str());
    std::printf("separator: %c\n", path::separator());
    return 0;
}
```
```bash
clang++ -std=c++17 -Wall -Wextra path.cpp pathmain.cpp -o pathapp && ./pathapp
g++-15  -std=c++17 -Wall -Wextra path.cpp pathmain.cpp -o pathapp_g && ./pathapp_g
```
```
data/config.json
data/config.json
separator: /
```
```bash
g++ -D_WIN32 -std=c++17 path.cpp pathmain.cpp -o path_win && ./path_win   # 模拟 Windows 实现
```
```
data\config.json
data/\config.json
separator: \
```
要点：**平台差异全部隔离在 `path.cpp` 一个翻译单元**，`path.h` 没有任何平台宏——调用方、测试、其它模块永远只面对统一接口，这就是"跨平台代码应隔离平台相关层"的最小示范；`-D_WIN32` 让 Windows 分支在本机也被编译和运行验证过。**坑：能用 `std::filesystem`（C++17）就别手写路径**——标准库已替你跨平台，适配层留给 filesystem 管不到的系统 API（socket、动态库、线程名等）。

## 7. 总结
### 关键要点
1. **标准是文档先行，编译器逐个特性实现**：C++ 三年一版（11/14/17/20/23），编译器支持总是滞后，"编译器支持和语言标准不是完全同步"是常态不是意外
2. **`__cplusplus` 是标准边界的第一道判据**：199711L/201103L/201402L/201703L/202002L/202302L；MSVC 需 `/Zc:__cplusplus`；判断具体特性用特性测试宏（`__has_include`/`__has_cpp_attribute`/`__cpp_lib_*`）
3. **平台宏与条件编译是跨平台的语法基础**：`_WIN32`/`__linux__`/`__APPLE__` 判平台，`_MSC_VER`/`__GNUC__`/`__clang__` 判编译器，组合条件用 `#if defined()`
4. **跨平台代码应隔离平台相关层**：平台差异收进适配层（一个 .cpp + 一个头文件），接口层零平台宏，调用方无感知
5. **`#pragma once` 与 include guard 二选一或双保险**：guard 是标准机制但宏名靠人，`#pragma once` 简洁但非标准（现代编译器全支持）
6. **公共接口用标准属性表达意图**：`[[deprecated]]`/`[[nodiscard]]` 可移植，`__has_cpp_attribute` 判断支持度；编译器私有写法（`__attribute__`/`__declspec`）留给老代码
7. **ABI 是二进制契约，标准不规定**：名字修饰（Itanium `_Z1fi` vs MSVC `?f@@YAHH@Z`）是"换编译器就链接失败"的根源；`extern "C"` 关闭修饰
8. **标准库 ABI 影响二进制兼容**：libstdc++/libc++/MSVC STL 布局不同，内联命名空间（`__cxx11`/`__1`）做 ABI 版本化；混用新老 ABI 的库会链接失败
9. **不要在公共接口暴露不稳定细节**：内部类型、实现宏、平台细节一律不进公共头文件
10. **可移植以三套编译器最保守者为准**：CI 矩阵（GCC/Clang/MSVC）+ 警告对齐 + `-Wpedantic` 抓非标准扩展
### 跨语言对比：标准演进与可移植性
| 维度 | C++ | C | Java | Python | Rust |
|------|-----|---|------|--------|------|
| 标准节奏 | 三年一版（11/14/17/20/23），编译器逐个实现 | C11/C17/C23，实现碎片化 | 大版本演进（8/11/17/21 LTS），向后兼容承诺强 | 无 ISO 标准，PEP 演进，解释器版本差异 | 六年大版本（2015/2018/2021/2024），edition 机制 |
| 编译器/实现 | GCC/Clang/MSVC 三家鼎立 | GCC/Clang/MSVC + 大量嵌入式编译器 | javac + 多厂商 JVM | CPython 为事实标准 | rustc 一家，跨平台行为一致 |
| 可移植性保障 | 平台宏 + 条件编译 + 适配层（手工） | 同 C++，宏更原始 | 字节码 + JVM，"一次编译到处跑" | 解释执行，源码即分发 | 标准库平台抽象（std::fs 等）内置 |
| ABI 稳定性 | 无标准 ABI，Itanium/MSVC 分裂 | 平台级 C ABI 相对稳定 | 有 JVM 规范 ABI，但主要靠字节码分发 | 无 ABI 概念 | 官方明示不承诺稳定 ABI |
| 公共接口稳定性 | 标准属性 + 工程纪律 | 同上，更弱 | 语言级保证 | 约定（PEP + 文档） | edition + RFC 稳定性保证 |

一句话：**Java 用"字节码 + JVM"把可移植性做成平台承诺，Python 用"解释器"绕开编译期差异，Rust 用"单一编译器 + edition"压缩差异面；C/C++ 是唯一把可移植性留给开发者手工管理的系统语言**——平台宏、条件编译、适配层、ABI 意识是 C++ 工程师的必修课，这正是本阶段训练的能力。
### 阶段验收标准
- 能说明 **C++17 和 C++20 的主要差异**：结构化绑定/if constexpr/std::filesystem vs concepts/ranges/协程/modules/std::format，并能用 `-std=` 切换验证（示例 4）
- 能处理**跨平台编译问题**：平台宏分支、条件编译、适配层隔离，同一份代码在 GCC/Clang 双编译器零警告通过（示例 1/2/5）
- 能识别 **ABI 风险**：名字修饰差异、标准库 ABI（内联命名空间、`_GLIBCXX_USE_CXX11_ABI`）、"换编译器/换标准库就链接失败"的原因（4.2/4.3）
### 进入下一阶段前
确保能完成以下练习：
- **同项目用 GCC/Clang/MSVC 编译**：对示例 2 的 warn.cpp 或自己的项目，分别用 g++-15 与 clang++ 编译，把两边告警差异列成表，用 `-Wall -Wextra` 对齐到零警告（提示：`-Werror` 强制；留意"同一告警两家命名不同"）
- **为平台 API 写适配层**：仿示例 5 给 ph09 的文件/网络代码加一层适配（路径、换行符、socket 细节），接口头文件不含任何平台宏（提示：平台差异收进一个 .cpp；用 `-D_WIN32` 在本机验证 Windows 分支）
- **检查项目使用的 C++ 标准特性**：把 ph10 工程模板里的代码逐条对照示例 4 的边界，列出用到的每个新特性属于哪个标准，确认 CMake 的 `CMAKE_CXX_STANDARD` 够用（提示：打印 `__cplusplus`、`__has_include` 探测、cppreference 特性表核对）
- 进阶（可选）：用 `nm`/`c++filt` 观察自己写的重载函数的名字修饰（4.2）；`-pedantic-errors` 抓出项目里所有非标准扩展
### 推荐项目
- **跨平台文件工具库**：示例 5 的完整形态——统一路径 API（join/normalize/扩展名提取）、目录遍历、文件大小/时间戳读取，POSIX 与 Windows 两套实现收进适配层，CMake 按平台选源文件，GCC/Clang 双编译器 + 可选 MSVC 验证——roadmap 指定项目，直接复用 ph10 工程模板，是"能处理跨平台编译问题"验收的直接产物
- **编译器兼容性实验项目**：一组故意跨标准/跨平台差异的代码（示例 4 的 features.cpp 扩展版 + 示例 2 的 warn.cpp 合集），记录"哪个特性在哪个编译器、哪个 `-std` 下报什么错"，整理成一份自己的编译器差异速查表——把"能识别 ABI 风险""能处理跨平台编译问题"的验收变成可复现的实验记录
### 下一阶段
**对象生命周期、值类别与所有权深入**（ph12-lifetime-values，文档规划中）—— ph11 讲清了"同一份代码在不同编译器/平台上的边界"，ph12 回到语言内部：对象何时创建、移动、销毁，prvalue/xvalue/lvalue 值类别，RVO/NRVO 与所有权转移；届时用本阶段的 `-std` 与多编译器意识去验证"移动语义是 C++11 起的标准特性"这类边界问题，标准与可移植性的功底会直接复用。
