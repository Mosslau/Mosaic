# examples —— 标准、编译器与可移植性阶段完整示例

验证环境：Apple clang 21.0.0（`c++`/`g++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra` 编译全部零警告。本机无 GCC/MSVC 编译器，GCC/MSVC 相关分支代码可编译（见 ex04 说明）但未在本环境验证。**全部产物输出到 /tmp，验证后清理，仓库不落二进制**（本目录只含源码）。

| 文件 | 说明 | 构建/运行 |
|------|------|-----------|
| `ex01-stdint.cpp` | `<cstdint>` 固定宽度类型：sizeof 实测、边界值宏、与 `int`/`long` 的对比 | `./ex01-stdint` 输出各类型字节数 |
| `ex02-endian.cpp` | 字节序：宏探测 + 运行期探测 + `std::endian` + 大端序列化往返 | `./ex02-endian` 输出 `roundtrip=16909060 (OK)` |
| `ex03-condcompile.cpp` | 平台宏与条件编译：`_WIN32`/`__APPLE__`/`__linux__` 分支、编译器分支、`__has_include` | `./ex03-condcompile`；`-D_WIN32` 变体输出 `platform = Windows` |
| `ex04-compilers.cpp` | 编译器差异宏实测：`__clang__`/`__GNUC__`/`_MSC_VER`/`__cplusplus`/`__VERSION__` | 分别用 `c++` 与 `clang++` 编译对比输出 |
| `ex05-path.h` `ex05-path.cpp` `ex05-main.cpp` | 平台 API 抽象：路径拼接适配层，接口头零平台宏 | `./ex05-path`；`-D_WIN32` 变体输出 `separator: \` |

## 示例 1：固定宽度整数类型（ex01-stdint.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex01-stdint.cpp -o /tmp/ex01-stdint
/tmp/ex01-stdint
```

本机实测输出（已验证，Apple clang 21 与 Homebrew clang 21 输出一致）：

```text
int8_t=1  int16_t=2  int32_t=4  int64_t=8
uint8_t=1  uint16_t=2  uint32_t=4  uint64_t=8
INT32_MAX=2147483647  UINT32_MAX=4294967295
int_least8_t=1  int_fast32_t=4  intmax_t=8
int=4  long=8  long long=8  void*=8
magic=0x50484C31 version=1
```

要点：**固定宽度类型在任何平台都是恰好 N 位**（`int32_t` 恒为 4 字节，`static_assert` 把关）；`int_least8_t`/`int_fast32_t` 只保证下限、具体宽度平台定；`int`/`long` 宽度跨平台不同（本机 4/8，Windows 是 4/4）——写二进制格式、跨平台协议必须用固定宽度。

## 示例 2：字节序探测与序列化（ex02-endian.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex02-endian.cpp -o /tmp/ex02-endian
/tmp/ex02-endian
```

本机实测输出（已验证）：

```text
macro __BYTE_ORDER__      : little
runtime byte probe        : little
std::endian::native       : little
value=0x01020304  big-endian bytes: 01 02 03 04
roundtrip=16909060 (OK)
```

要点：三种探测方式互相印证——`__BYTE_ORDER__` 宏（GCC/Clang 预定义）、运行期字节探测（可移植，任何编译器都行）、`std::endian`（C++20 `<bit>`，最规范）；**写文件/网络协议固定用大端（网络序）**，`to_big_endian` 在 little-endian 机器上做字节反转，读回再反转一次即还原。

## 示例 3：平台宏与条件编译（ex03-condcompile.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-condcompile
/tmp/ex03-condcompile
c++ -D_WIN32 -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-win
/tmp/ex03-win
```

本机实测输出（已验证）：

```text
# 原生编译：
platform = macOS
compiler = Clang
has <optional> = yes

# -D_WIN32 模拟：
platform = Windows
compiler = Clang
has <optional> = yes
```

要点：**`-D_WIN32` 模拟技巧让"Windows 分支"在本机也能验证**——分支逻辑是否正确、能否编译，不必真上 Windows；判平台（`_WIN32`/`__APPLE__`/`__linux__`）与判编译器（`_MSC_VER`/`__clang__`/`__GNUC__`）是两套宏，别混；`__has_include` 是 C++17 特性测试宏，回答"这个头在不在"。

## 示例 4：编译器差异宏实测（ex04-compilers.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex04-compilers.cpp -o /tmp/ex04-apple
/tmp/ex04-apple
clang++ -std=c++20 -Wall -Wextra ex04-compilers.cpp -o /tmp/ex04-hb
/tmp/ex04-hb
```

本机实测输出（已验证，两行输出对比）：

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

要点：**判编译器家族的顺序必须 `_MSC_VER` → `__clang__` → `__GNUC__`**——因为 Clang 为兼容也定义 `__GNUC__`（实测值 4.2.1，不是真实 GCC 版本），先查 `__clang__` 才能区分"真 GCC"和"Clang 假装的 GCC"；`__VERSION__` 是编译器自我介绍字符串，两家 Clang 各不相同，可用来精确区分 Apple 版与上游版。MSVC 的 `_MSC_VER`（如 1938 = VS2022 17.8）为微软文档值，本机无 MSVC，未在本环境验证（需 Windows）。

## 示例 5：平台 API 抽象（ex05-path.h / ex05-path.cpp / ex05-main.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-path
/tmp/ex05-path
c++ -D_WIN32 -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-win
/tmp/ex05-win
```

本机实测输出（已验证）：

```text
# POSIX 分支：
data/config.json
data/config.json
separator: /

# -D_WIN32 模拟 Windows 分支：
data\config.json
data/\config.json
separator: \
```

要点：**平台差异全部隔离在 `ex05-path.cpp` 一个翻译单元**，头文件 `ex05-path.h` 没有任何平台宏——调用方、测试、其它模块永远只面对统一接口，这就是"跨平台代码应隔离平台相关层"的最小示范；`-D_WIN32` 让 Windows 分支在本机也被编译和运行验证过。**坑：能用 `std::filesystem`（C++17）就别手写路径**——标准库已替你跨平台，适配层留给 filesystem 管不到的 API（socket、动态库、线程名等）。

## 双编译器验证记录

| 示例 | Apple clang 21.0.0 | Homebrew clang 21.1.8 | -D_WIN32 模拟 |
|------|--------------------|-----------------------|---------------|
| ex01 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | — |
| ex02 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | — |
| ex03 | ✅ 零警告 | ✅ 零警告 | ✅ `platform = Windows` |
| ex04 | ✅ 零警告，`__VERSION__="Apple LLVM..."` | ✅ 零警告，`__VERSION__="Homebrew Clang..."` | — |
| ex05 | ✅ 零警告 | ✅ 零警告 | ✅ `separator: \` |

验证用构建产物全部位于 /tmp，仓库无 .o/可执行文件残留。
