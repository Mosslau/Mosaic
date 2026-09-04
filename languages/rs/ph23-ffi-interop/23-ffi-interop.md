# Rust FFI 与跨语言接口设计阶段

> 面向「把 Rust 的安全与性能边界安全地开放给 C、C++、Python」的方向：从 `extern "C"` 与 `#[no_mangle]` 的最小导出开始，认识 cdylib/staticlib 的产物与消费方，穿过 CString/CStr 与 repr(C) 结构体，把错误、所有权、panic 三条 Rust 专有纪律翻译成跨边界协议，再用 bindgen（C→Rust）与 cbindgen（Rust→C）两个生成器消除「两边各维护一份声明」的漂移，最后用 pyo3 把 Rust 函数变成 Python 扩展——全程回答同一句话：**边界上的每一种类型都要有人负责：谁分配、谁释放、谁保证不 panic、谁保证语义一致**。

## 1. 概述

本阶段对应 roadmap 第 23 节，目标是**能安全地把 Rust 与 C、C++、Python 或其他语言集成**。它是学习路线中「Rust 与外部世界」的交汇点：ph14 已经教会 unsafe 与裸指针、`extern` 声明的语法基础；ph19 已经把 `repr(C)`、对齐与 padding 讲成内存布局知识；ph22 刚把性能纪律建立在测量之上——本阶段把这些线头织成一张**可用的跨语言边界设计图**：怎么导出（ABI）、怎么传数据（布局）、怎么表达失败（错误码）、怎么管内存（所有权），以及怎么不让工具链成为重复劳动（bindgen/cbindgen/pyo3）。ph14 的「FFI 调用基础」在此正式扩展为完整工程形态；ph22 预告的兑现点在文首导语已亮明：**把 ph22 的「分配在哪一侧」思考换成「分配由谁负责」，把 ph22 的性能纪律带过 FFI 边界**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| extern "C" 与 ABI | 调用约定声明、`#[no_mangle]`、导出函数最小形态、ABI 稳定类型的边界（3.1） |
| cdylib / staticlib / rlib | 三种 crate 产物的形态、消费方与选择依据（3.2） |
| 字符串跨边界 | CStr 借用视图、CString 拥有转换、NUL 截断与 UTF-8 校验、谁释放（3.3） |
| 布局跨边界 | 标量与 `#[repr(C)]` 结构体/enum 按值传递；对 ph19 布局知识的边界化复用（3.4） |
| 错误跨边界 | 错误码 + out 参数；`catch_unwind` 护栏阻止 unwind 穿越 FFI（3.5） |
| 所有权与内存释放 | `Box::into_raw/from_raw`、谁分配谁释放红线、不透明句柄模式（3.6/3.7） |
| 生成器生态 | bindgen（C 头文件→Rust 绑定）、cbindgen（Rust→C 头文件）消灭声明漂移（3.8/3.9） |
| Python 集成 | pyo3 模块、`#[pyfunction]`/`#[pymodule]`、PyResult 错误翻译、加速模块概念（3.10） |
| 底层原理 | repr(C) 与 C 编译器对齐、unwind 穿越 FFI 的 UB 机制、Box 与 malloc 指针差异、GIL 与 pyo3（4） |
| 场景与练习 | 何时 FFI / 何时重写 + C++/Go 跨语言策略对照；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及**跨语言边界本身的设计与工程化**（ABI、产物、字符串/结构体传递、错误与所有权翻译、绑定与头文件生成、Python 扩展的基础形态），**不涉及跨语言边界的系统化安全审计**（FFI 的 unsafe 安全审查这里只到「每个 unsafe 写清 soundness 前提」的纪律层面，漏洞扫描、供应链审计、制品签名与发布属 ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建）、**不涉及用 FFI 接数据库驱动与数据基础设施组件的工程化**（pyo3 模块的完整打包发布、maturin 多版本构建、给 KV/向量库做 Python 加速接口属 ph25 Rust 数据基础设施专项阶段，roadmap 第 25 节，目录待建）。同时与三条相邻知识划清边界：**unsafe 与裸指针本身**（`extern` 声明语法、裸指针算术、`as` 转换是 ph14 Unsafe 与安全抽象阶段的内容，这里默认已会，只讨论边界用法）；**内存布局的一般知识**（对齐/padding/`repr(C)` 的原理性讲解属 ph19 内存布局与零拷贝阶段，这里复用它做边界协议）；**Python 语言本身**（本阶段只需要会 import 一个模块、写几行冒烟脚本，Python 的语法与工程化不在 Rust 学习路线内展开）。

ph22 主文档「下一阶段」预告的逐条兑现如下——它就是本阶段的验收骨架：

| ph22 预告点 | 兑现位置 |
|------------|---------|
| extern "C" ABI | 3.1 的导出语法 + 4.1 的布局/调用约定原理 |
| cdylib 产物 | 3.2 的产物形态表 + ex01 双形态链接实测 |
| 所有权与内存释放规则跨边界 | 3.6 的三种模式表 + 3.7 的 ptr+len 协议 + ex07 往返实测 |
| pyo3 加速模块 | 3.10 + ex06 + project/rspeed（含真实性能数字） |
| 「分配在哪一侧」思考 →「分配由谁负责」 | 3.6 模式表把思考对象从「哪一侧内存」换成「哪个分配器、哪条释放通道」 |
| 把 ph22 的性能纪律带过 FFI 边界 | 5 节决策表「先测量解释开销占比再决定过不过 FFI」+ project 实测反例 |

## 2. 来源与演变

Rust FFI 的故事可以拆成四股脉络，最后在今天的生态里汇合：**ABI 稳定性探索、语言互操作工具、Python 集成、以及「谁分配谁释放」工程惯例**。

Rust 诞生于与 C 共存的动机——早期 rustc（2010~2015）曾探索自己的稳定 ABI，但很快意识到：一门要与 C 生态互操作的语言，在边界上必须**说 C 的语言**。于是 `extern "C"` 把 Rust 函数标成 C 调用约定（参数入寄存器/栈的排布方式遵循平台 C ABI），`#[no_mangle]` 关闭 Rust 的符号名改编（mangling），导出函数在链接器眼里与 C 函数无异。**设计哲学一句话加粗：Rust 不在边界上发明新协议——它把「安全」留在语言内部，把「边界」对齐到 C ABI 这一现存事实标准，用工具把两边的一致性交给机器维护。**

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 0.x 探索期 | 2010~2014 | 早期尝试自带 ABI；随 1.0 前重设计转向「extern 块 + C ABI」路线，确立 `#[no_mangle]`/`extern` 形态 |
| Rust 1.0 | 2015 | FFI 基础稳定：`extern` 块、`#[link]`、`std::ffi` 的 `CString`/`CStr` 入标准库；ph14 的语法基础即此 |
| cdylib 产物引入 | ~2016 | cargo 增加 `crate-type = ["cdylib"]`：给 C/Python 等外部宿主用的动态库，导出面可裁剪、符号干净，与 rlib（Rust 内部）分流 |
| bindgen 1.0 | 2017 | 从 C/C++ 头文件自动生成 Rust `extern` 绑定的标准工具成熟（用 libclang 解析，含注释搬运、`repr(C)` 结构体映射） |
| cbindgen 生态化 | 2017~ | Mozilla 为 WebRender 开发，从 Rust 反向生成 C/C++ 头文件；`#[repr(C)]` 类型与 doc 注释被翻译进头文件 |
| pyo3 崛起 | 2017~2020 | 基于 CPython C-API 的 Rust 绑定框架；`#[pyfunction]` 宏把错误、引用计数、GIL 的细节隐藏，成为 Python 扩展主流路线 |
| ffi-safe 惯例成型 | 2018~ | 社区把「边界类型必须 repr(C)、错误不上边界、panic 不跨 FFI、谁分配谁释放」沉淀为工程惯例；`mem::forget`/`Box::into_raw` 对读成为所有权转移的标准对 |
| maturin / setuptools-rust | 2019~ | pyo3 的打包工具链成型：从「cargo 手工改名 .so」升级为可发布的 wheel 构建 |
| Rust 2024 edition 前后 | 2024~ | `unsafe extern` 块显式化（2024 edition 要求 `extern` 内的声明标 unsafe）、`c"..."` C 字符串字面量稳定（1.77）——边界语法持续收紧 |

