# C 语言 C 与 C++ / Python / Rust 互操作阶段

> 面向跨语言 ABI 与高性能运行时基础，本阶段把"写好的 C 库"变成"其他语言都能调用的 C 库"——从 C ABI 与头文件接口出发，掌握动态库导出符号、extern "C"、opaque pointer 与 create/destroy、错误码与错误消息，并用 C++、Python（ctypes）、Rust（extern "C"）四种语言真实调用同一份 C 动态库，把"ABI 稳定优先于源码语法"变成肌肉记忆。

## 1. 概述

C 与 C++ / Python / Rust 互操作阶段是 C 学习路线中"从库到生态"的关卡。目标（roadmap §14）：**理解 C ABI 的边界，用 C 作为跨语言接口层**。ph07 讲过动态库的编译链接，ph09 讲过定宽整数与可移植类型，ph12 讲过二进制格式的字节序纪律，ph13 用 kvlog 库验证了可靠文件 IO——本阶段回答它们共同缺的那一环：**C 的函数与数据怎么穿过语言边界，被 C++、Python、Rust 可靠地调用**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| C ABI 与头文件接口 | 头文件即跨语言契约；extern "C" 守卫；简单稳定类型（int32_t / const char *）；ABI 稳定优先于源码语法 |
| 动态库导出符号 | 编译 .dylib/.so；nm 实测导出符号（T/t）；Mach-O 下划线前缀与 ELF 差异 |
| C++ 互操作 | C++ 调 C（extern "C" 头文件）；C 调 C++ 包装层（extern "C" 导出 C 接口） |
| Python 互操作 | ctypes 加载动态库；argtypes/restype 显式声明；指针出参；C 扩展 vs ctypes 取舍 |
| Rust 互操作 | extern "C" 声明；unsafe 调用边界；CString 与裸指针；错误码映射为 Result |
| opaque pointer 与 create/destroy | 句柄模式；"谁 create 谁 destroy"；结构体定义藏在 .c |
| 错误码与错误消息 | 0 成功/负数错误；err_out 出参；strerror 式消息函数；不用 errno |
| 跨语言所有权规则 | 字符串/数组/结构体的三种所有权约定；POD 结构体跨语言布局一致 |

这个阶段只涉及 C ABI 与跨语言互操作——头文件接口、动态库导出符号、C++ / Python / Rust 三方的调用与包装、opaque pointer 与 create/destroy、错误码与错误消息、跨语言所有权约定，**不涉及完整的状态机/回调框架/宏技巧与 API 工程化（ph15 高级 C 与代码质量阶段，roadmap 第 15 节）、存储引擎的完整 WAL/MemTable/SSTable 实现（[ph16 数据库存储引擎基础阶段](../ph16-storage-engine/16-storage-engine.md)，roadmap 第 16 节）和网络 socket 编程（ph08）** — 那些是 ph15 高级 C 与代码质量阶段、ph16 数据库存储引擎基础阶段和 ph08 Linux 系统编程阶段的内容；互操作中用到的 mmap/fsync 语义（ph13）、二进制字节序与 padding（ph12）只引用不展开；Python 的 C 扩展（写 CPython 扩展模块）只做与 ctypes 的取舍对比，具体写法（PyObject 引用计数、setup.py）不展开；Rust 的 bindgen/cbindgen 自动化工具只做提及。

## 2. 来源与演变

**C ABI 是"跨语言的汇编"——没有它，现代软件栈里 Python 调不到 SQLite、Rust 接不上系统库**。1970 年代 C 随 UNIX 普及，其函数调用约定与数据布局（参数怎么传、结构体怎么排、符号怎么命名）成为事实标准；后续语言（C++、Python、Rust、Go、Java 的 JNI）无一例外选择"按 C ABI 对接"而不是发明新约定——因为 C 的 ABI 简单、稳定、文档化，而且系统库几乎全是 C 接口。**设计哲学一句话：接口用最朴素的语言特性（定宽整数、指针、函数），把复杂特性（重载、对象、异常、所有权）留在语言内部**——ABI 稳定比源码语法更重要，因为跨语言边界的每一端都可能不再重新编译。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C（事实 ABI 标准） | 1970s | C 的函数调用约定与数据布局成为事实标准；后续语言都按 C ABI 对接 |
| C++（name mangling 诞生） | 1985 | C++ 靠名字改编（mangling）支持重载；与 C 库互操作开始需要显式声明 C 链接 |
| extern "C" 语法 | 1989 / C++98 | 正式语法：告诉编译器该声明/定义保持 C 链接与 C 命名；头文件守卫惯用法定型 |
| Windows DLL 导出 | 1990s | Windows 需要 `__declspec(dllexport)` 显式导出；POSIX 平台默认导出全部全局符号 |
| Python C API（C 扩展） | 1991 | CPython 解释器本身是 C；官方扩展机制是写 C 模块（PyObject、引用计数） |
| ctypes | 2006（Python 2.5） | 纯 Python 直接加载 C 动态库并声明函数签名，不必写一行 C 扩展代码 |
| Rust extern "C" | 2015（Rust 1.0） | 稳定的 FFI 边界：`extern "C"` 块 + unsafe 调用，成为 Rust 官方互操作基线 |
| C11 | 2011 | `_Static_assert`、`_Noreturn` 等，跨语言头文件的自描述与防御能力增强 |
| cbindgen | 2018 | 从 Rust 源码生成 C 头文件，反向 FFI（Rust 实现、C 头文件输出）的工程化 |
| Rust 2024 版（unsafe extern 块） | 2024 | `extern "C"` 块在 2024 edition 下必须写 `unsafe extern "C"`——边界显式化 |

