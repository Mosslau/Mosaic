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
| 测试 | 1166 项检查 |

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
│   ├── backend.hpp   # ★手写 AArch64 后端（含 1166 项检查的断言对象）
│   └── main.cpp      # CLI + as/ld 驱动 + 内嵌 arm64 运行时
├── examples/         # hello / fib / fizzbuzz / struct / nested / array / array_abi / array_struct / dynamic_array / dynamic_abi / dynamic_expr / dynamic_struct / nested_array / fixed_abi / print_aggregate / dynamic_nested / struct_array_field
└── tests/            # test_main.cpp
```

## 构建与使用

要求：Xcode 命令行工具（`as`/`ld`/`xcrun`）。

```bash
cd tenet/compiler-arm64

make                    # 构建 tenet 与 test_tenet 并跑测试
make test               # 1166 项检查
./tenet build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
./tenet run examples/fib.tenet          # 编译 + 运行一步到位
./tenet run examples/array_struct.tenet   # S3c-3b-1：固定 array<struct, N> 局部数组
./tenet run examples/dynamic_expr.tenet   # S3c-3a：动态字面量/调用结果作实参，return 字面量/调用
./tenet run examples/dynamic_struct.tenet # S3c-3b-2：动态 array<struct>（push/字段读写/ABI）
./tenet run examples/nested_array.tenet   # S3c-3c：固定嵌套数组 array<array<T,N>,M>
./tenet run examples/fixed_abi.tenet      # S3c-3d：固定 array<struct,N> / 嵌套数组参数与返回值
./tenet run examples/print_aggregate.tenet # print(struct / array / struct 数组 / 嵌套数组)
./tenet run examples/dynamic_nested.tenet  # S3c-3e：动态嵌套数组 array<array<T>>
./tenet run examples/struct_array_field.tenet # S3d：struct 的固定数组字段（字面量/读写/ABI/print）
./tenet asm examples/hello.tenet        # 看生成的 arm64 汇编（调试）
```

环境变量：`TENET_AS` / `TENET_LD` / `TENET_SDK` 可覆盖 as/ld/SDK 路径。

## 支持的语言特性（核心子集）

| 类别 | 内容 |
|---|---|
| 类型 | `int` / `float` / `bool` / `string`；struct；固定长度值数组 `array<T, N>`（局部、参数、返回值）；固定长度 struct 数组 `array<S, N>`（局部、参数、返回值）；动态数组 `array<T>` / `array<S>`（局部、参数、返回值，堆缓冲 `data/len/cap`）；固定嵌套数组 `array<array<T, N>, M>`（局部、参数、返回值）；动态嵌套数组 `array<array<T>>`（局部、参数、返回值，外层堆元素是内层 descriptor） |
| 变量 | `let`（类型标注可选，静态推断）、赋值（值语义） |
| struct | 顶层声明、嵌套字段（`struct Line { a: Point; b: Point; }`）、链式字段读写（`l.a.x`）、嵌套字面量、整体值拷贝；支持 struct 参数/返回值（指针 ABI：实参传扁平槽地址，返回值走隐藏 sret 指针）；字段可为 `int`/`float`/`bool`、其他 struct 或固定数组（S3d：`array<T,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>`），禁止循环嵌套与动态 `array<T>` 字段 |
| array（定长 v1 / 动态 S3c/S3c-2/S3c-3a） | 定长 `array<T, N>`：局部变量、参数、返回值（长度是类型的一部分），局部可省略标注由字面量推断；`a[i]` 读写、`len(a)` 编译期常量、逐元素值拷贝、同长度整体赋值（指针 + sret ABI，按值语义）。动态 `array<T>`：`[e1, ...]` / `[]` 初始化、`push(a, x)` 扩容（cap*2，空数组 cap=4，malloc 新缓冲 + 拷贝 + free 旧缓冲）、`len(a)` 运行时读 len、`a[i]` 运行时边界检查、`let b = a` / `b = a` 深拷贝（先 drop 旧值）、离开作用域 / `return` / `break` 前 drop；S3c-2 起支持参数与返回值（参数传 3 槽描述符指针 + 入口深拷贝；返回值走隐藏 sret 描述符 + 所有权转移，调用方 `let`/赋值接管堆缓冲）；S3c-3a 起动态实参还支持字面量 `f([1,2])` 与返回动态数组的调用 `f(g())`（调用方构造临时描述符、调用后只 free 临时堆缓冲），`return` 还支持字面量 `return [1,2];` 与调用 `return g();`（堆缓冲所有权转移给 sret）。标量元素仅 `int`/`float`/`bool`（8 字节槽，float 用位模式）；struct 元素与嵌套数组见下两行，均可整体 `print`（见“内建”） |
| array<struct>（S3c-3b-1 / S3c-3b-2 / S3c-3d） | 固定 `array<S, N>`（局部、参数、返回值）与动态 `array<S>`（局部、参数、返回值）都按扁平字段槽存储，元素 stride = 扁平字段数 slots × 8（float 位模式、bool 占一槽）：`[S { ... }, ...]` / `[]` 初始化、`a[i].field` / `a[i].p.x` 读写、`a[i] = S { ... }` / `a[i] = 同类型变量` 整体元素赋值、`let b = a` / `b = a` 深拷贝；动态另有 `push` 扩容（按 slots*8 字节）与 `len(a)` 运行时读取。固定数组常量下标编译期越界，动态下标运行时检查；动态数组下标（含常量）都读 len 槽做运行时检查。动态 `array<S>` 参数传 3 槽描述符指针 + 入口按 slots 深拷贝，返回值走 sret 描述符 + 所有权转移；固定 `array<S, N>` 参数传元素 0 地址 + 入口按 `N*slots` 拷贝，返回值走隐藏 sret（x0）按总槽数打包、调用方逐槽接管（S3c-3d）。drop 只 free 堆缓冲（S 的字段可以是固定数组，S3d 起元素 slots 递归计入数组槽）。`print(a)` 支持；不支持整体读取 `a[i]` 为 struct 值 |
| array<array<T,N>,M>（S3c-3c / S3c-3d） | 局部变量、参数、返回值，内层元素仅 `int`/`float`（bool 明确拒绝）：字面量 `[[1,2],[3,4]]` 初始化、同类型变量深拷贝/整体赋值；`a[i][j]` 读写，外层/内层分别边界检查；`len(a)` 仍为外层编译期常量（不支持 `len(a[i])`）。存储为扁平 `[M*N x i64]`：元素 i,j 在 `base + 8*(i*N + j)`。参数传元素 0 地址 + 入口按 `M*N` 槽拷贝；返回值走隐藏 sret（x0）+ 调用方逐槽接管（S3c-3d）。不支持动态外层/内层混用（动态形式见 S3c-3e 行）、更深嵌套与 struct 内层 |
| array<array<T>>（S3c-3e） | 动态嵌套数组 v1：外层、内层都是动态数组，内层元素仅 `int`/`float`/`bool`。外层堆元素是内层 descriptor 的 3 个 i64 槽 `[data,len,cap]`，外层 stride = `3*8 = 24` 字节。字面量 `[[1,2],[3]]` / 空 `[]` 初始化；`let b = a` / `b = a` 逐内层深拷贝；`a[i][j]` 读写，内外两层都做运行时边界检查；`len(a)` 读外层，`len(a[i])` 读内层；`push(a, inner)` 深拷贝内层并追加（外层 cap*2，空外层 cap=4）；参数传 descriptor + 入口逐内层深拷贝，返回值走 sret 转移所有权，调用方 `let`/赋值接管；drop 先逐内层 `free(data)` 再 free 外层；`print(a)` 输出 `[[1, 2], [3]]`。不支持 `a[i]` 整体取值/赋值、`array<array<struct>>`、更深嵌套、固定/动态内层混用与 struct 字段中的动态 array |
| 函数 | `fn f(a: int) -> int`、struct/array 参数与返回值（按值语义）、递归 |
| 控制流 | `if/else if/else`、`while`（唯一循环）、`break`、`return` |
| 运算符 | 算术（向零截断整除/取模，`sdiv`/`msub`）、比较、`&&`/`\|\|` 短路、一元 `-`/`!` |
| 字符串 | 拼接、比较（经 libc：strlen/malloc/memcpy/strcmp，内嵌 arm64 运行时） |
| 内建 | `print(...)`：标量/字符串按原行为；另支持直接打印 struct、定长/动态数组、struct 数组、定长嵌套数组与动态嵌套数组（编译期按类型展开 / 运行时循环，逐片段调用 printf） |
| 注释 | `//` 与 `/* */` |