一个值得记住的历史结论：**Rust 官方解决的只是「C ABI 一侧」——与 C++（名字改编、异常）、与 Python（GIL、引用计数）之间的翻译层全部交给生态工具**。bindgen/cbindgen 是 Mozilla 与社区工程实践的产物，pyo3 是第三方框架先做成事实标准、再成为「半官方」路线——这与 criterion/火焰图在 ph22 的地位同构。所以本阶段的知识结构是「**一条 C 主线的语法（编译器保证）+ 三条生态支线的工具（约定驱动）**」，前者的正确性由 rustc 把关，后者的正确性靠你选对工具并守住边界纪律。

本文示例以 **rustc/cargo 1.92.0、edition 2021** 为基线（与 ph21/ph22 及本仓库全部 rs/ 代码层一致）；跨语言侧验证工具链为 **Apple clang 21.0.0（arm64-apple-darwin25.6.0）与 Python 3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`；本机另有 Homebrew Python 3.12.12 用作「标准安装 Python」的对照实验）。生成器版本：**bindgen 0.71.1、cbindgen 0.27.0、pyo3 0.23.5**（本机从 crates.io 在线拉取并实测）。**代码验证状态**：examples 的 ex01~ex07、exercises 的 sol-01~sol-04、project 的 rspeed 全部在本机实测（C↔Rust 双向编译链接运行、pyo3 扩展 import、bindgen 绑定生成、cbindgen 头文件生成均标「已验证」，数字与命令见各 README 与文件头）；**Windows/Linux 平台、MSVC/GCC 工具链、C++ 消费方、Python 其他版本、maturin 打包**未在本环境验证——它们语法同源但平台细节不同，正文涉及处会单独注明。这个阶段的语法是 Rust 里最**「与人打交道」**的部分：新关键字极少，难的是把 Rust 的独占心智（所有权、panic、Result）翻译成对方语言能理解并遵守的协议——学习重点是建立「边界类型表」式的接口设计直觉，而不是背函数名。

## 3. 语法与参数

本章按 roadmap 第 23 节学习内容展开：extern "C" → cdylib/staticlib → CString/CStr → repr(C) 布局 → 错误处理 → 所有权与内存 → vec/slice → bindgen → cbindgen → pyo3。全部命令的完整工程形态见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合项目见 [`project/`](./project/)。

### 3.1 extern "C" 与 #[no_mangle]：Rust 函数怎么变成 C 函数

导出给 C 的最小形态是「`#[no_mangle]` + `pub extern "C"`」三件套（roadmap 第 23 节示例即此，examples/ex01 把三件套扩成两个函数并让 C 真正链接调用）：

```rust
// examples/ex01-export-c-function/src/lib.rs —— 最简导出（已验证）
#[no_mangle]
pub extern "C" fn ex01_add(a: c_int, b: c_int) -> c_int {
    a + b
}
```

拆开看两个属性各管什么：

| 成分 | 作用 | 漏掉的后果 |
|------|------|-----------|
| `extern "C"` | 声明**调用约定**（ABI）：参数与返回值按平台 C 规则排布 | 默认 `extern "Rust"` 约定不稳定，C 侧无法调用 |
| `#[no_mangle]` | 关闭符号名改编，导出符号就叫 `ex01_add` | 符号被改编成 `_ZN…` 长名，C 侧无从声明 |
| `pub` | 让导出项对链接器可见 | 不可见即不导出 |

**为什么这样设计**：Rust 内部不承诺 ABI 稳定（类型布局、函数符号都可能随编译器版本变），但 C ABI 是操作系统与所有语言共存的「共同语」。`extern "C"` 是「这里我说 C 语」的开关，`#[no_mangle]` 是「符号名请保持人类可读」的开关——两者共同保证：导出函数在链接器层面与一个 C 编译出来的函数无法区分。本机实测（macOS arm64，`nm` 查看静态库）：导出符号显示为 `_ex01_add`、`_ex01_mul`、`_ex01_impl_name`（Mach-O 的前导下划线是平台惯例，C 声明 `ex01_add` 与之对应）。

**常见错误**：
- 只写 `extern "C"` 忘写 `#[no_mangle]`（或反之）：编译期一切正常，链接期 C 侧找不到符号——**这是 FFI 第一类「编译过、链接挂」**；
- 把 `String`/`Vec`/`Result` 直接放进导出签名：这些类型无 C 对应布局，导出即错（详见 3.4）；边界上只允许 ABI 稳定类型；
- 在导出函数里放心大胆 `panic!`/`unwrap`：panic 的 unwind 穿过 `extern "C"` 边界是 UB（4.2），必须用 3.5 的护栏兜住。

### 3.2 cdylib vs staticlib vs rlib：给谁看决定产成什么

同一个 `#[no_mangle]` 导出，放进不同 `crate-type` 的库就产出不同形态。cargo 的 `[lib] crate-type` 支持多值，一次构建可同时产出多份（examples/ex01 配了 `["staticlib", "cdylib"]`，一次 `cargo build` 同时出现 `.a` 与 `.dylib`）：

| crate-type | 产物形态 | 消费方 | 何时选它 |
|-----------|---------|--------|---------|
| `rlib` | Rust 专属归档（带元数据），C 无法使用 | 其他 Rust crate（`cargo test` 也要它） | 纯 Rust 库默认；需要内部可测时与 cdylib 并列（ex02/ex03/ex07 即 `["cdylib","rlib"]`） |
| `cdylib` | 对外动态库（Linux `.so` / macOS `.dylib` / Windows `.dll`），符号表干净 | C/Python/其他语言运行时加载或链接 | 给外部宿主用：Python 扩展、插件系统、运行时 `dlopen` |
| `staticlib` | C 静态归档（`.a`/`.lib`），内含全部依赖 | 链接进 C/C++ 可执行文件 | 需要单文件分发、不想要动态库依赖场景 |
| `dylib` | Rust 内部动态库（非 cdylib，保留 Rust 元数据） | 仅 Rust 进程 | 罕见；`cargo test` 加速或大型 workspace 共享 |

**为什么这样设计**：cargo 把「给谁用」编码进构建产物——rlib 是给编译器看的（含让 rustc 增量重用的元数据），cdylib/staticlib 是给外部链接器看的（纯机器码 + 导出符号）。特别值得注意 cdylib 的「符号干净」：它只导出你 `#[no_mangle]` 的部分，不会把 `std` 内部符号泄出去污染宿主进程；staticlib 则相反会把 Rust std 一起归档进去（这也是 staticlib 体积大的原因）。

产物命名与链接参数是配套的：`[lib] name = "ex01_export"` 产出 `libex01_export.a` 与 `libex01_export.dylib`（macOS）/ `libex01_export.so`（Linux），C 侧用 `-lex01_export` 让链接器推导全名；动态链接还要在链接期用 `-Wl,-rpath,<产物目录>` 把运行时查找路径写进可执行文件，否则运行时报 `image not found`。本机实测（ex01，`nm -gU` 查看归档）确认导出符号为 `_ex01_add`/`_ex01_mul`/`_ex01_impl_name`——Mach-O 的前导下划线由链接器按平台惯例处理，C 侧 `extern` 声明无需关心。

