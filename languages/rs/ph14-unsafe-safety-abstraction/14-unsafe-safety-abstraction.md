# Rust Unsafe 与安全抽象阶段

> 面向系统底层与高性能组件方向：本阶段把 Rust 的「安全默认」这层外壳打开——理解 `unsafe` 关键字、裸指针、`unsafe fn` 契约、FFI 调用基础与安全抽象封装，掌握「最小 unsafe 边界」的封装心智，知道什么时候该用、什么时候不该用 `unsafe`。

## 1. 概述

Rust Unsafe 与安全抽象阶段对应 roadmap 第 14 节，目标是**理解 unsafe 的能力边界，只在必要时封装最小不安全代码**。具体定位是：**用 `unsafe` 块/`unsafe fn` 打开五类受限操作（裸指针解引用、调用 unsafe fn、调用 extern 函数、union 字段访问、unsafe impl Send/Sync），用裸指针做指针级编程，用 `extern "C"` 调 libc 与自建 C 库（FFI 调用基础），最后把 unsafe 封装进「对外零 unsafe」的安全抽象**。本阶段承接 ph10 智能指针阶段（`Box::into_raw` 是「把指针交出/收回」的最早接触）、ph12 并发与异步阶段（`unsafe impl Send/Sync` 是让类型跨线程的逃逸口）、ph13 文件、网络与系统编程阶段（fd 与系统资源模型是 FFI 的预备知识）；并为 ph19 内存布局、零拷贝与协议解析阶段（`repr(C)` 布局、`from_raw_parts` 零拷贝借用）与 ph23 Rust FFI 与跨语言接口设计阶段（导出 Rust 给 C、bindgen/cbindgen、pyo3）铺路。

| 核心维度 | 覆盖内容 |
|----------|---------|
| unsafe 关键字 | unsafe 块 / unsafe fn / unsafe trait、五类 unsafe 操作、最小 unsafe 边界、**unsafe 不关闭借用检查（实测 E0594/E0502/E0506）**（3.1） |
| 裸指针 | `*const T` / `*mut T`：创建/判空/解引用/`as` 转换/`addr_of!`/`add`/`offset`/`read`/`write`/比较；与引用的区别（3.2） |
| unsafe fn 与契约 | `# Safety` 文档契约、`SAFETY` 注释、E0133 调用规则、不变量由开发者维护（3.3） |
| 未定义行为 | UB 的定义与常见清单、优化器对「无 UB」的假设、行为差异实测（部分未初始化读取 / 移位溢出）（3.4） |
| FFI 调用基础 | `extern "C"` 声明、调用 libc（strlen/malloc/free/abs）、调自建 C 库（cc 编译 .dylib + rustc 链接）、CString/CStr（3.5） |
| 安全抽象封装 | 安全 API + unsafe 内部 + 不变量维护的封装模式、MiniVec 最小实现（3.6） |

这个阶段只涉及 unsafe 关键字的五类操作、裸指针、`unsafe fn` 契约、FFI **调用**基础与安全抽象封装，**不涉及宏与元编程（`macro_rules!` 与过程宏）、Rust 导出给 C（`#[no_mangle]`/cdylib/staticlib）、bindgen/cbindgen 与 pyo3、性能剖析与优化、`repr` 内存布局与字节序深入** — 那些是 [ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)、ph23 Rust FFI 与跨语言接口设计阶段、ph22 性能优化与 Profiling 阶段、ph19 内存布局、零拷贝与协议解析阶段的内容（ph15 目录已建；ph19/ph22/ph23 目录待建）。借用检查错误的系统化调试（E0382/E0499/E0502/E0597 的重构方法）属 ph18 Borrow Checker 调试专项阶段（目录待建），本阶段只把「借用检查在 unsafe 内依然生效」作为必会认知实测呈现。承接 [ph10 智能指针阶段](../ph10-smart-pointers/10-smart-pointers.md)：`Box::into_raw`/`from_raw` 是「所有权转成裸指针再收回」的安全抽象先例；承接 [ph12 并发与异步阶段](../ph12-concurrency-async/12-concurrency-async.md)：`unsafe impl Send/Sync` 在 ph12 是「绝不使用」的禁区，本阶段讲清它的证明责任；承接 [ph13 文件、网络与系统编程阶段](../ph13-file-network-sys/13-file-network-sys.md)：fd 与系统资源模型是 FFI 调用系统库的预备知识。

## 2. 来源与演变

