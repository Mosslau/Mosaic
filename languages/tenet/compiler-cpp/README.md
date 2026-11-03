# tenet/compiler-cpp —— Tenet 编译器（C++17 实现，LLVM 库进程内）

> Tenet 语言的 C++17 编译器前端。管线：`.tenet → 词法 → 语法 → 类型 → LLVM IR（内存构建）→ LLVM 后端库 → 原生二进制`。
> 这是 Tenet 三套实现中的第二套，后端采用 **rustc 方式**：进程内调用 LLVM 后端库，而不是 clang 驱动。

## 定位

| | |
|---|---|
| 语言 | C++17（纯标准库 + LLVM 开发库） |
| 后端方式 | **LLVM 后端库（进程内）**：IRBuilder 内存构建 IR → TargetMachine 产出机器码（rustc 方式） |
| 产出 | 原生可执行二进制（Mach-O / ELF） |
| 特点 | 进程内完整控制（常量折叠自动生效）；真正的"链接 LLVM 库"路线实证 |
| 测试 | 984 项检查 |

## 管线

```text
hello.tenet
   │  前端（自己写，C++17）
   ├─▶ lexer.hpp      词法分析：字符 → Token 流
   ├─▶ parser.hpp     语法分析：Token → AST（递归下降 + 优先级爬升）
   ├─▶ codegen.hpp    类型推断 + LLVM IR 构建（IRBuilder，内存对象）
   │  后端（LLVM 库，进程内——与 rustc 相同）
   ├─▶ TargetMachine 产出对象文件 .o（指令选择/寄存器分配/机器码）
   ├─▶ 系统 cc 链接 runtime.c
   └─▶ hello          原生二进制，直接运行
```

与 rustc 架构同构：前端自写、产物是 LLVM IR、后端复用 LLVM——区别是
"把 LLVM 请进门当员工"（链接库，进程内调用），而 compiler-rs 是"当外部供应商"
（clang 驱动）。

## 目录结构

```
compiler-cpp/
├── Makefile          # clang++ + llvm-config 自动取头文件/库
├── src/
│   ├── error.hpp     # 统一错误（[行:列] 定位）
│   ├── token.hpp     # 词法单元
│   ├── lexer.hpp     # 词法分析
│   ├── ast.hpp       # 抽象语法树（标签结构体）
│   ├── parser.hpp    # 语法分析
│   ├── codegen.hpp   # 类型推断 + struct（S3a）/ 定长 array（S3b）/ 动态 array（S3c-1 局部、S3c-2 参数/返回值、S3c-3a 字面量/调用表达式）/ 固定 array<struct, N>（S3c-3b-1 局部、S3c-3b-3 参数/返回值、S3c-3b-4 整体赋值）/ 动态 array<struct>（S3c-3b-2）/ 固定嵌套 array（S3c-3c v1 局部、v2 参数/返回值）/ 动态嵌套 array<array<T>>（S3c-3d v1）/ struct 固定数组字段（S3d v1）/ print aggregate（struct / 定长与动态数组 / 嵌套数组）
│   └── main.cpp      # CLI + 进程内后端（TargetMachine）+ 内嵌 runtime.c
├── examples/         # hello / fib / fizzbuzz / struct / nested_struct / array / array_abi / array_struct / dynamic_array / dynamic_abi / dynamic_expr / dynamic_struct / nested_array / dynamic_nested / fixed_abi / assign_array / single_field_array / struct_array_field / print_aggregate
└── tests/            # test_main.cpp
```

## 构建与使用

要求：LLVM 开发库和 `clang++`（macOS Homebrew：`brew install llvm`；
Ubuntu：`sudo apt-get install llvm-dev clang`）。代码兼容 LLVM 18 与 21。

```bash
cd tenet/compiler-cpp

make                    # 构建 tenet 与 test_tenet 并跑测试
make test               # 984 项检查
./tenet build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
./tenet run examples/fib.tenet          # 编译 + 运行一步到位
./tenet run examples/struct.tenet       # struct：字段 / 值拷贝 / 整体赋值
./tenet run examples/nested_struct.tenet  # S3a：嵌套 struct + struct 参数/返回值
./tenet run examples/array.tenet        # array：字面量 / 下标 / len / 拷贝
./tenet run examples/array_abi.tenet    # S3b：array<T, N> 参数/返回值（指针 / sret ABI）
./tenet run examples/array_struct.tenet # S3c-3b-1：固定 array<struct, N>（字段路径 / 元素赋值 / 深拷贝）
./tenet run examples/dynamic_array.tenet  # S3c-1：局部 array<T>（push / 深拷贝 / drop）
./tenet run examples/dynamic_abi.tenet    # S3c-2：array<T> 参数/返回值（descriptor / sret ABI）
./tenet run examples/dynamic_expr.tenet   # S3c-3a：字面量/调用结果作实参，return 字面量/调用
./tenet run examples/dynamic_struct.tenet # S3c-3b-2：动态 array<struct>（push/深拷贝/descriptor ABI）
./tenet run examples/nested_array.tenet   # S3c-3c v1：固定嵌套 array<array<T,N>, M>（a[i][j] 读写）
./tenet run examples/dynamic_nested.tenet   # S3c-3d v1：动态嵌套 array<array<T>>（push / 二级下标 / 深拷贝 / print）
./tenet run examples/fixed_abi.tenet      # S3c-3b-3/S3c-3c v2：固定数组参数/返回值 ABI（ptr / sret）
./tenet run examples/assign_array.tenet   # S3c-3b-4：固定数组整体赋值（b = a / b = [..] / b = f()）
./tenet run examples/struct_array_field.tenet # S3d v1：struct 固定数组字段（字面量 / s.a[i] / 深拷贝 / ABI / print）
./tenet run examples/single_field_array.tenet # 单字段 struct 数组 array<P,1> / 内层 1 槽嵌套数组
./tenet run examples/print_aggregate.tenet # print aggregate：struct / struct 数组 / 动态数组 / 嵌套数组
./tenet ir examples/hello.tenet         # 打印 LLVM IR（Module::print）
```