本文示例以 **C11 + C++17 + Python 3.13（ctypes）+ Rust 1.92（edition 2021）** 为基线（四门语言当前稳定版本，覆盖"哪一端的语法都可能升级，但 C ABI 不动"的现实；C11 与全库 ph09/ph12/ph13 同一口径）。验证工具链：**Apple clang 21.0.0（`cc` / `c++`，macOS arm64）+ Python 3.13.9 + rustc 1.92.0**。全部 C 代码 `cc -Wall -Wextra -std=c11` 零警告、C++ 代码 `c++ -Wall -Wextra -std=c++17` 零警告、Rust 代码 `rustc -D warnings` 零警告；**每个调用方（C / C++ / Python / Rust）都在本机真实编译运行验证**，文档引用的输出均为实测。C ABI 是几十年来最稳定的接口层：**变化的是各语言的 FFI 语法（Python 2.5 的 ctypes → 3.13 仍是 ctypes），不是 C 侧的函数签名与数据布局**。

## 3. 语法与参数

### 3.1 C ABI 与头文件接口：头文件就是契约

跨语言接口的第一步不是写代码，是**写头文件**——它声明了函数签名、类型、常量，是所有调用方（C / C++ / Python / Rust）共同遵守的契约。三个要点：

```c
// examples/calc.h —— 节选：extern "C" 守卫与简单稳定类型（完整版见 examples/）
#ifndef CALC_H
#define CALC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 简单整数运算：定宽 int32_t，跨语言 ABI 稳定 */
int32_t calc_add(int32_t a, int32_t b);
int32_t calc_mul(int32_t a, int32_t b);

/* 除法：b == 0 或 out == NULL 返回 -1（错误码），结果写 *out；
 * 返回 0 表示成功 */
int calc_div(int32_t a, int32_t b, int32_t *out);

/* 字符串长度（不含结尾 \0）：只读借用 s，不修改、不释放调用方的内存；
 * s == NULL 返回 -1（空指针返回错误码，而不是崩溃） */
int32_t calc_strlen(const char *s);

#ifdef __cplusplus
}
#endif

#endif /* CALC_H */
```

**简单稳定的 C 类型**（roadmap 必会概念）：参数与返回值只用 `int32_t`/`int64_t`、`const char *`、`uint8_t *` 这类定宽、跨语言都有标准封装的类型——不用 `int`/`long`（平台宽度不定，ph09），不用 `_Bool`（部分 FFI 边界布局有坑），字符串约定 NUL 结尾（各语言 FFI 都有标准转换），字节数组带显式长度参数（二进制值可能含 `\0`，见 3.8 与 ex06）。

**extern "C" 守卫**：`#ifdef __cplusplus / extern "C" { ... } / #endif` 三行让同一个头文件被 C 编译器包含时是普通声明、被 C++ 包含时保持 C 链接（符号不 mangling）。这是"C 头文件能被 C++ 直接包含"的唯一机制，忘写它 C++ 就链接失败（3.5 有实测报错）。

### 3.2 动态库导出符号：nm 实测

跨语言调用依赖**动态库导出符号**：只有导出（且可调用）的符号才能被其他语言链接到。macOS 上编译并实测：

```bash
# 1. 编译动态库（macOS; Linux 用 -shared -fPIC 生成 .so）
cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
# 2. 实测导出符号（-gU: 只列全局导出; T = 文本段可调用）
nm -gU /tmp/ph14-ex/libcalc.dylib
```

实测输出（本机一次运行）：

```text
00000000000002e8 T _calc_add
0000000000000328 T _calc_div
0000000000000308 T _calc_mul
0000000000000384 T _calc_strlen
```

四个函数全部以 `T` 导出（T = 全局文本段符号，可被链接调用；小写 `t` 是文件局部符号，外部调不到；`U` 是未定义符号，由链接器从其他库满足）。**macOS 的 Mach-O 符号带下划线前缀（`_calc_add`），Linux 的 ELF 不带（`calc_add`）**——链接器在背后处理这个差异，你的代码不用管，但 `nm` 输出对不上号时要知道是这个原因。POSIX 平台默认导出全部全局函数，不需要额外标记；Windows 需要 `__declspec(dllexport)`（来源与演变表），这是 Windows 与 POSIX 的导出模型差异。

### 3.3 opaque pointer 与 create/destroy API

跨语言传"对象"最稳的形态是 **opaque pointer（不透明指针）+ create/destroy API**：对外只暴露一个句柄类型，结构体定义藏在 .c 里，调用方（任何语言）只持有指针、永远不拆解内部布局——布局怎么改都不破坏 ABI（这正是"ABI 稳定"的工程实现）。

```c
// examples/session.h —— 节选：opaque 句柄 + create/destroy + 错误码（完整版见 examples/）
typedef struct session session_t;   /* opaque：具体定义只在 session.c */

/* 错误码（数值一经发布不再改，Python/Rust 按同一数值判断） */
enum {
    SESSION_OK = 0,
    SESSION_ERR_BADARG = -1,   /* 参数非法（如 name 为空） */
    SESSION_ERR_NOMEM = -2,    /* 内存不足 */
};

/* create：分配并初始化句柄；失败返回 NULL 且 *err_out 写入错误码 */
session_t *session_create(const char *name, int *err_out);
```

配套的生命周期纪律（roadmap 必会概念"内存分配和释放必须在同一侧约定清楚"）：

- **谁 create 谁 destroy**：`session_create` 分配、`session_destroy` 释放，所有权在 C 侧闭环；调用方绝不直接 free 句柄（它不知道内部还有子分配）
- **失败返回 NULL + err_out**：create 失败返回 `NULL`，错误码从 `err_out` 出参读——比返回"魔数句柄"或抛异常都更适合跨语言
- **借用与转移要写明**：`session_name` 返回的是 C 侧内部字符串的借用指针，注释里必须写明"调用方不得 free"