`unsafe` 不是 Rust 的补丁，而是**从第一天就内建的设计**：Rust 的目标是「安全系统编程」，但要与 C 对接、要能写 OS 内核，就必须保留「手动内存操作」的后门。设计哲学一句话加粗：**「Safe Rust 是一个内存错误不可能发生的语言；`unsafe` 是必须被论证的例外，而不是被随意使用的工具」**。因此 Rust 从语法上就是双层语言——绝大多数代码写安全 Rust，只有极少数经过论证的边界写 unsafe，且 unsafe 的合法性由「操作清单」精确限定，而不是「整个文件放开」。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2012 | Rust 早期（0.x）即含 `unsafe` 关键字 | 与所有权系统同源设计：「safe/unsafe 双层语言」从第一天就是核心 |
| 2015 | Rust 1.0（2015-05-15）稳定 | `unsafe` 语义定型：五类操作清单、`unsafe fn`/`unsafe impl` 语法 |
| 2016 | Unsafe Code Guidelines（UCG）工作组启动 | 目标是把「什么构成未定义行为」从口头约定写成规范 |
| 2018 | Edition 2018 | 借用检查与 NLL（非词法生命周期）落地，unsafe 代码的边界更清晰 |
| 2021 | `addr_of!`/`addr_of_mut!` 稳定（Rust 1.51，2021-03-25） | 不创建引用的取址宏——避免裸指针取址时误建引用 |
| 2020~2023 | Stacked Borrows（Ralf Jung）提出，后接 Tree Borrows | 为「什么引用/指针别名合法」建立形式化模型；Miri 成为 unsafe 代码的标准检查工具 |
| 2024 | Edition 2024 | `unsafe extern` 块（Rust 1.82 起）、`unsafe_op_in_unsafe_fn` 默认开启、`#[unsafe(no_mangle)]` 等 unsafe 属性——**unsafe 的边界更显式** |
| 2025 | 本环境工具链：rustc 1.92.0 + Apple clang 21.0.0 | 本文全部示例与错误码（E0133/E0594/E0502/E0506）均在本环境实测 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（与 ph10~ph13 一致：全仓库代码层统一 `rustc --edition 2021` 单文件编译；`unsafe` 关键字与裸指针是自 1.0 起最稳定的语言特性之一，本阶段语法无后续版本变数）。2024 edition 的变化（`unsafe extern` 必须显式、`unsafe_op_in_unsafe_fn` 默认开启）以「说明」形式覆盖，不切换基线——2021 edition 下 `unsafe_op_in_unsafe_fn` 是可选 lint，示例代码除 ex01 一处刻意展示 2021 隐式上下文外统一写显式 unsafe 块（与 2024 兼容）。**验证策略**：编译错误码（E0133/E0594/E0502/E0506）与运行行为（含 UB 行为差异）全部在本环境 rustc 1.92.0 实测后写入；FFI 与自建 C 库联调使用 Apple clang 21.0.0 实测（cc 编译 .dylib + rustc 链接），平台差异处已如实标注。

## 3. 语法与参数

### 3.1 unsafe 关键字与最小 unsafe 边界

`unsafe` 不是「关闭检查」的开关，而是**「我保证这里的操作合法，编译器不再替我检查」的声明**。它精确开放五类操作：

| # | unsafe 操作 | 示例 | 合法条件（由开发者保证） |
|---|------------|------|------------------------|
| 1 | 解引用裸指针 | `*ptr` | 指针非空、对齐、指向有效内存 |
| 2 | 调用 unsafe fn | `unsafe { double(21) }` | 满足被调函数的 `# Safety` 契约 |
| 3 | 调用 extern 函数 | `unsafe { strlen(p) }` | 参数满足 C 函数约定（如字符串以 `\0` 结尾） |
| 4 | 读写 union 字段 | `unsafe { u.i }` | 位模式按目标类型解释合理（否则是 UB） |
| 5 | `unsafe impl Send/Sync` | `unsafe impl Send for T` | T 跨线程使用不会导致数据竞争 |

```rust
// 片段：省略了 fn main 与 use 导入（完整可运行版见 examples/ex01-unsafe-keyword.rs）
let mut x = 42;
let p: *mut i32 = &mut x; // 创建裸指针是安全操作
unsafe {
    *p += 1; // 解引用裸指针必须在 unsafe 上下文内
}
```

