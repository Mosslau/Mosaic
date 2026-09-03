# Rust 内存布局、零拷贝与协议解析阶段

> 面向「把字节当一等公民」的方向：本阶段把布局、对齐、字节序这三块「内存如何摆位」的知识拼起来，学会用切片 `&[u8]` 借用网络与磁盘缓冲而不复制成 `Vec`，再落到协议解析的手艺上——从 length-prefix framing、WAL record、SSTable block header 一类真实格式中读出「安全 + 零拷贝」两不误的解析器。

## 1. 概述

本阶段对应 roadmap 第 19 节，目标是**理解数据布局与字节处理，能写出高效、安全的协议解析器**。它是二进制数据基础设施学习线的「工艺课」：ph18 把借用修到了「看错误码知道怎么改」，本阶段就兑现 ph18 主文档末尾的预告——**修好的「借用」正是零拷贝的地基**：当你用 `&[u8]` 直接借用网络缓冲、而不复制成 `Vec` 时，就是在让编译期的借用检查替每一次解析省下一次分配。上一阶段（[18-borrow-checker-debug.md](../ph18-borrow-checker-debug/18-borrow-checker-debug.md)）教的是「怎么让借用代码通过检查」，本阶段教的是「为什么值得让代码通过检查」。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 布局控制 | repr(Rust) / repr(C) / repr(packed) / repr(transparent)、repr(align)，为什么要控制布局、各 repr 的代价（3.1） |
| 对齐与 padding | 对齐规则、结构体内部的「洞」、`size_of`/`align_of`/`offset_of!`、字段重排（3.2/4.1） |
| 字节序 | 大端/小端/本机序、`from_be_bytes`/`to_be_bytes`、网络序读写、纯 std 读取器 BeReader（3.3） |
| slice 与 buffer | `&[u8]` 借用、`split`/`chunks_exact`、函数返回借用切片、指针算术证明零拷贝（3.4/4.2） |
| bytes crate | `Bytes`/`BytesMut` 引用计数共享缓冲、`freeze`、`Buf` trait 流式解码（3.5） |
| 组合子解析器 | nom 8 / winnow 的声明式解析、小解析器串成大树、错误与剩余输入（3.6/4.4） |
| 协议安全纪律 | 不可信字节不能直接转结构体引用——对齐/别名/未初始化三大红线；长度前缀与「先校验再信长度」（3.7） |
| 真实格式解析 | length-prefix frame、WAL record（magic+CRC+seq+op+key/value）、SSTable block header（3.8） |
| 底层原理 | 布局引擎重排、胖指针内存表示、memcpy vs 借用、缓存行点到即止（4） |
| 场景与练习 | 何时零拷贝 / 何时 copy 更简单；与 C 的裸指针解析对比；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及 **Rust 进程内的内存布局、字节序与二进制格式解析手艺**，**不涉及系统级性能优化**（缓存行、分配次数在本阶段只到「点到即止」的直觉层面，真实剖析与基准属 ph22 性能优化与 Profiling 阶段，roadmap 第 22 节，目录待建）、**跨语言 ABI**（把结构体导出给 C/Python、布局承诺跨语言生效，属 ph23 Rust FFI 与跨语言接口设计阶段，roadmap 第 23 节，目录待建）、**依赖与供应链安全**（bytes/nom 的选型、审计与锁版本策略属 ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建）、**存储引擎全貌**（本阶段只解析 WAL record / SSTable block header 的字节格式，append/replay、MemTable、compaction 等引擎机制属 ph25 Rust 数据基础设施专项阶段，roadmap 第 25 节，目录待建）。

同时与两条相邻知识点划清边界：**unsafe 的字节→结构体转换**（`transmute`、裸指针 cast 的对齐/别名/未初始化**形式语义**、Miri/Stacked Borrows 验证）属于 ph14 Unsafe Rust 与安全抽象阶段——本阶段 3.7 只站在安全码一侧解释「为什么编译器拦着你」，不在本阶段手写这类 unsafe；**crate 的选型方法论**（该不该引入 bytes/nom、怎么评审）属于 ph17 Crate 生态选择与常用库阶段，本阶段直接使用并给出锁定版本。

## 2. 来源与演变

Rust 的内存布局观与 C 一脉相承但多了一道纪律：**默认布局是可变的（由编译器优化），想与外部世界对齐时用 repr 家族显式声明**。这与「零开销抽象」（zero-cost abstractions，C++ 之父 Bjarne Stroustrup 提出的口号，Rust 将其贯彻为「你为不需要的抽象不付任何运行时成本」）直接相关——布局控制、借用切片、组合子解析器在 release 构建里都不引入额外运行时负担，语言替你付掉的只是编译期的类型检查。零拷贝理念在 Rust 里不是「避免复制」的号召，而是**所有权 + 借用让「共享一段内存而不复制」第一次成为编译器可证明安全的操作**：GC 语言里共享靠追踪回收、C 里共享靠程序员自律，Rust 里共享靠「只读借用随便开、可变借用唯一」的编译期规则——ph18 修的就是这条规则被违反时的报告。**设计哲学一句话加粗：零拷贝不是一门手艺，而是所有权系统的直接推论；布局不是字节排布，而是「对内存的声明」。**

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 0.x → 1.0 | 2010~2015 | 布局自由度写入语言设计：默认 repr(Rust) 允许重排，repr(C)/repr(packed) 供 FFI 与外部格式使用；借用/切片类型成为一等公民 |
| repr(transparent) 稳定 | 2018（Rust 1.28） | 单字段 newtype 可与内层类型 ABI 同布局，跨 FFI 的「类型更严、内存不变」惯用法落地 |
| bytes crate 起步 | 2015 起（0.1 于 2015 年初，1.0 于 2020 年底） | Carl Lerche 为 tokio 生态打造共享字节缓冲；`Bytes`/`BytesMut` 让「引用计数切片」成为网络栈标配（docs.rs/crates.io 记录） |
| nom 组合子解析器 | 2015 起（8.0 于 2025-01） | Geal 发起：用函数组合代替手写状态机解析二进制/文本；8.0 是破坏性大版本（`tag` 参数从数组引用改为切片等） |
| winnow 继任项目 | 约 2023 起 | 同为 nom 作者启动，定位是 nom 的后继（toml_edit 等已采用），编译更快、API 收敛；本阶段按「nom 家族同一心智」介绍 |
| `offset_of!` 稳定 | 2024（Rust 1.77） | 编译期查字段偏移进入标准库（此前只能靠 `memoffset` crate），repr(C) 布局自检变得零依赖 |
| Edition 2021 生态基线 | 2021 起 | 仓库全部代码层统一 edition 2021（ph16 已述）；布局/字节序语法与 edition 无关，是最稳定的部分 |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0（macOS arm64，rustup 管理）；bytes 1.12.1、nom 8.0.0 |

**解析器生态的一条主线值得单独拎出来**：nom 把「解析」做成函数组合之后，Rust 生态里的声明式解析大体分成两个阵营——nom 家族（含后继 winnow）与手写游标（3.3 的 BeReader 是它的最小形态）。nom 模块按 `bytes::complete` / `bytes::streaming` 双份组织（4.4 实测同一 `take` 在两种模块下对「输入不足」给出不同语义），winnow 与 nom 同作者、目标是继任者（toml_edit 等一线库已采用）。学习时**以锁定版本为准**即可：组合子的核心心智在两个库间通用，具体 API 看 docs.rs。

**历史上还有一个值得记住的「零拷贝先例」**：Rust 之前，任何想「共享大块内存又不复制」的系统语言都要么依赖 GC 的写屏障、要么靠调用方自律（C 的共享缓冲 + 手动生命周期）。Rust 是第一个把「N 个只读视图 + 0 个可变视图（或 1 个可变 + 0 只读）」写成**编译期规则**的语言——所以零拷贝解析在 Rust 里不是高风险技巧而是默认姿势，这也是 KV 存储、消息队列、网络框架普遍选 Rust 写解析层的原因之一。