### 3.4 错误码与错误消息

跨语言错误的两个选择：**错误码**（机器可判断）与**错误消息**（人可阅读）。本阶段的设计契约（roadmap 学习内容"错误码与错误消息"，练习 4 的完整设计）：

1. **0 = 成功；负数为错误码**。数值与含义一一对应，写进头文件注释，**一经发布不再改值**——下游 Python/Rust 可能已经按旧值写好了判断（ABI 稳定优先）
2. **不用 errno**：errno 是 C 的线程局部全局，ctypes / Rust FFI 读取麻烦且不可移植。错误码一律走 `err_out` 出参
3. **消息经 strerror 式函数读取**，返回静态字符串（借用，无需释放）：

```c
// examples/session.c —— 节选：错误消息函数（完整版见 examples/）
const char *session_strerror(int err) {
    switch (err) {
    case SESSION_OK:         return "ok";
    case SESSION_ERR_BADARG: return "invalid argument";
    case SESSION_ERR_NOMEM:  return "out of memory";
    default:                 return "unknown error";
    }
}
```

实测（ex05，四种语言输出一致）：空 name 调 `session_create` → 返回 NULL、err = -1（BADARG）、消息 "invalid argument"——**C 侧一行 strerror、Python 侧 decode 读回、Rust 侧 CStr 读回，同一份字符串**。

### 3.5 C++ 调 C 与 C 调 C++ 包装层

**C++ 调 C**：C++ 编译器会对函数名做名字改编（mangling，4.2 讲机制）来支持重载；调 C 库时如果头文件没有 extern "C" 守卫，C++ 会把 `calc_add(int, int)` 改编成 `_Z8calc_addii` 去找符号，而库里只有 `_calc_add`——**编译期无错，链接期报错**。实测报错（ex02 故意出错演示，本机一次运行）：

```text
Undefined symbols for architecture arm64:
  "calc_add(int, int)", referenced from:
      _main in ex02-mangle-fail-29b2dd.o
   NOTE: found '_calc_add' in libcalc.dylib, declaration possibly missing 'extern "C"'
ld: symbol(s) not found for architecture arm64
```

注意链接器最后一行 NOTE 直接给出了修复建议。**只要头文件带守卫（3.1），C++ 就能按 C 函数直接调用**（ex02-cpp-main.cpp 实测通过）。C++ 侧再进一步，把 create/destroy 配对包装成 RAII 类（构造 create、析构 destroy），"忘记释放"从根上消失——参考实现见 exercises/sol-02。

**C 调 C++ 包装层**：项目主体是 C++ 时，要暴露给只认 C 接口的调用方（C 程序、Python、Rust），做法是写一层 extern "C" 的 C 风格包装函数，C++ 实现藏在后面：

```cpp
// examples/ex02-cpp-lib.cpp —— 节选：extern "C" 导出 C 接口（完整版见 examples/）
extern "C" {

/* 借用内部 std::string 的缓冲区；调用方不得 free，且任何修改
 * g_greeting 的调用都可能使先前拿到的指针失效 */
const char *cw_greet(void) {
    return g_greeting.c_str();
}

int32_t cw_double(int32_t x) {
    return x * 2;
}
```

```c
// examples/ex02-c-main.c —— 节选：C 侧声明即 C 链接（完整版见 examples/）
/* 只声明 C 链接的函数原型（C 侧不需要 extern "C"，声明即 C 链接） */
const char *cw_greet(void);
int32_t cw_double(int32_t x);
void cw_set_greeting(const char *s);
```

`extern "C"` 只是链接约定，函数体仍是 C++——内部用 `std::string`、异常、模板都行，调用方完全无感。C 语言没有 mangling 这回事，**.c 文件里的每个函数声明天然就是 C 链接**，所以 C 调 C++ 包装层不需要任何特殊标记。

### 3.6 Python ctypes 调用

ctypes 是 Python 标准库自带的 FFI：加载动态库 → 声明函数签名 → 调用。**关键纪律：显式声明 argtypes / restype**（不声明时 ctypes 用默认 c_int 猜测，遇到指针、64 位整数、结构体就会错位）：

```python
# examples/ex03-py-ctypes.py —— 节选：argtypes/restype 显式声明（完整版见 examples/）
lib = ctypes.CDLL(LIB)

# 显式声明参数与返回类型（int32_t == c_int32）
lib.calc_add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.calc_add.restype = ctypes.c_int32

lib.calc_div.argtypes = [ctypes.c_int32, ctypes.c_int32,
                         ctypes.POINTER(ctypes.c_int32)]
lib.calc_div.restype = ctypes.c_int
```

配套的映射规则（ex03/ex05/ex06 全部实测）：

| C 侧 | ctypes 侧 | 备注 |
|------|-----------|------|
| int32_t / int64_t | c_int32 / c_int64 | 定宽，与平台 int 无关 |
| 指针出参（int32_t *out） | `ctypes.byref(ctypes.c_int32())` | 调用方分配，C 写 |
| opaque 句柄（session_t *） | c_void_p | 不拆解内部布局 |
| const char *（借用） | c_char_p（bytes） | 只读借用，Python 侧负责 bytes 生命周期 |
| const uint8_t * + len | c_void_p + c_uint32（配 ctypes.cast） | 二进制值可能含 \0，不能当字符串 |
| struct（POD） | `class X(ctypes.Structure)` + `_fields_` | 字段顺序与宽度必须与 C 一致 |

**ctypes vs C 扩展**（roadmap 学习内容"Python ctypes / C 扩展"）：ctypes 是纯 Python、不用重编译解释器、适合"调用现成 C 库"；C 扩展（写 CPython 模块）性能更好、能直接操作 Python 对象，但要处理 PyObject 引用计数与构建链（setup.py）——本阶段只做对比，C 扩展的完整写法不展开（边界声明）。本环境 Python 3.13.9 实测：`python3 ex03-py-ctypes.py` 5 条断言全过，退出码 0。

