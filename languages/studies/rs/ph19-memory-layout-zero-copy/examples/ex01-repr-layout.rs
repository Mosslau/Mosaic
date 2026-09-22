// examples/ex01-repr-layout.rs —— repr 家族与布局控制：repr(Rust) / repr(C) / repr(packed) / repr(transparent)
// 对应主文档 3.1/4.1。演示：默认布局会重排字段、repr(C) 按声明顺序 + C ABI、
// repr(packed) 取消对齐、repr(transparent) 让 newtype 与内层类型同布局、ZST 大小为零。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行：
//   rustc --edition 2021 -D warnings ex01-repr-layout.rs -o /tmp/ph19-ex01 && /tmp/ph19-ex01
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin；输出见本文件运行结果注释）。
use std::mem::{align_of, offset_of, size_of};

// —— 1. 三个「内容相同、布局不同」的结构体 ——

/// repr(Rust)：编译器允许重排字段，只承诺「每个字段对齐正确」。
#[derive(Debug)]
struct RustLayout {
    tag: u8,
    stamp: u64,
    kind: u8,
}

/// repr(C)：按声明顺序排布，布局与 C 语言结构体一致（对齐到最大字段）。
/// 跨 FFI / 磁盘映射需用 repr(C)；代价是可能出现 padding。
#[repr(C)]
#[derive(Debug)]
struct CLayout {
    tag: u8,
    stamp: u64,
    kind: u8,
}

/// repr(packed)：所有字段紧挨着排、对齐被压到 1，大小 = 字段大小之和。
/// ⚠️ 风险：packed 字段可能「未对齐」，取字段引用是编译错误（E0793）——
/// 只能按值读出 Copy 字段；跨 FFI 传指针给 C 结构体也可能制造未对齐访问（UB）。
/// 协议解析「把字节流转成结构体引用」的念头遇到 packed 会立刻撞上这条红线（见主文档 3.7）。
#[repr(packed)]
#[derive(Debug)]
struct PackedLayout {
    tag: u8,
    stamp: u64,
    kind: u8,
}

// —— 2. repr(transparent)：与唯一字段同布局的 newtype ——

/// repr(transparent)：Wrapper 的 ABI 布局与 inner 完全相同，可用于 FFI 场景
/// 「换一个更严格的类型，但不改变内存表示」。要求恰好一个非 ZST 字段。
#[repr(transparent)]
struct MonotonicId(u64);

// —— 3. ZST（零大小类型）与数组占位 ——

/// ZST：没有任何字段的类型，大小为 0。可作「类型级标记」而不占内存。
struct Marker;

fn main() {
    // 同一份字段，三种 repr 的尺寸与对齐天差地别
    println!("== 布局对比（同一组字段: u8/u64/u8）==");
    println!("rust    : size = {:>2}, align = {}", size_of::<RustLayout>(), align_of::<RustLayout>());
    println!("repr(C) : size = {:>2}, align = {}", size_of::<CLayout>(), align_of::<CLayout>());
    println!("packed  : size = {:>2}, align = {}", size_of::<PackedLayout>(), align_of::<PackedLayout>());
    // 实测（1.92.0 / aarch64）：
    //   rust    : size = 16, align = 8   ← 字段被重排：stamp(8B) 在前，tag/kind 塞进尾部的 2B，天然无洞
    //   repr(C) : size = 24, align = 8   ← 声明顺序：tag@0 → [7B 洞] → stamp@8 → kind@16 → [7B 尾洞]
    //   packed  : size = 10, align = 1   ← 取消一切对齐，大小 = 1+8+1

    // repr(C) 下用 offset_of! 看每个字段的字节偏移（Rust 1.77+，本基线 1.92.0 可用）
    println!();
    println!("== repr(C) 字段偏移 ==");
    println!("tag   @ {}", offset_of!(CLayout, tag));
    println!("stamp @ {}", offset_of!(CLayout, stamp));
    println!("kind  @ {}", offset_of!(CLayout, kind));
    // 实测：tag @ 0、stamp @ 8、kind @ 16 —— 第 1~7 字节就是 padding（洞）

    // 打印结构体实例：Debug 只显示值，看不到洞——布局要问 size_of/offset_of
    // 实例化三个结构体并读取字段（RustLayout/PackedLayout 的字段全被使用，避免 dead_code 告警）
    let r = RustLayout { tag: 0x05, stamp: 101, kind: 0x06 };
    let c = CLayout { tag: 0x01, stamp: 99, kind: 0x02 };
    let p = PackedLayout { tag: 0x03, stamp: 100, kind: 0x04 };
    let r_stamp = r.stamp; // repr(Rust) 实例按普通方式读，无对齐问题
    println!();
    println!("== 实例 ==");
    println!("repr(Rust) : stamp = {r_stamp}, tag/kind = {}/{}（size 16：编译器把 stamp 挪到头部、tag/kind 收进尾部 2B）", r.tag, r.kind);
    println!("repr(C)    : {c:?}");
    // packed 字段的读取必须先「按值拷贝到局部变量」：直接 println!("{}", p.stamp)
    // 会被 format 机制按 &u64 借用 → 报 E0793 "reference to packed field is unaligned"。
    // 这是 packed 红线的直接体现：借用未对齐字段本身就是 UB，编译器拒绝（实测报错见下）。
    let stamp = p.stamp; // Copy 按值读出，编译器负责未对齐读的合法性，不产生引用
    println!("packed    : stamp = {stamp}, tag/kind = {}/{}", p.tag, p.kind);

    // transparent newtype：大小/对齐与裸 u64 完全一致
    println!();
    println!("== repr(transparent) ==");
    println!("MonotonicId: size = {}, align = {}（与 u64 相同：{}, {}）",
        size_of::<MonotonicId>(), align_of::<MonotonicId>(),
        size_of::<u64>(), align_of::<u64>());
    let _id = MonotonicId(7);

    // ZST：大小为 0，不影响容纳它的结构体大小；数组 [(); N] 也整体为零大小
    println!();
    println!("== ZST ==");
    println!("Marker       : size = {}", size_of::<Marker>());
    println!("[(); 100]    : size = {}", size_of::<[(); 100]>());
    println!("bool 数组对比: size = {}", size_of::<[bool; 100]>());

    // —— 收尾小结（教学提醒，不做任何 unsafe）——
    // 1. 默认 repr(Rust) 会重排字段：本阶段 3.1 的关键结论是「结构体大小由布局策略决定，不由声明顺序决定」
    // 2. 协议/磁盘/FFI 需要「字节即结构体」的稳定对应 → 必须显式 repr(C)（甚至加 #[repr(C, packed)] 手控每字节）
    // 3. 把不可信字节直接转成结构体引用（哪怕 repr(C)）仍然危险：对齐/别名/未初始化三大红线见主文档 3.7，示例 ex04/ex05 演示安全做法
}
