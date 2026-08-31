# C 语言 C 标准、编译器与可移植性阶段

> 面向系统底层、存储引擎方向，本阶段理解不同 C 标准和编译器差异，写出更可移植的代码。

## 1. 概述

C 标准、编译器与可移植性阶段是 C 学习路线中"从写 Linux 程序走向写可移植程序"的节点。目标：**能说清 C89~C23 各标准带来什么、GCC/Clang/MSVC 三家编译器差异在哪，能用条件编译和 stdint.h 写出不随平台变化而变形的代码**——一句话，理解不同 C 标准和编译器差异，写出更可移植的代码。

| 核心维度 | 覆盖内容 |
|----------|---------|
| C 标准演进 | C89、C99、C11、C17、C23 的基本差异与新增特性 |
| 编译器格局 | GCC、Clang、MSVC 的默认标准、扩展体系与诊断差异 |
| API 边界 | ISO C 标准库 vs POSIX/Linux API vs Windows API |
| 条件编译 | `#ifdef`/`#if`、feature test macros、平台抽象层 |
| 固定宽度整数 | stdint.h 的 int8_t/uint32_t 与 inttypes.h 格式宏 |
| 可移植性风险 | 编译器扩展、类型宽度假设、严格别名与 restrict |

本阶段承接 ph08 的系统编程能力：ph08 里的 unistd.h、pthread、epoll 都是 POSIX/Linux API，本阶段把"标准 C 能做哪些、平台 API 又补了哪些"的边界彻底理清——以后写存储引擎时，凡是跨平台的部分都靠本阶段的写法兜底。

这个阶段只涉及 C 标准与编译器的差异认知、条件编译、固定宽度整数与可移植写法，**不涉及未定义行为的系统化梳理、Sanitizer 工具链、字节序与二进制格式的位级处理和跨语言互操作 ABI** — 那些是 ph10 未定义行为 UB 与常见坑阶段、ph11 Sanitizer / 静态分析 / 单元测试阶段、ph12 字节序、内存对齐与二进制格式解析阶段和 ph14 C 与 C++ / Python / Rust 互操作阶段的内容。

## 2. 来源与演变

C 的标准化始于 1983 年：ANSI 成立 X3J11 委员会，把 K&R 时代散落的各种 C 方言统一起来，1989 年发布 **C89**（即 ANSI C，次年 ISO 采纳为 C90，两者基本等价）。C89 引入了**函数原型**（prototype）、`void*`、`const`/`volatile` 限定符，并把标准库头文件（stdio.h/stdlib.h/string.h 等）固定下来——从此"写标准 C"有了明确依据。

演进主线是一条"每 12 年一次大版本"的节奏。**C99**（1999）带来 `//` 注释、for 循环内声明变量、`stdint.h`、`long long`、`%zd/%zu` 格式与 `inline`；**C11**（2011）把多线程与原子操作（`_Atomic`、`_Thread_local`）、`_Generic`、匿名结构体、`_Static_assert` 收进标准，还提供了标准自带的 `<threads.h>` 线程库（应用不多，pthread 仍是事实标准）；**C17**（2017）只做缺陷修复，无新特性；**C23**（2023）是 12 年来第一次大更新：`nullptr`、`typeof`、`constexpr`、二进制字面量 `0b1010`、`[[attributes]]`、`#embed`。

编译器格局则是"三足鼎立"：**GCC**（GNU Compiler Collection，1987 年 Stallman 发起）是 Linux 默认编译器，对 C 标准的实现最完整；**Clang**（2007 年苹果发起，LLVM 的前端）编译快、诊断信息最友好；**MSVC**（微软）随 Visual Studio 分发，C 标准支持长期滞后，近年才逐步补齐 C11/C17。同时必须分清三个层次：**ISO C 是语言与标准库标准，POSIX 是系统接口标准，Windows API 是微软私有接口**——`printf`/`fopen` 属于 ISO C，`open`/`fork`/`pthread`/`epoll` 属于 POSIX，`CreateFile`/`WaitForSingleObject` 属于 Windows API。

| 标准 | 年份 | 关键特性 |
|------|------|---------|
| C89 (ANSI C) | 1989 | 函数原型、`void*`、`const`/`volatile`、标准库头文件定型 |
| C99 | 1999 | `//` 注释、循环内声明、`stdint.h`、`long long`、`%zd/%zu`、`inline`、VLA（变长数组） |
| C11 | 2011 | `_Atomic`/`_Thread_local`、`_Generic`、`_Static_assert`、匿名结构体、`<threads.h>` |
| C17 | 2017 | 缺陷修复为主，无重大新特性（C11 勘误版） |
| C23 | 2023 | `nullptr`、`typeof`、`constexpr`、二进制字面量、`[[attributes]]`、`#embed` |

