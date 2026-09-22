// examples/ex03-ub-demo.rs —— 未定义行为（UB）演示：同一源码在不同编译选项下行为不同
// 运行前提（必读）：本文件故意包含未定义行为（UB），仅供教学演示「UB 使程序行为不可预测」，
//   不要在任何真实代码中复制这些写法。UB 结果依赖编译器/平台/优化级别，以下输出为本机实测值。
// 编译（debug 形态，带溢出检查）：rustc --edition 2021 -C overflow-checks=on ex03-ub-demo.rs -o /tmp/ex03-dbg
// 编译（release 形态，O3 优化）：rustc --edition 2021 -C opt-level=3 ex03-ub-demo.rs -o /tmp/ex03-rel
// 运行：/tmp/ex03-dbg  与  /tmp/ex03-rel
// 验证状态：已验证（rustc 1.92.0，macOS arm64）——两形态输出差异见 README 与下方注释

use std::hint::black_box;
use std::mem::MaybeUninit;

fn main() {
    // 演示 1：读取「部分未初始化」的内存（MaybeUninit）
    // 只把 i32 的最低 1 字节写成 0xAA，其余 3 字节从未初始化 → assume_init() 是 UB
    let mut m = MaybeUninit::<i32>::uninit();
    let p = m.as_mut_ptr();
    unsafe {
        std::ptr::write_bytes(p as *mut u8, 0xAA, 1); // 只初始化 1/4 字节
        let v = m.assume_init(); // UB：读未初始化字节（LLVM 中为 poison）
        println!("1. 部分初始化读 = {v:#010X}");
    }
    // 实测差异：
    //   debug 形态：低字节恒为 0xAA，高 3 字节为栈垃圾，每次运行可能不同（如 0x04DDC8AA / 0x021308AA）
    //   release 形态：恒为 0x000000AA —— 优化器根据「未初始化字节是 poison」把高 3 字节折叠成 0

    // 演示 2：移位量超过位宽（≥ 32）→ UB
    // black_box 防止常量折叠，保证这是一个「运行时」移位
    let shift = black_box(33u32);
    let x = 1u32 << shift; // UB：移位量 ≥ 位宽 32
    println!("2. shift = {shift}, 1 << 33 = {x}");
    // 实测差异：
    //   debug 形态（overflow-checks=on）：panic「attempt to shift left with overflow」，退出码 101
    //   release 形态（无溢出检查）：静默输出 shift = 33, x = 2 —— 处理器硬件对移位量取模 32 的结果，
    //     UB 允许产生任何值，「看起来正常」的 2 只是恰好

    // 演示 3（教学对照）：Vec 扩容后解引用旧指针（悬垂）
    // 实测：本机 debug/release 两种形态都输出 val = 2，未观察到差异——
    //   「UB 不保证出现可见差异，这正是它的危险」：代码可能长期"看似正常"，一旦编译器/平台变化就爆炸
    let mut v: Vec<i32> = vec![1, 2, 3];
    let dangling = v.as_ptr(); // 之后 v.push 可能触发重新分配，旧内存被释放
    v.push(4); // 重新分配 → dangling 悬垂
    let val = unsafe { *dangling }; // UB：解引用悬垂指针（本机两种形态均输出 2，仅供参考）
    println!("3. 悬垂解引用（实测两种形态均输出 2，未观察到差异）= {val}");
}