**最小 unsafe 边界**：unsafe 块越小越好——把 unsafe 限定在「单条操作」上，周围逻辑全部安全，错误面就收缩到可以逐一论证。这是 roadmap 必会概念，也是安全抽象封装（3.6）的落点。

**unsafe 不关闭借用检查**（必会概念）：`unsafe` 只豁免上面五类操作的合法性检查，**借用检查、所有权规则、生命周期推断在 unsafe 块/unsafe fn 内照常生效**——试图在 unsafe 里绕过借用错误（比如通过共享引用修改数据、在不可变借用存活时取可变借用）照样编译失败。这是初学者最大的误区（「用了 unsafe 是不是什么都能干」——不是）。实测演示见示例 4（`ex04-borrow-check-still-on.rs`，故意编译失败）：E0594（不能通过 `&` 引用修改）、E0502（不可变借用存活期间的可变借用）、E0506（借用期间赋值）在 unsafe 内全部照常拦截。

> 本阶段只把「借用检查在 unsafe 内依然生效」作为认知实测验证；**借用错误的系统化定位与重构方法属于 ph18 Borrow Checker 调试专项阶段（目录待建）**，这里只需理解「unsafe 不豁免借用规则」这一条。

### 3.2 裸指针

裸指针 `*const T` / `*mut T` 是 unsafe 世界的入口：**创建裸指针是安全操作，解引用/运算读写是 unsafe 操作**。它与引用的区别：

| 维度 | `&T` / `&mut T` | `*const T` / `*mut T` |
|------|----------------|----------------------|
| 参与借用检查 | 是（编译器保证别名规则） | 否（编译器不跟踪） |
| 自动释放 | 否（所有权系统管理） | 否（谁都不管，必须手动） |
| 可为空 | 否（引用必须有效） | 是（`null()`/`null_mut()`） |
| 能否传给 C | 不适合（C 需要裸指针） | 是（FFI 标准形态） |
| 是否要求有效内存 | 是（构造时就必须有效） | 否（可以是悬垂/空，解引用时才炸） |
| 移动 | 引用会移动值 | 指针本身可复制（`Copy`） |

常用操作（全部实测于示例 2）：

```rust
// 片段：省略了 fn main 与 use 导入（完整可运行版见 examples/ex02-raw-pointers.rs）
let mut x = 42i32;
let p: *mut i32 = &mut x;            // &mut T as *mut T：可写裸指针（创建是安全操作）
let r: *const i32 = &x;              // &T as *const T：只读裸指针
let n: *const i32 = ptr::null();     // 空指针
assert!(n.is_null() && !p.is_null());
unsafe {
    *p += 1;                         // 解引用写
    assert_eq!(*r, 43);              // 解引用读
    let u: *const u8 = r as *const u8; // as 类型转换（位不变，解释方式变）
    let _b = *u;                     // 按字节视角读取
    let a = ptr::addr_of!(x);        // 不经过引用的取址（addr_of_mut! 同理）
    a.read();                        // 显式读取（read/write 家族）
    p.write(99);                     // 显式写入
}
// 指针运算 add / offset / offset_from：步长按元素大小（+1 个 T，不是 +1 字节），
// 合法性（不越界、同一分配）由开发者保证——完整演示见 ex02 第 5 步
```

**指针运算与边界**：`add`/`offset`/`offset_from` 的合法性（不越界、同一分配、不悬垂）全部由开发者保证——越界 `offset`、解引用悬垂指针、跨分配 `offset_from` 都是 UB（实测见示例 3）；跨分配的关系比较（`<`/`>` 等）结果未指定（unspecified，非 UB）。`addr_of!`/`addr_of_mut!` 是取址的「安全版姿势」：`&x as *const _` 会先创建一个引用（虽然瞬时），`addr_of!` 完全不经过引用，是处理「尚未初始化内存」等场景的标准工具。

> 本阶段用裸指针做指针级编程的入门；**`Box::into_raw`/`from_raw` 的所有权交接属于 ph10 智能指针阶段**，这里只需理解「裸指针无所有权、无自动释放」的语义基础。

### 3.3 unsafe fn 与安全契约

`unsafe fn` 把「调用方必须满足前置条件」写进类型系统：**安全代码不能直接调用 unsafe fn（实测 E0133：`call to unsafe function` is unsafe and requires unsafe function or block，见示例 4 的 demo_e0133），必须用 unsafe 块，且调用方要为被调函数的契约负责**。