## 设计要点

1. **栈式表达式求值**：结果压入表达式栈（`stp reg, xzr, [sp, #-16]!`），
   二元运算弹出两操作数计算再压回——无需寄存器活跃度分析
2. **Apple Silicon：sp 恒 16 字节对齐**（本实现的头号坑）：8 字节 push 会触发
   `EXC_ARM_SP_ALIGN`，因此 push/pop 一律用 16 字节单位（浮点占位用 `d31`）
3. **栈帧**：变量是 x29 相对槽位（每槽 8 字节）；函数 `stp x29,x30` 保存帧指针与返回地址
4. **调用约定**：
   - 用户函数：AAPCS——参数 x0-x7 / d0-d7，返回值 x0 / d0
   - struct 参数：按自定义 Tenet ABI 传指针（x 寄存器传扁平槽首地址），被调函数入口
     逐字段拷贝到本地扁平槽，因此函数内改 struct 参数不影响调用方（参数值拷贝）
   - array 参数（S3b）：`array<T, N>` 同样传指针（x 寄存器传元素 0 的地址），被调函数入口
     逐元素拷贝到本地 `[N x T]` 栈数组，函数内改元素不影响调用方（参数值拷贝）
   - 固定 struct 数组 / 固定嵌套数组参数（S3c-3d）：同样传元素 0 地址，被调函数入口按
     **总槽数**（`N*slots` / `M*N`）逐槽拷贝到本地扁平槽（struct 元素仍是扁平字段槽），
     函数内就是普通数组局部变量；字面量实参由调用方在帧尾打包成同布局临时缓冲后传地址，
     返回同类型数组的调用直接把 sret 缓冲地址当实参
   - 固定 struct 数组 / 固定嵌套数组返回值（S3c-3d）：隐藏 sret 指针（x0），函数返回 void；
     `return 数组变量/字面量/调用` 先按总槽数打包到帧尾临时缓冲，再整块写进 sret；
     调用方 `let b = f()` / `b = f()` 按总槽数从返回缓冲逐槽接管（值语义）
   - 动态数组参数（S3c-2/S3c-3a）：传 3 槽描述符指针（[0]=data、[8]=len、[16]=cap），被调函数
     入口按 cap `_malloc` 并深拷贝 len 个元素到本地描述符；参数值语义（函数内 push/改元素
     不影响调用方），函数退出时 drop 本地副本。实参可以是变量、字面量或返回动态数组的调用：
     变量只复制三槽进临时描述符，字面量/调用结果先在调用方构造临时描述符，调用返回后
     调用方只 `_free` 临时堆缓冲（描述符本身是栈槽，不 free）
   - struct/array 返回值：隐藏 sret 指针占第一参数 x0，函数返回 void，被调函数把字段/
     元素写回调用方提供的缓冲区；调用方再按值拷入目标变量
   - 动态数组返回值（S3c-2/S3c-3a）：隐藏 sret 指针（x0）指向 3 槽描述符；`return` 支持
     变量、字面量与返回动态数组的调用——把 data/len/cap 写入描述符并**清空临时描述符**
     （所有权转移，不 free），随后 drop 其他局部；调用方 `let b = f()` / `b = f()` 接管堆
     缓冲，后续由 b 的 drop 释放
   - 动态嵌套数组参数/返回值（S3c-3e）：沿用同一 descriptor/sret ABI。参数入口先读取
     调用方外层描述符，再按外层 cap `_malloc(cap*24)`，逐内层 `_malloc(inner_cap*8)` 并拷贝
     `inner_len` 个槽，因此参数与调用方完全独立；返回值把外层 descriptor 的 data/len/cap
     写进 sret 并清空本地槽，内层堆随外层缓冲一起转移所有权；调用方 `let` / 赋值接管。
   - 指针 / sret 都占参数位，因此**含 sret 的函数最多 7 个显式参数**，总数上限 x0-x7；
     array 参数同样占一位，超出明确报错
   - 纯标量 `print`：**Apple 变参约定**（实测与 clang 一致）——固定参数 fmt 在 x0，
     变参全部压栈（从 [sp] 连续存放），不需要 w0/d 寄存器。含 aggregate 的 `print`
     改为每个片段一次 `_printf`（fmt 在 x0，唯一的 8 字节变参放 [sp]），因此不再受
     单次调用的 9 变参上限约束