本文示例以 **C11** 为基线（C99 之后、C23 普及之前，GCC/Clang/MSVC 三家支持度最一致的公共子集，覆盖本阶段全部主题：stdint.h、`_Static_assert`、`_Generic`），现代工具链（GCC 11+/Clang 16+）默认支持 C11，无需额外选项。验证工具链：Apple clang 21.0.0（macOS arm64，即 `cc`），另以 Homebrew clang 21.1.8 复核；GCC 与 MSVC 未在本环境提供（macOS 的 `gcc` 实为 Apple clang）。这个阶段的语法是 C 标准中最稳定的部分——C99 引入的 stdint.h 与格式宏至今二十余年未变。

## 3. 语法与参数

### 3.1 C 标准版本差异速查

同一份源码换 `-std=` 编译，就能直观体会标准差异：

```c
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
int main(void) {
    /* C99: for 循环内声明变量, C89 下直接报错 */
    for (int i = 0; i < 3; i++)
        printf("%d ", i);
    /* C99: stdint.h 固定宽度类型 */
    uint32_t magic = 0xCAFEu;
    /* C99: %zu 打印 size_t, PRIx32 打印 uint32_t */
    printf("\nmagic = 0x%" PRIx32 " (%zu 字节)\n", magic, sizeof magic);
    return 0;
}
```

```bash
# 1. C99 编译运行, 正常
cc -std=c99 -Wall -Wextra std_diff.c -o std_diff && ./std_diff
# 2. C89 严格模式, 硬报错: 循环内声明是 C99 特性(// 注释同理)
cc -std=c89 -Wall -Wextra -pedantic-errors std_diff.c -o std_diff
```

| 写法/特性 | 需要标准 | 说明 |
|-----------|---------|------|
| `//` 注释、for 循环内声明 | C99 | 最常用的 C99 特性，C89 下编译报错 |
| `stdint.h`、`long long`、`%zd/%zu` | C99 | 固定宽度类型与 size_t 打印 |
| `_Static_assert`、`_Generic`、`_Atomic` | C11 | 编译期断言、泛型选择、原子操作 |
| `nullptr`、`typeof`、`0b1010` 字面量 | C23 | 需要 GCC 13+ / Clang 16+，MSVC 尚不支持 |
| VLA（变长数组） | C99，C11 起改为可选 | 现代编译器不保证支持，**尽量别用** |

**要点（坑必背）**：

- **编译器默认不是严格标准模式**：GCC/Clang 默认 `-std=gnu17`（C17 + GNU 扩展），`-std=c11 -pedantic` 才是严格模式，能暴露"依赖扩展"的代码。
- **C23 还没普及**：写库要按 C99/C11 公共子集，别急着用 `nullptr`/`typeof`，否则 MSVC 和老编译器直接编译失败。

### 3.2 编译器差异：GCC vs Clang vs MSVC

三个编译器通过预定义宏自报家门：

```c
#include <stdio.h>
int main(void) {
#if defined(_MSC_VER)
    printf("编译器: MSVC %d\n", _MSC_VER);
#elif defined(__clang__)
    printf("编译器: Clang %s\n", __clang_version__);
#elif defined(__GNUC__)
    printf("编译器: GCC %d.%d\n", __GNUC__, __GNUC_MINOR__);
#else
    printf("编译器: 未知\n");
#endif
    return 0;
}
```

| 维度 | GCC | Clang | MSVC |
|------|-----|-------|------|
| 出身 | GNU 项目（1987） | LLVM 前端（2007） | 微软 Visual Studio |
| 标识宏 | `__GNUC__` | `__clang__`（**同时定义 `__GNUC__`**） | `_MSC_VER` |
| 扩展体系 | `__attribute__((...))`、`__builtin_*` | 兼容 GCC 的 `__attribute__`，另有自己的内建 | `__declspec(...)`、`__pragma` |
| 诊断质量 | 全面 | 最友好（带颜色、带修复建议） | 一般，报错信息偏长 |
| 严格模式选项 | `-std=c11 -Wall -Wextra -pedantic` | 同左 | `/W4 /WX` |
| C 标准支持 | 最完整（含 C23 大部分） | 紧随其后 | 长期滞后，C99 的 VLA/复合字面量至今不支持 |

