# tenet/compiler-arm64 —— Tenet 编译器（C++17 实现，手写 AArch64 后端）

> Tenet 语言的 C++17 编译器前端。管线：`.tenet → 词法 → 语法 → 类型 → arm64 汇编 → 系统 as 汇编 → ld 链接 → 原生二进制`。
> 这是 Tenet 三套实现中的第三套，后端**完全自写**：指令选择、寄存器使用、栈帧、调用约定全部自己实现，**零 LLVM、零 clang 做代码生成**。

## 定位

| | |
|---|---|
| 语言 | C++17（纯标准库，零依赖） |
| 后端方式 | **手写 AArch64 汇编后端**：AST 直接生成 arm64 汇编文本（.s）→ 系统 `as` 汇编 → `ld` 链接 |
| 产出 | 原生可执行二进制（Mach-O arm64） |
| 特点 | 全链路零 LLVM/clang（仅用系统 as/ld 作"手"）；类似 TCC / 早期 GCC 的做法 |
| 测试 | 234 项检查 |

## 管线

```text
hello.tenet
   │  前端（自己写，C++17）
   ├─▶ lexer.hpp      词法分析：字符 → Token 流
   ├─▶ parser.hpp     语法分析：Token → AST
   ├─▶ backend.hpp    类型推断 + AArch64 汇编生成（指令选择/寄存器/栈帧/调用约定全自己写）
   │  后端"手"（系统工具，仅汇编与链接）
   ├─▶ as hello.s -o hello.o         （Apple 汇编器）
   ├─▶ ld hello.o -o hello -lSystem  （Apple 链接器）
   └─▶ hello          原生二进制，直接运行
```

## 目录结构

```
compiler-arm64/
├── Makefile          # 纯 clang++ -std=c++17，无 LLVM 库
├── src/
│   ├── error.hpp / token.hpp / lexer.hpp / ast.hpp / parser.hpp   # 前端（与 compiler-cpp 同构）
│   ├── backend.hpp   # ★手写 AArch64 后端（含 234 项检查的断言对象）
│   └── main.cpp      # CLI + as/ld 驱动 + 内嵌 arm64 运行时
├── examples/         # hello / fib / fizzbuzz / struct / array
└── tests/            # test_main.cpp
```

## 构建与使用

要求：Xcode 命令行工具（`as`/`ld`/`xcrun`）。

```bash
cd tenet/compiler-arm64

make                    # 构建 tenet 与 test_tenet 并跑测试
make test               # 234 项检查
./tenet build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
./tenet run examples/fib.tenet          # 编译 + 运行一步到位
./tenet asm examples/hello.tenet        # 看生成的 arm64 汇编（调试）
```

环境变量：`TENET_AS` / `TENET_LD` / `TENET_SDK` 可覆盖 as/ld/SDK 路径。

## 支持的语言特性（核心子集）

| 类别 | 内容 |
|---|---|
| 类型 | `int` / `float` / `bool` / `string`；局部定长 `array<int/float/bool>` |
| 变量 | `let`（类型标注可选，静态推断）、赋值（值语义） |
| struct（v1） | 顶层 `struct Point { x: int; y: int; }`、字面量初始化、字段读写、逐字段值拷贝；字段仅 `int`/`float`/`bool`，不支持 struct 参数/返回值/嵌套 |
| array（v1） | 定长字面量 `[e1, e2, ...]`、`a[i]` 读写、`len(a)`（编译期常量）、逐元素值拷贝、同长度整体赋值；仅局部变量，元素仅 `int`/`float`/`bool`，不支持空数组/动态扩容/嵌套/参数/返回值 |
| 函数 | `fn f(a: int) -> int`、递归 |
| 控制流 | `if/else if/else`、`while`（唯一循环）、`break`、`return` |
| 运算符 | 算术（向零截断整除/取模，`sdiv`/`msub`）、比较、`&&`/`\|\|` 短路、一元 `-`/`!` |
| 字符串 | 拼接、比较（经 libc：strlen/malloc/memcpy/strcmp，内嵌 arm64 运行时） |
| 内建 | `print(...)`（编译期拼 printf 格式串） |
| 注释 | `//` 与 `/* */` |

## 设计要点

