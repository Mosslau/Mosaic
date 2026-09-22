//! ex05：内联与单态化影响 —— 三种「对集合做多态计算」的分发方式对比。
//!
//! 1. **enum + match**：静态分发基线。运行时对 tag 做分支，无间接跳转，最接近
//!    手写分支的代价；
//! 2. **泛型（单态化）**：编译器为每种具体类型生成一份代码，调用可完全内联，
//!    理论代价与直接调用相同——Rust「零成本抽象」的兑现点；
//! 3. **`Box<dyn Trait>`**：动态分发。每次调用走 vtable 间接跳转，且编译器无法
//!    内联/常量传播——语义灵活（异质集合）换来的运行时代价。
//!
//! 另外演示 `#[inline(always)]` vs `#[inline(never)]` 对**同一函数体**的影响。
//!
//! 陷阱提醒：这类微基准最容易「全部一样快」或「全被优化掉」——输入必须每次
//! 变化（防常量折叠）、结果必须被消费（防死代码消除），本程序用 `black_box`
//! 双端夹住。实测数字只在「本机 + 本工具链 + 本输入」下成立，复现即见分晓。

use std::env;
use std::hint::black_box;
use std::time::Instant;

/// 迭代次数（每条测量都做这么多次多态调用）。
const DEFAULT_N: u64 = 400_000_000;

// ---------- 1) enum 静态分发 ----------
#[derive(Clone, Copy)]
enum Calc {
    Triple,
    Rotate,
    AddConst,
}

impl Calc {
    #[inline(always)]
    fn calc(self, x: u64) -> u64 {
        match self {
            Calc::Triple => x.wrapping_mul(3),
            Calc::Rotate => x.rotate_left(13),
            Calc::AddConst => x.wrapping_add(0x9e37_79b9_7f4a_7c15),
        }
    }
}

fn enum_dispatch(ops: &[Calc], n: u64) -> u64 {
    let mut acc = 0u64;
    let mut seq = 0u64;
    for i in 0..n {
        let op = ops[(i % ops.len() as u64) as usize];
        seq = seq.wrapping_add(i);
        acc ^= black_box(op.calc(black_box(seq)));
    }
    acc
}

// ---------- 2) 泛型静态分发 ----------
trait CalcTrait {
    fn calc(&self, x: u64) -> u64;
}

struct Triple;
struct Rotate;
struct AddConst;

impl CalcTrait for Triple {
    #[inline(always)]
    fn calc(&self, x: u64) -> u64 {
        x.wrapping_mul(3)
    }
}
impl CalcTrait for Rotate {
    #[inline(always)]
    fn calc(&self, x: u64) -> u64 {
        x.rotate_left(13)
    }
}
impl CalcTrait for AddConst {
    #[inline(always)]
    fn calc(&self, x: u64) -> u64 {
        x.wrapping_add(0x9e37_79b9_7f4a_7c15)
    }
}

/// 泛型版本：调用点单态化后等价于直接调用 `T::calc`。
fn generic_dispatch<T: CalcTrait>(op: &T, n: u64) -> u64 {
    let mut acc = 0u64;
    let mut seq = 0u64;
    for i in 0..n {
        seq = seq.wrapping_add(i);
        acc ^= black_box(op.calc(black_box(seq)));
    }
    acc
}

// ---------- 3) dyn 动态分发 ----------
fn dyn_dispatch(ops: &[Box<dyn CalcTrait>], n: u64) -> u64 {
    let mut acc = 0u64;
    let mut seq = 0u64;
    for i in 0..n {
        let op: &dyn CalcTrait = &*ops[(i % ops.len() as u64) as usize];
        seq = seq.wrapping_add(i);
        acc ^= black_box(op.calc(black_box(seq)));
    }
    acc
}

// ---------- inline 注解 ----------
/// 反复提示内联：把函数体直接嵌进调用点。
#[inline(always)]
fn always_inline(x: u64) -> u64 {
    x.wrapping_mul(0x9e37_79b9_7f4a_7c15)
        .rotate_left(17)
        .wrapping_add(0xffff_ffff_ffff)
}

/// 禁止内联：保留真实调用边界。
#[inline(never)]
fn never_inline(x: u64) -> u64 {
    x.wrapping_mul(0x9e37_79b9_7f4a_7c15)
        .rotate_left(17)
        .wrapping_add(0xffff_ffff_ffff)
}