**要点（坑必背）**：

- **Clang 为了兼容海量现有代码，也定义 `__GNUC__`**——判断"是不是 GCC 家族"用 `__GNUC__`，判断"具体是不是 Clang"必须**先查 `__clang__`**（顺序不能反）。
- **MSVC 的 C 支持是"能用子集"**：跨平台项目以 C99/C11 公共子集为基线，`_Atomic`、`__attribute__` 这类东西一律绕开。

### 3.3 标准库与平台 API 边界

```c
#include <stdio.h>
#ifdef _WIN32
#  include <io.h>                              /* Windows: _access 等 POSIX 替代 */
#  define FILE_EXISTS(p) (_access((p), 0) == 0)
#else
#  include <unistd.h>                          /* POSIX: access/F_OK */
#  define FILE_EXISTS(p) (access((p), F_OK) == 0)
#endif
int main(void) {
    /* access 是 POSIX API; unistd.h 不在 ISO C 标准头文件列表里 */
    if (FILE_EXISTS("data.txt"))
        printf("文件存在 (POSIX access 封装)\n");
    else
        printf("文件不存在或不可访问\n");
    return 0;
}
```

| 层次 | 代表 API | 可用范围 | 归属 |
|------|---------|---------|------|
| ISO C 标准库 | printf、fopen、malloc、time | 所有平台 | ISO/IEC 9899 |
| POSIX | open、read、fork、pthread、socket、epoll | Linux/macOS/BSD 等 Unix 系 | IEEE 1003.1 |
| Windows API | CreateFile、WaitForSingleObject、GetProcAddress | Windows | 微软私有 |

**要点（坑必背）**：**标准 C 与 POSIX/Linux API 不是一回事**（本阶段必会概念）——`printf` 到处可用，`open`/`pthread` 只在 Unix 系，`CreateFile` 只在 Windows；一个"可移植"的程序 = ISO C 为主干 + 把平台 API 差异收进小封装（见第 6 章示例 2/5 与 project/）。

### 3.4 条件编译与平台抽象

```c
#include <stdio.h>
/* 平台抽象: 把差异收敛到一个宏里, 业务代码零 #ifdef */
#ifdef _WIN32
#  define PATH_SEP "\\"
#else
#  define PATH_SEP "/"
#endif
int main(void) {
#if defined(_WIN32)
    printf("平台: Windows\n");
#elif defined(__linux__)
    printf("平台: Linux\n");
#elif defined(__APPLE__)
    printf("平台: macOS\n");
#else
    printf("平台: 其他\n");
#endif
    printf("路径分隔符: %s\n", PATH_SEP);
    return 0;
}
```

**要点（坑必背）**：

- **平台宏由编译器预定义**：`_WIN32` 在 32/64 位 Windows 上都定义（判断 Windows 用它）；`__linux__`、`__APPLE__` 由 GCC/Clang 定义，MSVC 不定义。
- **feature test macros（特性测试宏）**：glibc 默认把非标准 POSIX 函数藏起来，要在源码**顶部（任何 #include 之前）**写 `#define _POSIX_C_SOURCE 200809L`（或 `-D_POSIX_C_SOURCE=200809L`），`strdup`、`clock_gettime`、`pthread` 等声明才可见；`_GNU_SOURCE` 则一次打开全部 GNU 扩展。
- 抽象原则：**按"功能"抽象，不按"平台"散落**——差异收敛到宏或独立小模块，业务代码里不出现 `#ifdef`。

### 3.5 stdint.h 固定宽度整数

```c
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
int main(void) {
    uint32_t seq = 0x00000001u;   /* 恰好 32 位, 任何平台都不漂移 */
    int64_t  ts  = -1;            /* 恰好 64 位 */
    printf("seq = %08" PRIx32 "\n", seq);   /* 格式宏: 平台无关的打印 */
    printf("ts  = %" PRId64 " (%zu 字节)\n", ts, sizeof ts);
#ifdef INT32_MAX
    printf("int32_t 存在\n");     /* 该宏存在 = 平台有恰好 32 位的类型 */
#endif
    return 0;
}
```