```rust
// 契约由文档承担：调用方先读 # Safety，再决定是否在 unsafe 块里调用
/// # Safety
/// - `idx` 必须小于 `slice.len()`
/// - 调用方必须保证 `slice` 在调用期间有效
unsafe fn get_unchecked(slice: &[u8], idx: usize) -> u8 {
    unsafe { *slice.get_unchecked(idx) } // 内部无需再检查——契约已保证
}
```

**不变量由开发者维护**（必会概念）：`unsafe fn` 的 `# Safety` 契约、unsafe 块的 SAFETY 注释、结构体的内部不变量（如 `len ≤ cap`）——这些都是「开发者声明并维护的事实」。编译器相信这些声明，所以**契约错了 = UB**，不会有报错提醒。因此规范要求：每个 unsafe 块/函数必须写 `// SAFETY:` 注释说明「凭什么这里合法」，这是 unsafe 代码可审查性的底线。完整的契约写作与边界测试见练习 2（`sol-02-unsafe-fn-contract.rs`）。

### 3.4 未定义行为（UB）

**未定义行为（undefined behavior，UB）**：程序的行为完全不受 Rust 语言规范约束——编译器可以假设「UB 不会发生」并据此优化，所以 UB 可能表现为：立刻崩溃、静默产生错误值、安全代码被破坏（包括与本阶段无关的其它代码）、或「看起来一切正常」。Rust 的 UB 清单（部分，与 C/C++ 重叠）：解引用悬垂/空指针、越界访问（含 `get_unchecked` 违规）、创建重叠的可变引用（别名违规）、读未初始化内存、`offset` 越界、移位量 ≥ 位宽、`transmute` 产生无效值（如非法 bool/引用）等。**区别于 C/C++ 的常见陷阱**：整数溢出在 Rust 中**不是 UB**（debug 下溢出检查 panic、release 下回绕 wrap，均为 defined behavior）；类型不兼容的 `transmute` 是编译错误而非 UB。

> ⚠️ **UB 是「无诊断要求」的**：编译器不需要警告你。`unsafe` 的合法性与 UB 之间的边界由开发者维护——写错契约不会有 lint 提醒，这正是 unsafe 代码需要测试工具（Miri、sanitizer）的原因。

UB 的破坏性来自优化器假设（见第 4 章）。实测演示（示例 3，`ex03-ub-demo.rs`，首行注释写明运行前提）：

- **读部分未初始化的内存**：`MaybeUninit::<i32>` 只写 1 字节就 `assume_init()`（UB）——debug 形态（无优化）高 3 字节是栈垃圾（实测每次运行不同，如 `0x6FB918AA`）；release 形态（O3）高 3 字节被优化器折叠成 `0x000000AA`（恒定）——**同一源码，两种行为**。
- **移位溢出**：`1u32 << 33`（运行时值，UB）——带溢出检查的 debug 形态直接 panic（实测退出码 101，`attempt to shift left with overflow`）；release 形态静默输出 `2`（处理器硬件对移位量取模 32）。
- **对照**：Vec 扩容后解引用旧指针（悬垂）——本机两种形态都输出 `2`，**未观察到差异**。UB 不保证出现可见差异，这正是它的危险：代码可能长期「看似正常」。

### 3.5 FFI 调用基础

FFI（Foreign Function Interface，外部函数接口）调用基础 = **用 `extern "C"` 声明外部函数，在 unsafe 块里调用**。C 的函数就是「裸指针 + 约定」：Rust 侧把 C 的 ABI（Application Binary Interface，二进制接口）声明出来，参数与返回值按 C ABI 传递。

```rust
// 片段：省略了 fn main 与 use 导入（完整可运行版见 examples/ex05-ffi-libc.rs）
// extern "C" 块：声明 C ABI 的外部函数（2021 edition 下 unsafe 前缀可省略；2024 必须写 unsafe extern）
extern "C" {
    fn strlen(s: *const c_char) -> usize;
    fn malloc(size: usize) -> *mut c_void;
    fn free(ptr: *mut c_void);
}
let s = CString::new("hello").unwrap(); // CString：以 \0 结尾、可跨边界不截断
let len = unsafe { strlen(s.as_ptr()) };
let p = unsafe { malloc(16) };
unsafe { free(p); } // 谁分配谁释放——不变量由开发者维护
```

两类实测（示例 5/6）：