5. **控制流**：`if`/`while`/`break`/短路全部翻译为标签 + 条件分支（`cmp`/`b.eq`/`cset`）
6. **常量与寻址**：字符串放 `__TEXT,__cstring`、浮点放 `__TEXT,__const`（`.align 3`），
   取址用 `adrp x9, L.xx@PAGE; add x9, x9, L.xx@PAGEOFF`（Apple 语法，非 ELF `:lo12:`）
7. **符号**：函数前 `.globl _name`（否则 ld 找不到入口 `_main`）
8. **内嵌运行时**：`tenet_concat`（strlen×2 + malloc + memcpy×2）与 `tenet_strcmp`（尾调用 strcmp）
   以 arm64 汇编写成，随每个产物一起输出
9. **struct 扁平化**：struct 不生成聚合布局，而是深度优先按声明顺序把字段展开成
   8 字节栈槽（`Line { a: Point; b: Point; }` → `a.x`、`a.y`、`b.x`、`b.y`）。
   标量字段 1 槽；S3d 的固定数组字段占 `N * elem_slots` 个连续槽（`array<struct,N>`
   的 `elem_slots` 为 struct 总槽数，固定嵌套数组递归相乘）；struct 总槽数递归求和。
   int/float/bool 都占 8 字节槽，float 用位模式、bool 存 0/1。字段读写按完整路径
   （`l.a.x`）直接寻址；`let q = p;`/`q = p;` 逐字段 `ldr`/`str` 值拷贝（数组字段逐槽）。
   调用点的 struct 临时实参与 sret 缓冲由帧规划按需追加到普通槽之后：函数体发射完
   才能确定最终帧大小，因此 prologue 的 `sub sp, sp, #N` 先用占位符、发射后回填
10. **array v1 栈布局**：帧规划时数组占 N 个连续 8 字节槽（bool 同样占 8 字节），
    元素 0 在最低地址；`a[i]` 的地址 = 元素 0 槽位 + `i*8`（`ldr/str [x16, x10, lsl #3]`）。
    常量下标在编译期查越界；动态下标用无符号 `cmp idx, len` + `b.hs` 跳到失败块，
    越界时调用内嵌 `_tenet_bounds_fail`（`dprintf(2, ...)` 打印到 stderr，`exit(1)`）。
    超过 ±256 的槽位与超过 4095 的栈帧也走寄存器地址，不受 ldr/str 立即数范围限制
11. **S3b 定长数组语义与 ABI**：`array<T, N>`（带长度）是定长值数组（局部变量、参数、返回值一致，
    长度是类型的一部分）。函数签名必须写 `array<T, N>`；局部可省略标注，由数组字面量推断为 `array<T, N>`。
    数组缓冲布局与局部数组槽一致：
    元素 0 在指针最低地址，元素 i 在 `ptr + 8*i`；参数入口用 `ldr x9, [xN, #8*i]` 逐元素
    拷贝到本地槽，返回值用 `str x9, [x15, #8*i]` 打包到 sret 缓冲。调用点按需分配数组
    临时缓冲（字面量实参 / sret 返回），调用返回后 `ldr x9, [x10, #8*i]` 解包到目标数组；
    float 用 `fmov x9, d9` 按位模式打包/拷贝，bool 与其他元素一样占 8 字节槽