**常见错误**：
- 只配 cdylib 的库想 `cargo test`：没有 rlib，测试目标无从链接——**纯导出库的测试天然要落在消费方**（C 端或 Python 端），这是形态决定的、不是缺陷（ex06/sol-03/project 的测试全在 Python 冒烟侧；要 Rust 单测就把 rlib 一起配上）；
- 给 Python 做扩展时用 rlib/staticlib：Python 的 C 扩展加载器要的是动态库 + 特定导出符号，形态错则 import 失败；
- 忘记 macOS 动态链接的运行时查找：C 程序链接 cdylib 后运行报 `image not found`——链接时加 `-Wl,-rpath,<库目录>`（examples/README ex01 命令里已含）。

### 3.3 CString/CStr：字符串跨边界的两层真相

字符串是 FFI 里最典型的「看起来简单、做起来全是坑」的类型。核心认识是：**跨边界的字符串没有 UTF-8 保证、没有长度前缀，只有「NUL 结尾的字节流」**——Rust 标准库为此提供两个类型，方向完全不同：

| 类型 | 语义 | 方向 | 是否拥有内存 |
|------|------|------|------------|
| `CStr` | 「NUL 结尾字节串」的**借用视图** | C→Rust（读入） | 不拥有，借用 C 侧内存 |
| `CString` | 保证 NUL 结尾、可移交的**拥有型**字符串 | Rust→C（交出） | 拥有；`into_raw` 后所有权归 C |

字符串跨边界的完整数据流（两个方向各两层，混淆任一层都会出错）：

```text
C→Rust（读入）:  C 的 char* ──CStr::from_ptr──▶ &CStr（字节视图，NUL 结尾前提）
                                                │
                                                ▼
                                 &str（UTF-8 视图）── 先 from_utf8 校验，字符数才能数
Rust→C（交出）:  &str / String ──CString::new──▶ CString（补 NUL、拒内嵌 NUL）
                                                │
                                      CString::into_raw
                                                ▼
                                    C 的 char*（C 侧持有，须配套释放函数归还）
```

```rust
// examples/ex02-cstring-boundary/src/lib.rs —— 核心三函数（已验证）
// C→Rust：CStr 只管字节；要当 &str 用必须先验证 UTF-8
pub unsafe extern "C" fn ex02_bytes_len(ptr: *const c_char) -> c_int {
    let cstr = unsafe { CStr::from_ptr(ptr) }; // 只认 NUL，不认编码
    cstr.to_bytes().len() as c_int
}
pub unsafe extern "C" fn ex02_utf8_chars(ptr: *const c_char) -> c_int {
    let bytes = unsafe { CStr::from_ptr(ptr) }.to_bytes();
    match std::str::from_utf8(bytes) {          // &str 层才校验 UTF-8
        Ok(s) => s.chars().count() as c_int,
        Err(_) => -1,
    }
}
// Rust→C：CString::into_raw 把所有权交给 C，配套导出释放函数
pub extern "C" fn ex02_make_greeting() -> *mut c_char {
    let c = CString::new("hello from rust").expect("...");
    c.into_raw()
}
pub unsafe extern "C" fn ex02_free_string(ptr: *mut c_char) {
    unsafe { drop(CString::from_raw(ptr)) };    // 谁分配谁释放
}
```

本机实测（ex02 的 C 主程序输出）：中文串「你好，Rust」`C strlen=13 bytes=13 chars=7`——C 的 `strlen` 与 Rust 的 `CStr::to_bytes().len()` 都是字节数，**字符数必须 UTF-8 解码后才能数**；含内嵌 NUL 的 `"ab\0cd"` 两侧都只看到 `2`（NUL 是终点）；非法 UTF-8 字节 `0xFF 0xFE` 在 CStr 层照常返回字节数 2，到 `&str` 层才返回 -1。

**为什么这样设计**：C 字符串的「长度靠扫 NUL」与 Rust 字符串的「长度前缀 + UTF-8 保证」是两种截然不同的不变量。CStr/CString 是这两套不变量之间的翻译器：`CStr::from_ptr` 扫到 NUL 为止构造借用视图（安全前提：C 保证 NUL 结尾）；`CString::new` 检查输入不含内嵌 NUL 并补一个结尾 NUL，从而保证 `into_raw` 交出的指针满足 C 侧一切 strlen/printf 的期待。

**常见错误**：
- 把 C 的 `char*` 直接 `as *const u8` 再读 UTF-8：绕过了「NUL 结尾」前提，C 字符串没有长度边界，越界读是 UB——**永远走 CStr**；
- Rust→C 返回 `String` 的 `.as_ptr()`：`String` 不保证 NUL 结尾，且函数返回后 String 被 drop、指针悬垂——返回**必须**走 `CString::into_raw`（或写进调用方给的缓冲区）；
- `CString::new` 遇到内嵌 NUL 会 panic：`"a\0b"` 这类输入要先校验或允许它 panic 并被 3.5 的护栏接住；
- 忘了「谁分配谁释放」：C 侧拿到 `into_raw` 的指针后用 `free()` 释放——malloc 分配器与 Rust 分配器的差异见 4.3，这在规则层面永远是红线。

### 3.4 基础类型与 repr(C) 结构体：按值穿过边界

标量类型（整数、浮点、指针、`bool`）在大多数平台上的 C 布局与 Rust 一致，可以直接跨边界；`bool` 例外——Rust `bool` 是 1 字节 0/1，C `_Bool` 同为 1 字节但语义约束不同，稳妥做法是导出的布尔用 `i32` 的 0/1 表达。真正的边界大户是**结构体与枚举**：Rust 默认布局（`#[repr(Rust)]`）允许编译器重排字段、插入 padding，跨编译器版本都不稳定——必须用 `#[repr(C)]` 把它钉成「C 编译器眼中的排布」（字段顺序保持声明序、对齐规则与 C 相同；原理见 4.1，ph19 已讲对齐/padding）：

```rust
// examples/ex05-cbindgen-header/rust_lib/src/lib.rs —— repr(C) 类型跨边界（已验证）
#[repr(C)]           // 字段偏移/对齐与 C 结构体一致，可安全按值传递
pub struct Point2D { pub x: f64, pub y: f64 }

#[repr(C)]           // 判言值在 ABI 上就是普通整数
pub enum Quadrant { Origin = 0, Q1 = 1, Q2 = 2, Q3 = 3, Q4 = 4 }

#[no_mangle]
pub extern "C" fn ex05_distance(a: Point2D, b: Point2D) -> f64 { /* … */ }
```

**为什么这样设计**：Rust 不承诺默认布局稳定，为的是给编译器留优化空间（字段重排、去掉未用 padding）。但跨边界时「稳定可预测的布局」比「可能更优的布局」重要——`#[repr(C)]` 就是「在这里放弃 Rust 布局自由、服从 C 规则」的显式声明。repr(C) enum 的判言同理：C 的 enum 本质是整数，Rust 端 `#[repr(C)] enum` 让两边对「这个值在内存里是几号整数」达成一致。ex05 用 cbindgen 把上述类型原样翻译成了 C 头文件里的 `typedef struct`/`typedef enum`（见 3.9 的真实输出），C 侧按值传 `Point2D` 调用距离函数，实测 `distance((0,0),(3,4))=5.0`。

**常见错误**：
- 忘了 `#[repr(C)]` 就导出结构体：Rust 侧布局是「当前编译器版本说了算」，C 侧按声明序读字段会读到错位数据——**跨语言的结构体 bug 常表现为「值对不上」，极难排查**；
- `repr(packed)` 跨边界：去掉对齐换体积在 ph19 已被标记为风险，跨边界时与 C 编译器对 packed 的处理差异更容易踩，非必要不用；
- 结构体里塞了 `Vec`/`String`/`&str`：这些是胖指针/堆句柄，C 结构体里没有对应物，跨边界只能传「裸指针 + 长度」的 C 形态（3.7）；
- 用 `Option<T>`/`Result<T,E>` 当字段：内存布局含判别位且无 C 对应，cbindgen/bindgen 都会拒绝或乱译——边界上用错误码（3.5）与哨兵值（如 -1/0）表达「无值」。

### 3.5 错误处理跨 FFI：Result 不上边界，panic 不跨边界