历史教训值得一提：**默认布局不承诺、也别赌**。早期 Rust 的默认布局就允许重排，编译器也确实在演进（当前 rustc 倾向于把大对齐字段前置来消除洞），但语言从未把具体排布写进规范——这正是协议/磁盘/FFI 场景必须 `repr(C)` 的根本原因。同理，`nom 7 → nom 8` 的破坏性变更提醒我们：组合子 API 会随大版本漂移（本阶段 ex07 就是按 8.0 实测适配的写法），而「先校验长度、try_into 定长数组、切借用的子切片」这套手艺在任何版本都成立。

本文示例以 **rustc 1.92.0 / edition 2021** 为基线（edition 2021 自 Rust 1.56 起是生态事实默认，与 ph10~ph18 全仓库代码层一致——单文件示例统一 `--edition 2021`；`offset_of!` 需 1.77+，本基线 1.92.0 可用），验证工具链 **rustc/cargo 1.92.0（macOS arm64，rustup 管理）**，第三方依赖 **bytes 1.12.1 / nom 8.0.0**（版本已在 examples/crates/Cargo.lock 锁定）。这个阶段的语法是 Rust 最稳定的部分：整数宽度、`to_be_bytes`/`from_be_bytes` 语义自 1.0 起未变，repr 家族的语义也基本冻结；会漂的只有默认布局的具体策略（语言不承诺，不用于外部格式）与 nom/winnow 的 API（锁版本并参考实测）。**代码验证状态**：ex01~ex05 纯 std 单文件已在 rustc 1.92.0 本机实测编译运行通过；ex06/ex07 已在 cargo 1.92.0 本机实测（bytes 1.12.1 / nom 8.0.0，ex07 含 4 条单元测试，crates 工程 `clippy -D warnings` 与 `cargo fmt --check` 全绿），全部标注「已验证」。

## 3. 语法与参数

本章按「布局 → 读数 → 切片 → 解析器 → 安全纪律 → 实战」推进：3.1~3.2 解决「字节怎么摆」（repr 与对齐），3.3 解决「多位字节按什么顺序读」（字节序），3.4~3.6 给出三类解析工具（纯 std 切片 / bytes 共享缓冲 / nom 组合子），3.7 立安全纪律，3.8 把前面全串到 WAL record 与 SSTable header 上。章节代码的可运行完整版见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)。

### 3.1 repr 家族与布局控制

Rust 结构体的默认布局（repr(Rust)）**允许编译器自由重排字段**，目的是消除 padding、减小体积；代价是**内存表示不对任何人承诺**。当你需要「内存里怎么排」与外部世界对齐时——写磁盘、上网络、跨 FFI——就改用 repr 家族显式声明：

| 属性 | 布局承诺 | 典型用途 | 代价/风险 |
|------|---------|---------|----------|
| （默认）repr(Rust) | 无：编译器可重排、可插 padding | 纯内存业务结构体 | 不能用于跨边界格式；`size_of` 可能随编译器版本变化 |
| `#[repr(C)]` | 按字段声明顺序排布、与 C ABI 一致 | FFI、与磁盘/网络格式一一对应 | 声明顺序差时出现 padding「洞」，体积变大 |
| `#[repr(C, packed)]` / `#[repr(packed)]` | 对齐压到 1，字段紧挨、零 padding | 压缩存储、老格式 | **未对齐**：取字段引用是编译错误 E0793；跨 FFI 有未对齐访问 UB 风险 |
| `#[repr(transparent)]` | 与唯一非 ZST 字段完全相同 | newtype 包装不改变 ABI | 只能有一个非零大小字段 |
| `#[repr(align(N))]` | 提升整体对齐到 N 的倍数 | 缓存行对齐（CachePadded 惯用法） | 体积变大（尾部 padding 更多） |

同一组字段 `{ u8 tag, u64 stamp, u8 kind }` 在三种 repr 下实测（rustc 1.92.0，已验证，`examples/ex01-repr-layout.rs`）：

```rust
// examples/ex01-repr-layout.rs —— repr 家族实测（已验证：rustc 1.92.0）
println!("rust    : size = {:>2}, align = {}", size_of::<RustLayout>(), align_of::<RustLayout>());
println!("repr(C) : size = {:>2}, align = {}", size_of::<CLayout>(), align_of::<CLayout>());
println!("packed  : size = {:>2}, align = {}", size_of::<PackedLayout>(), align_of::<PackedLayout>());
// 实测输出：rust 16/align 8；repr(C) 24/align 8；packed 10/align 1
```

三种排布各说明了什么：**repr(Rust) 把两个 1B 字段并排塞进头部、给 8B 字段让出对齐起点，只留对齐收尾 → 16B 无洞**；**repr(C) 严格按声明顺序 → tag 后 7B 洞、kind 后 7B 尾洞 → 24B**；**packed 取消对齐 → 1+8+1=10B**，但每个非 1 对齐字段都可能「骑跨」在地址上。协议结构体的 C 布局示意（repr(C)，字段偏移实测 0/8/16）：

```text
#[repr(C)] struct CLayout { tag: u8, stamp: u64, kind: u8 }
┌────┬──────────────────────┬──────────────┬──────┬──────────────────────┐
│tag │   padding（7 字节洞） │    stamp     │ kind │   padding（7 字节尾洞）│
└────┴──────────────────────┴──────────────┴──────┴──────────────────────┘
0    1                      8              16     17                    24 ← size = 24
```

**repr(transparent)** 常见于 newtype：`#[repr(transparent)] struct MonotonicId(u64)` 的 size/align 与裸 `u64` 完全一致（实测 8/8），跨 FFI 时既能换更严格的类型、又不改变内存表示。**repr(packed) 的红线**值得单独强调：packed 字段可能未对齐，编译器拒绝借用它——`println!("{}", p.stamp)` 会被 format 机制按 `&u64` 借用而报 **E0793** `reference to packed field is unaligned`，只能「按值拷出 Copy 字段」（编译器负责未对齐读的合法性，见 ex01 实测）。这条红线与 3.7 的三大红线同源：**别创建指向未对齐数据的引用**。

> 本阶段用 repr 家族回答「如何让字节与结构体对应」；**跨语言 ABI 稳定（extern "C" 导出、cbindgen 生成头文件）属于 ph23 Rust FFI 与跨语言接口设计阶段（roadmap 第 23 节，目录待建）**，这里只需理解「repr(C) + 固定宽度整数 = 可跨边界的结构体」，不必会写导出代码。

### 3.2 对齐 alignment 与 padding

**对齐**（alignment）是硬件的地址偏好：`u64` 喜欢落在 8 的倍数地址、`u32` 落在 4 的倍数。结构体的对齐 = 各字段对齐的最大值，**size 会向上取整到对齐的倍数**，取整留下的空隙就是 **padding（填充「洞」）**。Rust 保证对齐正确、零拷贝取字段也天然对齐——这正是 3.7 里「不要自己从字节构造结构体引用」的镜像：编译器保证不了从任意字节地址开始的引用合法。

`std::mem` 三件套（本基线 1.92.0，均稳定）：`size_of::<T>()` 看大小、`align_of::<T>()` 看对齐、`offset_of!(T, field)` 看字段偏移（Rust 1.77+ 标准库，此前用 memoffset crate）。实测（64 位目标，已验证）：

| 类型 | size | align | 备注 |
|------|-----:|------:|------|
| `u8` / `bool` | 1 | 1 | |
| `u16` | 2 | 2 | |
| `u32` / `char` / `f32` | 4 | 4 | |
| `u64` / `f64` / `usize` | 8 | 8 | usize 的 8 是「平台相关」，**这正是协议要用固定宽度类型的理由** |
| `&u8` / `&str` / `Box<T>`（瘦） | 8 | 8 | 单指针 |
| `&[u8]` / `&str` 胖指针 | 16 | 8 | ptr + len 两个词（4.2） |
| `Vec<u8>` / `String` | 24 | 8 | ptr + len + cap 三个词 |
| `[u8; 100]` | 100 | 1 | 数组 = 元素 × 数量 |
| `[(); 100]` / 无字段 struct | 0 | 1 | ZST：不占空间（ex01 实测） |