### 3.7 Rust FFI：extern "C"

Rust 的 FFI 以 `extern "C"` 块声明 C 链接函数，调用必须包在 `unsafe` 里——**unsafe 是"我保证跨语言边界两侧的契约成立"的显式声明**：

```rust
// examples/ex04-rs-ffi.rs —— 节选：extern "C" 声明（完整版见 examples/）
#[link(name = "calc")]
extern "C" {
    fn calc_add(a: i32, b: i32) -> i32;
    fn calc_div(a: i32, b: i32, out: *mut i32) -> i32;
    fn calc_strlen(s: *const std::os::raw::c_char) -> i32;
}
```

Rust 侧的纪律（ex04/ex05/project 全部实测）：

- **`#[link(name = "calc")]` + 编译期 `-L <目录> -l calc`**：告诉链接器找 `libcalc.dylib`；C 字符串用 `CString::new(...)` 构造（含结尾 `\0`），`as_ptr()` 只读借用给 C
- **create 失败必须判空**：C 返回 NULL 的指针不能解引用，`assert!(!s.is_null(), ...)` 后再用（ex05-rs-handle）
- **错误码映射为类型化结果**：把 C 的 -1 在边界上翻译成 `Result<bool, LeapError>`，C 错误码不泄漏进 Rust 业务代码（exercises/sol-03）
- **C 分配的内存必须 C 侧释放**：`bufio_str_free` 这类函数要原样暴露给 Rust 调用，Rust 的 drop 管不到 C 的 malloc（ex06-rs-ownership）

> **注意**：Rust 2024 edition 起 `extern "C"` 块本身也要写 `unsafe extern "C"`（本阶段基线 edition 2021 用 `extern "C"` 即可）——方向一致：跨语言边界必须显式。

### 3.8 跨语言类型与所有权规则

**跨语言接口应使用简单稳定的 C 类型**（roadmap 必会概念），选型表：

| 场景 | 推荐 C 类型 | 为什么 |
|------|------------|--------|
| 整数 | int32_t / int64_t | 定宽、平台无关（ph09）；ctypes/Rust 都有直接对应 |
| 无符号/长度 | uint32_t / 显式 len 参数 | 宽度明确；长度与缓冲区配套传递 |
| 字符串 | const char *（NUL 结尾） | 各语言 FFI 都有标准转换（c_char_p / CString / std::string） |
| 字节数组 | const uint8_t * + len | 二进制值可能含 \0，必须有长度（ex06/project 的 blob 往返） |
| 布尔 | int32_t（0/1） | C99 _Bool 在部分 FFI 边界的布局/转换有坑 |
| 结构体 | 简单 POD（无指针/无 padding 敏感字段） | 跨语言布局必须一致（对齐与 padding 见 ph12） |

**字符串、数组、结构体都要定义所有权规则**（roadmap 必会概念）——三种约定（ex06 完整演示，C/Python/Rust 三侧输出一致）：

- **约定 1（谁分配谁释放）**：C 分配（malloc），调用方用完必须调 C 侧释放函数（`bufio_str_dup` / `bufio_str_free`）。跨语言时"释放"也必须回到 C 侧——Python 的 GC、Rust 的 drop 都不管 C 的 malloc
- **约定 2（调用方分配，C 只写）**：缓冲区由调用方分配（Python `create_string_buffer` / Rust `Vec<u8>`，ex06-rs 用 `vec![0u8; 32]`；栈上 `[u8; N]` 数组亦可，见 project/rs_kvdb 的 `[0u8; 64]`），C 只往里面写（`bufio_str_copy`）——缓冲区的生命周期天然归调用方
- **约定 3（C 只读借用）**：C 借用调用方的数据（`bufio_sum` 借用数组）或借出内部指针（`session_name`）——借用期间双方都要保证对方数据存活，注释写明"不得 free / 不得修改"

**ABI 稳定比源码语法更重要**（roadmap 必会概念）：跨语言边界的每一端都可能不再重新编译，所以——函数签名（参数个数/类型/顺序）改了，对端崩溃；结构体加字段，对端布局错位；导出符号改名，对端链接失败；错误码改值，对端判断全错。**稳定性来自"不变量"**：用定宽类型（不变量 = 宽度）、opaque 句柄（不变量 = 布局可藏）、create/destroy（不变量 = 所有权闭环）、版本化错误码（不变量 = 数值语义）。这也正是 ph13 之后把 kvlog 升级为 C ABI 库（project/）的价值。

## 4. 底层原理

### 4.1 符号表与动态链接

```text
calc.c ──cc -dynamiclib──▶ libcalc.dylib ──导出符号表──▶ _calc_add (T, 全局可调用)
                                                        _calc_div (T)
调用方 main.o ──未定义符号 _calc_add──▶ 链接器 ──动态查找──▶ libcalc.dylib 命中
                                                    └─ 找不到 ──▶ 链接错误
```

动态库的"导出符号"就是它的公共 API：`nm` 列出符号表，`T`（文本段全局符号）可被外部链接，`t` 是文件局部符号。运行时动态链接器按 install name（macOS）/ SONAME（Linux）找到库文件，把调用方的未定义符号与库的导出符号一一对上——**跨语言调用在链接层就是"把对方语言的未定义符号喂给 C 库的导出符号"**，符号名对得上就通，对不上就链接失败（3.5 的 mangling 报错就是实例）。

### 4.2 name mangling 与 extern "C" 的机制