| FFI 目标 | 做法 | 实测结果（rustc 1.92.0 + Apple clang 21.0.0） |
|---------|------|----------------------------------------------|
| libc 函数（strlen/malloc/free/abs） | `extern "C"` 声明后直接调用（macOS/Linux 上 rustc 默认链接 libSystem/libc） | `strlen("hello")=5`、`abs(-42)=42`、malloc 写入读回 `0xAB` |
| 自建 C 库（mystrlib.c） | `cc -shared -fPIC -o /tmp/libmystrlib.dylib` → `rustc -L /tmp -l dylib=mystrlib ... -C link-args="-Wl,-rpath,/tmp"` | `add_i32(3,4)=7`、`mul_u64(6,7)=42`、`point_len((3,4))=5`、`greet()="hello from C"`（结构体按值传参用 `#[repr(C)]`） |

关键认知：**C 函数不报告错误**——`strlen` 假定字符串合法、`malloc` 失败返回空指针（要自己 `is_null()` 检查）、错误码走 errno 约定——这与 Rust 的 `Result` 体系完全不同（错误处理工程化见 ph11 错误处理与工程质量阶段）。字符串跨边界用 `CString`（Rust → C，拥有 `\0`）与 `CStr`（C → Rust，借用不复制，见 ex06 的 `greet()`）。

> 本阶段只做 FFI **调用**基础（调 libc / 调自建 C 库）；**Rust 导出给 C（`#[no_mangle]`/cdylib）、bindgen/cbindgen 自动生成绑定、pyo3 给 Python 用，以及「谁分配谁释放」的完整所有权约定属于 ph23 Rust FFI 与跨语言接口设计阶段（目录待建）**，这里只需掌握「声明 + 调用 + 手写 C 库联调」的最小闭环。

### 3.6 安全抽象封装

安全抽象封装 = **把 unsafe 关进笼子**：对外是纯安全 API（调用方零 unsafe），内部用 unsafe 操作原始内存，**不变量由实现者维护并在每处 unsafe 写 SAFETY 注释**。这是 roadmap 必会概念「最小 unsafe 边界」的工程落地，也是标准库的常态（`Vec`/`String`/`HashMap` 内部全是 unsafe，对外全是安全 API）。

```rust
// 片段：结构体与 impl 片段，省略 fn main；grow() 扩容（倍增 + realloc）也省略
// 完整可运行版见 exercises/sol-03-mini-vec.rs
struct MiniVec { ptr: NonNull<i32>, len: usize, cap: usize } // 不变量：len ≤ cap；ptr 按 cap 分配
impl MiniVec {
    fn push(&mut self, v: i32) {
        if self.len == self.cap { self.grow(); } // 扩容在 unsafe 内维护不变量
        unsafe { self.ptr.as_ptr().add(self.len).write(v) }; // SAFETY: len < cap 已保证
        self.len += 1;
    }
    fn get(&self, idx: usize) -> Option<i32> {
        if idx >= self.len { return None; } // 边界检查放在安全侧
        Some(unsafe { self.ptr.as_ptr().add(idx).read() })
    }
}
impl Drop for MiniVec { /* dealloc——谁分配谁释放，忘写就是泄漏 */ }
```

封装的三条纪律：① **不变量在安全 API 边界内维持**（`push` 先 `grow` 再写，`get` 先检查再读）；② **unsafe 只做「已知合法」的最后一击**（边界检查后的一次解引用）；③ **Drop 补全释放**（RAII，承接 ph13「资源释放由 Drop 管理」）。完整实现见练习 3（`sol-03-mini-vec.rs`）与综合项目（受控缓冲区封装 SafeBuffer）。

## 4. 底层原理

**为什么 unsafe 不关闭借用检查？** 因为借用检查发生在类型与语法层，而 unsafe 只修改「操作合法性」清单——借用规则（一个可变借用或任意多个不可变借用、借用不越过生命周期）是独立于 unsafe 的约束系统，`unsafe` 没有触碰它的开关。可以这样理解分层：

```text
安全 Rust（Safe Rust）────────────── 借用检查 / 所有权 / 生命周期 全程生效
        │
        │  只有五类操作需要 unsafe 前缀（3.1 表格）
        ▼
unsafe 上下文（块 / fn / trait / impl）── 借用检查照常生效，只是允许了这五类操作
        │
        │  合法性声明：不变量由开发者维护
        ▼
内存操作（解引用 / 分配 / FFI）──────── 若声明错误 → 未定义行为（UB）
```