Rust 的错误通道（`Result`、`?`、panic）是**进程内**概念：C 没有 `Result<T,E>`，异常语义也完全不同。跨边界时错误要翻译成对方能懂的语言——**返回值 = 错误码，out 参数 = 结果，成功才写 out**；同时 panic 的 unwind 穿越 `extern "C"` 边界是未定义行为（4.2），所以每个边界函数都要有 `catch_unwind` 护栏：

```rust
// examples/ex03-error-code-outparam/src/lib.rs —— 错误码 + out + 护栏（已验证）
pub const FFI_OK: c_int = 0;
pub const FFI_ERR_NULL: c_int = -1;   // 输入指针 null
pub const FFI_ERR_PARSE: c_int = -2;  // 解析失败/越界
pub const FFI_ERR_PANIC: c_int = -3;  // panic 被护栏拦下

pub unsafe extern "C" fn ex03_parse_port(ptr: *const c_char, out: *mut u16) -> c_int {
    let caught = std::panic::catch_unwind(|| {
        if ptr.is_null() || out.is_null() { return FFI_ERR_NULL; }
        let bytes = unsafe { CStr::from_ptr(ptr) }.to_bytes();
        match parse_port_inner(bytes) {          // 内部纯安全函数，可单测
            Ok(port) => { unsafe { *out = port }; FFI_OK }
            Err(code) => code,
        }
    });
    caught.unwrap_or(FFI_ERR_PANIC)              // panic 绝不 unwind 进 C
}
```

本机实测（ex03 的 C 主程序）：`"8080"` → `OK, port=8080`；`"0"`/`"70000"`/`"abc"` → `err=-2` 且 out 保持哨兵值不变；null 输入 → `-1`；触发内部故意 panic 的 `panic_probe(1)` → `-3`（panic 消息打到 stderr，但进程不崩）。C 侧还有一个配套纪律：**先读返回值判断成功，再读 out**——失败路径不写 out，先读 out 会拿到未初始化的垃圾（ex03 用哨兵值演示了这个坑）。

**为什么这样设计**：错误跨语言的本质是「两种错误模型的翻译」。Rust 的 `Result` 好处（穷尽匹配、错误携带上下文）依赖类型系统，C 没有；C 的错误码好处（简单、可序列化）Rust 内部用不惯。边界协议取双方交集：**整数错误码**。而 panic 之所以必须拦，是因为 unwind 依赖 Rust 特有的栈展开元数据，C 代码没有它——栈展开穿过非 Rust 栈帧的后果是未定义的（可能是崩溃、可能是静默损坏，4.2 详述）。`catch_unwind` 把「本不该发生的 panic」翻译成错误码，等于给边界上了最后一道保险。

**常见错误**：
- 导出 `fn f() -> Result<i32, MyError>`：无 C 对应，cbindgen 直接拒绝或生成怪签名——**Result 永远止步于边界内侧**；
- out 参数在错误路径也写入：调用方按成功读 out 时会拿到半成品数据；
- 在导出函数里假设「我不会 panic」就裸写：切片越界、`unwrap`、`expect`、分配失败都可能在运行时发生——护栏不是给「错误代码」准备的，是给「预期外的 panic」准备的；
- 错误码文档化不足：`-1/-2/-3` 的语义不写进头文件，C 侧只能靠猜——错误码常量表要作为接口文档随库交付（cbindgen 可把常量导进头文件，3.9）。

### 3.6 所有权与内存释放规则：谁分配，谁释放

跨边界传递大块数据时，最经济的做法不是复制，而是**转移堆分配的所有权**。Rust 侧两把钥匙：`Box::into_raw`（把所有权变成裸指针交出去）与 `Box::from_raw`（把裸指针收回成 Box 再 drop）。ex07 演示了完整往返——Rust 分配、C 改写、Rust 校验、Rust 释放：

```rust
// examples/ex07-ownership-box-transfer/src/lib.rs —— 所有权往返（已验证）
pub extern "C" fn ex07_allocate(len: c_int) -> *mut f64 {
    let v: Vec<f64> = (0..len as usize).map(|i| i as f64).collect();
    let boxed: Box<[f64]> = v.into_boxed_slice();
    Box::into_raw(boxed) as *mut f64   // 所有权移交：此后 Rust 不再触碰
}

pub unsafe extern "C" fn ex07_sum(ptr: *const f64, len: c_int) -> f64 {
    let slice = unsafe { std::slice::from_raw_parts(ptr, len as usize) };
    slice.iter().sum()
}

pub unsafe extern "C" fn ex07_free(ptr: *mut f64, len: c_int) {
    let slice = unsafe { std::slice::from_raw_parts_mut(ptr, len as usize) };
    drop(unsafe { Box::from_raw(slice) })   // 唯一合法归还通道
}
```

本机实测（ex07 的 C 主程序）：C 把每个元素写成 `i²` 后，调回 `ex07_sum` 得到 `1240 = Σi² (0..16)`——证明 C 改写与 Rust 读取的是**同一块内存**，不是拷贝。

**为什么这样设计**：跨边界拷贝有两个成本——时间（大块数据复制）与协议复杂度（谁负责两份内存）。所有权转移把「数据搬运」变成「指针交接」，但代价是责任必须清晰。工程上把责任固定成三种模式，每次设计边界时选一种并写进文档：

| 模式 | 谁分配谁释放 | 适用场景 | 例子 |
|------|------------|---------|------|
| A. 只读借用 | C 分配，Rust 借用期内不释放 | 把现有 C 缓冲区交给 Rust 计算 | `ex07_sum`、bindgen 对 C 数组的读取（3.8） |
| B. 转移所有权 | Rust 分配，必须**归还 Rust**释放 | 大块结果从 Rust 返回 / 大输入交给 Rust 处理 | ex07、`CString::into_raw`（3.3） |
| C. 调用方缓冲 | 调用方分配，被调方只写入 | 字符串等不定长结果 | C 提供 `char* buf, size_t cap` 式签名 |

**常见错误**：
- 模式 B 里让 C 用 `free()` 释放 Rust 指针（4.3 的红线）；
- 模式 B 里 Rust 侧归还时忘了长度（3.7 的 `ptr+len` 协议）；
- 模式 A 里 C 在 Rust 仍借用时释放了缓冲——借用期约定不写清等于把 UB 交给运行时；
- 句柄形态（C 持有 `*mut Opaque` 多次调用）里漏配 destroy——见 exercises 的 sol-04：把 new/destroy 成对导出，让「归还」只有一条路可走。

句柄形态值得单独说一句：当 C 需要「持有 Rust 对象、多次调用方法、最后归还」时，常用**不透明句柄**——Rust 侧导出一个不公开字段的结构体指针，C 侧只做前向声明（`typedef struct VecStore VecStore;`），所有操作走导出的函数。句柄结构体**不需要** `#[repr(C)]`（内部字段从不出现在 C 侧），也不需要 cbindgen 导出其定义——这正是不透明（opaque）的含义：C 侧既不能 `sizeof` 它、也不能用 `free()` 释放它，唯一的释放通道就是配套的 destroy。exercises 的 sol-04 完整实现了这套契约并用 C 程序验证。

### 3.7 vec/slice 跨边界：长度与指针分离传递

裸指针不带长度。`Vec<T>`/`&[T]` 的 C 形态是**`ptr + len` 分离传递**（C 侧用 `const T* data, size_t n`），这是 C ABI 世界传递连续缓冲的通用协议，也是 bindgen 生成物里最常见的形态（`n: usize` 参数即长度）。ex07 正是 `ptr + len` 协议的一个实例；两个实现细节必须钉死：