12. **S3c 动态数组**：显式标注 `array<T>`（不带长度）才是动态数组；
    字面量 `[1, 2]` 仍默认推断为定长 `array<T, N>`。每个动态数组在栈上占 3 个 8 字节槽
    （data 指针 / len / cap），元素按 8 字节槽存堆上（int/float/bool，float 用位模式）。
    - `let a: array<T> = [..]` / `= []`：`_malloc(cap*8)`，`cap = max(n, 4)`；`let b = a` 按源 cap
      重新 malloc 并深拷贝 len 个元素（下标 0 在最低地址）
    - `push(a, x)`：len == cap 时 `cap*2`（cap==0 保底 4），`_malloc` 新缓冲 → 循环拷贝 len 个
      元素 → 写新元素 → `_free` 旧缓冲；否则直接写 `data[len]`，最后 len += 1
    - `len(a)` 运行时 `ldr` len 槽；`a[i]` 先 `cmp idx, len` + `b.hs` 走
      `_tenet_bounds_fail`，再 `ldr/str [data, idx, lsl #3]`（常量下标也保留运行时检查）
    - `b = a` / `b = [...]`：先在帧尾临时描述符里构造新值（深拷贝），再 `_free` 旧 b，
      最后把 data/len/cap 搬进 b；`b = b` 是无操作
    - drop：离开函数/块/if 分支/while 每轮时按声明逆序 `_free(data)` 并清零描述符；
      `return` 前 drop 当前全部作用域；`break` 前 drop 到循环体作用域。
      `_free(NULL)` 合法，因此未初始化/重复 drop 路径都安全；只 malloc/free，无 RC/GC
13. **S3c-2/S3c-3a 动态数组参数/返回值 ABI**：
    - 参数：调用方在帧尾构造 3 槽描述符（data/len/cap 由低地址到高地址），把描述符地址
      放 x 寄存器传入；被调函数入口先把所有参数落槽（malloc 会破坏参数寄存器），再对每个
      动态参数 `ldr` 描述符三槽 → `_malloc(cap*8)` → 循环深拷贝 len 个元素。参数是独立副本，
      函数内 `push`/改元素不影响调用方，退出时随作用域 drop
    - 实参形式（S3c-3a）：变量（只把源三槽复制进描述符，调用方保留所有权，不复制不 drop）、
      字面量 `f([1,2])`（`_malloc` 临时数组并填元素，登记临时描述符）、返回动态数组的调用
      `f(g())`（把内层 sret 描述符搬进临时描述符并清空内层）。后两种在 `bl` 返回后由调用方
      逐个 `_free` 临时堆缓冲并清零三槽（描述符是栈槽，不 free）；标量返回值跨 `_free`
      先压栈保存。被调函数入口已深拷贝，故 call 后释放临时缓冲安全
    - 返回：`array<T>` 返回值的隐藏 sret 指针（x0）指向调用方 3 槽描述符。`return` 支持
      （S3c-3a）：变量 `return a;`（转移本地三槽并清零，不 free）、字面量 `return [1,2];`
      （构造临时动态数组后把 data/len/cap 搬进 sret，不 free）、返回动态数组的调用
      `return g();`（把内层 sret 描述符搬进本函数 sret，并清空内层临时描述符）。三者都
      只转移所有权不 free，`str xzr` 清零保证退出路径上的 drop 只 `_free(NULL)`
    - 调用方：`let b = f()` / `let b: array<T> = f()` / `b = f()` 从 sret 描述符读回
      data/len/cap 并清零临时描述符（临时描述符是栈槽，不参与 free），堆缓冲改由 b 的
      drop 负责；被调函数落空时临时描述符已预清零，接管到的也是空描述符
    - 不支持的表达式（数字、struct 等）在实参/return 处明确报错；定长 `array<T, N>` 参数/
      返回值仍走 S3b 指针 ABI；固定 `array<S, N>` 与嵌套数组参数/返回值走 S3c-3d 扁平槽
      ABI（见下）；不引入 RC/GC
14. **S3c-3b-1 固定长度 struct 数组**：`array<S, N>` 的 S 可为 struct（可嵌套，
    字段仍只含标量/struct）。帧规划按 `len * slots` 占连续 8 字节槽，其中
    `slots = struct_total_slots(S)` 是元素总槽数（S3d：含固定数组字段）；元素 0 的字段 0 在最低地址，
    元素 i 的字段 j 位于 `base + 8*(i*slots + j)`，即 stride = `slots*8`。
    - 初始化 `let a: array<S, N> = [S { ... }, ...]`：每个元素先按 S 字面量打包到帧尾
      临时缓冲（复用同一 `slots` 槽缓冲），再逐槽 `ldr`/`str` 平铺进数组槽；
      `let b = a` / `b = a` 只接受同类型同长度数组变量，逐槽值拷贝（深拷贝）
    - 字段读写 `a[i].field` / `a[i].p.x`：常量下标直接按 `base + 8*(i*slots + field_index)`
      寻址并在编译期查越界；动态下标先 `cmp idx, len` + `b.hs` 边界检查，再用
      `lsl`（slots 为 2 的幂）或 `mov x15, #slots; mul` 计算 `idx*slots + field_index`，
      最后 `ldr/str [x14, x17, lsl #3]`；float 字段用 `d9`
    - 元素整体赋值 `a[i] = S { ... }` / `a[i] = 同类型变量`：右值先打包到 `slots` 槽临时
      缓冲，再逐槽复制到元素基址；动态下标跨右值求值期间把下标压栈保存
    - 边界与 `len(a)` 语义与标量定长数组一致；S3c-3b-2 起同一布局也用于动态 `array<S>`
      （见下）；S3c-3d 起同一布局也用于参数/返回值（见下）；整体读取 `a[i]`
      （为 struct 值）仍明确拒绝（S 的字段自 S3d 起可含固定数组）；`print(a)` 按元素逐个展开