```text
C++ 源码        C++ 编译器              库里的符号
calc_add(int,int) ──mangling──▶ _Z8calc_addii ──查找──▶ 找不到!
calc_add(int,int) ──extern "C"──▶ _calc_add    ──查找──▶ libcalc.dylib 命中
```

C++ 用 mangling 把"函数名 + 参数类型"编码进符号名，从而支持重载（两个 `calc_add` 重载各有一个唯一符号）；C 的符号就是函数名本身（加平台前缀）。`extern "C"` 告诉 C++ 编译器：这一段用 C 的命名与链接规则，不 mangling——**它是 C++ 侧对"这是 C 库"的显式声明**，与 C 侧无关（C 没有这回事，3.5 已述）。

### 4.3 调用约定：简单类型为什么稳

```text
调用方(任意语言) ──按平台调用约定──▶ C 函数
  System V AMD64 / Apple arm64:
  x0~x7 传整数/指针参数, 返回在 x0; 浮点走 v0~v7; 栈上放不下的参数
  结构体 ≤16 字节(arm64) 按值进寄存器, 更大的走内存 + 隐藏指针
```

调用约定（calling convention）是"参数放哪、返回值放哪、谁清理栈"的平台规则。C 的 ABI 把这套规则固化成文档，任何语言的 FFI 都按它生成调用序列。**简单稳定类型稳，是因为它们在所有平台约定里都是"直接进寄存器"的基本单元**；复杂类型（大结构体、联合、位域）的布局与传递方式因平台/编译器而异，跨语言容易踩坑——所以本阶段一律用定宽整数、指针、POD 小结构体。

### 4.4 跨语言内存所有权：谁分配谁释放

```text
C 侧分配:  bufio_str_dup ──▶ 堆内存 ──只能由──▶ bufio_str_free 释放
                     ▲                            │
              Python/Rust 只持有指针              │
              （GC/drop 不知道这是 C 的 malloc）   └── 回到 C 侧闭环
```

各语言的运行时内存管理只认识自己分配的内存：Python 的 GC 管 PyObject、Rust 的 drop 管 Box，**它们都不知道也不该管 C 的 malloc**。所以跨语言内存的所有权规则只有一条可用的：**分配与释放必须回到同一侧**——要么 C 分配 C 释放（约定 1）、要么调用方分配调用方释放（约定 2）、要么根本不转移（约定 3 借用）。违背它（比如 Python 侧释放 C 的 malloc 内存）是未定义行为，崩溃与堆损坏都算轻的。

### 4.5 为什么 ABI 稳定优先于源码语法

源码语法是"语言内部的便利"，ABI 是"跨语言的承诺"。语法可以随语言版本演进（C++17 的代码换 C++20 重编），但 ABI 一旦发布就面向所有下游：**改函数签名/结构体布局/符号名/错误码数值，任何一端不重新编译就会错位**——而现实是另一端（比如别人已经编译好的 Python 扩展、Rust 二进制）根本不会为你重编。本阶段的所有约定（简单类型、opaque、create/destroy、版本化错误码、所有权写进注释）本质上都是**减少 ABI 的变动面**：让"稳定的部分"（函数签名与布局）尽量小、尽量不变。

## 5. 使用场景

| 场景 | 用什么 | 依据 |
|------|--------|------|
| 插件系统 / 语言边界（数据库、编辑器、游戏引擎） | C ABI 动态库 + opaque 句柄 | 任何语言都能调；句柄藏住内部状态（project/ 的 kvdb 即 C ABI KV 插件接口） |
| Python 高性能计算 / 调现成 C 库 | ctypes（或 C 扩展） | 计算密集部分下沉 C；ctypes 零编译链、不改解释器（3.6） |
| Rust 安全地调 C 系统库 | extern "C" + unsafe 封装 + 类型化错误 | 把 C 错误码在边界映射成 Result，业务代码不碰裸指针（3.7/sol-03） |
| C++ 项目嵌入 C 库 | extern "C" 头文件 + RAII 包装 | 避免 mangling；RAII 把 create/destroy 变成构造/析构（3.5/ex05-cpp/sol-02） |
| C 项目嵌入 C++ 引擎 | extern "C" 包装层 | C++ 实现藏在 C 接口后，C 调用方无感（ex02-cpp-lib） |
| 跨语言传数据 | 定宽类型 + 显式长度 + 所有权注释 | 布局稳定、不变量清晰（3.8） |

**不适合**本阶段手段的场景：

- **高频小调用跨语言**：每次 FFI 调用有边界开销（参数搬运、安全检查），性能敏感的热路径应把循环留在 C 侧，只跨一次边界
- **复杂 C++ 对象直接跨语言**：类布局、虚表、异常在 ABI 上没有标准——只传 POD 与句柄（3.8）
- **需要 C ABI 之外的平台机制**：COM / Objective-C runtime 等有各自的对象模型与生命周期，属各自生态的互操作，不是 C ABI 能表达的
- **多语言共享大对象**：优先"各持一份 + 同步"，而不是共享内存（mmap 共享只读数据的语义见 ph13）

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C 的 FFI 就是 ABI 本身，最朴素也最稳；C++ 没有稳定 ABI（mangling、类布局随编译器版本变），必须靠 extern "C" 收口；Python 的 ctypes 是"运行时声明"，C 扩展是"编译进解释器"；Rust 把边界做成 `unsafe extern "C"` + 类型化封装，安全成本显式化。**四门语言语法各异，底层链接的都是同一个 C ABI**——这正是本阶段把 C 定位为"跨语言接口层"的原因。

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令与验证状态见其 README）。本阶段示例均为**正常工程代码**，无故意出错演示（唯一例外 ex02-mangle-fail 是演示链接失败的"故意出错"用例，其文件头注释写明了运行前提）；可任意编译运行。以下所有实测输出来自 Apple clang 21.0.0 + Python 3.13.9 + rustc 1.92.0（macOS arm64）；文档内嵌片段与对应源文件逐字一致（节选关键部分，完整文件以 examples/ 为准）。