- `Vec::into_boxed_slice()` 先压掉容量元数据再 `into_raw`：直接对 `Vec` 调 `as_ptr` 后忘掉 Vec，容量区内存泄漏；直接 `Box::into_raw` 一个 `Box<[T]>` 得到的是**胖指针**（含长度元数据），转成 `*mut f64` 后元数据丢失——所以协议必须由调用方把 len 传回来，归还时用 `from_raw_parts_mut` 重建（ex07 注释里把这段原理写全了）；
- len 是安全前提不是性能参数：`from_raw_parts(ptr, len)` 里 len 撒谎 = UB。**边界函数要把 len 当作与指针同等重要的安全不变量**，文档写清「len 必须等于分配时的长度」。

**为什么这样设计**：C 没有切片类型，但「指针 + 长度」是它处理数组的通行证——`fread`/`memcpy`/`qsort` 全是这个形态。Rust 侧 `from_raw_parts` 就是对这个通行证的信任状：它假设调用方给的 `(ptr, len)` 描述了一块真实内存。这也解释了为什么错误码纪律（3.5）和长度契约必须写进接口文档——**越界与长度撒谎的后果在安全语言内部会被拦下，跨边界后直接变成 UB**。

**常见错误**：
- 返回 `Vec` 的 `.as_ptr()` 让 C 去读：函数返回后 Vec drop，指针悬垂；
- 长度用 `i32` 传、实际 `usize`：超过 2^31 的元素数被截断成负数（或相反）——长度跨界要用能覆盖平台地址空间宽度的类型，或约定上限并校验；
- C 侧拿着 `ptr+len` 自己往后读写越界：Rust 无法阻止 C 越界（那是 C 的责任），但协议文档要写清「缓冲区长度是 len，不是更大」。

### 3.8 bindgen：从 C 头文件生成 Rust 绑定

bindgen 解决的是「我要在 Rust 里调用一个现成的 C 库」时的重复劳动：与其手写 `extern "C"` 声明（易漏、易错、C 头文件一改就失同步），不如让工具扫描头文件自动生成。它用 libclang 解析 C/C++ 头文件，把函数声明、`repr(C)` 结构体、常量宏翻译成对应的 Rust `extern` 块与类型。惯用姿势是挂在 `build.rs` 里构建期生成（examples/ex04）：

```rust
// examples/ex04-bindgen-from-c/build.rs —— 构建期生成绑定（已验证，bindgen 0.71.1）
let bindings = bindgen::Builder::default()
    .header("include/vector_math.h")                 // 扫描哪个头文件
    .parse_callbacks(Box::new(bindgen::CargoCallbacks::new()))
    .generate().expect("bindgen 生成绑定失败");
bindings.write_to_file(out_dir.join("bindings.rs")).expect("写入失败");
// （同一步用 cc/ar 把 C 实现编成静态库并告诉 rustc 链接参数）
```

ex04 本机实测生成的 `bindings.rs`（bindgen 0.71.1 真实输出，全文 10 行）就是「C 头文件 → Rust 声明」的直译：

```rust
/* automatically generated by rust-bindgen 0.71.1 */
pub type wchar_t = ::std::os::raw::c_int;
pub type max_align_t = f64;
unsafe extern "C" {
    pub fn vm_dot(a: *const f64, b: *const f64, n: usize) -> f64;
}
unsafe extern "C" {
    pub fn vm_euclidean(a: *const f64, b: *const f64, n: usize) -> f64;
}
```

注意生成的绑定**全部是 unsafe**——bindgen 管「翻译」，不管「不变量」。ex04 的教训是必须在绑定外再包一层安全 API：长度不一致在进入 C 前拦下、把裸指针藏进切片借用。ex04 用「同一批向量，C 实现 vs 纯 Rust 实现各算一遍断言一致」自检绑定真的在调那份 C 库（实测 doc0 `dot=20.0 euclidean=4.4721`，与纯 Rust 参考逐位一致）。

**为什么这样设计**：C 头文件是 C 库的「唯一事实源」——函数签名、结构体布局、常量都在里面。bindgen 把「手抄这份事实」变成「编译期自动抄」，头文件一改、重新构建，绑定自动跟上；再叠加安全封装层，「不变量检查」与「声明翻译」两层职责分离，各管各的。

**常见错误**：
- 直接用生成的绑定而不封装：裸 `unsafe extern` 把 null/越界判断全推给调用方，等于把 C 的危险性原样请回 Rust——**生成绑定永远只该被安全封装层调用**；
- 让 bindgen 解析带复杂宏/C++ 模板的头文件：解析范围要收敛（`Builder::allowlist_function`/`blocklist_item`），否则生成物巨大且常带警告；
- 忘了 libclang 依赖：bindgen 构建期需要本机 C 编译器的 libclang（macOS CLT 自带，本机实测路径 `/Library/Developer/CommandLineTools/usr/lib/libclang.dylib`）；CI 里要单独装。

### 3.9 cbindgen：从 Rust 生成 C/C++ 头文件

cbindgen 是 bindgen 的镜像：bindgen 让 Rust 消费 C 头文件，cbindgen 让 C/C++ 消费 Rust 库——扫描 crate 里 `#[no_mangle] extern "C"` 导出与 `#[repr(C)]` 类型，生成一份 C/C++ 头文件，连 doc 注释都原样搬过去。examples/ex05 的完整闭环是：Rust 库 → `cbindgen` 生成 `.h` → C 程序 `#include` 该头文件并链接 Rust 静态库运行（本机实测输出 `distance((0,0),(3,4))=5.0`、`quadrant((3,4))=1`）：

```c
/* /tmp/.../ex05_rust_lib.h —— cbindgen 0.27.0 真实输出摘录 */
typedef enum Quadrant {
  Origin = 0, Q1 = 1, Q2 = 2, Q3 = 3, Q4 = 4,
} Quadrant;
typedef struct Point2D { double x; double y; } Point2D;
/* 判断点落在哪个象限。约定：…… doc 注释被原样搬进头文件 */
enum Quadrant ex05_quadrant(struct Point2D p);
```

**为什么这样设计**：cbindgen 诞生于 Mozilla WebRender——Rust 库要给 C++ 引擎消费，手写头文件必然在「Rust 侧改了签名、C++ 侧还在用旧声明」上翻车。生成器的价值不是省打字，而是把**单边事实源**变成两边一致：签名与注释都从 Rust 侧派生，Rust 改 → 重新 cbindgen → C 侧编译器立刻在类型层报警。这与 bindgen 的动机同构，只是方向相反——两个工具合起来，Rust↔C 的声明漂移问题就闭环了（C↔C++ 之间也可以让 cbindgen 生成 `language = "C++"`）。

**常见错误**：
- 期望 cbindgen 导出 `String`/`Vec`/`Result`：头文件里没有它们的对应物，要么导出失败要么被跳过——**能进头文件的只有 repr(C) 类型与标量**；
- `cbindgen.toml` 里写错配置键（如 0.27 的 `[parse] parse_deps`，不是 `parse.parse_dependencies`）：配置语法随版本演化，报错信息会直接指出合法键（本机实测踩过，README 记录了正确写法）；
- 在错误目录运行/`--crate` 传 lib 名而非包名：cbindgen 通过 `cargo metadata` 定位 crate，必须在 crate 目录内运行、`--crate` 传**包名**（本机实测：`--crate ex05-rust-lib` 成功、`ex05_rust_lib` 报「Unable to find」）；
- 让头文件落进仓库：生成物应由构建流程产出到构建目录，仓库只留 Rust 源与 cbindgen.toml——examples 的命令把 `.h` 输出到 `/tmp`，避免「生成物与源失同步」（详见各示例文件头）。

### 3.10 pyo3 简介：把 Rust 函数变成 Python 扩展

pyo3 是 Rust 侧基于 CPython C-API 的绑定框架：`#[pyfunction]` 把普通 Rust 函数标记成可导出、`#[pymodule]` 标记模块初始化函数，`cargo build` 产出 cdylib 后改名 `.so` 即被 Python `import`（examples/ex06 的完整闭环）。它内部替你处理了与 CPython 交互的脏活：引用计数、GIL、Python 对象与 Rust 值互转、Rust panic → Python 异常。ex06 的教学模块 ex06_geo 提供三个函数（本机实测 Python 冒烟全过）：