Makefile 会优先使用 PATH 中的 `llvm-config`；也可用
`LLVM_CONFIG=/path/to/llvm-config` 显式覆盖。

## 支持的语言特性（核心子集）

| 类别 | 内容 |
|---|---|
| 类型 | `int` / `float` / `bool` / `string`；`struct`（可嵌套）；定长 `array<int/float/bool, N>`、`array<struct, N>`、固定嵌套 `array<array<int/float, N>, M>`（长度是类型的一部分）；动态 `array<int/float/bool>`、`array<struct>`（堆数组，S3c-1 局部 / S3c-2 参数与返回值；struct 元素 S3c-3b-2）；struct 字段支持固定数组 `array<T,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>`（S3d v1） |
| 变量 | `let`（类型标注可选，静态推断）、赋值（值语义） |
| 函数 | `fn f(a: int) -> int`、递归；定长 `array<T, N>` 参数/返回值按值传递（指针 / sret）；动态 `array<T>` / `array<struct>` 参数传 descriptor、返回值走 sret（S3c-2 / S3c-3b-2），动态实参与 `return` 支持变量 / 字面量 / 返回动态数组的调用（S3c-3a）；固定 `array<struct, N>`（S3c-3b-3）与固定嵌套 `array<array<T,N>,M>`（S3c-3c v2）参数/返回值同样按值传递：参数传 ptr + 入口按总槽数拷贝，返回值走隐藏 sret + 调用方接管 |
| 控制流 | `if/else if/else`、`while`（唯一循环）、`break`、`return` |
| 运算符 | 算术（向零截断整除/取模）、比较、`&&`/`\|\|` 短路、一元 `-`/`!` |
| 字符串 | 拼接、比较（经 runtime.c：tenet_concat / tenet_strcmp） |
| 运行时 | `tenet_concat` / `tenet_strcmp` / `tenet_bounds_fail`（越界报错退出）；动态数组直接调用 libc `malloc`/`free` |
| 内建 | `print(...)`（标量 / 字符串 / 数组元素编译期拼 printf 格式串；struct、定长与动态数组、struct 数组、固定嵌套数组可直接打印 aggregate 变量，按 `P { x: 1, y: 2 }` / `[1, 2, 3]` / `[P { x: 1 }, P { x: 2 }]` / `[[1, 2], [3, 4]]` 输出；aggregate 表达式如 `print(f())` 明确报错）；`push(a, x)` / `len(a)`（动态数组） |
| struct | S3a：顶层声明，字段可为 `int`/`float`/`bool`、另一个 struct，或固定数组（禁止循环嵌套；动态数组字段明确拒绝）；链式字段 `l.a.x`、嵌套字面量；struct 参数按值拷贝、struct 返回值按值拷贝（指针 / sret ABI）；逐字段值拷贝 / 整体赋值；struct 变量可直接 `print`（嵌套字段用点分路径）。S3d v1：固定数组字段按 `N*elem_slots` 个扁平 i64 槽计入总槽数与后续字段偏移；支持 `array<int/float/bool,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>` 字面量、`s.a[i]` 读写、`s.a[i].field` / `s.a[i][j]`、嵌套 struct 字段里的数组（`o.i.a[i]`）、数组字段整体赋值、整体深拷贝、struct 参数/返回值按总槽数 ABI、`print` 展开数组字段 |
| array | S3b：`array<T, N>` 是固定长度值数组类型，局部变量/参数/返回值都可用；标量元素限 `int`/`float`/`bool`；局部省略标注时由数组字面量推断为 `array<T, N>`（长度是类型的一部分）；参数按值传递（传 `ptr` + 入口逐元素拷贝），返回值走隐藏 `%sret`（调用方缓冲 + 拷回本地）；下标读写、`len`（编译期常量）、逐元素值拷贝；字面量/变量/返回数组的调用可做实参与返回；编译期常量越界 / 运行时动态越界（`tenet_bounds_fail`，stderr + exit 1）。S3c-3b-1：固定 `array<struct, N>` 局部数组——元素按 struct 扁平标量字段占连续 8 字节槽（元素 stride = 字段数×8），支持字面量 / 同类型数组变量初始化、`a[i].field` / `a[i].p.x` 读写、`a[i] = struct` 整体元素赋值、`let b = a` 深拷贝（逐槽复制）、`len` 与越界检查；单字段 struct 数组 `array<P, 1>`（元素仅 1 槽）与 `array<array<int, 1>, M>` 仍按“元素是 struct / array”走扁平槽路径，不会被误判为标量数组。S3c-3c v1：固定嵌套数组 `array<array<int/float, N>, M>`——存储为 `[M*N x i64]` 扁平缓冲（外层第 i 个元素占内层 N 个连续 8 字节槽），支持 `[[1, 2], [3, 4]]` 字面量 / 同类型变量深拷贝（含整体赋值）、`a[i][j]` 读写与内外层运行时边界检查、`len(a)` 外层常量；`len(a[i])` 与整体读取内层数组未开放。S3c-3b-3 / S3c-3c v2：固定 `array<struct, N>` 与固定嵌套数组可作参数/返回值——参数传 `ptr`，被调函数入口按总槽数（`N*slots` / `M*N`）拷贝到本地 `[total x i64]`；返回值走隐藏 `ptr %sret`（函数返回 void），`return 数组变量/字面量/调用` 逐槽打包进 sret，调用方 `let b = f()` 从返回缓冲接管；实参支持同类型变量、`array<P,2>` / 嵌套字面量与返回同类型数组的调用。S3c-3b-4：固定数组整体赋值 `b = a` / `b = [..]` / `b = f()` 把右侧变量 / 字面量 / 返回数组的调用按总槽数打包到临时扁平缓冲，再逐槽覆盖目标（固定数组无堆，直接覆盖），`array<T, N>` / `array<struct, N>` / `array<array<T, N>, M>` 均支持。固定嵌套内层仅 `int`/`float`（bool / 更深嵌套 / 动态外层与固定内层混用明确拒绝；动态嵌套见「动态数组」行 S3c-3d）。S3d v1：struct 的固定数组字段可声明为 `array<int/float/bool,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>`（含 struct 叶子），按扁平槽计入 struct 布局，支持字面量 / `s.a[i]` / `s.a[i].field` / `s.a[i][j]` / 整体赋值 / 深拷贝 / ABI / print；动态数组字段 `array<T>` 明确拒绝。仍不支持整体读取 `a[i]` 为 struct 值；数组变量可直接 `print` |
| 动态数组 | S3c-1：显式标注 `array<T>` 的局部动态数组——堆缓冲区 `{data,len,cap}`、`push` 扩容（cap*2，空数组 cap=4）、运行时 `len`、下标读写（运行时越界检查）、`let b = a` / `b = a` 深拷贝、离开作用域 / `return` / `break` 前 `free`。元素限 `int`/`float`/`bool`，按 8 字节槽存放（int→i64、float↔bitcast、bool↔zext/trunc）。S3c-2：`array<T>` 可作函数参数/返回值——参数传 3 槽 descriptor 指针（data/len/cap），被调函数入口深拷贝（值语义，函数内 push/改元素不影响调用方）；返回值用隐藏 `ptr %sret` descriptor，`return 变量` 转移 data/len/cap 并清空本地槽位（不 free）；调用方 `let b = f()` / `b = f()` 接管 sret 缓冲区并清空临时 descriptor。S3c-3a：动态实参支持变量 / 字面量 / 返回动态数组的调用——字面量与调用结果先构造临时 descriptor，被调函数入口仍深拷贝，调用返回后只 free 临时堆缓冲区（不 free 栈 descriptor），变量实参不复制不 drop；动态 `return` 支持变量 / 字面量 / 调用结果——字面量与调用结果把 data/len/cap 转移进 sret（不 free），调用结果的内层 descriptor 转移后清空。S3c-3b-2：`array<struct>` 元素按 struct 扁平字段占 `slots` 个 8 字节槽（stride = slots×8），堆缓冲区按 `cap*slots*8` 分配；支持字面量 / 同类型变量深拷贝、`push(a, S{...})` / `push(a, 变量)`、`a[i].field` / `a[i].p.x` 读写、`a[i] = S{...}` / struct 变量整体元素赋值；参数传 descriptor + 入口按槽深拷贝，返回值走 sret descriptor 转移并清空；drop 只 free 堆缓冲（struct 不含 array）。S3c-3d v1：动态嵌套 `array<array<int/float/bool>>`——外层堆元素是内层 descriptor（data/len/cap 三个 i64 槽，stride=24），支持字面量 / 同类型变量深拷贝 / 整体赋值、`a[i][j]` 读写（内外双层运行时边界检查）、`len(a)` / `len(a[i])`、`push(a, 内层变量/字面量/返回内层数组的调用)`（内层深拷贝、外层 cap*2）、`print` 输出 `[[1, 2], [3]]`；参数/返回值走 descriptor/sret ABI，入口逐内层深拷贝、返回转移所有权；drop 先逐内层 free(data) 再 free 外层。`a[i]` 整体取值/赋值不支持（`len(a[i])` 支持）；不支持 `array<array<struct>>`、更深嵌套、固定内层混用、struct 字段动态数组；不做 RC/GC，仅 malloc/free |
| 注释 | `//` 与 `/* */` |