**为什么关心「洞」**：同样是 `{ u8, u64, u8 }`，repr(C) 24B 里只有 9B 是数据、15B 是洞；若一张表存一亿行，光 padding 就白费 15 亿字节。反过来，**别为了省洞乱用 packed**——packed 的未对齐读在部分架构上是性能灾难（3.2 点到为止，测量属 ph22 性能优化与 Profiling 阶段，roadmap 第 22 节，目录待建）。协议字段的黄金组合是 **repr(C) + 固定宽度整数 + 合理排列字段（大对齐在前）**，既零洞又能与字节流一一对应。练习如何手算偏移与洞：`size = round_up(最后字段末尾, align)`，中间每个字段从「大于等于上一字段末尾的最小对齐倍数」开始。

> 本阶段只讲「对齐/洞/重排」的布局机理；**把结构体数组按 SIMD/缓存行对齐做极致优化属于 ph22 性能优化与 Profiling 阶段（roadmap 第 22 节，目录待建）**，这里先建立「布局 = 大小 + 洞」的定量直觉。

### 3.3 字节序：大端、小端与 from_be_bytes/to_be_bytes

多位整数在内存/线上按什么顺序放字节，叫**字节序**。**大端**（big-endian，高字节在前）是 TCP/IP 的**网络字节序**、也是多数磁盘格式的选择；**小端**（little-endian，低字节在前）是 x86/ARM 的**本机序**；本机到底哪种用 `to_ne_bytes` 的语义表示「不跨机器时用」。`u16/u32/u64` 都配了 `from_be_bytes`/`to_be_bytes`/`from_le_bytes`/`to_le_bytes`（取 `[u8; N]` 数组），以及 `_ne_` 家族。

```rust
// examples/ex02-byteorder.rs —— 大小端实测（已验证：rustc 1.92.0，本机为小端）
let n: u32 = 0x1234_5678;
println!("{:02X?}", n.to_be_bytes()); // [12, 34, 56, 78] ← 网络序：高字节在前
println!("{:02X?}", n.to_le_bytes()); // [78, 56, 34, 12] ← 本机（小端）
println!("{:02X?}", n.to_ne_bytes()); // [78, 56, 34, 12] ← 本机字节序，别用于持久化/传输
```

读写字节流时的**核心难点是「从切片拿定长数组」**：`from_be_bytes` 要的是 `[u8; 2]`（按值），而手里是 `&[u8]`。唯一正道是 `get` + `try_into`——这正好是 roadmap 第 19 节示例代码：

```rust
fn read_u16_be(buf: &[u8]) -> Option<u16> {
    let bytes: [u8; 2] = buf.get(0..2)?.try_into().ok()?;
    Some(u16::from_be_bytes(bytes))
}
```

这两行的纪律价值大于技巧价值：`get(0..2)?` 做**长度检查**（不足返回 None 而非越界 panic），`try_into()` 完成 `&[u8]` → `[u8; 2]` 的**定长转换**（切片长度在编译期不可知，只有运行期转换）。把这几步封装成带游标的读取器（`BeReader`，ex02），解析多字段头部就不必每次都手动算下标。ex02 同时演示了错误传播闭环：BeReader 每个读返回 `Option`，组合函数用 `?` 汇聚成 `Result`，buffer 不足时报「截断」而非 panic——这套「先检查长度、后取字节」的模式是后面所有解析器的地基。

**协议里到底选大端还是小端？** 约定先行：线上报文因为 TCP/IP 的历史原因普遍用网络序（大端），本地文件格式则常跟着实现平台或生态走小端——LevelDB/RocksDB 家族的文件编码（WAL、SSTable 的定宽数字与 varint）就统一走小端。这也是本仓库 WAL record 字段选 LE 的用意：对齐主流存储引擎的编码习惯。选择本身没有对错，关键是**写进格式规范、解析严格按规范读**——最坏的局面是「有的字段 LE、有的字段 BE 却不注明」。真实协议里混合字节序并不罕见，这种逐字段显式读数（而非整块解释）的解析器天然免疫「我以为是 LE 其实是 BE」的整类 bug。

> ⚠️ 常见反模式：`(buf[0] as u16) << 8 | buf[1] as u16` 手工拼大端。能跑但容易错位、难读；`from_be_bytes` 一行的意图远比移位清晰，且编译器会把它优化成单条机器指令。**位移手工拼字节序只在教学「理解原理」时出现**，生产代码请用标准函数。

### 3.4 slice 与 buffer：零拷贝的语法基础

零拷贝解析的第一步动作极朴素：**持有缓冲用 `Vec<u8>`，借用/切分用 `&[u8]`，需要数据进函数/结构体用子切片而不是再分配一份**。`&owned[..]` 取借用零成本；`Vec`（24B：ptr+len+cap）与 `&[u8]`（16B：ptr+len，胖指针）共享同一块堆内存——ex03 用指针算术实测过：payload 子切片首地址 = 原包首地址 + 头部长度 5，**证明没有任何字节被复制**。

```rust
// examples/ex03-slice-zero-copy.rs —— 返回借用输入的子切片（已验证：rustc 1.92.0）
fn payload_of<'a>(buf: &'a [u8]) -> Option<&'a [u8]> {
    const HEADER: usize = 1 + 2 + 2; // flags(1B) + type(2B BE) + payload_len(2B BE)
    let whole = buf.get(..HEADER)?;
    let payload_len = u16::from_be_bytes(whole[3..5].try_into().ok()?) as usize;
    buf.get(HEADER..HEADER + payload_len) // 长度检查不足返回 None
}
```

注意这条函数的签名：`fn payload_of<'a>(buf: &'a [u8]) -> Option<&'a [u8]>`——**返回值的生命周期绑定到输入**。这正是 ph18 反复训练的「返回借用的前提是数据活得够久」：返回的是输入的内部区间，不是函数新造的数据（新造数据必须返回拥有值，E0515 的教训）。ph18 让你把借用修对，本阶段让你意识到**修对的借用 = 白捡的一次免复制**。

`&[u8]` 的切分工具集（全部 O(1)、零拷贝）：

| 方法 | 行为 | 协议解析的用途 |
|------|------|---------------|
| `buf.get(a..b)` | 边界检查的区间取（越界返回 None，**不 panic**） | 解析器唯一的取区间入口 |
| `split_at(n)` / `split_at_checked` | 切成前后两段 | 剥帧头/帧体 |
| `split` / `splitn` | 按分隔符/数量切 | 定界文本段（b'\n' 等） |
| `chunks_exact(n)` / `remainder()` | 等宽分块，**尾部长短不齐可检测** | 等宽记录扫描；`!remainder().is_empty()` ⇒ 数据损坏 |
| `windows(n)` | 滑窗迭代 | 校验滑窗等 |
| `iter()` | 逐字节/逐元素 | 遍历 |

**chunks_exact vs chunks 的差异是「坏尾」检测**：`chunks(3)` 静默给出 1~2 字节的短尾块，等宽记录解析里这往往意味着「尾部有残缺数据」；`chunks_exact` 把余数单独留在 `remainder()` 里，让解析器显式决定报错还是忽略——ex03 实测了两者的行为差异。切片之上还叠加了**借用检查的免费安全网**：想一边读子切片一边 `push` 原 Vec 会报 E0502（ph18 已练过），零拷贝不会退化成「悬垂视图」。

**「零拷贝」的精确表述是「读零拷贝、写要独占」**：`&[u8]` 给的是一堆只读视图，想原地改写字节（解密、转义、位翻转）必须持有 `&mut [u8]` 或拥有 `Vec<u8>`——借用规则保证「同一时刻最多一个可变视图」，改写永远不会与别人的读取并发。真实 I/O 管线因此常呈两段式：**fill 阶段**把网络/磁盘数据写进独占缓冲（此时它是 `&mut Vec`/`BytesMut`），**parse 阶段**把填充好的缓冲冻结为 `&[u8]` 并到处派发只读子切片。两阶段之间那道「独占变共享」的边界，就是 ph18 借用规则在协议解析里的日常形态。