```rust
// examples/ex06-pyo3-module/src/lib.rs —— pyo3 0.23.5（已验证）
#[pyfunction]
fn chunk_text(text: &str, chunk_size: usize, overlap: usize) -> PyResult<Vec<String>> {
    if chunk_size == 0 {
        return Err(PyValueError::new_err("chunk_size must be > 0"));
    }
    /* …核心实现与 Rust 内部完全相同… */
}

#[pymodule]
fn ex06_geo(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    Ok(())
}
```

Python 侧调用 `ex06_geo.chunk_text("…", 10, 2)` 得到 `list[str]`，非法参数得到 `ValueError`——**错误跨边界的形态由 pyo3 决定**：`PyResult` 的 Err 转成 Python 异常，Rust 侧 panic 也被 pyo3 转成 `PanicException`（理想情况仍应像 C 边界一样先用 3.5 的护栏接住，双保险）。

**为什么这样设计**：Python 扩展的底层是 CPython C-API——手动写需要管理引用计数、`PyObject*`、GIL，极易泄漏与段错误。pyo3 把「Python 对象 ↔ Rust 类型」的转换表与生命周期藏进宏和类型系统：`&str`/`i64`/`f64` 等标量近乎零成本进出；`Vec<f64>` 从 Python list 提取是一次 O(n) 复制（pyo3 无法预知 list 长度，只能逐个取）；`PyResult<T>` 让错误走 Python 的异常通道而不是错误码。**加速模块的概念**（roadmap 学习内容的落点）就是：把 Python 里解释开销大的逐元素/逐字符计算移进 Rust，Python 侧只剩一次调用——project 的 rspeed 用真实测量验证了「什么负载值得这么干、什么不值得」（见 project/README 验收表：euclidean ≈5–6x，chunk 反而慢）。

正式发布走 maturin（生产路径，本机未安装、命令未在本环境验证）：

```bash
# 生产路径（maturin 处理 macOS dynamic_lookup、wheel 打包、abi3 等全部脏活）
pip install maturin            # 在含 pyproject.toml 的项目里
maturin develop                # 开发态：编译并装进当前虚拟环境
maturin build --release        # 发布态：产出可 pip install 的 wheel
```

**常见错误**：
- crate-type 没配 cdylib：Python 加载不了 rlib/staticlib；
- 忘了 `extension-module` feature 与 macOS 链接参数：extensions 不链接 libpython，macOS 链接器默认拒绝未定义符号，构建时需 `RUSTFLAGS="-C link-arg=-Wl,-undefined,dynamic_lookup"`（本机实测必需；maturin 会替你加）——Linux 无此问题；
- 在 `#[pyfunction]` 里用会 panic 的写法：pyo3 会转成 Python 异常，但跨 C-API 的 panic 仍不是理想路径，核心逻辑放纯 Rust、边界函数用 PyResult 显式翻译（project rspeed 的做法）；
- 用不同解释器版本编译/导入：非 abi3 的扩展与具体 Python 小版本绑定（本机用 Python 3.13.12 编译，就必须用同一个 3.13.12 导入）；
- 期望它比 numpy 快：numpy 的向量运算本身就是 C——pyo3 的胜场是 numpy 没覆盖的串行/逻辑负载（project/README 的对照说明是诚实注脚）。

## 4. 底层原理

### 4.1 ABI 层类型布局一致性：repr(C) 到底对齐了什么

跨边界传结构体之所以必须是 `#[repr(C)]`，根因在**编译器对布局的自由度**。Rust 默认布局（`#[repr(Rust)]`）允许编译器重排字段顺序、按最优对齐插入 padding，且不承诺跨 rustc 版本稳定；C 编译器则遵守一份由平台 ABI 文档规定的排布规则（System V / Win64 等）：字段按声明序排列、每个字段对齐到其对齐值、结构体总大小是最大成员对齐的整数倍、必要时尾部补 padding。

```text
struct { char a; double b; char c; }   ← C 规则下的内存排布（x86-64 类平台）
偏移: 0         1        8         9 … 16   (对齐 double=8 → a 后空 7 B，b 占 8..15，c 占 16，总大小 24)
布局: [a][ 7B padding ][     b     ][c][ 7B padding ]
```

Rust 侧 `#[repr(C)]` 声明「本结构体按上述 C 规则排布」，于是两边的 `sizeof`、字段偏移、函数传参的寄存器分配全部一致。**为什么不能两边各自「默认」**：Rust 编译器有权把 `b` 挪到开头省 padding——那时 Rust 侧 `b` 在偏移 0、C 侧 `b` 在偏移 8，同一次跨边界调用读到的就是错位数据。这类 bug 不崩溃、不报错，只在数值/行为上悄悄出错，是 FFI 里最阴险的一类。bindgen/cbindgen 生成的正是 `#[repr(C)]` 的精确翻译，它们消除的就是「两边对布局的心智模型不一致」。

### 4.2 unwind 穿越 FFI 边界的 UB 机制

Rust 的 panic 默认走「栈展开」（unwinding）：沿调用栈逐帧运行析构、释放局部资源，直到被 `catch_unwind` 接住或抵达线程边界终止。这个机制依赖**每个栈帧都带展开元数据**（rustc 为每个 Rust 函数生成）。C 函数没有这些元数据——当 panic 的展开过程进入 C 栈帧时，运行时不知道 C 帧的布局、不知道该调用哪些析构，行为未定义：轻则 `abort`（`-C panic=abort` 构建或运气好），重则内存损坏后继续执行。

```text
Rust 导出函数 ffi_f()  ── panic! ──▶ 栈展开开始
   ▼ 展开 Rust 帧（有元数据，安全）
extern "C" 边界 ◀── 展开到此处：再往上全是 C 栈帧 ──▶ 未定义行为（UB）
   C main() 调 ffi_f()        （C 帧无展开元数据，运行时不知道该做什么）
```

所以 `extern "C"` 函数在语义上承担着「展开屏障」的职责，而 rustc **不自动**在边界上加护栏——3.5 的 `catch_unwind` 就是手动补上这层：让 panic 止步于边界内侧，翻译成错误码后以正常返回路径跨过去。`#[no_mangle] pub extern "C"` 函数内一旦有 panic 风险（unwrap、越界索引、`CString::new` 内嵌 NUL……），就必须有这层保险；这也是为什么 3.5 把「护栏」而不是「别写 panic 代码」当作纪律——人无法保证代码永远不 panic，护栏保证的是 panic 发生时的后果可控。

### 4.3 Box 指针与 malloc 指针：为什么不能混着释放

「谁分配谁释放」的底层原因是**分配器身份**。Rust 的默认全局分配器 `#[global_allocator]` 指向 `std::alloc::System`——在 macOS/Linux 上通常就是平台 malloc 家族，因此「Rust 分配、C 用 free() 释放」在本机很多时候**碰巧能跑**。但这是巧合不是契约：

| 维度 | Rust Box 指针 | C malloc 指针 |
|------|--------------|--------------|
| 分配来源 | 当前 `#[global_allocator]`（System，但**可替换**） | `malloc` 家族（当前 libc 的实现） |
| 释放方式 | 回到 Rust 侧 drop（`Box::from_raw`） | C 侧 `free()` |
| 额外元数据 | Box 携带对齐/大小信息走 Rust 侧路径 | malloc 头记录块大小 |
| 替换风险 | `#[global_allocator]` 可换 jemalloc/tcmalloc/自写——换后与 malloc 彻底不同源 | free 一个非 malloc 指针 = UB |