15. **S3c-3b-2 动态 struct 数组**：`array<S>` 的堆缓冲按 `stride = slots*8` 存放
    （`slots = struct_total_slots(S)`），描述符仍是 data/len/cap 三槽。
    - 初始化：字面量 `cap = max(n, 4)`、`_malloc(cap*slots*8)`，每个元素先在帧尾 `slots`
      槽临时缓冲打包再逐槽写堆；变量按源 cap 深拷贝 `len*slots` 个槽；调用结果接管 sret 描述符
    - `push(a, S { ... })` / `push(a, s)`：len == cap 时 `cap*2`，`_malloc(newcap*slots*8)`
      → 运行时循环搬 `len*slots` 个槽 → free 旧缓冲 → 追加 slots 个槽；否则直接写
      `data[len*slots]`
    - `a[i].field` / `a[i].p.x`：先 `cmp idx, len` + `b.hs`（常量下标也运行时检查），再按
      `data + 8*(i*slots + field_index)` 寻址；`a[i] = S { ... }` / `a[i] = s` 整体元素赋值
      同样按 slots 逐槽复制
    - 参数：描述符指针 + 入口 `_malloc(cap*slots*8)` 并深拷贝 `len*slots` 槽（参数值语义）；
      返回值：sret 描述符 + 所有权转移（变量/字面量/调用）；drop 只 `_free(data)`
    - 固定 `array<S, N>` 参数/返回值走 S3c-3d 的扁平槽 ABI（见下）
16. **S3c-3c 固定嵌套数组**：`array<array<T, N>, M>` 在帧里占
    `M*N` 个连续 8 字节槽（扁平 `[M*N x i64]`），外层元素 i 的内层元素 j 在
    `base + 8*(i*N + j)`。字面量 `[[...], ...]` 逐内层展开平铺，同类型变量逐槽深拷贝。
    `a[i][j]` 读写先边界检查外层 M、再检查内层 N（常量下标编译期报错，动态下标
    `cmp` + `b.hs`）；地址 = `base + 8*(i*N + j)`，N 为 2 的幂时用 `lsl`，否则
    `mov x15, #N; mul`。`len(a)` 仍是外层常量；内层 bool、动态外层/内层混用
    （动态嵌套数组见 S3c-3e）、更深嵌套、struct 内层与 `len(a[i])` 都明确拒绝
17. **S3c-3d 固定数组参数/返回值 ABI**：`array<S, N>`（struct 元素）与
    `array<array<T, N>, M>`（嵌套数组，内层仅 int/float）支持参数与返回值，元素/内层
    仍按 8 字节扁平槽存放（总槽数 = `N*slots` / `M*N`）。
    - 参数：x 寄存器传元素 0 的地址（调用方局部数组首槽 / 字面量临时缓冲 / 返回数组
      调用的 sret 缓冲）；被调函数入口先落其它参数槽，再按总槽数 `ldr x9, [xN, #8*i]`
      + `str x9, [x29, #...]` 逐槽拷贝到本地扁平槽，因此函数内修改不影响调用方
    - 返回值：隐藏 sret 指针占 x0，函数返回 void。`return a;` / `return [..];` /
      `return f();` 先按总槽数打包到帧尾临时缓冲，再 `str x9, [x15, #8*i]` 整块写 sret；
      `return f();` 直接按总槽数从内层返回缓冲拷贝
    - 调用方：`let b = f()` / `let b: array<S,N> = f()` / `b = f()` 从 sret 缓冲
      `ldr x9, [x10, #8*i]` 逐槽接管到本地数组；字面量实参打包成同布局临时缓冲
      （struct 元素先按 `slots` 槽打包再平铺，嵌套数组逐内层 `[..]` 平铺）
    - 参数指针与 sret 各占一个参数位，仍受 x0-x7 限制；`a[i].field` / `a[i][j]`
      在函数内与局部数组完全一致（含编译期/运行时越界检查）

18. **print aggregate（struct / array）**：`print` 先按参数类型分派——纯标量仍走单次
    printf 拼格式串（保持既有输出与 9 变参上限）；只要出现 struct/数组变量，就改成
    逐片段多次 `_printf`，避免变参寄存器/栈槽与 aggregate 展开互相干扰。
    - struct：按 `layout_of` 的扁平字段顺序打印 `P { x: 1, y: 2 }`，嵌套字段用
      点分路径 `Q { p.x: 1, p.y: 2, z: 3 }`；局部 struct 字段槽向低地址排列（stride -8），
      数组元素内的字段槽向高地址排列（stride +8）；S3d 固定数组字段展开成 `[..]`
      （元素方向与所在 struct 表示一致）
    - 定长标量数组 `[1, 2, 3]`、定长 struct 数组 `[P { x: 1 }, P { x: 2 }]`、定长嵌套
      数组 `[[1, 2], [3, 4]]` 全部在编译期展开；struct 元素按 `slots*8` 步长定位
    - 动态数组在运行时循环：下标存在帧尾 scratch 槽（printf 会破坏 caller-saved 寄存器，
      不能只放在 xN 里），len 从描述符槽读取，元素按 `data + 8*i` 或 `data + 8*i*slots`
      取址；空数组输出 `[]`
    - 参数之间输出一个空格、结尾换行；bool 统一输出 `true`/`false`，float 用 `%g`、
      int 用 `%lld`、string 用 `%s`
    - 动态嵌套数组（S3c-3e）在外层/内层各有一个运行时循环，内层 data/len 与两侧下标
      都放帧尾 scratch 槽；输出 `[[1, 2], [3]]`，空内层输出 `[]`
    - 只支持直接打印 aggregate 变量：`print(f())`、`print([1,2])`、`print(a[i])`（整体
      读取 struct/内层数组）都在编译期明确报错；print 不引入堆分配