## 设计要点

1. **进程内 IR**：`IRBuilder` 在内存里构建 IR（非文本）——`CreateAlloca`/`CreateLoad`/
   `CreateStore`/`CreateCall` 直接生成指令对象
2. **LLVMContext 生命周期**（本实现的头号坑）：`Module` 持有 `LLVMContext&`，
   二者必须与 `CompiledModule{ctx, mod}` 一起转移所有权，否则 context 析构后模块悬空 → 段错误
3. **基本块 + phi**：`if`/`while`/短路用基本块；短路结果用 `CreatePHI`（进程内 API 下最简洁）
4. **常量折叠**：LLVM 自动做编译期求值（`7 / 2.0` 在 IR 阶段就算成 3.5）——进程内库的天然优化
5. **数组**：`alloca [N x T]` + GEP + load/store；常量下标编译期越界报错，
   动态下标生成 `idx >= len`（无符号比较）分支，越界调用 `tenet_bounds_fail(i64, i64)`
   （runtime.c 中 `fprintf(stderr, ...)` + `exit(1)`）
6. **后端**：`InitializeAllTargets` → `TargetMachine` → `legacy::PassManager`
   `addPassesToEmitFile` 产出对象文件 → 系统 `cc` 链接
7. **LLVM 21 API 适配**：`Triple.h`/`Host.h` 移至 `TargetParser/`、`verifyModule` 签名、
   `setTargetTriple` 收 `Triple`、`getOpcode()` 返回 `unsigned`