1. **栈式表达式求值**：结果压入表达式栈（`stp reg, xzr, [sp, #-16]!`），
   二元运算弹出两操作数计算再压回——无需寄存器活跃度分析
2. **Apple Silicon：sp 恒 16 字节对齐**（本实现的头号坑）：8 字节 push 会触发
   `EXC_ARM_SP_ALIGN`，因此 push/pop 一律用 16 字节单位（浮点占位用 `d31`）
3. **栈帧**：变量是 x29 相对槽位（每槽 8 字节）；函数 `stp x29,x30` 保存帧指针与返回地址
4. **调用约定**：
   - 用户函数：AAPCS——参数 x0-x7 / d0-d7，返回值 x0 / d0
   - `print`：**Apple 变参约定**（实测与 clang 一致）——固定参数 fmt 在 x0，
     变参全部压栈（从 [sp] 连续存放），不需要 w0/d 寄存器
5. **控制流**：`if`/`while`/`break`/短路全部翻译为标签 + 条件分支（`cmp`/`b.eq`/`cset`）
6. **常量与寻址**：字符串放 `__TEXT,__cstring`、浮点放 `__TEXT,__const`（`.align 3`），
   取址用 `adrp x9, L.xx@PAGE; add x9, x9, L.xx@PAGEOFF`（Apple 语法，非 ELF `:lo12:`）
7. **符号**：函数前 `.globl _name`（否则 ld 找不到入口 `_main`）
8. **内嵌运行时**：`tenet_concat`（strlen×2 + malloc + memcpy×2）与 `tenet_strcmp`（尾调用 strcmp）
   以 arm64 汇编写成，随每个产物一起输出
9. **struct v1 扁平化**：struct 局部变量不生成聚合布局/ABI，而是每个字段占一个 8 字节栈槽；
   字段读写直接按槽寻址，`let q = p;`/`q = p;` 逐字段 `ldr`/`str` 值拷贝
10. **array v1 栈布局**：帧规划时数组占 N 个连续 8 字节槽（bool 同样占 8 字节），
    元素 0 在最低地址；`a[i]` 的地址 = 元素 0 槽位 + `i*8`（`ldr/str [x16, x10, lsl #3]`）。
    常量下标在编译期查越界；动态下标用无符号 `cmp idx, len` + `b.hs` 跳到失败块，
    越界时调用内嵌 `_tenet_bounds_fail`（`dprintf(2, ...)` 打印到 stderr，`exit(1)`）。
    超过 ±256 的槽位与超过 4095 的栈帧也走寄存器地址，不受 ldr/str 立即数范围限制

## 测试

```bash
make test
```

词法/语法用文本断言；代码生成用**汇编模式断言**（stp 16 字节对齐、sdiv/msub、
scvtf 混合提升、tenet_concat/strcmp 调用、条件分支、.globl）。

## 已知限制与演进

- 只支持核心子集；`Option`/`Result`/`match` 设计已定待实现
- struct 仅 v1：局部变量级、字段只允许标量、不能作参数/返回值、不能嵌套、不能整体 `print`
- array 仅 v1：局部变量、定长、元素只允许 `int`/`float`/`bool`；不支持空数组/动态扩容/嵌套/参数/返回值/struct 字段，不能整体 `print`
- 函数参数最多 8 个（AAPCS 寄存器上限）；print 最多 7 个变参
- 无优化（教学编译器定位；可后续加简单 peephole）
- 仅支持 arm64（本机架构）；移植 x86-64 需要重写指令选择

## 与另外两套实现的关系

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 语言 | Rust | C++17 | C++17 |
| 后端 | clang 驱动（.ll 文本） | LLVM 库进程内（rustc 方式） | **手写 AArch64 后端（零 LLVM）** |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| 测试 | 66 | 195 | 234 |
| LLVM/clang | 有（clang） | 有（LLVM 库） | **零** |
| 产物 | 原生二进制，示例输出一致 | 同左 | 同左 |

三套实现构成**自主度阶梯**：clang 驱动 → LLVM 库进程内 → 手写后端。
compiler-arm64 证明：只要目标架构固定（arm64）、不追求优化，机器码生成的
"头脑"完全可以自己写。