**红线逻辑**：跨边界的每一次分配都必须能回答「这块内存会由哪个分配器释放」。只要把全局分配器换成 jemalloc（数据基础设施场景很常见，ph17 生态阶段提过），「碰巧能跑」立刻变成崩溃或堆损坏。工程惯例因此不赌巧合，而是把释放通道显式化：要么成对导出（`_create`/`_destroy`、`CString::into_raw`/配套 free），要么约定调用方缓冲。exercises 的 sol-04 把这条红线做成接口——不透明句柄只有 `vecstore_destroy` 一条归还路，C 侧从结构上就没有用 `free()` 的机会。

### 4.4 Python GIL 与 pyo3 的交互

CPython 的引用计数内存模型由 **GIL（全局解释器锁）** 保护——同一时刻只有一个线程执行 Python 字节码。任何触碰 Python 对象的代码（读 `PyObject*`、改引用计数、调 Python API）都必须在持锁状态下进行。pyo3 的设计围绕 GIL 展开：

- **进入点自动持锁**：`#[pyfunction]`/`#[pymodule]` 被调用时，pyo3 已持有 GIL，Rust 代码内的 Python 交互安全；
- **Rust 侧主动回 Python**（比如从 Rust 线程里调 Python 回调）：需要 `Python::with_gil` 显式获取——GIL 在 pyo3 里是 `Python<'py>` 标记类型的来源，类型系统保证「没有 GIL 标记就拿不到 `&PyAny`」；
- **持锁不放的代价**：`&str`/`f64` 等标量参数在进入 Rust 时已**提取**成 Rust 值，计算阶段不碰 Python 对象、不占 GIL——这正是加速模块的机制：**热循环在 Rust 侧无锁运行**，只在边界各取/放一次 GIL。若边界函数里长时间调用 Python API，等于替 Python 线程持锁，其他线程全被堵死（project/README 的基准正是「无 GIL 竞争的纯计算」形态，数字才可信）。

理解 GIL 还解释了 pyo3 两个工程决策：`Vec<f64>` 提取是逐元素复制（每次 `PyFloat_AsDouble` 都是持锁的 Python API 调用，所以转换成本是 O(n) 量级）；多线程下若多个 Rust 线程共享 Python 对象，`Send` 的检查会拒绝跨线程携带 `Python` 标记——pyo3 用类型（而非运行时检查）表达「GIL 标记不能离开持锁线程」。

## 5. 使用场景

FFI 不是「Rust 更快的万能接口」——本阶段的核心判断力是**选对跨语言策略**。project 的实测给出了一个绝佳的反例：同为「看似该加速」的负载，向量距离 ≈5–6x 而字符窗口切分反而慢（0.15x）。决策表如下：

| 场景 | 做什么 / 不做什么 | 理由 |
|------|-----------------|------|
| Python 逐元素数值循环是热点（距离、归一化、评分） | 用 pyo3/C ABI 加速 | Python 解释开销 ≫ 算术本身，Rust 把时间花在计算上（rspeed 实测 5–6x） |
| 负载本质是 memcpy/系统调用（切片、文件搬移） | **不跨 FFI** | CPython 底层已是 C，解释开销≈0，Rust 没东西可省（rspeed 的 chunk 反例） |
| 已有成熟 C 库（libuv、sqlite、第三方 SDK） | bindgen 生成绑定 + 安全封装，别重写 | 重写 C 库的维护成本与兼容风险远大于绑定层成本 |
| 自己的 Rust 库要给 C/C++ 消费 | cbindgen 生成头文件 + staticlib/cdylib | 声明漂移由生成器消除，导出面由 repr(C) 类型限定 |
| 给 Python 做正式发布的分发 | maturin 打包，别手工改名 .so | wheel 构建、abi3、多 Python 版本由工具链管理（本环境未验证，命令见 3.10） |
| 跨语言场景是大规模长期工程（插件系统、语言运行时） | 先评估纯 Rust 重写或 IPC，别默认 FFI | 边界把两套错误/内存/生命周期模型缝在一起，边界越多维护成本越高 |
| 语言之间只是偶尔传个文件/结果 | 用文件、标准流、HTTP 等进程边界 | 跨进程边界自带序列化与失败隔离，比跨语言内存共享好调试 |

**纯 Rust 重写 vs FFI 的边界**：重写的判据不是「Rust 快」，而是「这段逻辑的领域复杂度是否值得用所有权表达」。解析器、状态机、协议处理这类「状态与生命周期密集」的代码，重写常比绑一个旧 C 库更安全；数值内核、既有 C SDK 这类「接口稳定、领域知识在对方」的代码，FFI 绑定比重写便宜。ph22 的性能纪律在这里原样适用：**先测量负载里的解释开销占比，再决定要不要过 FFI**——project 的 chunk 反例就是「没测量就假设 Rust 快」的现成教训。

**跨语言策略对比**（为 analysis/ 与 Tenet 合成积累素材）。Rust 与 C++/Go 面对「给别家语言提供能力」时选了三条不同路线：

| 维度 | Rust | C++ | Go |
|------|------|-----|-----|
| 对外 ABI | `extern "C"` + `#[no_mangle]`，cdylib/staticlib 官方支持 | `extern "C"` 可导出，但无统一工具链惯例；pybind11 绑定 C++ ABI | cgo 生成 C 桥，`//export` 指令 |
| 头文件/绑定同步 | bindgen + cbindgen 双向生成器，单边事实源 | pybind11/CppSharp 等社区方案 | cgo 自动生成，无头文件问题（但跨 C ABI 有额外调用层） |
| 错误跨边界 | 错误码 + catch_unwind（panic 永不跨边界） | 异常跨边界是灾难，导出函数必须包 try/catch | panic 在 cgo 桥被转为显式错误 |
| 内存所有权 | 编译器强制 + 「谁分配谁释放」文档化 | RAII 约定 + 智能指针，跨边界靠人守 | GC 托管，跨边界对象需显式 `C.free`/`runtime.KeepAlive` |
| Python 扩展事实标准 | pyo3 + maturin | pybind11 | `go-python` 等（生态弱，少用） |
| 数据基础设施现实 | 加速模块/嵌入式库的高质量选择 | 数据库内核/既有 SDK 绑定的主流 | 少用于跨语言加速，偏服务端 |

跨语言读出的规律：**三家的边界语法都收敛到 C ABI，差异在「谁来保证一致性」**——Rust 用生成器（bindgen/cbindgen）+ 编译器强制（repr(C)、所有权）把漂移与内存错误压到编译期；C++ 靠约定与工具链（pybind11）；Go 用 cgo 自动生成桥、把内存问题交给 GC 与显式 free。**对 Tenet 的启示候选：一门语言若要「成为别人的加速器」，最小可行集合 = 稳定的 C ABI 出口 + 双向声明生成器 + 错误/panic 的显式边界翻译 + 谁分配谁释放的文档契约，其中前两条是工具问题、后两条是设计问题——Rust 把后两条也类型化了，这是它的差异化卖点。** 这些观察在 analysis/ 设计解剖时再深化，本阶段只收集素材。

## 6. 代码示例