8. **struct ABI（S3a）**：扁平布局——所有标量叶子字段按深度优先/声明顺序占 8 字节槽
   （int→i64、float↔bitcast、bool↔zext/trunc）；struct 参数传 `ptr`，被调函数入口逐字段
   拷贝到本地槽位；struct 返回值用隐藏 `ptr %sret` 第一参数、函数返回 void，调用方分配
   `[N x i64]` 结果缓冲。字面量/同类型变量/函数调用统一打包进缓冲，保证按值拷贝。
9. **array ABI（S3b）**：与 struct 同构——`array<T, N>` 是固定长度值数组类型，
   局部/参数/返回值都可用。参数以 `ptr` 传入，被调函数入口逐元素拷贝到本地 `[N x T]`；
   返回值用隐藏 `ptr %sret`、函数返回 void，调用方分配 `[N x T]` 缓冲，返回后拷回本地数组。
   实参可以是同类型变量、同长度字面量或返回同类型数组的调用：前两者直接打包/拷贝，
   调用结果从其 sret 缓冲复制。类型比较按元素类型 + 长度（不比较原始字符串）；数组字面量
   推断为 `array<T, N>`；`array<T>`（无长度）是动态数组，S3c-2 起也可作参数/返回值。
   固定 `array<struct, N>` / 固定嵌套数组沿用同一 ABI，但缓冲改为 `[total x i64]`
   扁平槽（见第 16 条）。
10. **动态数组（S3c-1）**：局部 `array<T>` 在栈上拆成 data/len/cap 三个槽位，堆缓冲区用
    libc `malloc`/`free`，元素统一 8 字节槽（int→i64、float↔bitcast、bool↔zext/trunc）。
    `push` 在 `len == cap` 时 cap*2 分配新缓冲区、逐元素拷贝、free 旧缓冲区；`len(a)` 读
    运行时 len；`a[i]` 生成 `idx >= len` 无符号检查（`tenet_bounds_fail`）。`let b = a` /
    `b = a` 先深拷贝到临时 descriptor，整体赋值在 drop 旧缓冲区后接管；离开函数/块、
    if/while 每轮、`return` 前、`break` 退出循环体前都会 `free` data；空字面量 `[]` 的
    cap 从 4 起步。
11. **动态数组 ABI（S3c-2）**：动态数组参数传调用方栈上的 3 槽 descriptor
    `[data ptr, len i64, cap i64]` 指针；被调函数入口按 descriptor 重新 `malloc(cap*8)`、
    逐槽深拷贝，得到本地 `{data,len,cap}`（值语义，push / 改元素只影响副本），
    函数退出时随作用域 drop。动态返回值用隐藏 `ptr %sret` descriptor 第一参数、函数返回
    void；`return 变量` 把 data/len/cap 写入 sret 并清空本地槽位（所有权转移，不 free），
    随后 drop 其他局部。调用方 `let b = f()` / `b = f()` 从 sret descriptor 接管缓冲区并
    清空 descriptor，之后由 b 的 drop 释放，避免 double free。
12. **动态数组表达式（S3c-3a）**：动态实参除变量外还接受数组字面量与返回动态数组的调用。
    字面量先构造临时动态数组（`malloc` + 3 个栈槽），调用结果先拿到内层 sret descriptor，
    二者都写入实参 descriptor 传给被调函数；被调函数入口照旧深拷贝，所以调用返回后
    调用方可以安全地只 `free` 临时堆缓冲区（`drop_desc_owned` / `dyn_drop`），栈上的
    descriptor 本身不参与 free。变量实参仍直接指向调用方数组，不复制、不 drop。
    动态 `return` 支持变量 / 字面量 / 调用结果：字面量构造临时动态数组后把
    data/len/cap 写进 sret 并清空临时槽位（所有权给调用方，不 free）；调用结果把内层
    descriptor 逐槽复制进 sret，再清空内层 descriptor（不 free），避免 double free。