**为什么 UB 危险？** 编译器（LLVM）假定「程序没有 UB」并据此优化：它可以重排内存读写、把读未初始化内存的字节折叠成任意值（示例 3 实测：O3 把 poison 字节折叠成 0）、消除「不可能」的分支。一旦真实程序踩中 UB，这些优化结果就不再保证与「直观语义」一致——**UB 的影响范围是整个程序，不只是那一行 unsafe**。因此 Rust 社区的检查工具链是：Miri（解释执行，抓 UB 的黄金标准，nightly 可用）→ sanitizer（nightly `-Zsanitizer`）→ 代码审查（`SAFETY` 注释）。Stacked Borrows / Tree Borrows 则是学术侧给「什么别名合法」的形式化模型——本阶段只需知道「存在一个模型定义别名规则」，深入属高级专题。

**为什么 unsafe 是必要之恶？** 与 C/C++ 不同，Rust 不把「手动内存操作」交给每个程序员，而是收拢到显式声明的边界：C 的程序员在每一行都要防 UB，Rust 只在 unsafe 边界内防。代价是 unsafe 代码的审查负担集中，收益是安全代码的 95% 以上可以完全信任编译器。

## 5. 使用场景

- **FFI：调 C 库 / 系统库**——本阶段的最小闭环（示例 5/6）；真实工程里大多数系统调用、C 生态库（如 sqlite、zlib）都走这条路，自动化绑定工具属 ph23。
- **实现安全抽象的高性能内核**——`Vec`/`String` 内部、零拷贝解析（`from_raw_parts`）、缓存/缓冲池：把「边界检查」从热路径移除（`get_unchecked`）通常是安全抽象内部最后的性能手段——**先测出瓶颈再用**，性能方法论属 ph22 性能优化与 Profiling 阶段。
- **并发与无锁原语**——`unsafe impl Send/Sync` 是让自定义类型跨线程的唯一逃逸口（ph12 并发与异步阶段提过它的存在，本阶段讲清证明责任）。
- **什么时候不用 unsafe**：能靠所有权/借用/索引解决就绝不用——「用 unsafe 绕过编译错误」是反模式（roadmap 阶段验收明令「能避免用 unsafe 绕过普通编译错误」）；能用 `Rc`/`Arc`/`RefCell`/索引就不用裸指针（ph10 智能指针阶段的结论在这里闭环）。
- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C 的全部内存操作都「裸奔」（每行都要防 UB）；C++ 的 UB 清单更宽、`reinterpret_cast` 到处可及，靠纪律约束；Rust 把不安全收拢到显式 `unsafe` 边界、用类型系统承担其余——三种语言对「谁为内存安全负责」给出了三种答案：程序员 / 程序员+规范 / 编译器+显式例外。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件在 `examples/` 目录（除 ex03 外全部 `rustc --edition 2021 -D warnings` 单文件编译、产物输出 `/tmp/`，验证环境 rustc 1.92.0 macOS arm64）：

### 示例 1：unsafe 关键字（ex01-unsafe-keyword.rs）

```rust
// examples/ex01-unsafe-keyword.rs —— unsafe 关键字：unsafe 块 / unsafe fn / 五类 unsafe 操作
// 编译：rustc --edition 2021 -D warnings ex01-unsafe-keyword.rs -o /tmp/ex01
let mut x = 42;
let p: *mut i32 = &mut x;
unsafe {
    *p += 1; // 解引用裸指针：unsafe 操作 #1
}
println!("1. 裸指针解引用（unsafe 块内）: x = {x}");
```

实测输出：`1. 裸指针解引用（unsafe 块内）: x = 43`、`2. 调用 unsafe fn: double(21) = 42`、`3. 调用 extern fn: strlen("hello") = 5`、`4. union 字段访问: f32 3.5 的位模式按 i32 读 = 1080033280`（平台相关）、`5. unsafe fn 内调用 unsafe fn: inner() = 10`。

### 示例 2：裸指针（ex02-raw-pointers.rs）

```rust
// examples/ex02-raw-pointers.rs —— 裸指针：创建 / 判空 / 解引用 / 转换 / 运算 / 读写
// 编译：rustc --edition 2021 -D warnings ex02-raw-pointers.rs -o /tmp/ex02
let mut x = 42i32;
let p: *mut i32 = &mut x; // &mut T as *mut T：可写裸指针
let r: *const i32 = &x; // &T as *const T：只读裸指针
unsafe {
    *p += 1;
    assert_eq!(*r, 43);
}
```