| 类型 | 保证宽度 | 说明 |
|------|---------|------|
| `int` / `long` | 仅最小范围（int≥16 位、long≥32 位） | 实际宽度随平台 ABI 变，**不能用于协议** |
| `uint8_t`/`uint16_t`/`uint32_t`/`uint64_t` | 恰好 N 位 | 平台**没有恰好该宽度**的类型时不存在（用 `INT32_MAX` 等宏检测） |
| `int_least32_t`/`int_fast32_t` | 至少 32 位 / 最快的那档 | 不要求恰好宽度，可移植性最稳 |
| `intptr_t`/`uintptr_t` | 能容纳指针的整数 | 指针 ↔ 整数互转的唯一安全类型 |

**要点（坑必背）**：打印固定宽度整数**必须用 `<inttypes.h>` 的格式宏**（`PRId32`/`PRIx64` 等），写死 `%d`/`%ld` 在宽度不同的平台上就是 UB；`uint32_t` 这类类型让协议字段宽度**可读、可断言、可审计**——本阶段必会概念"使用 uint32_t 等类型能明确协议字段宽度"。

### 3.6 编译器扩展与可移植性风险

```c
/* 编译器扩展必须包一层并给回退: 非 GCC 家族退化为普通表达式 */
#if defined(__GNUC__)
#  define LIKELY(x)   __builtin_expect(!!(x), 1)
#else
#  define LIKELY(x)   (x)
#endif
#include <stdio.h>
int main(void) {
    int ret = 0;
    if (LIKELY(ret == 0))          /* 提示分支预测: 大多数时候成立 */
        printf("成功路径\n");
    return 0;
}
```

常见扩展与风险：

| 扩展 | 平台/编译器 | 风险 |
|------|------------|------|
| `__attribute__((packed/unused/format))` | GCC/Clang | MSVC 不认，需 `__declspec` 或放弃 |
| `__builtin_*`（expect/swap/ctz 等） | GCC/Clang | 其它编译器无对应内建 |
| `#pragma once` | 三大编译器都支持 | **不是标准**，标准做法是 include guard |
| 零长度数组 `int a[0]` | GCC/Clang | 非标准，C23 用 `int a[]` 柔性数组替代 |
| 语句表达式 `({ ... })` | GCC/Clang | MSVC 完全不支持 |

**要点（坑必背）**：**编译器扩展会降低可移植性**（本阶段必会概念）——换编译器/编译器版本即编译失败或语义改变；对策三选一：`#ifdef __GNUC__` 包一层并提供回退实现、用标准写法替代、或干脆不用。`-pedantic` 会把"用了扩展"的代码全部标出来。

### 3.7 严格别名与 restrict 简介

```c
#include <stdint.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    uint32_t bits = 0x3F800000u;   /* 即 float 1.0f 的位模式 */
    float f;
    memcpy(&f, &bits, sizeof f);   /* 标准做法: 用 memcpy 搬运位模式 */
    printf("f = %g\n", f);         /* 输出 1 */
    return 0;
}
```

**严格别名规则（strict aliasing rule）**：同一块内存只能通过"兼容类型"访问——`*(float *)&bits` 这种**类型双关（type punning）**是未定义行为，优化器按"两者无关"乱序后结果不可预测（**同样的代码，-O2 下行为可能变化**）。正解是 `memcpy`（或 C11 起用联合体搬运，但 memcpy 最无争议）。

**restrict**：向编译器承诺"两个指针不指向同一对象"，换取优化空间——`memcpy` 的签名就是 `void *memcpy(void *restrict dst, const void *restrict src, size_t n)`；只在确实不重叠时使用，滥用就是自造 UB。这两块都是 ph10 未定义行为与常见坑阶段的铺垫。

## 4. 底层原理

### 4.1 为什么 C 标准规定"最小范围"而非固定宽度

C 诞生于 PDP-11 时代，目标是从 8 位单片机到 64 位主机"一次编写、到处编译"。若标准规定 `int` 必须 32 位，8/16 位机器要么无法实现、要么性能崩坏——所以标准只给**最小范围**（char≥8 位、short≥16 位、int≥16 位、long≥32 位、long long≥64 位），把确切宽度留给实现去定（implementation-defined）。

这是**可移植性与性能的权衡**：确切宽度其实是平台 ABI 的一部分，一旦发布就冻结（x86-64 System V ABI 规定 long=8 字节），库与二进制才能互操作；"最小范围"让每个平台选自己最快最自然的宽度，代价就是程序员不能用 `int` 承载固定宽度的协议字段——这正是 stdint.h 存在的意义。

### 4.2 编译器前端/后端与方言

现代编译器都是三段流水线：