13. **固定 array<struct, N>（S3c-3b-1）**：局部数组存储为 `alloca [N*slots x i64]`，
    元素按 struct 扁平标量字段连续排列（stride = 字段数 × 8 字节）。`a[i]` 先做常量/
    运行时越界检查，再按 `idx * slots` 求元素首槽；字段路径按 `layout_of(S)` 的槽位号
    做 `getelementptr i64`，标量按 8 字节槽 pack/unpack（int→i64、float↔bitcast、
    bool↔zext/trunc），因此 `a[i].field`、`a[i].p.x`、深拷贝与整体元素赋值共用同一
    扁平布局。字面量逐元素打包到对应槽；`let b = a` 逐槽深拷贝；`a[i] = struct` 接受
    字面量 / 同类型 struct 变量 / 返回 struct 的调用。扁平槽路径按**元素种类**
    （struct 或 array）判断，不看元素槽数，因此 `array<P, 1>`（单字段 struct，1 槽）
    与 `array<array<T, 1>, M>`（内层 1 槽）不会被误判成标量数组。S3c-3b-3 起固定
    `array<struct, N>` 参数/返回值已开放（见第 16 条），S3c-3b-4 起整体赋值也已开放
    （见第 17 条）；`array<struct>` 作 struct 字段、整体读取 `a[i]` 为 struct 值仍未开放
    （给出明确错误文案）。
14. **动态 array<struct>（S3c-3b-2）**：堆缓冲区的元素 stride 从标量的 1 槽扩展为
    `array_elem_slots(array<S>) = |layout(S)|`（元素占 `slots` 个连续 8 字节槽）。
    字面量与变量深拷贝按 `cap*slots*8` 分配、按 `len*slots` 逐槽复制；`push` 在扩容时
    用 `cap*2*slots*8` 计算新缓冲字节数并把 struct 打包进 `[slots x i64]` 临时缓冲后
    逐槽追加；`a[i].field` / `a[i].p.x` 与固定数组共用 `struct_array_elem_addr`
    的动态分支（运行时 `tenet_bounds_fail` 检查后按 `idx*slots` 定位）；`a[i] = struct`
    复用 `pack_expr_to_buffer`。参数仍是 3 槽 descriptor，入口深拷贝按槽计数；返回值
    仍是 sret descriptor + 转移清空；drop 只 free 堆缓冲（struct 不含 array）。
15. **固定嵌套数组（S3c-3c v1/v2）**：`array<array<T, N>, M>` 存储为
    `alloca [M*N x i64]`。`a[i][j]` 先分别对外层、内层生成运行时边界检查，再以
    `i*N + j` 求扁平槽（内层为标量，stride 1 槽）；内层 float 与普通数组一样按
    double↔i64 bitcast 打包。字面量要求每个外层元素都是长度 N 的内层字面量；
    同类型变量初始化与整体赋值（`b = a` / `b = [[...]]`）都逐槽深拷贝；
    `len(a)` 仍取外层编译期常量（`len(a[i])` 未开放）。内层 bool、更深嵌套、
    动态外层混用明确拒绝；参数/返回值 ABI 见第 16 条，动态嵌套见第 19 条。
16. **固定数组签名 ABI（S3c-3b-3 / S3c-3c v2）**：`array<struct, N>` 与固定嵌套
    `array<array<T, N>, M>` 的参数/返回值都按总槽数（`N*slots` / `M*N`）在
    `[total x i64]` 扁平缓冲间逐槽拷贝。参数仍传 `ptr`，被调函数入口分配本地
    `alloca [total x i64]` 并 `copy_flat_i64`（值语义）；返回值仍用隐藏 `ptr %sret`、
    函数返回 void，`return` 的变量 / 字面量 / 调用结果经 `pack_fixed_array_expr`
    打包进 sret，调用方 `let b = f()` 再逐槽复制到本地数组。实参支持同类型变量、
    字面量与返回同类型数组的调用；类型比较按完整类型字符串（元素 + 长度 + 嵌套层数）。
    `copy_flat_i64` 只按 8 字节槽复制，因此 struct 字段仍共享 S3c-3b-1 的扁平布局，
    嵌套数组仍共享 S3c-3c 的 `i*N+j` 寻址。
17. **固定数组整体赋值（S3c-3b-4）**：`b = a` / `b = [..]` / `b = f()` 先按目标类型的
    总槽数（`N*slots` / `M*N`）分配临时 `[total x i64]` 缓冲，用 `pack_fixed_array_expr`
    把右侧变量 / 字面量 / 返回数组的调用打包进去，再 `copy_flat_i64` 逐槽覆盖目标。
    固定数组没有堆，不需要释放旧值，直接覆盖即可；右侧先完整打包再写入，因此
    `b = b` 之类的自赋值也安全。标量固定数组 `array<T, N>` 仍走原有的逐元素赋值路径。