19. **S3c-3e 动态嵌套数组**：`array<array<T>>`（外层、内层都动态，T 限
    `int`/`float`/`bool`）。外层描述符仍是 data/len/cap 三槽，但堆元素是内层
    descriptor 的三个 i64 槽 `[data, len, cap]`，外层 stride = `3*8 = 24` 字节；
    外层 `cap = max(n, 4)`。
    - 字面量 `[[...], ...]` / `[]`：外层 `_malloc(cap*24)`；每行先按内层 `array<T>`
      构造临时 descriptor（内层 `cap=max(len,4)`、`_malloc(inner_cap*8)`），再把
      data/len/cap 搬进外层行并清空临时槽；空内层 `[]` 也有独立的 cap=4 缓冲
    - `let b = a` / `b = a`：外层按源 cap `_malloc(cap*24)`，逐行读源内层 descriptor，
      再 `_malloc(inner_cap*8)` 并拷贝 `inner_len` 个槽，内层堆与源完全独立；整体赋值
      先构造新值（临时描述符）再 drop 旧值，最后搬三槽
    - `push(a, inner)`：`inner` 支持内层字面量、内层变量或返回内层数组的调用——
      变量深拷贝、字面量新建、调用结果接管；外层 len==cap 时 `cap*2`（cap==0 保底 4）
      扩容，按 `len*3` 个槽搬运（stride=24），再把内层 descriptor 追加到
      `data[len*3]` 并 len += 1
    - `a[i][j]` 读写：先读外层 len 做 `cmp/b.hs` 检查，按 `data + i*24` 定位行
      descriptor，再读内层 len 做第二次检查，最后 `ldr/str [inner_data, j, lsl #3]`；
      `len(a[i])` 只做外层检查后读行 descriptor 的 len 槽；`a[i]` 整体取值/赋值明确拒绝
    - drop：外层 data 非空时循环 len 行，逐行 `_free([row].data)`，最后 `_free(外层 data)`
      并清零三槽；参数入口逐内层深拷贝（与调用方完全独立），返回值把外层 descriptor
      写进 sret 并清空本地槽（内层堆随外层缓冲一起转移）
    - `print(a)`：外层运行时循环；每行把内层 data/len 存帧尾 scratch 槽（printf 会破坏
      caller-saved 寄存器），内层再循环打印 `[1, 2]`，整体输出 `[[1, 2], [3]]`

20. **S3d struct 固定数组字段 v1**：struct 字段可为 `array<int,N>` / `array<float,N>` /
    `array<bool,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>`；动态 `array<T>`
    字段在 `collect_structs` 阶段明确拒绝。布局用 `LayoutEntry {path, ty, offset, slots}`
    表达：`layout_of` 深度优先累加槽偏移，`struct_total_slots` 递归求和；局部 struct 的
    slot j 在 `base - 8*j`，packed 缓冲/struct 数组元素的 slot j 在 `base + 8*j`。
    - 字面量 `S { a: [1,2,3], x: 9 }`：数组字段按元素槽打包到字段基址（struct 元素先
      按 `slots` 槽打包再平铺），也支持同类型数组变量 / 返回数组的调用
    - `s.a[i]` / `s.a[i].f` / `s.a[i][j]`：`array_ref` 支持「struct 变量.固定数组字段」
      基址（字段基址 = struct 基址 - `8*offset`，元素 stride -8），常量/动态下标都做边界
      检查；struct 数组元素字段沿用 packed +8 布局；固定嵌套数组字段复用双下标路径
    - 深路径 `arr[i].f[j]`（数组元素内的固定数组字段）按「元素基址 + 字段偏移 + 字段下标」
      寻址，支持一层数组元素（`s.ps[i].q.f[j]` 也可以）；更深的
      `arr[i].f[j].g[...]` 多级元素混用不在 v1 范围
    - 整体拷贝 / 参数 / 返回值：`copy_struct`、`pack_expr_to_buffer`、
      `unpack_buffer_from_reg`、sret 缓冲大小全部按 `entry.offset` + `entry.slots` 遍历；
      struct ABI 仍是「总槽数」指针 / 隐藏 sret（`N*elem_slots` 递归计入）
    - print：struct 布局条目逐个展开，数组字段按 `[..]` 递归打印；动态 `array<struct>`
      含数组字段时先把元素拷进临时缓冲再按局部布局展开，普通动态 struct 数组保持原汇编
    - 整体赋值 `s.a = [..]` / `s.a = 同类型数组变量` / `s.a = 返回数组的调用` 复用
      字段写入路径；整体读取 `s.a` 仍要求下标（或 `print(struct)`）
    - 明确不支持：动态 `array<T>` 字段、整体读取 `s.a`、`array<struct>` 元素整体读取；
      多级数组元素与字段数组混用（如 `arr[i].f[j].g[0]`）按现有错误文案拒绝

## 测试

```bash
make test
```

