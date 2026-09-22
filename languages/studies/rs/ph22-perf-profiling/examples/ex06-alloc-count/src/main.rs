//! ex06：分配次数 —— 四组「避免/减少堆分配」写法的对照实验。
//!
//! 每组都用计数分配器夹住：`reset() → 干活 → snapshot()`。教学点：
//! **分配次数是比耗时更早暴露问题的信号**——一次分配 ~几十 ns 在单测里看不出来，
//! 但分配器锁在多线程下的争用、page fault 的抖动都随分配次数放大。

mod counting;

use std::hint::black_box;

use counting::{reset, snapshot};

/// 打印一组对照结果。
fn report(name: &str, a: (usize, usize), b: (usize, usize)) {
    println!("[{name}]");
    println!("  写法 A : 分配 {:>7} 次 / {:>9} B", a.0, a.1);
    println!("  写法 B : 分配 {:>7} 次 / {:>9} B", b.0, b.1);
    if b.1 > 0 {
        println!("  B/A 分配次数 ≈ {:.2}x", b.0 as f64 / a.0.max(1) as f64);
    }
    println!();
}

/// 组 1：复用缓冲 —— 每次临时 `format!` vs 复用同一个 String。
fn demo_reuse_buffer(n: usize) {
    // A：每次构造新 String（format! 必然堆分配一次 + 可能的 realloc）
    reset();
    {
        let mut sink = 0usize;
        for i in 0..n {
            let s = format!("key-{i}=value-{i}");
            sink = sink.wrapping_add(black_box(s.len()));
        }
        black_box(sink);
    }
    let a = snapshot();

    // B：复用缓冲：clear() 保留容量，容量够时零分配
    reset();
    {
        use std::fmt::Write;
        let mut sink = 0usize;
        let mut buf = String::with_capacity(32);
        for i in 0..n {
            buf.clear();
            let _ = write!(buf, "key-{i}=value-{i}");
            sink = sink.wrapping_add(black_box(buf.len()));
        }
        black_box(sink);
    }
    let b = snapshot();
    report("复用缓冲 (format! vs clear+write!)", a, b);
}

/// 组 2：String vs &str —— 收集同一批行的首字段。
fn demo_string_vs_str(n: usize) {
    // 输入：n 行文本（构造成本不计入任何一组的测量窗口）
    let lines: Vec<String> = (0..n)
        .map(|i| format!("2026-09-04 svc-{i:<4} op 字段"))
        .collect();

    // A：字段复制成 String 再收集
    reset();
    {
        let mut fields: Vec<String> = Vec::new();
        for line in &lines {
            fields.push(black_box(
                line.split_whitespace().nth(1).unwrap_or("").to_string(),
            ));
        }
        black_box(fields.len());
    }
    let a = snapshot();

    // B：字段直接借用 &str（lines 活得比 fields 长）
    reset();
    {
        let mut fields: Vec<&str> = Vec::new();
        for line in &lines {
            fields.push(black_box(line.split_whitespace().nth(1).unwrap_or("")));
        }
        black_box(fields.len());
    }
    let b = snapshot();
    report("String vs &str 收集", a, b);
}

/// 组 3：Vec 预留容量 —— push 扩容 vs with_capacity。
fn demo_with_capacity(n: usize) {
    reset();
    {
        let mut v: Vec<u64> = Vec::new();
        for i in 0..n as u64 {
            v.push(black_box(i));
        }
        black_box(v.len());
    }
    let a = snapshot();

    reset();
    {
        let mut v: Vec<u64> = Vec::with_capacity(n);
        for i in 0..n as u64 {
            v.push(black_box(i));
        }
        black_box(v.len());
    }
    let b = snapshot();
    report("Vec 扩容 vs with_capacity", a, b);
}

/// 组 4：小向量优化 —— Vec 起步必分配 vs 栈内嵌小数组。
/// 教学简化版 SmallVec：元素 ≤ 4 个时存栈上，超出才转堆。
struct SmallVec<T> {
    inline: [Option<T>; 4],
    len: usize,
    heap: Vec<T>,
}

impl<T> SmallVec<T> {
    fn new() -> Self {
        SmallVec {
            inline: std::array::from_fn(|_| None),
            len: 0,
            heap: Vec::new(),
        }
    }

    fn push(&mut self, value: T) {
        if self.len < 4 {
            self.inline[self.len] = Some(value); // 栈上，零分配
        } else {
            self.heap.push(value); // 第 5 个起才可能分配
        }
        self.len += 1;
    }

    fn len(&self) -> usize {
        self.len
    }
}

fn demo_small_vec(n: usize, per: usize) {
    // A：每个小集合用 Vec（>4 个元素时的堆分配）
    reset();
    {
        let mut total = 0usize;
        for i in 0..n {
            let mut v: Vec<u64> = Vec::new();
            for j in 0..per as u64 {
                v.push(black_box(i as u64 + j));
            }
            total = total.wrapping_add(v.len());
        }
        black_box(total);
    }
    let a = snapshot();

    // B：每个小集合用 SmallVec（≤4 元素全程零分配）
    reset();
    {
        let mut total = 0usize;
        for i in 0..n {
            let mut v = SmallVec::new();
            for j in 0..per as u64 {
                v.push(black_box(i as u64 + j));
            }
            total = total.wrapping_add(v.len());
        }
        black_box(total);
    }
    let b = snapshot();
    report(
        &format!("小向量 (Vec vs 栈内嵌, {per} 元素/集合 × {n})"),
        a,
        b,
    );
}

fn main() {
    println!("== ex06 分配次数对照 ==\n");
    demo_reuse_buffer(200_000);
    demo_string_vs_str(100_000);
    demo_with_capacity(1_000_000);
    demo_small_vec(500_000, 3);
    demo_small_vec(200_000, 40);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smallvec_stays_inline_under_four() {
        let mut v = SmallVec::new();
        for i in 0..4u64 {
            v.push(i);
        }
        assert_eq!(v.len(), 4);
        assert!(v.heap.is_empty());
    }

    #[test]
    fn smallvec_spills_to_heap() {
        let mut v = SmallVec::new();
        for i in 0..10u64 {
            v.push(i);
        }
        assert_eq!(v.len(), 10);
        assert_eq!(v.heap.len(), 6);
    }

    // 复用缓冲/收集路径的「精确分配次数」不在单元测试里断言——全局计数
    // 与并行测试互相干扰（见 counting.rs 头注释）；由 main 单线程实测输出。
}