```text
GCC:   前端(词法/语法 ──▶ GENERIC/GIMPLE) ──▶ 中端优化 ──▶ 后端(GIMPLE ──▶ RTL ──▶ 汇编/机器码)
LLVM:  Clang 前端(──▶ LLVM IR)           ──▶ 优化 passes ──▶ 后端 codegen(x86/ARM/RISC-V/...)
```

- **扩展（方言）在前端进入**：`__attribute__`、`__builtin_expect` 这类扩展由**前端**解析成 IR 的特殊节点，中端和后端天然支持——所以"支持什么方言"由前端决定，这也是 Clang 能"兼容 GCC 扩展"的原因（它照抄了 GCC 的解析规则）。
- `-std=gnu11`（默认）打开 GNU 扩展方言；`-std=c11 -pedantic` 关闭方言、只认标准——同一个源码在两种模式下可能编译出**行为不同**的程序（扩展语义、UB 假设不同）。

### 4.3 预处理与条件编译的展开机制

预处理是**纯文本替换**，发生在编译器正式开工之前；`#include`、`#define`、`#if` 全部在这一步完成。

```text
.c 源文件 ──预处理(cc -E)──▶ 展开后的 .i ──编译──▶ .s 汇编 ──汇编──▶ .o 目标文件 ──链接──▶ 可执行文件
```

- **`#if` 的求值顺序**：先把宏全部展开，再按整数常量表达式求值；**未定义的标识符按 0 处理**——所以 `#if defined(X)` 比 `#if X` 安全得多（`X` 忘了定义时，`#if X` 静默当成 0，`#if defined(X)` 明确区分"未定义"与"值为 0"）。
- 调试手段：`cc -E` 看展开后的完整源码，`cc -dM -E - </dev/null` 列出编译器全部预定义宏（平台宏、`__STDC_VERSION__` 都在里面）。
- 条件编译是"编译期裁剪"：不满足 `#if` 条件的分支**根本不会进入编译器**，语法错误都不会报——这也是平台分支写错时"静默少了一段代码"的根源。

### 4.4 平台 ABI 如何决定类型宽度：LP64 vs LLP64

| 数据模型 | 典型平台 | int | long | 指针 |
|----------|---------|-----|------|------|
| ILP32 | 32 位 Linux/Windows | 4 | 4 | 4 |
| LP64 | 64 位 Linux/macOS | 4 | **8** | 8 |
| LLP64 | 64 位 Windows | 4 | **4** | 8 |

- **为什么 Windows x64 的 long 是 4 字节**：微软选 **LLP64**（long 保持 32 位）是为了让 Win32 API 里大量 `long` 参数的签名原样保留、二进制兼容旧代码；代价是 Windows 上 `long` 与 `int` 等宽，**与指针不等宽**。
- 推论（坑）：**把指针塞进 `long`（如 `(long)p`）在 Windows 上会截断**；指针 ↔ 整数必须用 `intptr_t`/`uintptr_t`；**`sizeof(long)`、`sizeof(void*)`、`sizeof(size_t)` 在三大平台上各不相同**，跨平台代码一律不假设。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 跨平台库（日志、配置、网络） | 条件编译、平台抽象、feature test macros |
| 网络协议实现（TCP 消息、文件格式） | uint16_t/uint32_t 字段、PRIx32 格式宏 |
| 存储引擎的元数据与页结构 | 固定宽度整数、_Static_assert 尺寸断言 |
| 多编译器 CI（GCC + Clang 双编译） | 编译器差异、-Wall -Wextra -pedantic |
| 嵌入式与驱动开发 | 特征宏、__STDC_VERSION__、数据模型（ILP32/LP64） |
| 跨平台命令行工具分发 | ISO C 函数优先、平台 API 收敛封装 |

**不适合**此阶段的事项：

- 未定义行为的深入排查（ph10 未定义行为 UB 与常见坑阶段：数组越界、悬垂指针、整数溢出、严格别名案例）
- Sanitizer 与调试工具链（ph11 Sanitizer / 静态分析 / 单元测试阶段：ASan/UBSan/TSan 的使用）
- 字节序与二进制格式的位级处理（ph12 字节序、内存对齐与二进制格式解析阶段：大端/小端、htonl、位域布局）
- 跨语言互操作 ABI（ph14 C 与 C++ / Python / Rust 互操作阶段：C ABI、FFI、JNI 等）

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令见其 README）。示例 1~5 均在 macOS + Apple clang 21.0.0 验证（`cc -Wall -Wextra -std=c11` 零警告）；涉及 `_WIN32` 分支的示例 2/5 只验证了 POSIX 分支，Windows 分支未在本环境验证（需 Windows）。