18. **print aggregate（struct / array）**：`print` 先按参数类型分派——纯标量 / 字符串 /
    数组元素仍拼一个格式串、只调用一次 `printf`（保持既有输出与行为）；参数里出现
    struct / 数组变量时改成逐片段多次 `printf`，避免 aggregate 展开与变参列表互相干扰。
    - struct：按 `layout_of` 的扁平槽位顺序打印 `P { x: 1, y: 2 }`，嵌套字段用
      点分路径 `Q { p.x: 1, p.y: 2, z: 3 }`；局部 struct 变量直接读各自字段槽，
      struct 数组元素则从 8 字节扁平槽读 i64 后按字段类型 unpack
    - 定长标量数组 `[1, 2, 3]`、定长 struct 数组 `[P { x: 1 }, P { x: 2 }]`、定长嵌套
      数组 `[[1, 2], [3, 4]]` 全部在编译期展开；struct 元素按 `slots*8` 步长定位
    - 动态数组在运行时循环：索引存栈槽，len 从描述符槽读取，元素按 `data + 8*i`
      或 `data + 8*i*slots` 取址；空数组输出 `[]`
    - 参数之间输出一个空格、结尾换行；bool 统一输出 `true`/`false`，float 用 `%g`、
      int 用 `%lld`
    - aggregate 只支持直接打印变量：`print(f())` / `print([1, 2])` / `print(a[i])`
      这类表达式仍由原有表达式路径明确报错
19. **动态嵌套数组（S3c-3d v1）**：`array<array<T>>`（外层与内层都动态，T 限
    `int`/`float`/`bool`）。外层堆缓冲区按元素 stride = 3 个 i64 槽（24 字节）布局，
    每个外层元素就是内层 descriptor `[data, len, cap]`；`array_elem_slots` 对动态内层
    返回 3。字面量 `[[1, 2], [3]]` / 空 `[]` 为每行单独构造内层动态数组再写入 descriptor；
    `let b = a` / `b = a` 走 `nested_copy_from_slots`——重新 malloc 外层，再对每行
    malloc 内层并逐元素拷贝（源数组完全独立）。`a[i][j]` 由 `dynamic_nested_row_desc`
    先做外层越界检查并定位 descriptor，再由 `nested_dynamic_index_addr` 读内层 len 做
    第二次越界检查；`len(a)` 读外层 descriptor，`len(a[i])` 只做外层检查后读内层 len。
    `push(a, inner)` 先用内层动态数组初始化路径深拷贝 `inner`（变量 / 字面量 / 返回
    内层数组的调用），再按 stride=3 追加；外层容量不足时 `cap*2`，新缓冲字节数按
    `newcap*24` 计算。参数 ABI 仍是 3 槽 descriptor，被调函数入口
    `dynamic_param_from_desc` 检测到内层是数组后改走 `nested_copy_from_slots`（逐内层
    深拷贝，值语义）；返回值仍是隐藏 `ptr %sret` descriptor，`return` 变量/字面量/调用
    转移所有权并清空本地槽位。drop 由 `dyn_drop_slots` 按类型分派：先循环外层元素
    逐内层 `free(data)`，再 `free` 外层缓冲区。`a[i]` 整体取值/赋值明确报错；
    `array<array<struct>>` / 更深嵌套 / 固定内层混用都在类型校验处拒绝。

20. **struct 固定数组字段（S3d v1）**：`layout_of` 从「每字段 1 槽」升级为
    `LayoutEntry{path, ty, offset, slots}`——标量 1 槽，固定数组字段
    `N * array_elem_slots(T)` 槽，struct 总槽数递归求和；`array_elem_slots(array<S>)`
    改用 `struct_total_slots(S)`，因此 struct 数组元素、ABI 缓冲、深拷贝的 stride
    自动跟随。局部 struct 变量把数组字段单独分配为 `alloca [slots x i64]`（与 ABI
    扁平槽同构）；`unpack_buffer` / `pack_expr_to_buffer` / `copy_struct` 对数组字段
    整块逐槽拷贝。左值统一经 `resolve_place` 解析：`s.a[i]`、`s.a[i].f`、
    `s.a[i][j]`、嵌套 struct 字段里的 `o.i.a[i]` 都定位到扁平槽，字段偏移按
    `layout_of` 的 `offset` 计算（数组字段后面的标量字段不再假设偏移 = 字段序号）。
    字面量打包由 `pack_array_field_expr` 递归完成：标量元素逐槽 pack，struct 元素
    走 `pack_expr_to_buffer`，嵌套数组递归到叶子；支持 `array<int/float/bool,N>`、
    `array<struct,N>`、`array<array<T,N>,M>`（含 struct 叶子）。struct 参数/返回值
    仍是 ptr + 隐藏 sret，但缓冲大小从 `layout_of(...).size()` 改为
    `struct_total_slots(...)`。`print(struct)` 把数组字段展开为 `a: [1, 2, 3]` /
    `[P { x: 1 }]` / `[[1, 2], [3, 4]]`。数组字段支持整体赋值（`s.a = [..]` /
    `s.a = t.a`）；动态数组字段（`array<T>`，含嵌套里的动态内层）在声明处明确拒绝；
    整体读取 `s.a[i]` 为 struct 值仍保持既有明确报错。

## 测试

```bash
make test
```