fn bench_inline_annotation(n: u64) {
    let mut acc = 0u64;
    let mut seq = 0u64;

    let t0 = Instant::now();
    for i in 0..n {
        seq = seq.wrapping_add(i);
        acc ^= black_box(always_inline(black_box(seq)));
    }
    let dt_always = t0.elapsed();

    let t0 = Instant::now();
    for i in 0..n {
        seq = seq.wrapping_add(i);
        acc ^= black_box(never_inline(black_box(seq)));
    }
    let dt_never = t0.elapsed();

    let ms = |d: std::time::Duration| d.as_secs_f64() * 1e3;
    println!(
        "[inline] #[inline(always)]: {:>9.2} ms   #[inline(never)]: {:>9.2} ms   acc=0x{acc:x}",
        ms(dt_always),
        ms(dt_never)
    );
}

fn main() {
    let n: u64 = env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_N);
    println!("迭代次数 n = {n}\n");

    let ops_enum = [Calc::Triple, Calc::Rotate, Calc::AddConst];
    let boxes: Vec<Box<dyn CalcTrait>> =
        vec![Box::new(Triple), Box::new(Rotate), Box::new(AddConst)];

    let t0 = Instant::now();
    let a1 = black_box(enum_dispatch(&ops_enum, n));
    let dt_enum = t0.elapsed();

    let t0 = Instant::now();
    let a2 = black_box(generic_dispatch(&Triple, n));
    let dt_gen_t = t0.elapsed();

    let t0 = Instant::now();
    let a3 = black_box(generic_dispatch(&Rotate, n));
    let dt_gen_r = t0.elapsed();

    let t0 = Instant::now();
    let a4 = black_box(dyn_dispatch(&boxes, n));
    let dt_dyn = t0.elapsed();

    let ms = |d: std::time::Duration| d.as_secs_f64() * 1e3;
    println!(
        "[enum  ] 静态 match 分发   : {:>9.2} ms  acc=0x{a1:x}",
        ms(dt_enum)
    );
    println!(
        "[generic] 单态化(逐类型)   : {:>9.2} ms / {:>9.2} ms  acc=0x{:x}",
        ms(dt_gen_t),
        ms(dt_gen_r),
        a2 ^ a3
    );
    println!(
        "[dyn   ] Box<dyn> 动态分发 : {:>9.2} ms  acc=0x{a4:x}",
        ms(dt_dyn)
    );
    println!(
        "[对比] dyn / enum ≈ {:.2}x ; dyn / generic ≈ {:.2}x",
        dt_dyn.as_secs_f64() / dt_enum.as_secs_f64(),
        dt_dyn.as_secs_f64() / dt_gen_t.as_secs_f64()
    );
    println!("\n(enum 测 3 种混算、generic 测单类型, 各自都保持每轮输入变化——避免常量折叠)");
    println!("\n--- inline 注解对比 ---");
    bench_inline_annotation(n / 4);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enum_and_dyn_dispatch_agree() {
        // 同样 3 个实现按同样顺序轮转 + 同样 seq 序列 → 输出必须一致
        let ops_enum = [Calc::Triple, Calc::Rotate, Calc::AddConst];
        let boxes: Vec<Box<dyn CalcTrait>> =
            vec![Box::new(Triple), Box::new(Rotate), Box::new(AddConst)];
        let e = enum_dispatch(&ops_enum, 5_000);
        let d = dyn_dispatch(&boxes, 5_000);
        assert_eq!(e, d, "enum 与 dyn 分发语义必须一致");
    }

    #[test]
    fn inline_annotation_preserves_semantics() {
        // inline(always) 与 inline(never) 是同一函数体 → 结果一致
        let mut acc_a = 0u64;
        let mut acc_b = 0u64;
        let mut seq = 0u64;
        for i in 0..5_000u64 {
            seq = seq.wrapping_add(i);
            acc_a ^= black_box(always_inline(black_box(seq)));
        }
        let mut seq = 0u64;
        for i in 0..5_000u64 {
            seq = seq.wrapping_add(i);
            acc_b ^= black_box(never_inline(black_box(seq)));
        }
        assert_eq!(acc_a, acc_b);
    }

    #[test]
    fn generic_dispatch_agrees_with_direct_call() {
        let direct = |seq: u64| Triple.calc(seq);
        let g = generic_dispatch(&Triple, 100);
        let mut acc = 0u64;
        let mut seq = 0u64;
        for i in 0..100u64 {
            seq = seq.wrapping_add(i);
            acc ^= black_box(direct(black_box(seq)));
        }
        assert_eq!(g, acc);
    }
}