### 示例 1：C 动态库与导出符号（nm 实测）

对应 roadmap 学习内容"动态库导出符号"。C 主程序是"对照组"：其他语言调用同一份 libcalc.dylib，输出必须与它一致。

> 运行前提：无（正常工程代码，可任意编译运行）。产物写 /tmp/ph14-ex。

```c
// examples/ex01-c-main.c —— C 主程序调用 libcalc 动态库（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
    int32_t sum = calc_add(20, 22);
    int32_t prod = calc_mul(6, 7);
    int32_t q = 0;
    int rc = calc_div(84, 2, &q);
    int32_t n = calc_strlen("hello");
```

```bash
# 1. 编译动态库
cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
# 2. 编译 C 主程序并链接
cc -Wall -Wextra -std=c11 ex01-c-main.c -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex01
# 3. 运行
/tmp/ph14-ex/ex01
# 4. 实测导出符号
nm -gU /tmp/ph14-ex/libcalc.dylib
```

实测输出关键行（本机一次运行）：

```text
calc_add(20,22) = 42
calc_mul(6,7)   = 42
calc_div(84,2)  = rc=0 q=42
calc_div(1,0)   = rc=-1（除零错误码, q 未被改写）
calc_strlen(hello) = 5
```

解读：定宽类型 + 错误码约定（除零返回 -1）+ 字符串借用，全部在 C 侧先立住；`nm -gU` 显示四个函数全部 `T` 导出——这就是其他语言能链接到的全部入口。

### 示例 2：C++ 调 C 与 C 调 C++ 包装层

对应 roadmap 学习内容"C++ 调 C、C 调 C++ 包装层"与必会概念"ABI 稳定比源码语法更重要"。

> 运行前提：ex02-mangle-fail.cpp 是**故意出错**演示（预期链接失败），文件头注释已写明，不要期望它生成可执行文件；其余为正常工程代码。

```cpp
// examples/ex02-cpp-main.cpp —— C++ 调 C（calc.h 自带 extern "C" 守卫，已验证）
// 验证环境：Apple clang 21.0.0（c++，macOS arm64）
int main() {
    std::int32_t sum = calc_add(20, 22);          /* 按 C 函数直接调用 */
    std::int32_t q = 0;
    int rc = calc_div(42, 2, &q);
```

```bash
# 1. C++ 调 C
c++ -Wall -Wextra -std=c++17 ex02-cpp-main.cpp -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex02-cpp
# 2. 运行
/tmp/ph14-ex/ex02-cpp
# 3. 故意出错: 无 extern "C" 守卫 → 预期链接失败（报错文本见主文档 3.5）
c++ -Wall -Wextra -std=c++17 ex02-mangle-fail.cpp -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex02-mangle-fail
```

实测输出关键行（本机一次运行）：

```text
cpp: calc_add(20,22)=42 calc_div(42,2)=rc=0 q=21
c: greet()      = hello from C++
c: double(21)   = 42
c: after set, greet() = hello from C!
```

解读：`calc.h` 的 extern "C" 守卫让 C++ 直接按 C 函数调用成功；`libcppwrap.dylib`（C++ 实现的 C 接口）被 `.c` 文件调用成功——两个方向的链接语义都在实测里闭环。

### 示例 3：Python ctypes 调用 C

对应 roadmap 学习内容"Python ctypes / C 扩展"与练习 1 的完整版。

> 运行前提：无（正常工程代码，可任意编译运行）。运行勿加 `-O`（断言会被移除）。

```python
# examples/ex03-py-ctypes.py —— Python 用 ctypes 调用 libcalc（已验证）
# 验证环境：Python 3.13.9 + Apple clang 21.0.0（macOS arm64）
out = ctypes.c_int32()
rc = lib.calc_div(84, 2, ctypes.byref(out))
assert rc == 0 and out.value == 42, f"div(84,2): rc={rc} out={out.value}"

# 3) 错误码路径：除零返回 -1，而不是崩溃
rc = lib.calc_div(1, 0, ctypes.byref(out))
assert rc == -1, f"div(1,0) 应返回 -1，实际 {rc}"
```

```bash
# 1. 运行（argv[1] 可换成你自己的库路径）
python3 ex03-py-ctypes.py /tmp/ph14-ex/libcalc.dylib
```

实测输出（本机一次运行）：

```text
py-ctypes: add(20,22)=42 add(-1,1)=0 div(84,2)=rc0/42 div(1,0)=rc-1 strlen(hello)=5 —— 全部断言通过
```

解读：`byref` 把 Python 侧分配的 c_int32 地址交给 C 写（指针出参）；除零不崩而是返回 -1——C 侧的错误码约定在 Python 侧被正确消费。

### 示例 4：Rust extern "C" 调用 C

对应 roadmap 学习内容"Rust FFI：extern C"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```rust
// examples/ex04-rs-ffi.rs —— Rust 用 extern "C" 调用 libcalc（已验证）
// 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
    let mut q: i32 = 0;
    let rc = unsafe { calc_div(84, 2, &mut q) };
    assert_eq!((rc, q), (0, 42), "calc_div(84,2) 结果不符");

    let rc0 = unsafe { calc_div(1, 0, &mut q) };
    assert_eq!(rc0, -1, "calc_div(1,0) 应返回 -1 错误码");
```

```bash
# 1. 编译（-l calc 找 libcalc.dylib）
rustc --edition 2021 -D warnings ex04-rs-ffi.rs -L /tmp/ph14-ex -l calc -o /tmp/ph14-ex/ex04-rs
# 2. 运行
/tmp/ph14-ex/ex04-rs
```