本节展示示例的关键片段，完整工程与运行命令在 [`examples/`](./examples/)。验证环境：rustc/cargo 1.92.0 + Apple clang 21.0.0 + Python 3.13.12（macOS arm64），bindgen 0.71.1 / cbindgen 0.27.0 / pyo3 0.23.5。七个示例全部本机实测，标注「已验证」；逐示例输出见 [`examples/README.md`](./examples/README.md)。

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-export-c-function/`](./examples/ex01-export-c-function/) | 3.1/3.2 | Rust 导出库被 C 以动态 + 静态两种方式链接消费 | 已验证 |
| [`examples/ex02-cstring-boundary/`](./examples/ex02-cstring-boundary/) | 3.3 | CStr/CString 三形态：字节 vs 字符、内嵌 NUL、Rust 分配 C 归还 | 已验证 |
| [`examples/ex03-error-code-outparam/`](./examples/ex03-error-code-outparam/) | 3.5 | 错误码 + out 参数 + catch_unwind 护栏（故意 panic → -3） | 已验证 |
| [`examples/ex04-bindgen-from-c/`](./examples/ex04-bindgen-from-c/) | 3.8 | bindgen 构建期生成绑定 + 编译 C 实现，Rust 封装后调用并对照纯 Rust | 已验证 |
| [`examples/ex05-cbindgen-header/`](./examples/ex05-cbindgen-header/) | 3.9 | cbindgen 生成头文件，C include 后链接 Rust 静态库运行 | 已验证 |
| [`examples/ex06-pyo3-module/`](./examples/ex06-pyo3-module/) | 3.10 | pyo3 扩展：cargo 产出改名 .so 即被 Python import | 已验证 |
| [`examples/ex07-ownership-box-transfer/`](./examples/ex07-ownership-box-transfer/) | 3.6/3.7 | Box 所有权往返：Rust 分配 → C 改写 → Rust 校验 → Rust 释放 | 已验证 |

```rust
// examples/ex03-error-code-outparam/src/lib.rs —— 边界函数的三层结构（已验证）
// 第一层护栏 catch_unwind → 第二层判空 → 第三层内部纯安全实现
let caught = std::panic::catch_unwind(|| {
    if ptr.is_null() || out.is_null() { return FFI_ERR_NULL; }
    match parse_port_inner(unsafe { CStr::from_ptr(ptr) }.to_bytes()) {
        Ok(port) => { unsafe { *out = port }; FFI_OK }
        Err(code) => code,
    }
});
caught.unwrap_or(FFI_ERR_PANIC)
```

```rust
// examples/ex07-ownership-box-transfer/src/lib.rs —— ptr+len 协议的两个端点（已验证）
pub extern "C" fn ex07_allocate(len: c_int) -> *mut f64 {
    Box::into_raw((0..len as usize).map(|i| i as f64).collect::<Vec<_>>().into_boxed_slice())
        as *mut f64 // 所有权移交
}
pub unsafe extern "C" fn ex07_free(ptr: *mut f64, len: c_int) {
    // SAFETY: (ptr, len) 对应一次尚未归还的 ex07_allocate 分配——重建 Box 后 drop。
    drop(unsafe { Box::from_raw(std::slice::from_raw_parts_mut(ptr, len as usize)) });
}
```

## 7. 总结

### 关键要点

- **边界上只暴露 ABI 稳定类型**：`extern "C"` + `#[no_mangle]` 是导出语法，`#[repr(C)]` 是布局契约，`String`/`Vec`/`Result`/`Option` 一律止步于边界内侧——cbindgen 能导出什么，就是边界能放什么的清单（3.1/3.4）
- **产物形态按消费方选**：rlib 给 Rust 与测试、cdylib 给外部宿主动态加载、staticlib 给 C/C++ 链接归档；纯 cdylib 无法 `cargo test`，导出库的测试天然落在消费方（3.2）
- **字符串跨边界是两层真相**：CStr 只管 NUL 结尾的字节，`&str` 才校验 UTF-8；Rust→C 走 `CString::into_raw` + 配套释放函数（3.3）
- **错误不上边界、panic 不跨边界**：错误码 + out 参数（成功才写 out）+ 每条边界函数的 catch_unwind 护栏——ex03 实测故意 panic 被翻译成 `-3` 而不是中止进程（3.5/4.2）
- **谁分配谁释放是红线不是风格**：`Box::into_raw/from_raw` 成对、`ptr+len` 成对、句柄 new/destroy 成对；macOS/Linux 上 malloc 与 System 分配器「碰巧同源」不改变规则本身（3.6/3.7/4.3）
- **声明一致性交给生成器**：bindgen 从 C 头文件生成 Rust 绑定、cbindgen 从 Rust 生成 C 头文件，把「两边各维护一份声明」的漂移变成单边事实源（3.8/3.9）
- **pyo3 把 Python 扩展的脏活藏起来**：引用计数/GIL/类型转换由框架处理，`PyResult` 错误转 Python 异常；加速模块的机制是热循环在 Rust 侧无 GIL 运行（3.10/4.4）
- **FFI 不是自动加速器**：rspeed 实测向量距离 ≈5–6x、字符切分反而慢——负载里「Python 解释开销占比」才是是否过 FFI 的判据（5 节/project）

### 阶段验收清单

- [ ] 能说清 `extern "C"`、`#[no_mangle]`、`#[repr(C)]` 各自保证什么、漏掉会出哪类问题（roadmap 验收「能让接口只暴露 ABI 稳定类型」）（3.1/3.4）
- [ ] 能手写一个 cdylib + staticlib 库，并用 clang 分别以动态与静态方式链接 C 主程序运行（3.2/ex01）
- [ ] 能说清 CStr 与 CString 的方向/所有权差异，能写出 Rust→C 字符串的配套释放函数（3.3/ex02）
- [ ] 能把一个会失败 + 一个会 panic 的 Rust 函数包装成「错误码 + out + 护栏」的 C 接口，并在 C 侧验证 panic 不穿越（3.5/ex03）
- [ ] 能说出「谁分配谁释放」的三种模式并各举一例；能解释为什么 C 用 `free()` 释放 Rust 指针是规则层违例（3.6/4.3）
- [ ] 能跑通 bindgen（C→Rust）与 cbindgen（Rust→C）各一条完整链路，并说出生成物为什么不能裸用（3.8/3.9/ex04/ex05）
- [ ] 能把一个 Rust 函数包装成 Python 扩展并冒烟验证；能解释 extension-module 与 macOS dynamic_lookup 的关系（3.10/ex06）
- [ ] 能对一个「疑似该加速」的 Python 负载先测后判：给出过/不过 FFI 的实测依据，而不是默认「Rust 快」（roadmap 验收「能让错误处理不跨 FFI 直接 panic」之外的工程判断力）（5 节/project）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap 第 23 节练习一一对应：练习 1 =「导出一个 C 可调用函数」（sol-01：gcd/lcm，静态 + 动态双链运行），练习 2 =「用 cbindgen 生成头文件」（sol-02：Fraction 结构体，C include 生成头文件计算 1/2+1/3），练习 3 =「把 Rust 函数包装成 Python 扩展」（sol-03：pyo3 词频模块 + Python 冒烟），练习 4 =「不透明句柄模式」（sol-04：谁分配谁释放的接口化，null/越界契约）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Rust 加速库 rspeed**——roadmap 第 23 节推荐项目落地：纯 Rust 核心（可 cargo test）+ pyo3 薄绑定（feature 门控）+ Python 冒烟 + 性能实测，验收标准为「给出纯 Python vs Rust 扩展的真实对比并能解释差异」（本机实测：euclidean dim=200k 纯 Python 10.1~12.2 ms vs Rust 1.9~2.3 ms ≈ 5–6x；chunk_text 222 KB 文本 Rust 反而慢 0.15x——后者的解释是验收的一部分）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（本机跑出 `cargo test` + `smoke_test.py` + `bench.py` 性能表）

### 跨语言对比

- Rust/C++/Go 的跨语言策略都收敛到 C ABI，差异在「谁来保证一致性」：Rust 用生成器 + 编译器强制（repr(C)、所有权）把漂移与内存错误压到编译期，C++ 靠 pybind11 等约定，Go 靠 cgo 自动桥 + GC——「稳定的 C ABI 出口 + 双向声明生成器 + 错误/panic 显式翻译 + 谁分配谁释放契约」是成为「别家语言的加速器」的最小集合（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

**ph24 安全、供应链与发布阶段**（roadmap 第 24 节，目录待建）——本阶段把 FFI 的 unsafe 审查纪律止步于「每个 unsafe 写清 soundness 前提」；下一阶段系统回答「怎么让交付物可信」：cargo audit/cargo deny、许可证与 SBOM、secret 管理、可复现构建与 crates.io 发布流程——届时本阶段的 cdylib/pyo3 制品将进入审计、签名与发布流水线，跨语言边界的系统化安全审查在那里补完。