> 本阶段只讲进程内缓冲的借用视图；**文件 mmap、网络 read_buf 直接落入缓冲的完整 I/O 管线属于 ph13 文件、网络与系统编程阶段与 ph25 Rust 数据基础设施专项阶段（roadmap 第 25 节，目录待建）的内容**，这里把 `&[u8]` 的手艺练熟，将来接真 I/O 时解析层代码一行不用改。

### 3.5 bytes crate：拥有型的零拷贝——引用计数共享缓冲

纯 `&[u8]` 有个生命周期天花板：视图只能借，**不能像拥有者一样被分到多个任务/缓冲里长期持有**。网络栈的答案是把「引用计数的共享字节缓冲」做成类型——这就是 **bytes crate 的 `Bytes`**（Carl Lerche 为 tokio 生态打造，1.0 于 2020-12 发布）。它的心智是「Arc + 切片」：

| bytes 类型/方法 | 行为 | 对应纯 std 的心智 |
|----------------|------|------------------|
| `Bytes` | 引用计数共享的不可变字节缓冲 | 能跨线程/跨任务持有的 `&[u8]` |
| `Bytes::clone()` | 引用计数 +1，**不复制字节** | ex06 实测 `a.as_ptr() == b.as_ptr()` |
| `bytes.slice(a..b)` / `split_to` / `split_off` | 在共享分配上切子视图 | `&buf[a..b]`，但随父持有分配存活 |
| `BytesMut` | 可增长的独占缓冲 | `Vec<u8>` 的网络友好版 |
| `bm.freeze()` | 独占 → 共享，**零拷贝** | — |
| `Buf::get_u32()` / `advance(n)` / `copy_to_bytes(n)` | 流式解码：读字段自动推进**头指针** | BeReader（3.3）的 crate 化版本 |

为什么需要它？ex04 的纯 std 流式解码器每吃完一帧要 `pending.drain(..consumed)` 把剩余字节**前移（memmove）**；而 bytes 的 `advance`/`get_u32` 只是移动「当前窗口头指针」——**整段解码零字节搬运**，且 `copy_to_bytes` 切出的是引用计数子视图，可以安全地送进另一个任务而底层分配不释放（ex06 实测双帧解析零搬运）：

```rust
// examples/crates/src/bin/ex06-bytes-crate.rs —— Buf trait 流式解码（已验证：cargo 1.92.0 / bytes 1.12.1）
while stream.len() >= 4 {
    let len = stream.get_u32() as usize;      // Buf::get_u32：大端读 4 字节并前进窗口
    if stream.len() < len { break; }          // 半帧等待
    let payload = stream.copy_to_bytes(len);  // 切出引用计数子视图，零搬运
    frames.push(payload);
}
```

bytes crate 是 **tokio 生态的网络缓冲事实标准**（hyper、tonic 等都在用），理解它的心智对后面读网络服务代码至关重要。代价是它是第三方依赖——引入前先过一遍 ph17 的评审纪律（本仓库锁 bytes 1.12.1）。一段值得记住的对照：`Vec` 的 `drain(..n)` 把余下字节**前移**（O(剩余) 的 memmove），bytes 的 `advance(n)`/`get_u32` 只是把窗口头指针**挪 n**——前者在「每帧几百字节、每秒几十万帧」的路径上是实打实的搬运量，后者是 O(1)。ex06 完整实测了这条差距（对照 ex04 的纯 std 版 compact）。

**bytes 在真实网络栈里的位置**：接收端不再是「`read` 进 Vec 再 `parse` 切切片」，而是把「可增长缓冲」直接交给 I/O 层填充，填完冻结成共享视图分发：

```rust
// 伪码示意：tokio 接收侧零拷贝链（I/O 细节属 ph12/ph13，这里只演示 bytes 的角色）
let mut buf = BytesMut::with_capacity(64 * 1024); // 独占可增长缓冲
// socket.read_buf(&mut buf).await?;              // 数据直接落进 BytesMut，无中间拷贝
let bytes: Bytes = buf.freeze();                  // 独占 → 共享，零拷贝
// bytes 可 clone 分发给解码任务、写盘任务，底层分配由引用计数决定何时释放
```

诚实提示一点：`Bytes::from(vec)`（把已有 `Vec` 变成 `Bytes`）并不保证零拷贝——容量富余时可能复制一次；**真正零拷贝的路径是数据从源头就落在 `BytesMut` 里（read_buf），或 `Bytes::from_static` 借用静态区**。写教学/示例代码时不依赖「Vec → Bytes 零拷贝」这一假设，才能保证换平台不翻车。

> 工具选择的分工（本阶段心智）：**单函数内借来借去 → `&[u8]` 就够**；**缓冲要跨函数边界长期持有、要按引用计数拆分送走 → `Bytes`**；**要边收边改（解码缓冲）→ `BytesMut`**。从 `&[u8]` 到 `Bytes` 不是升级，是按所有权需求换工具。

### 3.6 nom / winnow：组合子式的声明解析

手写解析器是「过程式」的：一个游标、一段循环、一串 if。**组合子解析器是「声明式」的**：每个小解析器是一个函数，`fn f(input: &[u8]) -> IResult<&[u8], T>`，成功返回 `Ok((剩余输入, 结果))`，失败返回 `Err`；`tag` 认固定字节、`take(n)` 切 n 字节、`be_u16`/`be_u32` 按大端读数——然后用函数调用把小的串成大的。nom（2015 年起，Geal 维护）是这条路线的代表；winnow（约 2023 起，同为 nom 作者启动的继任项目，toml_edit 已采用）是 nom 家族的后继。三选一的心智：

| 路线 | 本质 | 选它的理由 | 不选它的理由 |
|------|------|-----------|-------------|
| 手写游标（3.3 BeReader 式） | 过程式，全部自己控制 | 格式简单、想逐条控制错误 | 复杂格式下样板代码膨胀、容易漏检查 |
| nom 8 | 组合子函数树 | 格式规则多、要单元测试每个小解析器 | 需要学习函数式心智；API 大版本有破坏性变更 |
| winnow | 同心智、更新收敛 | 编译更快、新项目倾向 | 生态存量文档少于 nom |

组合子写法（ex07 实测版，注意 nom 8 的 `tag` 要传切片）：

```rust
// examples/crates/src/bin/ex07-nom-parser.rs —— nom 8 组合子（已验证：cargo 1.92.0 / nom 8.0.0）
fn parse_msg(i: &[u8]) -> IResult<&[u8], Msg<'_>> {
    let (i, _) = tag(&b"KV"[..])(i)?;   // 认魔数
    let (i, ty) = be_u16(i)?;           // 大端读 u16（内部 take(2) 后 from_be_bytes）
    let (i, seq) = be_u32(i)?;
    let (i, klen) = be_u32(i)?;
    let (i, key) = take(klen)(i)?;      // 按长度字段切出子切片 → 零拷贝
    let (i, vlen) = be_u32(i)?;
    let (i, value) = take(vlen)(i)?;
    Ok((i, Msg { ty, seq, key, value }))
}
```

三个值得停留的点。**① 返回的剩余输入让「连排记录循环消费」白送**：`parse_msg(&log[pos..])` 成功后用 `log.len() - rest.len()` 前进，ex07 实测一段双 record 日志逐条吐出。**② 错误携带剩余输入**：截断时 `Err` 里的 `input` 是失败点剩下的字节，天然支持「差数据、等下一块」的流式语义（完整与流式模块：`nom::bytes::complete::*` vs `streaming::*`）。**③ 解析不拥有输入**：所有输出字段都是借用的子切片，`&[u8]` 输入 → 解析结果引用它，零拷贝承诺不变（4.4 看类型层面为什么）。

> 组合子解析器与 serde 的定位不同：serde（ph13 已用）面向「结构体 ↔ JSON/TOML/消息格式」的声明式序列化，**本阶段的二进制格式手写布局与组合子才是主战场**；遇到非常规文本协议时两者也可混用。nom/winnow 的具体选型评审遵循 ph17。