词法/语法用文本断言；代码生成用**汇编模式断言**（stp 16 字节对齐、sdiv/msub、
scvtf 混合提升、tenet_concat/strcmp 调用、条件分支、.globl；S3a 另断言嵌套 struct
的扁平槽、struct 参数 `ldr [xN]` 入口拷贝、sret 隐藏指针与 `sub x0, x29` 调用侧缓冲；
S3b 断言 `array<T, N>` 解析、字面量推断 `array<T, N>`、
数组参数 `ldr [xN, #8*i]` 入口拷贝、sret 返回
`str [x15, #8*i]`、调用侧 `ldr [x10, #8*i]` 解包、参数值拷贝、长度不匹配与错误定位；
S3c 断言 `array<T>` 解析、data/len/cap 三槽与 `cap=max(n,4)`、push 扩容
（`add cap, cap` + malloc/copy/free）、运行时 `len` 读取、`cmp idx, len` + `b.hs` 越界检查、
深拷贝（let / 整体赋值的临时描述符）、while/if/return/break 前的 drop，以及
`push` 限制、动态/定长数组互转的报错文案；
S3c-2 断言动态参数描述符三槽读取 + 入口 malloc/深拷贝循环、多参数（动态/标量/float 混排）
先落槽再拷贝、返回值 sret 三槽写入 + 本地 `str xzr` 清零、调用方描述符接管与清零、
`let`/赋值从调用结果接管、float/bool 元素与错误定位；
S3c-3a 断言字面量/调用结果作实参（临时描述符构造、`bl` 后 free 且清零、内层描述符复制
后清零）、`return` 字面量/调用（malloc 后 data/len/cap 转移进 sret、不 free、临时描述符
清零）、链式调用 `id(id([..]))`、float/bool 字面量、变量实参保持"不复制不 drop"、
非法表达式报错，以及"无 double-free"的清理路径，
还有"以 return 结束的函数之后循环体不被截断"的回归）；
S3c-3b-1 断言 `array<S, N>` 的扁平槽布局（P 2 字段 × 2 元素占 4 槽；Q 嵌套 3 字段
元素 stride=24）、字面量初始化逐槽平铺、`a[i].field` 常量/动态下标读写
（`lsl`/`mul x15` + `ldr/str [x14, x17, lsl #3]`）、嵌套路径 `q[i].p.y`、整体元素赋值、
`let b = a` / `b = a` 深拷贝、float/bool 字段、函数内局部数组、编译期越界与运行时
`cmp idx, len` + `b.hs` 边界检查，以及动态 `array<S>`、参数/返回值、
整体读取 `a[i]` 的明确报错文案（`print(a)` 已支持）。
S3c-3b-2 断言动态 `array<S>` 的 `cap=max(n,4)` 与 `cap*slots*8` 字节分配、三槽描述符
清零、`a[i].field`/嵌套路径的 len 槽运行时检查与 slots 寻址、push 追加/扩容
（`len*slots` 搬运 + free 旧缓冲）、整体元素赋值、`let b = a`/`b = a` 深拷贝、
参数入口 `cap*slots*8` 深拷贝循环、sret 三槽转移/清空/调用方接管。
S3c-3c 断言嵌套数组扁平 `[M*N x i64]` 布局、`[[...], ...]` 字面量平铺、常量下标
直接寻址与编译期外层/内层越界、动态下标的双边界检查（`cmp x10, #M` / `#N`）、
`outer*N + inner` 地址计算（`lsl`/`mul x15`）、同类型深拷贝/整体赋值、float 内层与
推断，以及 bool 内层、固定内层放入动态外层（动态外层配动态内层见 S3c-3e）、
更深嵌套、struct 内层与 `len(a[i])` 的明确报错文案。
S3c-3d 断言固定 `array<S, N>` 参数入口按 `N*slots` 逐槽拷贝（`ldr x9, [xN, #8*i]`）、
函数内 `a[i].field` 的 slots 步长寻址与运行时越界、返回值 sret 隐藏指针 +
`str x9, [x15, #8*i]` 打包（变量/字面量/调用）、调用方 `ldr x9, [x10, #8*i]` 逐槽接管
（`let` 与整体赋值）、字面量实参临时缓冲与 `x0/x1` 参数位、`len(a)` 编译期常量、
float 字段/内层位模式拷贝；嵌套数组参数入口按 `M*N` 拷贝、`a[i][j]` 双边界检查与
`outer*N+inner` 寻址、返回值 sret 打包/接管；以及实参类型/长度、返回值类型、
bool/struct 内层、动态外层配固定内层与"取下标作实参"的报错文案。
print aggregate 断言 struct 的 `P { ` / `x: ` / `%lld` / `%g` 分片与扁平字段槽、
嵌套 struct 的点分路径（`p.x`）、定长标量/struct/嵌套数组的编译期展开（元素布局、
stride=slots*8、无运行时循环）、动态标量/struct 数组的 `L.print.cond.` 循环与
`data + i*slots*8` 寻址、bool 的 true/false、参数间空格/结尾换行、纯标量 print
仍只调用一次 `_printf`，以及 `print(f())` / 字面量 / `a[i]` 整体读取的明确报错文案。

S3c-3e 断言动态嵌套数组外层 `cap=max(n,4)*24`、逐行内层 malloc、外层 descriptor
`[data,len,cap]` 三槽写入、`let`/整体赋值的两次 `L.dnest.copy.` 深拷贝、push 字面量/变量
（`L.dyn.nested.grow`、`L.copy.words`、内层 `L.dyn.copy.`）、float 的 `%g` / bool 的
true-false 与 `L.print.nested.cond.` / `L.print.inner.cond.` 双循环、`print(a)` 的
`[` / `]` / `, ` 分片、参数入口深拷贝与 sret 三槽转移、`len(a[i])` 单边界与
`a[i][j]` 双边界、drop 先内层 `L.dnest.drop.loop.` 再外层 free，以及 struct 内层、
更深嵌套、固定内层混用、整体行取值/赋值与类型不匹配的报错文案。