实测输出：7 段断言全部通过（`x 首字节 = 0x2B`、`diff = 3` 等，完整见文件内注释）。

### 示例 3：未定义行为（UB）行为差异（ex03-ub-demo.rs）

> ⚠️ **运行前提**：本示例包含 UB，仅在了解后果的前提下运行，不要复制进真实代码。需分别编译 debug 形态（`-C overflow-checks=on`）与 release 形态（`-C opt-level=3`）对比输出（完整命令见 examples/README）。

```rust
// examples/ex03-ub-demo.rs —— 未定义行为（UB）演示：同一源码在不同编译选项下行为不同
// 编译（debug 形态）：rustc --edition 2021 -C overflow-checks=on ex03-ub-demo.rs -o /tmp/ex03-dbg
// 编译（release 形态）：rustc --edition 2021 -C opt-level=3 ex03-ub-demo.rs -o /tmp/ex03-rel
let mut m = MaybeUninit::<i32>::uninit();
let p = m.as_mut_ptr();
unsafe {
    std::ptr::write_bytes(p as *mut u8, 0xAA, 1); // 只初始化 1/4 字节
    let v = m.assume_init(); // UB：读未初始化字节（LLVM 中为 poison）
    println!("1. 部分初始化读 = {v:#010X}");
}
```

实测：debug 形态 `0x6FB918AA`（高 3 字节为栈垃圾，每次运行不同）、release 形态恒为 `0x000000AA`；移位溢出 demo：debug panic（退出码 101）vs release 输出 `shift = 33, 1 << 33 = 2`；悬垂指针对照：两种形态均输出 `2`，未观察到差异（UB 不保证出现可见差异）。

### 示例 4：unsafe 不关闭借用检查（ex04-borrow-check-still-on.rs）

> ⚠️ **运行前提**：本示例故意编译失败，用于实测「借用检查在 unsafe 内依然生效」，请勿期待编译成功。

```rust
// examples/ex04-borrow-check-still-on.rs —— 「unsafe 不关闭借用检查」演示（故意编译失败）
// 编译（预期失败）：rustc --edition 2021 -D warnings ex04-borrow-check-still-on.rs -o /tmp/ex04
fn demo_e0594() {
    let x = 42;
    let p: *const i32 = &x; // 裸指针创建是安全操作
    let r: &i32 = &x; // 共享引用
    unsafe {
        let _ = *p; // 真实 unsafe 操作：解引用裸指针（让 unsafe 块"名副其实"）
        *r += 1; // 实测错误：error[E0594]: cannot assign to `*r`, which is behind a `&` reference
    }
}
```

实测错误码：E0594（不能通过 `&` 引用修改）、E0502（不可变借用存活期间的可变借用）、E0506（借用期间赋值）——全部在 unsafe 上下文内照常拦截；另含 E0133（安全代码直接调用 unsafe fn，缺少 unsafe 上下文）——完整错误文本与四个 demo 见 examples/README 与 `ex04` 文件。

### 示例 5：FFI 调用 libc（ex05-ffi-libc.rs）

```rust
// examples/ex05-ffi-libc.rs —— FFI 调用基础 ①：用 extern "C" 声明并调用 libc 函数
// 编译：rustc --edition 2021 -D warnings ex05-ffi-libc.rs -o /tmp/ex05
extern "C" {
    fn strlen(s: *const c_char) -> usize;
    fn malloc(size: usize) -> *mut c_void;
    fn free(ptr: *mut c_void);
    fn abs(i: c_int) -> c_int;
}
let s = CString::new("hello").unwrap(); // 内部含 '\0'，跨 FFI 边界不会截断
let len = unsafe { strlen(s.as_ptr()) };
println!("1. strlen(\"hello\") = {len}");
```

实测输出：`strlen("hello") = 5`、`malloc(16) 后首字节 = 0xAB`、`abs(-42) = 42`。

### 示例 6：FFI 调用自建 C 库（ex06-ffi-c-library.rs + mystrlib.c）

> 运行前提：先按 examples/README「示例 6 完整构建步骤」用 `cc -Wall -Wextra` 编译 `mystrlib.c` 为 `/tmp/libmystrlib.dylib`，再 `rustc -L /tmp -l dylib=mystrlib ... -C link-args="-Wl,-rpath,/tmp"` 链接（rpath 让运行无需设置 DYLD_LIBRARY_PATH）。