### 示例 1：用 stdint.h 定义跨平台协议字段

对应 roadmap 练习"用 stdint.h 重写协议字段定义"与推荐项目"协议字段类型定义库"。

```c
// examples/ex01-stdint-protocol.c —— 用 stdint.h 定义跨平台协议字段（已验证）
/* 固定 16 字节的协议头: 每个字段宽度与平台无关 */
typedef struct {
    uint16_t magic;    /* 魔数 0xCAFE */
    uint8_t  version;  /* 协议版本 */
    uint8_t  flags;    /* 标志位 */
    uint32_t seq;      /* 报文序号 */
    uint32_t length;   /* 载荷长度 */
    uint32_t crc32;    /* 校验和 */
} proto_header_t;
_Static_assert(sizeof(proto_header_t) == 16, "协议头必须是 16 字节");
/* 逐字段拷贝到字节缓冲, 规避结构体对齐/填充的平台差异 */
unsigned char wire[16];
memcpy(wire + 0, &h.magic, 2);
wire[2] = h.version;
wire[3] = h.flags;
memcpy(wire + 4, &h.seq, 4);
/* 位域: 紧凑, 但布局(位顺序/对齐)由编译器决定 —— 跨平台协议慎用 */
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex01-stdint-protocol.c -o ex01
# 2. 运行
./ex01
```

要点：`uint32_t` 保证字段宽度不随 int/long 平台差异漂移；`_Static_assert` 把"尺寸契约"写进编译期（**编译不过就不许上线**）；结构体存在对齐填充，上"线"要逐字段 memcpy；**位域布局是实现定义的**，跨平台协议里应改用显式掩码位运算；字节序（大端/小端）仍随平台不同，网络传输前还需 htonl（ph12 字节序、内存对齐与二进制格式解析阶段深入）。

### 示例 2：条件编译平台抽象（Windows/Linux 路径分隔符、sleep 封装）

对应 roadmap 练习"为 Windows/Linux 分别封装路径分隔符"。

```c
// examples/ex02-platform-abstraction.c —— 条件编译平台抽象（已验证, POSIX 分支）
#include <stdio.h>
#ifdef _WIN32
#  include <windows.h>
#  define PATH_SEP "\\"
#  define SLEEP_MS(ms) Sleep(ms)
#else
#  include <unistd.h>
#  define PATH_SEP "/"
#  define SLEEP_MS(ms) usleep((ms) * 1000)
#endif
int main(void) {
    printf("路径分隔符: %s\n", PATH_SEP);
    printf("数据文件: data%slog.txt\n", PATH_SEP);
    SLEEP_MS(300);   /* 业务代码零 #ifdef */
    return 0;
}
```

```bash
# Linux / macOS:
cc -Wall -Wextra -std=c11 examples/ex02-platform-abstraction.c -o ex02 && ./ex02
# Windows (MSVC):  cl /W4 ex02-platform-abstraction.c
```

要点：`_WIN32` 在 32/64 位 Windows 上都定义，判断平台用它；抽象原则是"**按功能抽象**"——路径分隔符、sleep 这类差异收敛成一组宏，业务代码零 `#ifdef`；扩展练习：再封装目录创建（`mkdir` vs `_mkdir`，见 exercises 练习 2）与文件删除（`remove` 是 ISO C，可跨平台）。

### 示例 3：跨平台类型宽度探测

对应必会概念"不同平台上 int、long、指针宽度可能不同"。

```c
// examples/ex03-type-widths.c —— 跨平台类型宽度探测（已验证, LP64 数据模型）
#include <stdint.h>
#include <stdio.h>
int main(void) {
    printf("int        = %2zu 字节\n", sizeof(int));
    printf("long       = %2zu 字节\n", sizeof(long));
    printf("void* 指针 = %2zu 字节\n", sizeof(void *));
    printf("int32_t    = %2zu 字节\n", sizeof(int32_t));
    printf("int64_t    = %2zu 字节\n", sizeof(int64_t));
    printf("size_t     = %2zu 字节\n", sizeof(size_t));
    printf("intptr_t   = %2zu 字节\n", sizeof(intptr_t));
    return 0;
}
```

```bash
cc -Wall -Wextra -std=c11 examples/ex03-type-widths.c -o ex03 && ./ex03
```