S3d 断言 struct 固定数组字段：布局 `array<int,3>` 占 3 槽 + 标量 1 槽（帧 32 字节、
字段槽 -8/-16/-24/-32）、字面量逐元素写槽、`s.a[i]` 常量/动态下标读写与 `cmp idx,#3`
运行时边界、`let t = s` 4 槽深拷贝、struct 参数入口 `ldr [x1,#0..#-24]` 与 sret
`str [x15,#0..#-24]`、数组字段由数组变量/返回数组调用初始化、嵌套 struct 字段
`o.i.arr[1]`、`array<P,2>` 字段的 `s.a[i].x` 与整体元素赋值、固定嵌套字段
`m.m[i][j]` 双下标、数组元素内字段数组深路径 `s.ps[i].xs[j]`、float/bool 数组字段、
整体赋值 `s.a = [..]`，以及动态数组字段/
string 元素/未定义元素/数组循环嵌套/长度与元素类型不匹配/整体读取/越界的报错文案。

## 已知限制与演进

- 只支持核心子集；`Option`/`Result`/`match` 设计已定待实现
- struct 字段允许 `int`/`float`/`bool`、其他 struct 或固定数组（S3d：`array<T,N>` / `array<struct,N>` / 固定嵌套 `array<array<T,N>,M>`）；禁止循环嵌套与动态 `array<T>` 字段；整体读取 `s.a` 要求写下标（整体赋值 `s.a = ...` 支持）；`print(p)` 支持整体打印 struct（数组字段展开为 `[..]`）
- struct 字段链必须访问到标量；嵌套 struct 字段本身不能整体赋值/作实参（参考 compiler-rs 的 S3a 范围）
- 定长标量数组 `array<T, N>`：局部可省略标注，由字面量推断；标量元素 `int`/`float`/`bool`；不支持空数组、整体读取 `a[i]`；`print(a)` 支持
- 固定 struct 数组 `array<S, N>`（S3c-3b-1 / S3c-3d）：局部变量、参数、返回值（字面量/同类型数组/返回数组调用初始化、`a[i].field`/嵌套路径读写、`a[i] = struct`、深拷贝；参数传元素 0 地址 + 入口按 `N*slots` 拷贝，返回值 sret + 调用方逐槽接管）；支持元素 struct 内含固定数组字段（slots 递归计入）；不支持整体读取 `a[i]`；`print(a)` 支持
- 动态数组 `array<T>`（S3c / S3c-2 / S3c-3a）：支持局部变量、参数、返回值（堆缓冲 + push 扩容 + 运行时 len/越界检查 + 深拷贝 + 作用域 drop；参数 descriptor 指针 + 入口深拷贝，返回值 sret 描述符 + 所有权转移）；S3c-3a 起动态实参支持变量/字面量/返回动态数组的调用，`return` 支持变量/字面量/调用；标量元素仅 `int`/`float`/`bool`；不支持嵌套/struct 字段；`print(a)` 支持；不做 RC/GC，纯 malloc/free
- 动态 struct 数组 `array<S>`（S3c-3b-2）：局部变量、参数、返回值都支持（描述符 + stride=slots*8、push 扩容、`a[i].field`/嵌套路径读写、整体元素赋值、深拷贝与 drop）；元素 struct 可含固定数组字段（slots 递归计入），不能整体读取 `a[i]`；`print(a)` 支持
- 固定嵌套数组 `array<array<T,N>,M>`（S3c-3c / S3c-3d）：局部变量、参数、返回值，内层仅 `int`/`float`（bool 拒绝）；参数/返回值按 `M*N` 槽指针 + sret ABI；`print(a)` 支持；不支持 `len(a[i])`、动态外层/内层混用（动态嵌套数组见下）、更深嵌套、struct 内层
- 动态嵌套数组 `array<array<T>>`（S3c-3e，v1）：外层/内层均动态，内层元素仅 `int`/`float`/`bool`；外层堆元素是内层 descriptor（stride=24）；支持局部字面量/空 `[]`/深拷贝/赋值、`push` 深拷贝、`a[i][j]` 双边界读写、`len(a)`/`len(a[i])`、参数入口逐内层深拷贝、sret 返回值转移、先内层后外层 drop、`print(a)`；不支持 `a[i]` 整体取值/赋值、`array<array<struct>>`、更深嵌套、固定/动态内层混用；只 malloc/free，无 RC/GC
- 函数参数最多 8 个参数位（AAPCS x0-x7；sret 与 struct/array 指针也各占一位）；纯标量 print 最多 9 个变参（x9-x15 + 需要时借用 callee-saved x19/x20），含 aggregate 时逐片段调用 printf、不受此上限约束
- print 只支持直接打印 aggregate **变量**；返回 struct/array 的调用、数组/struct 字面量、`a[i]` 整体读取等 aggregate 表达式明确报错；动态嵌套数组可整体打印
- 无优化（教学编译器定位；可后续加简单 peephole）
- 仅支持 arm64（本机架构）；移植 x86-64 需要重写指令选择

## 与另外两套实现的关系

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 语言 | Rust | C++17 | C++17 |
| 后端 | clang 驱动（.ll 文本） | LLVM 库进程内（rustc 方式） | **手写 AArch64 后端（零 LLVM）** |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| 测试 | 116 | 984 | 1166 |
| LLVM/clang | 有（clang） | 有（LLVM 库） | **零** |
| 产物 | 原生二进制，示例输出一致 | 同左 | 同左 |

三套实现构成**自主度阶梯**：clang 驱动 → LLVM 库进程内 → 手写后端。
compiler-arm64 证明：只要目标架构固定（arm64）、不追求优化，机器码生成的
"头脑"完全可以自己写。