### 3.7 length-prefix framing 与协议解析安全纪律

协议解析的**第一安全纪律：不可信字节不能直接转成结构体引用**。C 里常见的 `Header* h = (Header*)buf;`（或 `memcpy(&h, buf, sizeof h)`）在 Rust 里绝不能照搬——不是语法不允许，而是它踩中三大红线：

| 红线 | 内容 | 直接转引用为何是 UB |
|------|------|--------------------|
| ① 对齐 | 结构体要求按 align 对齐的地址放置 | 网络字节流开头任意，几乎必然未对齐；未对齐引用本身就是 UB（E0793 同源） |
| ② 别名 | Rust 假设引用不与别处别名可变（Stacked Borrows） | 字节缓冲通常还有别的借用/可变路径；raw pointer 转引用绕过检查即违约 |
| ③ 未初始化 | 结构体的 padding 洞、enum/bool 的非法位型可能未初始化或非法 | 从字节拼出的 padding/字段可能违反「已初始化 + 合法位型」不变量 |

所以安全解析 = **逐字段读 + 显式转换 + 每步长度检查**（3.3 的 BeReader 就是它的最小形态）。Rust 把「把一个字节切片解释成一组有类型的值」这件事，从 C 的免费（也免费出错）变成「要么逐字段 parse、要么显式 unsafe + 手动保不变量（ph14）」——**默认走前者**。

**length-prefix framing（长度前缀分帧）**是二进制协议最常见的骨架：每条消息 = `[payload_len: u32][payload]`。它把「这条消息到哪结束」编码进前 4 字节，代价是引入一个必须警惕的字段——**长度**。纪律三件套（ex04 已全部实测）：

1. **先校验再信长度**：任何「按长度分配 / 按长度切分」之前先过闸门，`if payload_len > MAX_FRAME { return Err }`，否则恶意 `0xFFFF_FFFF` 会打穿 `Vec::with_capacity`（内存耗尽 DoS）；
2. **长度不足 = 合法状态而非崩溃**：流式解析里「连帧头都没齐」与「帧头齐了载荷没齐」都返回「等下一块」（`Ok(None)`），绝不 panic（ex04 实测半帧等待）；
3. **定长转换用 try_into**：`&[u8]` → `[u8; 4]` 只在长度充足时成功，越界由类型系统拦在门口。

帧结构落到代码（ex04，已验证）：

```rust
// examples/ex04-length-prefix-frame.rs —— 单帧解析 + 长度闸门（已验证：rustc 1.92.0）
fn parse_frame<'a>(buf: &'a [u8]) -> Result<Frame<'a>, FrameErr> {
    let len_bytes: [u8; 4] = buf.get(..4).ok_or(FrameErr::Truncated)?.try_into()?;
    let payload_len = u32::from_be_bytes(len_bytes) as usize;
    if payload_len > MAX_FRAME {                    // ← 闸门：先校验再信长度
        return Err(FrameErr::TooLarge(payload_len));
    }
    let payload = buf.get(4..4 + payload_len).ok_or(FrameErr::Truncated)?; // 长度检查
    Ok(Frame { payload })
}
```

> ⚠️ 一个真实的 CVE 教训值得记住：早期 Redis 协议解析曾在「读长度 → 分配」两步之间缺上限检查，恶意长度直接触发亿级分配。**任何声称来自网络/文件的长度，进入内存前的第一道工序是「≤ 上限」**。上限之外还有第二道防线 CRC/魔数（3.8），前一道挡「资源耗尽」，后一道挡「数据损坏」。

### 3.8 实战：WAL record 与 SSTable block header 解析

把 3.1~3.7 全部串起来的真实格式，取存储引擎最常解析的两类。**WAL（Write-Ahead Log）**是 KV 存储崩溃恢复的支柱：所有写操作先追加进一段只追加的日志，系统崩溃后重放日志恢复内存态——它的 record 格式就是「字节 → 结构化记录」的教科书（完整引擎机制属 ph25 Rust 数据基础设施专项阶段，roadmap 第 25 节，目录待建，本阶段只解析字节）。本仓库教学用 record 格式（字段一律小端）：

| 字段 | 宽度 | 偏移 | 作用 |
|------|-----:|-----:|------|
| magic | u32 | 0 | `b"WAL1"`，快速排除错位/异格式垃圾 |
| crc | u32 | 4 | 对 key\|\|value 求 CRC32，防数据损坏 |
| seq | u64 | 8 | 单调序列号，重放排序用 |
| op | u8 | 16 | 1=Put / 2=Delete |
| klen | u32 | 17 | key 长度 |
| vlen | u32 | 21 | value 长度（Delete 为 0） |
| key | klen 字节 | 25 | 借用切片，不复制 |
| value | vlen 字节 | 25+klen | 借用切片，不复制 |

解析函数的纪律顺序很讲究：**先魔数（对错位）、再 CRC（对损坏）、后取业务字段、最后才是把 key/value 借出去**（ex05 完整实现带一个零依赖手写 CRC32 + IEEE 测试向量自检，全部已验证）：

```rust
// examples/ex05-wal-record-parse.rs —— WAL record 解析骨架（已验证：rustc 1.92.0）
let magic = u32::from_le_bytes(head[0..4].try_into()?);
if magic != MAGIC { return Err(WalErr::BadMagic(magic)); }
let expect_crc = u32::from_le_bytes(head[4..8].try_into()?);
// ……读 seq/op/klen/vlen……
let actual = crc32_combine(key, value);
if actual != expect_crc { return Err(WalErr::ChecksumMismatch { expect: expect_crc, actual }); }
```

**SSTable block header** 是另一个 LSM 家常格式：RocksDB 的 BlockHandle 是 `{offset: varint64, size: varint64}` 两个变长整数；教学简化版常用**固定宽度版**——例如 `offset: u64 LE + size: u64 LE` 的 16B 头，指向数据块位置；数据块内每条记录又是 `[klen: u32][key][vlen: u32][value]` 的重复单元。它的解析**和 WAL record 是同一门手艺**：offset 字段也可能来自不可信文件，解析者依然要先过「≤ 文件长度」的闸门再 `get` 区间。**代码形态示意**（教学为聚焦「偏移双闸门」省略了错误类型定义等无关部分；可运行完整版见 [`exercises/sol-04-sstable-header.rs`](./exercises/sol-04-sstable-header.rs)）：

```rust
struct BlockHandle<'a> { offset: u32, size: u32, block: &'a [u8] }

fn parse_block_handle<'a>(file: &'a [u8], handle_pos: usize) -> Result<BlockHandle<'a>, SstErr> {
    let head = file.get(handle_pos..handle_pos + 8).ok_or(SstErr::Truncated)?; // offset: u32 LE + size: u32 LE
    let offset = u32::from_le_bytes(head[0..4].try_into().map_err(|_| SstErr::Truncated)?) as usize;
    let size = u32::from_le_bytes(head[4..8].try_into().map_err(|_| SstErr::Truncated)?) as usize;
    // 双闸门：offset + size 先做溢出检查，再整体落在文件长度内，最后才切零拷贝块视图
    let end = offset.checked_add(size).ok_or(SstErr::TooBig)?;
    let block = file.get(offset..end).ok_or(SstErr::Truncated)?;
    Ok(BlockHandle { offset: offset as u32, size: size as u32, block })
}
```

两个「偏移来自文件」的要点都在这几行里：① `offset + size` 可能溢出 `usize`（恶意值），用 `checked_add`；② 加法过了不代表落在文件里，`file.get(offset..end)` 的边界检查是最后一道闸。越过两道闸，`block` 就是直接指向文件缓冲内部的零拷贝切片——**一个 header 解析 + 两次检查 = 一次安全的数据块随机读**。WAL record 与 SSTable header 的解析实例合起来说明一个事实：**二进制解析没有银弹，只有固定的纪律清单**——魔数定位、CRC/校验、长度闸门、try_into、借用切片。这道清单写进 [`exercises/sol-03`](./exercises/) 与 [`exercises/sol-04`](./exercises/) 就成了反复演练的模板。