实测输出（本机一次运行）：

```text
rs-ffi: calc_add(20,22)=42 calc_div(84,2)=rc0/42 calc_div(1,0)=rc-1 strlen(hello)=5 —— 全部断言通过
```

解读：与 ex03 同构的断言集合（ex04 少一条 `add(-1,1)`，其余测试点一致）——C++、Python、Rust 三个调用方对同一份 C 库读到一致结果，跨语言验证的核心闭环。

### 示例 5：opaque pointer + create/destroy + 错误码/消息（四语言）

对应 roadmap 学习内容"opaque pointer、create/destroy API、错误码与错误消息"，四种语言调用同一份 libsession.dylib。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex05-c-handle.c —— C 调用 session 句柄库（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
    session_t *s = session_create("c-caller", &err);
    if (s == NULL) {
        printf("create 失败: %s\n", session_strerror(err));
        return 1;
    }
    printf("create 成功, name=%s\n", session_name(s));   /* 借用内部指针 */
    session_add(s, 40);
    session_add(s, 2);
    printf("total = %lld\n", (long long)session_total(s));

    int rc = session_destroy(s);                          /* 谁 create 谁 destroy */
```

```bash
# 1. C
cc -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
cc -Wall -Wextra -std=c11 ex05-c-handle.c -L/tmp/ph14-ex -lsession -o /tmp/ph14-ex/ex05-c && /tmp/ph14-ex/ex05-c
# 2. C++
c++ -Wall -Wextra -std=c++17 ex05-cpp-handle.cpp -L/tmp/ph14-ex -lsession -o /tmp/ph14-ex/ex05-cpp && /tmp/ph14-ex/ex05-cpp
# 3. Python
python3 ex05-py-handle.py /tmp/ph14-ex/libsession.dylib
# 4. Rust
rustc --edition 2021 -D warnings ex05-rs-handle.rs -L /tmp/ph14-ex -l session -o /tmp/ph14-ex/ex05-rs && /tmp/ph14-ex/ex05-rs
```

实测输出关键行（本机一次运行，四语言摘录）：

```text
c:  create 成功, name=c-caller   total = 42   destroy rc=0 (ok)   空 name → NULL, err=-1 (invalid argument)
cpp: name=cpp-caller total=42
py:  create 成功 name=py-caller   total=42   destroy rc=0 msg=ok   空 name → NULL, err=-1 msg=invalid argument
rs:  create 成功 name=rs-caller   total=42   空 name → NULL, err=-1 msg=invalid argument
```

解读：opaque 句柄在四种语言里都是"不透明指针"（c_void_p / *mut c_void），create/destroy 配对、错误码 -1、错误消息 "invalid argument" 四侧完全一致——**跨语言契约（头文件）+ 所有权闭环（create/destroy）+ 错误设计（err_out/strerror）在实测里闭环**。

### 示例 6：跨语言所有权三种约定

对应 roadmap 必会概念"字符串、数组、结构体都要定义所有权规则"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex06-c-ownership.c —— 三种所有权约定的 C 侧对照（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
    /* 约定 1：C 分配、C 释放 */
    char *dup = bufio_str_dup("malloc'd by C");
    printf("约定1: dup=%s\n", dup);
    bufio_str_free(dup);               /* 必须用 C 侧释放函数 */
    dup = NULL;

    /* 约定 2：调用方分配 buffer，C 只写 */
    char buf[32];
    size_t need = bufio_str_copy(buf, sizeof buf, "caller buffer");
    printf("约定2: buf=%s need=%zu\n", buf, need);

    /* 约定 3：C 只读借用调用方数组 */
    int32_t arr[] = {1, 2, 3, 4, 5};
    int64_t sum = bufio_sum(arr, sizeof arr / sizeof arr[0]);
    printf("约定3: sum=%lld\n", (long long)sum);
```

```bash
# 1. C
cc -Wall -Wextra -std=c11 -dynamiclib bufio.c -o /tmp/ph14-ex/libbufio.dylib
cc -Wall -Wextra -std=c11 ex06-c-ownership.c -L/tmp/ph14-ex -lbufio -o /tmp/ph14-ex/ex06-c && /tmp/ph14-ex/ex06-c
# 2. Python
python3 ex06-py-ownership.py /tmp/ph14-ex/libbufio.dylib
# 3. Rust
rustc --edition 2021 -D warnings ex06-rs-ownership.rs -L /tmp/ph14-ex -l bufio -o /tmp/ph14-ex/ex06-rs && /tmp/ph14-ex/ex06-rs
```

实测输出关键行（本机一次运行，三语言摘录）：

```text
C:      约定1: dup=malloc'd by C   约定2: buf=caller buffer need=13   约定3: sum=15   struct: (10,20)+(30,40)=(40,60)
Python: py 约定1: dup=malloc'd by C  py 约定2: buf=caller buffer need=13  py 约定3: sum=15  py struct: (40,60)
Rust:   rs 约定1: dup=malloc'd by C  rs 约定2: buf=caller buffer need=13  rs 约定3: sum=15  rs struct: (40,60)
```

解读：三种所有权约定在 C / Python / Rust 三侧行为一致；POD 结构体（bufio_pt）按值传递，ctypes 的 Structure 与 Rust 的 repr(C) struct 布局对齐后正确解码——**所有权规则与结构体布局是跨语言传数据的两条硬边界**。

## 7. 总结

### 关键要点