预期输出：64 位 Linux/macOS 为 int=4、long=8、pointer=8（LP64）；64 位 Windows 为 long=4（LLP64）；32 位平台三者都是 4（ILP32）。**坑**：`sizeof` 结果随平台变化，序列化/协议里不能直接写结构体；把指针存进 `long` 在 Windows 会截断，用 `intptr_t`。

### 示例 4：特征宏检测（__STDC_VERSION__ 判断 C 标准版本 + feature macros）

对应学习内容"各标准基本差异"与"条件编译与平台抽象"。

```c
// examples/ex04-feature-macros.c —— 特征宏检测（已验证, -std=c99/c11/c17 输出正确）
#include <stdio.h>
int main(void) {
#if defined(__STDC_VERSION__)
    printf("C 标准: C%d\n", (int)(__STDC_VERSION__ / 100 % 100));
#else
    printf("C 标准: C89 或更早\n");
#endif
#if defined(_WIN32)
    printf("平台: Windows\n");
#elif defined(__linux__)
    printf("平台: Linux\n");
#elif defined(__APPLE__)
    printf("平台: macOS\n");
#endif
#if defined(__x86_64__) || defined(_M_X64)
    printf("架构: x86-64\n");
#elif defined(__aarch64__)
    printf("架构: AArch64\n");
#endif
    return 0;
}
```

```bash
# 1. 默认 c11 编译运行
cc -Wall -Wextra -std=c11 examples/ex04-feature-macros.c -o ex04 && ./ex04   # 输出 C11
# 2. 换标准对比
cc -Wall -Wextra -std=c99 examples/ex04-feature-macros.c -o ex04c99 && ./ex04c99   # 输出 C99
cc -Wall -Wextra -std=c17 examples/ex04-feature-macros.c -o ex04c17 && ./ex04c17   # 输出 C17
# 3. 换编译器对比
clang -Wall -Wextra -std=c11 examples/ex04-feature-macros.c -o ex04c && ./ex04c
```

要点：`__STDC_VERSION__` 从 C99 起定义（199901L），C11=201112L、C17=201710L、C23=202311L，是判断"哪些语法可用"的标准手段；`_POSIX_C_SOURCE` 是 feature test macro——glibc 默认不暴露非标准 POSIX 函数，必须在**任何 #include 之前** `#define _POSIX_C_SOURCE 200809L`（或 `-D` 传入），`strdup`/`clock_gettime` 才可见。

### 示例 5：可移植日志库骨架

对应推荐项目"跨平台日志库"。

```c
// examples/ex05-portable-log.c —— 可移植日志库骨架（已验证, POSIX 分支）
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <time.h>
#ifdef _WIN32
#  include <process.h>
#  define getpid _getpid
#else
#  include <unistd.h>
#endif
void log_msg(log_level_t level, const char *fmt, ...) {
    char ts[32];
    time_t now = time(NULL);
    struct tm *t = localtime(&now);  /* ISO C: 本地时间 */
    strftime(ts, sizeof ts, "%Y-%m-%d %H:%M:%S", t);
    fprintf(g_log, "[%s][%s][pid=%" PRId64 "] ", ts, level_names[level],
            (int64_t)getpid());      /* getpid 经封装: POSIX/Windows 通用 */
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fflush(g_log);                   /* 及时落盘, 崩溃不丢尾部日志 */
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex05-portable-log.c -o ex05
# 2. 运行(日志写当前目录, 请先 cd /tmp 再运行)
cd /tmp && /path/to/ex05 && cat app.log
```

要点：时间（time/localtime/strftime）、文件（fopen/fprintf）、可变参数（va_*）全是 ISO C，天然跨平台；**唯一需要抽象的差异（getpid、路径、线程）用 `#ifdef` 收进小封装**；`"pid=%" PRId64` 是字符串字面量拼接，拼出平台无关的 64 位格式串；扩展方向：加 mutex 保证线程安全（ph08）、按大小轮转日志文件、级别过滤——完整实现见本阶段 project/ 跨平台日志库。

## 7. 总结

### 关键要点