```rust
// examples/ex06-ffi-c-library.rs —— FFI 调用基础 ②：调用自建 C 库（cc 编译 .dylib + rustc 链接）
// 构建：cc -Wall -Wextra -shared -fPIC -O2 -o /tmp/libmystrlib.dylib mystrlib.c && \
//       rustc --edition 2021 -D warnings -L /tmp -l dylib=mystrlib ex06-ffi-c-library.rs -o /tmp/ex06 -C link-args="-Wl,-rpath,/tmp"
#[link(name = "mystrlib")]
extern "C" {
    fn add_i32(a: i32, b: i32) -> i32;
    fn point_len(p: Point2D) -> f64;
    fn greet() -> *const c_char;
}
#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct Point2D {
    x: f64,
    y: f64,
}
let s = unsafe { add_i32(3, 4) };
println!("1. add_i32(3, 4) = {s}");
let g = unsafe { CStr::from_ptr(greet()) };
println!("4. greet() = {:?}", g.to_str().unwrap());
```

实测输出：`add_i32(3, 4) = 7`、`mul_u64(6, 7) = 42`、`point_len(Point2D{3.0, 4.0}) = 5`、`greet() = "hello from C"`。

## 7. 总结

### 关键要点

- **unsafe 不是「关闭检查」**：它只精确开放五类操作（裸指针解引用/调用 unsafe fn/调用 extern 函数/union 字段访问/unsafe impl Send/Sync），**借用检查与所有权规则在 unsafe 内照常生效**（实测 E0594/E0502/E0506）
- **不变量由开发者维护**：`# Safety` 契约 + `SAFETY` 注释是 unsafe 代码的身份证——契约错了就是 UB，编译器不提醒
- **UB 是「编译器可以假设不发生的」行为**：同一源码在 debug/release 下行为可以不同（实测：poison 折叠 `0x6FB918AA → 0x000000AA`、移位溢出 panic vs 静默出值 2）；UB 不保证立刻爆炸，这正是危险
- **最小 unsafe 边界**：unsafe 块越小越好；安全抽象封装 = 安全 API + unsafe 内部 + 不变量维护 + Drop 补全释放（MiniVec / SafeBuffer）
- **FFI 调用基础**：`extern "C"` 声明 + unsafe 调用 + `CString`/`CStr`；调 libc 与调自建 C 库（cc 编译 .dylib + rustc 链接 + rpath）全部实测；C 函数不报告错误，错误约定由 C 库文档定义
- **谁分配谁释放**：`malloc` 必须 `free`、`MiniVec` 必须 `dealloc`——RAII 的 Drop 是 Rust 侧的标准答案（承接 ph13）

### 阶段验收清单

- [ ] 能说明每个 unsafe 块的必要性和不变量（「为什么这里必须 unsafe」「凭什么合法」）
- [ ] 能避免用 unsafe 绕过普通编译错误（借用错误在 unsafe 内依然报错——实测 E0594/E0502/E0506）
- [ ] 能识别 UB 风险（悬垂/越界/别名违规/未初始化/移位溢出）并知道用 Miri/sanitizer 检查
- [ ] 能用 `extern "C"` 调 libc 与自建 C 库并处理 C 字符串与「谁分配谁释放」
- [ ] 能把 unsafe 封装进对外零 unsafe 的安全抽象（不变量 + SAFETY 注释 + Drop）

### 跨语言对比

- C 的所有内存操作都裸奔、每行都要防 UB；C++ 用 RAII 与智能指针收缩、但 `reinterpret_cast` 与宽 UB 清单仍靠纪律；Rust 把不安全收拢到显式 `unsafe` 边界、类型系统承担其余——三种「内存安全责任模型」的对比是 analysis/ 的素材（详见第 5 章）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题（裸指针安全函数 / unsafe fn 契约与边界测试 / 最小安全抽象 MiniVec / FFI 调 libc）后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**受控缓冲区封装（SafeBuffer）**——提供安全 API、内部用少量 unsafe 操作切片的可增长字节缓冲区，带内置内存泄漏自检（roadmap 推荐项目；`demo` 断言与泄漏归零、`--stress 1000000` 压力路径均已实测）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md) — `unsafe` 与宏是 Rust 两大「高级逃逸口」：unsafe 在运行时层面逃逸安全检查，宏在编译期生成代码。本阶段建立的「边界必须显式、契约必须论证」的心智，正好用来理解宏的维护成本（宏展开后代码依然要过借用检查）。在此之前可先按推荐学习顺序巩固 ph13~ph14 的练习与项目。