词法/语法用文本断言；代码生成用 **LLVM Module 结构断言**（main 含 alloca/store、
add 含 Add 指令、fib 递归自调用、短路含 phi、混合提升含 sitofp；array 断言
`[N x T]` alloca / GEP / `tenet_bounds_fail` 调用；S3a 断言嵌套字段扁平槽、
`define void @f(ptr %sret, ptr %p0)` 指针/sret ABI、调用方结果缓冲、参数入口拷贝、
循环嵌套 / array 字段 / aggregate 表达式 print 报错；S3b 断言 `array<T, N>` 解析、
字面量推断 `array<T, N>`、`define i64 @sum(ptr %p0)` 参数 ABI /
`define void @make(ptr %sret)` 返回 ABI、入口逐元素拷贝、实参打包、
长度不匹配 / 越界错误定位；S3c-1 断言 `array<T>` 局部动态数组的
descriptor 槽位（data/len/cap）、`malloc`/`free` 调用、push 扩容分支、运行时 `len`、
运行时下标越界检查、深拷贝 / 整体赋值、作用域 / `return` / `break` 前 drop、
float bitcast / bool zext·trunc；S3c-2 断言动态参数 descriptor ABI
（`define i64 @sum(ptr %p0)`）、动态返回 sret ABI（`define void @f(ptr %sret, ptr %p0)`）、
入口深拷贝、参数副本退出 drop、return 变量转移后清空本地槽位、`let` / 整体赋值从
sret descriptor 接管、不支持表达式的错误定位；S3c-3a 断言字面量/调用结果实参的临时
descriptor 构造与调用后清理（`call` 在 `free` 之前、只 free 数据）、return 字面量的
临时数组转移进 sret 后清空槽位、return 调用结果的内层 descriptor 转移并清空、
链式/嵌套调用的 malloc/free 配平（无 double free）、float/bool 元素、变量实参语义不变；
S3c-3b-1 断言固定 `array<struct>` 的扁平槽 alloca（`[N*slots x i64]`）、元素 stride GEP、
字段路径读写（含嵌套 struct）、整体元素赋值（字面量 / struct 变量 / 返回 struct 的调用）、
`let b = a` 深拷贝、编译期/运行时越界，以及整体读取的明确拒绝
与错误定位；S3c-3b-2 断言动态 `array<struct>` 的 `malloc(cap*slots*8)`、push 按 slots
扩容与逐槽追加、字段/元素赋值、变量深拷贝、descriptor 参数入口按槽深拷贝、sret 返回值
转移、drop 只 free 一次，以及初始化 / 整体读取 / 固定 `array<struct, N>` 参数与返回值的
明确拒绝；S3c-3c 断言嵌套数组 `[M*N x i64]` alloca、`i*N+j` 扁平槽 GEP、外层与内层
`tenet_bounds_fail`、初始化/整体赋值深拷贝、float bitcast、`len(a)` 外层常量，以及内层
bool / 更深嵌套 / 动态外层与固定内层混用 / 整体读取的明确拒绝；S3c-3b-3 / S3c-3c v2 断言固定
`array<struct, N>` 与嵌套数组的 `define void @f(ptr %sret, ptr %p0)` 签名、
`[total x i64]` 扁平缓冲（入口 4 槽 / sret 4 槽拷贝、`let b = f()` 接管）、
字面量 / 调用结果实参（`pid(pid(c))` / `nid([[5,6],[7,8]])`）、`array<struct,1>`
仍走扁平槽布局、嵌套内层 float bitcast，以及内层 bool / 动态内层 /
动态外层与固定内层混用 / 实参类型不匹配的明确拒绝；S3c-3b-4 断言固定数组整体赋值 `b = a` / `b = [..]` /
`b = f()` 的临时扁平缓冲与逐槽覆盖（`array<T,N>` / `array<struct,N>` /
`array<array<T,N>,M>`，无 malloc/free），并覆盖单字段 struct 数组
`array<P,1>` / 内层 1 槽嵌套数组的局部 / 参数 / 返回值 / 字段读写 / 元素赋值全链路，
以及类型与长度不匹配的错误定位，
并用 LLVM verifier 校验生成模块结构合法）；S3c-3d 断言动态嵌套数组的外层
`malloc(cap*3*8)`（cap=4 → 96 字节）与每行内层 `malloc(32)`、外层元素
`getelementptr [3 x i64]` 三槽 descriptor、`let` / 整体赋值 / 参数入口的
`nested.copy.cond` 循环（逐内层深拷贝）、push 的 `cap*2`（`newcap*24`）与
`dyn.grow.after` 分支、`a[i][j]` 两层 / `len(a[i])` 一层的
`tenet_bounds_fail` 数量、drop 的 `dyn.drop.inner.free` → `dyn.drop.rows`
顺序（先内层后外层）、float bitcast / bool trunc 与 print 的内层行循环
`pnr.cond`（`[[1, 2], [3]]`）、`len(a)` 运行时读取，以及 `array<struct>` 内层 /
更深嵌套 / 固定内层 / `a[i]` 整体取值赋值 / 元素与参数类型错误的明确拒绝；
S3d 断言 struct 固定数组字段的 `[N*slots x i64]` 布局（`array<int,3>` 占 3 槽、
`array<array<int,2>,3>` 占 6 槽、`array<P,2>` 元素 stride 按 P 的总槽数）、
`define void @f(ptr %sret, ptr %p0)` 总槽数 ABI、字面量 / 深拷贝 / 整体赋值、
`s.a[i]` / `s.a[i].field` / `s.a[i][j]` / 嵌套 struct 字段数组读写、运行时下标
`tenet_bounds_fail`、float bitcast / bool trunc、print 数组字段展开，以及动态数组
字段 / 嵌套动态内层 / string 元素 / 数组字段循环嵌套 / 长度与元素类型不匹配 /
直接读取整个数组字段 / 整体读取 `array<struct>` 元素的明确拒绝；
print aggregate 断言 struct 的
`P { ` / `x: ` / `%lld` / `%g` 分片与扁平字段槽、嵌套 struct 的点分路径（`p.x`）、
定长标量/struct/嵌套数组的编译期展开（元素布局、`slots` 步长、无运行时循环）、
动态标量/struct 数组的 `pr.cond` 循环与描述符寻址、bool 的 true/false、空动态数组、
参数间空格/结尾换行、纯标量 print 仍只调用一次 printf，以及 `print(f())` /
字面量 / `a[i]` 整体读取的明确报错文案。共 984 项检查。