把全章的安全认知收敛成一张可抄进代码注释的**出口检查清单**（写完解析函数逐条核对）：

1. **每个从字节读出的长度/偏移字段**：是否先过「≤ 上限 / ≤ 可用长度」闸门再使用？
2. **每个取区间**：用的是 `get(a..b)`（返回 Option）而不是裸下标 `buf[a..b]`（panic）？
3. **每个定长数组**：`&[u8]` → `[u8; N]` 走的是 `try_into()`？
4. **每个多字节数字**：明确选了 BE 或 LE，并和格式规范一致？
5. **整条消息完整性**：魔数/CRC/校验码是否在业务字段被信任之前验证过？
6. **错误路径**：长度不足返回的是「等下一块 / Truncated」类结果，而不是 panic 或 unwrap？
7. **返回的数据**：key/value/payload 是借用的切片（零拷贝）还是必须拥有的副本？若是副本，分配理由是什么（5 节判据）？

七条全过，这个解析器才达到本阶段的「安全 + 零拷贝」标准。

## 4. 底层原理

### 4.1 布局引擎：字段重排、洞的计算与 ZST

编译器视角下，repr(Rust) 的排布是个小的装箱优化问题：目标是在满足每个字段对齐的前提下，让结构体总大小最小。rustc 的实际策略倾向**按对齐降序放字段**（大对齐的放前面，小字段在尾部密集收拢），这样洞最少——`{u8,u64,u8}` 因此从 C 排布的 24B 缩到 16B。但**这是当前实现而非语言承诺**：Rust Reference 只保证字段互不重叠、整体对齐正确，不保证顺序——一旦代码依赖默认布局的某种排布（比如「小字段在尾部」），未来编译器优化就可能悄悄改掉它。规则收敛为一句：**内存里用默认布局图省事，出内存（磁盘/网络/FFI）必须 repr(C) + 固定宽度**。

洞的计算是纯算术：字段 f 的偏移 = 从上一字段末尾起，向上取整到 `align_of(f)` 的倍数；结构体 size = 末尾向上取整到结构体对齐（字段最大对齐）。ZST（零大小类型，如空 struct、`[(); N]`）在排布里是「幽灵」：大小 0、对齐 1（除非显式 repr(align)），不占洞；`struct S { m: Marker, x: u32 }` 的 size 就是 4——Marker 只提供类型级信息。`Vec<()>` 之类还能利用 ZST 让「容量字段」形同虚设，但那属于集合内部优化，本阶段不用深究。

**手算一遍抵看十遍**——读者先算再对答案（`#[repr(C)]`）：

```rust
#[repr(C)]
struct Rec { a: u8, b: u32, c: u16, d: u64 } // 答案：size = 24
```

推演过程：① `a: u8`（align 1）→ offset 0，占 `[0,1)`；② `b: u32`（align 4）→ 下一候选 1，取整到 4 → offset 4，占 `[4,8)`；③ `c: u16`（align 2）→ 候选 8 已对齐 → offset 8，占 `[8,10)`；④ `d: u64`（align 8）→ 候选 10 取整到 16 → offset 16，占 `[16,24)`；⑤ 末尾 24 已是 8 的倍数 → size 24。用 `size_of::<Rec>()`、`align_of::<Rec>()` 与 `offset_of!(Rec, d)`（16）三连自检即可。这个例子的教训：**声明顺序「紧凑」不等于布局紧凑**——`u32` 后面跟 `u16` 本可塞进 `[4,8)` 的尾部，但 `u64` 一来，中间 [10,16) 的 6 字节洞就白送了；把大对齐字段提前（`d, b, a, c` 之类）可以消洞。

`#[repr(align(N))]` 的代价也由同一公式给出：把结构体对齐抬到 N，size 就被迫向上取整到 N 的倍数——`#[repr(align(64))] struct Aligned([u8; 60]);` 的 size 是 64 而非 60。它是缓存行对齐惯用法（CachePadded）的底层机制，用法见 4.3。

### 4.2 胖指针与零拷贝的本质：memcpy vs 借用

零拷贝不是魔法，它的全部秘密在**内存表示**里：`&[u8]` 是 16 字节的胖指针 = `(data: *const u8, len: usize)`；`Vec<u8>`/`String` 是 24 字节 = `(data, len, cap)`。所谓零拷贝切分，是**新建一个 16B 的胖指针、让 data 指向原缓冲内部偏移**——CPU 只搬运两个词（16 字节），而不是把 payload 复制一份；ex03 里「payload 首地址 - 原包首地址 = 头部 5 字节」就是在证明「subslice 的 data 指针在共享堆内存内部」。

```text
Vec<u8> = (ptr, len, cap)                    &[u8] = (ptr, len)
         ┌──────────────┬─────────────┐      视图1 = (ptr+0,  5)   ← meta 区
         │  同一块堆内存  │             │      视图2 = (ptr+5,  8)   ← payload 区
         └──────────────┴─────────────┘      （两个视图共享底层，谁都不拥有）
```

**memcpy vs 借用的取舍本质是「字节搬运 vs 词搬运」**：复制 N 字节是 O(N) 的访存；借用是 O(1) 造两个词。`Box<T>`（瘦）是 8B 单指针，`Box<[T]>` 是 16B 胖指针——理解胖/瘦指针的区别，才看得懂为什么 `Vec` 转 `Box<[T]>` 会「瘦身」掉 cap。而这一切能安全成立，全靠 ph18 修的那套借用规则：**共享视图随便借（&）、写缓冲需要独占（&mut）、视图活得比缓冲久会被编译期拦下**。你在 ph18 里练的每一条 E0502/E0597 修复，落到这里都是在守卫零拷贝视图不悬垂。

### 4.3 缓存行与布局的关系（点到即止）

CPU 以缓存行（cache line）为单位搬运内存：x86-64 常见 64B，Apple Silicon 为 128B（本机 `sysctl hw.cachelinesize` 实测 128）。布局在缓存侧的两条直觉，本阶段点到即止（测量与调优属 ph22 性能优化与 Profiling 阶段，roadmap 第 22 节，目录待建）：

- **结构体越小，一个缓存行装得越多**：24B 的 repr(C) 结构体，一个 128B 行装 5 个；如果换用 16B 的紧凑布局装 8 个，同样扫 100 万行少触发约 40% 的缓存行加载——这就是「洞」的真实代价的物理来源；
- **顺序访问吃满预取，随机 offset 吃瘪**：`chunks_exact` 顺序扫一个数组，硬件预取器几乎逐行命中；而记录里夹着「跳到 offset 指向的另一块」，预取失效，延迟以百纳秒计——SSTable 的 index block 就是在为「避免全扫」服务。

`repr(align(N))` 的用途也在这里：让热结构体不被意外切跨两个缓存行（CachePadded 惯用法）。但**别在没测量时按直觉改布局**——这正是 ph22 性能优化与 Profiling 阶段（roadmap 第 22 节，目录待建）「先测量后优化」的适用范围。

### 4.4 解析器组合子的类型展开

组合子为什么「声明式」又「零成本」？看类型就懂：`IResult<&[u8], T>` 是 `Result<(剩余输入, 结果), 错误>`，一个解析器就是 `fn(&[u8]) -> IResult<&[u8], T>`。三个组合子各有语义：

```text
tag(x)   : 认前缀，成功消费掉 → 输入前移 len(x)
take(n)  : 消费 n 字节 → 产出借用子切片（零拷贝的关键动作）
be_u32   : 消费 4 字节 → 产出 u32 值（内部 = take(4) + from_be_bytes）
```