1. **C 标准是"最小公分母"，平台 API 才是"能力上限"**：printf/fopen 到处可用，open/pthread/epoll 只在 POSIX，CreateFile 只在 Windows
2. **类型宽度由平台 ABI 决定，不能写死**：int 至少 16 位、long 至少 32 位；64 位 Linux 的 long=8，Windows x64 的 long=4（LP64 vs LLP64）
3. **协议与文件格式字段一律用 stdint.h**：uint16_t/uint32_t 保证宽度，inttypes.h 的 PRIx32/PRId64 保证打印
4. **编译器扩展会降低可移植性**：__attribute__、__builtin_*、#pragma once 都要用 #ifdef 包一层并给回退，或干脆不用
5. **条件编译按"功能"抽象**：差异收敛到宏/小模块，业务代码零 #ifdef；feature test macros 在源码顶部定义
6. **特征宏是跨标准写代码的开关**：__STDC_VERSION__ 判标准版本，_POSIX_C_SOURCE 控制 POSIX 声明可见性
7. **严格别名与 restrict 是隐藏的 UB 来源**：类型双关用 memcpy，restrict 只在指针确实不重叠时用（ph10 展开）
8. **用 _Static_assert 把尺寸契约写进编译期**：协议头 16 字节、页大小 4096，编译不过就不许上线
9. **同一份源码要多编译器编译**：GCC + Clang（+MSVC）双编译是发现可移植性问题最廉价的手段
10. **标准不是"最强的"，而是"最小的"**：`-std=c11 -pedantic` 打开严格模式，才能暴露依赖扩展的代码

### 跨语言对比：类型宽度与可移植性

| 维度 | C | C++ | Go | Java | Rust |
|------|---|-----|----|------|------|
| 整数类型 | int/long 宽度随平台 | 同 C（继承） | 由名字决定（int32/int64） | 固定（int 恒 32 位） | 由名字决定（i32/i64/usize） |
| 固定宽度类型 | stdint.h（C99 起） | `<cstdint>` | 内建 int32/int64 | 内建 | 内建 i8..i128 |
| 指针/机器字 | intptr_t/uintptr_t | std::intptr_t | uintptr | 无指针概念 | usize/isize |
| 打印格式 | %d/%ld 易错 → PRIx32 | 同 C | fmt 自动推导 | 类型安全 | println! 类型安全 |
| 未定义行为 | 有（溢出、别名、越界） | 有（继承 C） | 无（溢出 wrap 或 panic） | 无（越界抛异常） | 默认无（debug panic / release wrap） |
| 跨平台策略 | 条件编译 + 宏 + 扩展 | 同 C + 模板 | GOOS/GOARCH 编译期常量 | JVM 抹平平台差异 | cfg!(target_os) 条件编译 |

C 是最"裸露"的：类型宽度、未定义行为、可移植性全部暴露给程序员，没有运行时兜底——存储引擎恰好需要这种精确控制；Go/Rust/Java 用语言机制抹平宽度差异，代价是牺牲与硬件的零距离。

### 阶段验收清单

- [ ] 能说清 C 标准与平台 API 的区别（printf 属 ISO C、open/pthread 属 POSIX、CreateFile 属 Windows API）
- [ ] 能避免依赖未声明的编译器扩展（用 #ifdef 包裹并给回退，或用 -pedantic 自查）
- [ ] 能写出跨平台类型定义（协议字段用 uint32_t + PRIx32，尺寸用 _Static_assert 固化）
- [ ] 能说出不同平台 int/long/指针宽度的差异（LP64 vs LLP64）并解释原因
- [ ] 能用条件编译完成平台抽象（路径分隔符、sleep 封装等，业务代码零 #ifdef）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题与 roadmap「练习」一一对应：

- 用 stdint.h 重写协议字段定义（★★）：int/long 协议头改成 uint16_t/uint32_t + `_Static_assert`，打印换成 PRIx32/PRIx64
- 为 Windows/Linux 分别封装路径分隔符（★★）：参考示例 2，再封装目录创建（mkdir/_mkdir）与文件删除（remove）
- 尝试用 GCC 和 Clang 编译同一项目（★）：`-std=c11` 双编译对比警告，`-std=c89 -pedantic-errors` 观察回退分支（-std= 多版本编译对比与平台探测程序合并为示例 4 的扩展玩法）

完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：跨平台日志库——级别过滤 + 线程安全 + 按大小轮转 + 固定宽度文件头，Makefile 构建，演示程序内置行数自检。建议完成练习后再动手。roadmap 的另一个推荐项目「协议字段类型定义库」由示例 1 与 exercises 练习 1 覆盖。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[未定义行为 UB 与常见坑](../ph10-ub/10-ub.md) —— 数组越界、悬垂指针、整数溢出、严格别名等 UB 的识别与规避；本阶段埋下的 restrict、类型双关、有符号溢出问题将在那里系统化排查。