## 已知限制与演进

- struct S3a 已支持嵌套字段、链式访问、struct 参数/返回值（指针 / sret ABI）与按值拷贝；
  仍不支持：struct 字段为动态数组、循环嵌套；S3d v1 已支持 struct 固定数组字段
  （字面量 / 下标读写 / 字段与嵌套数组 / 深拷贝 / 参数返回 / print），但整体读取
  `s.a[i]` 为 struct 值与动态数组字段仍保持明确报错；struct 变量可直接 `print`；
  嵌套字面量中的 struct 字段目前要求写成同类型嵌套字面量（不能直接放变量/调用结果）
- array S3b 已支持 `array<T, N>` 局部变量/参数/返回值与按值拷贝；S3c-3b-1 支持局部
  固定 `array<struct, N>`（字段路径读写 / 整体元素赋值 / 深拷贝 / 越界检查）；
  S3c-3b-3 起固定 `array<struct, N>` 参数/返回值（ptr + 隐藏 sret，入口/调用方按
  `N*slots` 槽拷贝）；S3c-3b-4 起固定数组整体赋值 `b = a` / `b = [..]` / `b = f()`
  （变量 / 字面量 / 返回数组的调用，先打包到临时扁平缓冲再逐槽覆盖，覆盖
  `array<T,N>` / `array<struct,N>` / `array<array<T,N>,M>`）；S3c-3c v1/v2 支持固定嵌套
  `array<array<int/float, N>, M>` 的局部变量、参数与返回值（`a[i][j]` 读写 / 深拷贝 /
  内外层边界检查 / `M*N` 槽 ABI）；单字段 struct 数组 `array<P,1>` 与内层 1 槽的嵌套
  数组仍走扁平槽路径；S3d v1 已支持 struct 的固定数组字段（`s.a[i]` /
  `s.a[i].field` / `s.a[i][j]` / 整体赋值 / 深拷贝 / ABI / print），动态数组字段
  明确拒绝；仍不支持 `len(a[i])`、整体读取内层数组、整体读取 `a[i]` 为 struct 值；
  数组变量可直接 `print`
- 动态数组 S3c-1 已支持局部 `array<int/float/bool>`：字面量（含空数组）、`push` 扩容、
  运行时 `len`、下标读写与越界检查、`let b = a` / `b = a` 深拷贝、作用域 / `return` /
  `break` 前 drop；S3c-2 已支持动态数组作函数参数（descriptor + 入口深拷贝）与返回值
  （sret descriptor + 所有权转移 / 清空），调用方 `let` / 整体赋值可接管返回值；
  S3c-3a 已支持字面量/调用结果作动态实参（临时 descriptor，调用后 free 临时缓冲区）
  与 `return` 字面量/调用结果（所有权转移进 sret）；S3c-3b-2 已支持动态 `array<struct>`
  （堆 stride=slots×8、push struct、字段/整体元素赋值、深拷贝、参数/返回值 ABI）。
  S3c-3d 已支持动态嵌套 `array<array<int/float/bool>>`（v1：一层嵌套、内外均动态、
  内层标量；字面量/深拷贝/整体赋值/push/二级下标/len(a[i])/drop/参数返回/print）。
  仍不支持 `array<array<struct>>` 内层、更深嵌套、固定内层混用、`a[i]` 整体取值/
  赋值、struct 字段动态数组（固定数组字段见 S3d v1）、aggregate 表达式 print、
  RC/GC（只 malloc/free）
- `Option`/`Result`/`match` 设计已定待实现
- 未开启 `-O2`（可 `TargetMachine` 配置或 `opt` pass）
- 链接用系统 `cc`（LLVM 完成 IR→机器码，链接与 rustc 一样交给系统链接器）

## 与另外两套实现的关系

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 语言 | Rust | C++17 | C++17 |
| 后端 | clang 驱动（.ll 文本） | LLVM 库进程内（rustc 方式） | 手写 AArch64 后端（零 LLVM） |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| 测试 | 116 | 984 | 1166 |
| 产物 | 原生二进制，示例输出一致 | 同左 | 同左 |

compiler-cpp 证明了"从 clang 驱动切换到链接 LLVM 库"的路线：前端产物不变，
后端集成方式可换，编译出的二进制行为一致。