`parse_msg` 这类「大解析器」不是运行时解释器，而是**一串普通函数调用**：`be_u32` 调用 `take`，`parse_msg` 依次调用它们。泛型 + 单态化（monomorphization，ph07）让每个组合子对具体输入类型展开成专用代码，release 构建里函数树被内联成几乎等价手写循环的机器码——这就是 nom README 声称「与手写 C 解析器一样快」的机制基础，代价由编译期付出。组合子的**安全增值**在错误路径：`?` 让失败逐层回传、剩余输入留在错误里；但「组合子不引入运行时开销」不等于「可以无上限嵌套」——对不可信输入，**递归/嵌套深度仍需上限或长度闸门**（同 3.7 的资源红线），这是声明式解析唯一需要补纪律的地方。

**complete 与 streaming 双模块的语义差**是 nom 家族另一个值得记的类型设计：同一组组合子按「输入是否可能分块到达」提供两份实现（`nom::bytes::complete::*` 与 `nom::bytes::streaming::*`）。对不足的输入，`complete::take` 直接判失败（Error），`streaming::take` 却返回 `Err(Incomplete(Needed))`、把「还差几个字节」编码进错误里——ex07 第 4 节实测（已验证：cargo 1.92.0 / nom 8.0.0）：

```rust
// examples/crates/src/bin/ex07-nom-parser.rs —— 同一 take 的两种终止语义（实测输出见注释）
let r: IResult<&[u8], &[u8]> = nom::bytes::complete::take(5usize)(b"ab");
println!("complete::take(5) on 2B → {r:?}");
// 实测：Err(Error(Error { input: [97, 98], code: Eof }))
let r2: IResult<&[u8], &[u8]> = nom::bytes::streaming::take(5usize)(b"ab");
println!("streaming::take(5) on 2B → {r2:?}");
// 实测：Err(Incomplete(Size(3)))
```

读这段输出得到的结论：**全量已知缓冲（读文件、一次读完的报文）用 complete**——不完整就是错误；**边收边解析（TCP 流）用 streaming**——把「差 N 字节」作为正常中间态消化掉。它与 3.7 手写解析器里的「半帧等待返回 None」是同一个思路，只是把「还差多少」从运行期字符串升级成了类型。ex07 主线示例用 complete（输入是组好的整段），练习与 project 的流式版可换 streaming 重写一遍体会差异。

## 5. 使用场景

**零拷贝的收益曲线由三件事决定：载荷多大、路径多热、借用能活多久**。小头部、低频、边界本来就要拥有数据 → copy 进结构体值反而更简单直白；大载荷、热路径、数据从网络/磁盘进来到用完不跨所有权边界 → 切片借用白捡一次免复制。判据收敛成三连问（与 ph18 的 clone 三问同构）：**① 这块数据多大？** 几字节的头部复制无关痛痒，几十 MB 的 payload 才值得为免复制搭结构；**② 这条路径多热？** 请求处理循环里每秒百万次的位置，一次免复制就是实打实的吞吐；**③ 借用能活多久？** 视图只在一个函数内流转 → `&[u8]` 就够；要跨任务/跨结构体长期持有 → `Bytes`；数据到手就要改造、落库 → 干脆拥有 `Vec`。还有一层工程建议：**先直白后零拷贝**——原型期先写 copy 版跑通语义，用测量（ph22 性能优化与 Profiling 阶段，roadmap 第 22 节，目录待建）找出真热点，再按判据逐点换零拷贝，比一上来就把全链路塞满 `&[u8]` 泛型要省力得多。

| 场景 | 推荐做法 | 理由 |
|------|---------|------|
| 网络包/磁盘块解析，payload 大、用完即读 | `&[u8]` 借用子切片，解析器返回借用视图 | O(1) 造胖指针，免整段复制（3.4/3.6） |
| 同一缓冲要切给多个任务/异步持有 | `Bytes`（引用计数） | `&[u8]` 借不了那么久；Bytes 让切片随共享分配存活（3.5） |
| 头部小、字段数量固定、一次性 | 直接读进 `FixedHeader {…}` 值 | 结构体按值进出，语义清晰，复制成本可忽略（3.3） |
| 数据要变异/缓存/排序 | 拥有 `Vec<u8>` | 借用视图是只读；写路径需要独占缓冲 |
| 消息需持久化、需回读自校验 | 先魔数/CRC、再借用字段 | 完整性闸门在「数据进业务逻辑」之前（3.8） |
| 只在本进程内、不跨格式边界 | 默认布局即可 | 别为不存在的边界付 repr(C) 的心智税 |

**对照一：C 的裸指针协议解析 vs Rust**——这是本阶段最值得做的对比（为 analysis/ 积累素材）。C 的经典写法是 `struct hdr *h = (struct hdr*)buf; h->len`：一次转换 + 0 次复制，**但把三大红线（对齐/别名/未初始化）全部押给程序员**——错位的包、struct 的 padding、`packed` 后的未对齐访问、以及「谁保证这块内存活着」全无编译期保障；`memcpy` 进对齐好的栈结构体是常见补救，却要自己算大小和字节序。Rust 的安全路径把这些换成了「逐字段 parse + try_into + 长度检查」的显式代码（代价是几行样板），再用借用检查让「视图悬垂」成为编译错误；若你确实需要 C 式零拷贝转换，Rust 也提供 unsafe 通道（ph14）与 `bytemuck` 这类「校验后转换」库——但默认路线永远是 3.7 的安全解析。一句话：**C 让「零拷贝 + 指针算术」免费且危险，Rust 让它付费（写检查）且安全**。

两种路线逐维对照（为 analysis/ 积累素材）：

| 维度 | C 裸指针转换 | Rust 安全逐字段解析 |
|------|-------------|--------------------|
| 对齐 | `(Header*)buf` 撞上未对齐即 UB，靠程序员保证 | 编译器拒绝创建未对齐引用（E0793 同源）；解析器显式 `get+try_into` |
| 别名 | 指针随意 alias，优化器假设与现实可能冲突 | 借用规则：N 只读或 1 可变，编译期排他 |
| 未初始化 | 从字节拼出的 padding/位型可能非法，无提示 | 结构体只能由类型安全构造，无「字节直填」通道 |
| 字节序 | 手工 `ntohs`/移位，易错位 | `from_be_bytes`/`from_le_bytes` 一行，意图显式 |
| 悬垂 | 缓冲释放后指针仍被使用（运行期爆炸） | 借用生命周期编译期检查，悬垂视图直接编译失败 |
| 复制 | 想安全就自己 `memcpy` 对齐结构 | 需要时显式 `copy_from_slice`/`to_vec`，默认零拷贝 |

**对照二：GC 语言**：Go 的 `encoding/binary` 是安全的逐字段读（与 Rust 的 try_into 思路同源），`unsafe.Pointer` 直转 struct 同样要自担对齐风险；Java/C# 有 `ByteBuffer`/`MemoryMarshal` 但真正零拷贝读取依赖堆外内存与 pin，样板更重。Rust 的组合子 + 借用把「声明式描述格式」与「编译期证明视图不悬垂」叠在了一起，这是 GC 语言靠运行时无法给到的组合。

## 6. 代码示例