1. **跨语言接口应使用简单稳定的 C 类型**（roadmap 必会概念）：int32_t / const char * / uint8_t * + len，不用平台宽度不定的 int/long；ctypes 的 c_int32、Rust 的 i32 一一对应（3.1/3.8）
2. **头文件即契约，extern "C" 守卫是 C 头文件被 C++ 直接包含的唯一机制**：忘写守卫 C++ 链接期报 mangling 错误（3.5 实测报错文本），报错里链接器会提示 missing 'extern "C"'
3. **动态库导出符号决定"能被谁链接"**：nm 实测 T 导出 / t 文件局部；macOS 符号带下划线前缀、Linux 不带（3.2）
4. **opaque pointer + create/destroy 是跨语言对象的稳定形态**：结构体定义藏在 .c，"谁 create 谁 destroy"，布局怎么改都不破坏 ABI（3.3/ex05）
5. **错误码 0 成功负数错误 + err_out 出参 + strerror 消息，不用 errno**：数值一经发布不改；消息是静态字符串借用（3.4/练习 4）
6. **字符串、数组、结构体都要定义所有权规则**（roadmap 必会概念）：C 分配 C 释放 / 调用方分配 C 只写 / 只读借用——"释放必须回到分配的那一侧"（3.8/ex06）
7. **ABI 稳定比源码语法更重要**（roadmap 必会概念）：签名、布局、符号名、错误码数值都是不变量；任何一端不重编，另一端就必须兼容（4.5）
8. **Python 用 ctypes 必须显式声明 argtypes/restype**：指针出参用 byref、句柄用 c_void_p、二进制用 c_void_p + 长度（3.6/ex03/ex05）
9. **Rust 的 unsafe 是"跨语言契约成立"的显式声明**：extern "C" 声明、判空、错误码映射 Result、C 内存回 C 侧释放（3.7/sol-03）
10. **C 调 C++ 用 extern "C" 包装层**：C++ 实现藏在 C 接口后，C/Python/Rust 调用方无感（3.5/ex02-cpp-lib）

### 跨语言对比：FFI 机制

| 维度 | C（本阶段） | C++ | Python | Rust |
|------|------------|-----|--------|------|
| 边界形态 | ABI 本身（函数 + 数据布局） | extern "C" 收口（无稳定 ABI） | ctypes 运行时声明 / C 扩展 | extern "C" + unsafe |
| 句柄/对象 | opaque 指针 + create/destroy | 类（RAII） | c_void_p（不拆解） | 裸指针（判空 + 封装） |
| 错误 | 错误码 + err_out + strerror | 异常/错误码 | 断言/返回值 + strerror 读回 | Result（边界映射） |
| 字符串 | const char *（借用） | std::string（内部） | c_char_p（bytes） | CString / CStr |
| 内存所有权 | 谁分配谁释放（C 侧闭环） | RAII | GC 只管 Python 对象 | drop 只管 Rust 对象 |

语法各异，**底层链接的都是同一个 C ABI**——这正是 C 作为"跨语言接口层"的生态位（为 analysis/ 与 Tenet 合成积累素材）。

### 阶段验收清单

- [ ] 能解释 ABI 与 API 的区别：API 是源码层面的函数签名，ABI 是二进制层面的符号名、参数传递与布局——跨语言保证的是 ABI（3.1/4.3/4.5）
- [ ] 能写出稳定的 C 头文件接口：简单稳定类型 + extern "C" 守卫 + 注释写明所有权与错误码（3.1/3.8，练习 1/4）
- [ ] 能明确跨语言内存所有权：说清三种约定、能指出"Python 直接 free C 的 malloc"错在哪（3.8/4.4，ex06）
- [ ] 能用 nm 实测导出符号并解释 T/t/U 与平台前缀差异（3.2，示例 1）
- [ ] 能完成 C++ 调 C（extern "C"）与 C 调 C++（包装层）两个方向并解释 mangling（3.5，示例 2）
- [ ] 能用 Python ctypes 调用 C 动态库：argtypes/restype、byref 出参、错误码与消息（3.6，示例 3）
- [ ] 能用 Rust extern "C" 调用 C：unsafe 边界、判空、错误码映射 Result（3.7，示例 4）
- [ ] 能设计跨语言错误码：0 成功/负数错误、err_out、strerror、数值稳定（3.4，练习 4）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap ph14「练习」一一对应：

- 编译一个 C 动态库给 Python 调用（★★）
- 用 C++ 包装 C 接口（★★）
- 用 Rust 调用 C 函数（★★★）
- 设计跨语言错误码（★★）

完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**kvdb——C ABI KV 库（WAL 持久化）**——对应 roadmap ph14「推荐项目」三个之一体（C ABI KV 插件接口 + Python 调用 C buffer 解析库 + Rust 调用 C WAL 库）：一个 `cc -Wall -Wextra -std=c11` 零警告的 C ABI 库，被 C CLI（22 项断言自测）、Python ctypes、Rust extern "C" 三方真实调用，覆盖本阶段全部核心概念（opaque 句柄、create/destroy、错误码/消息、所有权、简单稳定类型、WAL 回放持久化），并把 ph13 的 append-only log 升级为可跨语言调用的 WAL 底座。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make test` 三方全过退出码 0、`make clean` 零残留）

### 下一阶段

[ph15 高级 C 与代码质量阶段](../ph15-code-quality/15-code-quality.md) — 本阶段解决了"怎么把 C 库暴露给其他语言"，ph15 将解决"怎么写更稳定、可维护、可移植的 C 代码"：宏与条件编译、函数指针与回调、状态机与错误码设计、handle-based API 与 opaque pointer 的完整工程化（本阶段已铺垫 opaque 句柄与错误码的心智模型）；再往后 [ph16 数据库存储引擎基础阶段](../ph16-storage-engine/16-storage-engine.md)（roadmap 第 16 节）将把本阶段 project/ 的 kvdb（C ABI KV + WAL）升级为完整 WAL + MemTable + SSTable 的存储引擎。