本节展示示例的关键片段，完整文件在 [`examples/`](./examples/) 目录。验证环境：rustc/cargo 1.92.0（macOS arm64）+ bytes 1.12.1 / nom 8.0.0。**验证说明**：ex01~ex05 纯 std 单文件已实测编译运行通过；ex06/ex07 已在 cargo 1.92.0 实测（ex07 含 4 条单元测试，crates 工程 clippy/fmt 全绿），全部标注「已验证」。逐示例运行命令见 [`examples/README.md`](./examples/README.md)。

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-repr-layout.rs`](./examples/ex01-repr-layout.rs) | 3.1/4.1 | 三种 repr 的 size/align/offset 实测 + packed 的 E0793 纪律 | 已验证 |
| [`examples/ex02-byteorder.rs`](./examples/ex02-byteorder.rs) | 3.2/3.3 | 大小端换算、纯 std BeReader、截断返回 Result 不 panic | 已验证 |
| [`examples/ex03-slice-zero-copy.rs`](./examples/ex03-slice-zero-copy.rs) | 3.4/4.2 | 借用返回切片、指针算术证明零拷贝、chunks_exact 坏尾 | 已验证 |
| [`examples/ex04-length-prefix-frame.rs`](./examples/ex04-length-prefix-frame.rs) | 3.7 | 长度闸门 + 半帧等待 + 粘连多帧逐条吐出 | 已验证 |
| [`examples/ex05-wal-record-parse.rs`](./examples/ex05-wal-record-parse.rs) | 3.8 | WAL record：魔数/CRC/零拷贝 key/value/篡改拦截 | 已验证 |
| [`examples/crates/`](./examples/crates/) 中 `ex06-bytes-crate.rs` | 3.5 | Bytes 引用计数共享缓冲、freeze、Buf 流式解码 | 已验证 |
| [`examples/crates/`](./examples/crates/) 中 `ex07-nom-parser.rs` | 3.6/4.4 | nom 8 组合子解析 + 外层信封 + 连排消费 + 4 测试 | 已验证 |

### 示例 4：length-prefix 单帧解析（`examples/ex04-length-prefix-frame.rs`）

```rust
// examples/ex04-length-prefix-frame.rs —— 安全纪律三件套（已验证：rustc 1.92.0）
fn parse_frame<'a>(buf: &'a [u8]) -> Result<Frame<'a>, FrameErr> {
    let len_bytes: [u8; 4] = buf.get(..4).ok_or(FrameErr::Truncated)?.try_into().map_err(|_| FrameErr::Truncated)?;
    let payload_len = u32::from_be_bytes(len_bytes) as usize;
    if payload_len > MAX_FRAME {
        return Err(FrameErr::TooLarge(payload_len));
    }
    let payload = buf.get(4..4 + payload_len).ok_or(FrameErr::Truncated)?;
    Ok(Frame { payload })
}
```

实测行为：合法帧返回借用的 payload；截断帧返回 `Err(FrameErr::Truncated)`；伪造 `0xFFFF_FFFF` 长度返回 `Err(FrameErr::TooLarge(4294967295))`。流式 `FrameReader` 接受分块到达，半帧等待返回 `Ok(None)`，两帧粘连时循环逐条吐出。

### 示例 5：WAL record 解析（`examples/ex05-wal-record-parse.rs`）

```rust
// examples/ex05-wal-record-parse.rs —— 魔数/CRC 先行的 WAL record 解析（已验证：rustc 1.92.0）
let magic = u32::from_le_bytes(head[0..4].try_into()?);
if magic != MAGIC {
    return Err(WalErr::BadMagic(magic));
}
let expect_crc = u32::from_le_bytes(head[4..8].try_into()?);
// ……读 seq/op/klen/vlen……
let actual = crc32_combine(key, value);
if actual != expect_crc {
    return Err(WalErr::ChecksumMismatch { expect: expect_crc, actual });
}
```

实测行为（ex05 输出）：日志内两条 record（一条 Put `temperature=36.5`、一条 Delete `humidity`）逐条回放成功；翻转 key 的一个字节后，回放被 `ChecksumMismatch` 拦下并打印声明值与实算值；坏魔数、尾部截断分别报 `BadMagic` 与 `Truncated`。文件内置的零依赖 CRC32 实现通过了 IEEE 标准测试向量自检（`crc32("123456789") == 0xCBF43926`）。project 的 `wal-record-parser` 工程把同一手艺做成了带类型与集成测试的完整解析库。

### 示例 7：nom 8 组合子（`examples/crates/src/bin/ex07-nom-parser.rs`）

```rust
// examples/crates/src/bin/ex07-nom-parser.rs —— 组合子串接（已验证：cargo 1.92.0 / nom 8.0.0）
let (i, _) = tag(&b"KV"[..])(i)?;
let (i, ty) = be_u16(i)?;
let (i, klen) = be_u32(i)?;
let (i, key) = take(klen)(i)?;
```

实测输出：合法 record 返回 `Ok((空剩余, Msg{ty, seq, key, value}))`；截断输入返回 `Err` 且错误携带失败点；4 条单元测试（roundtrip、信封、截断、坏魔数）全部通过。

## 7. 总结

### 关键要点

- **布局是可声明的，不是天生的**：默认 repr(Rust) 自由重排（省洞）、repr(C) 按声明顺序 + C ABI（跨边界）、repr(packed) 压到 1 对齐（省字节但 E0793 红线）、repr(transparent) 与内层同布局；协议/磁盘/FFI 一律 `repr(C) + 固定宽度整数`（3.1）
- **洞是算出来的**：size 向上取整到对齐倍数，offset = 前一字段末尾向上取整到本字段对齐；`size_of`/`align_of`/`offset_of!` 是三个自检工具（3.2）
- **字节序只有一组函数**：`from/to_be/le/ne_bytes`，从切片取定长数组唯一正道是 `get + try_into`；网络序 = 大端（3.3）
- **零拷贝 = 造胖指针，不是魔法**：`&[u8]` = (ptr, len)，切子切片 O(1) 搬 16B 而非复制载荷；返回借用要求数据活得够久（ph18 的地基）（3.4/4.2）
- **bytes 让视图可拥有**：`Bytes` 引用计数共享、`BytesMut` 增长、`freeze` 零拷贝、`Buf::get_u32` 移动头指针而非 memmove（3.5）
- **组合子 = 声明式解析**：`tag/take/be_uXX` 小函数串大树，返回剩余输入天然支持连排消费；nom 8 与 winnow 同家族（3.6）
- **安全纪律三件套**：长度先过上限闸门再分配/切分、半帧等待返回 None 不 panic、定长数组靠 try_into；不可信字节直接转结构体引用踩中**对齐/别名/未初始化**三大红线（3.7）
- **真实格式是纪律清单的复读**：魔数定位 → CRC/校验 → 取字段 → 借用载荷；WAL record 与 SSTable header 同模板（3.8）

### 阶段验收清单

- [ ] 能说清 repr(Rust)/repr(C)/repr(packed)/repr(transparent) 各自承诺什么、代价是什么（能预判 `{u8,u64,u8}` 三者大小）
- [ ] 能手算简单 repr(C) 结构体的 size 与各字段 offset（用 `offset_of!` 验证）
- [ ] 能解释网络序是什么、`get + try_into + from_be_bytes` 为什么是唯一正道
- [ ] 能写一个返回借用输入子切片的解析函数，并说清为什么借用检查保证了它不悬垂
- [ ] 能解释 `Bytes::clone` 为什么免费、`freeze` 为什么零拷贝、与 `Vec::drain` 的 memmove 差在哪
- [ ] 能复述对齐/别名/未初始化三大红线，说明为什么不能把不可信字节转成结构体引用
- [ ] 能写 length-prefix 解析并保证「长度先过上限闸门」；WAL record/SSTable header 解析带魔数与 CRC 校验（练习 3~5 验收）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。五题与 roadmap 第 19 节练习一一对应：固定头部二进制协议、用切片返回借用数据、WAL record、SSTable block header、length-prefix frame parser。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**WAL record 解析器**——解析 record header、sequence、key、value、checksum 字段（roadmap 推荐项目之二落地，零第三方依赖 Cargo 工程 + 单元/集成测试）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 跨语言对比

- Rust 把 C 的「`(Header*)buf` 一次转换 + 0 复制」拆成显式的逐字段 parse（安全）与 unsafe/校验库（高危但可证）两条路；三大红线在 C 里是注释里的约定，在 Rust 里是编译器报错——**这是「把内存不变量从纪律升级为类型」最典型的案例**（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

[**ph20 测试体系进阶阶段**](../ph20-testing-advanced/20-testing-advanced.md)——本阶段写出的解析器有大量「长度不足、坏魔数、CRC 失败、粘连边界」等边界路径，正是测试体系的理想练兵场：把 ex07/project 的样例测试升级成异常样例矩阵（ph20 的 test fixtures）、用 proptest 生成随机字节流找解析器崩溃点、用 criterion 基准验证「零拷贝真的比逐次复制快」。届时你手里这批解析器，会从「能跑」变成「可证明能跑」。
