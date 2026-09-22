//! 全局计数分配器：统计进程内 `分配次数` 与 `分配字节`。
//!
//! 原理：实现 `GlobalAlloc` 的包装分配器，每次 `alloc` 用原子计数累加，
//! 再把真实分配转发给 `std::alloc::System`；通过 `#[global_allocator]`
//! 安装为进程唯一分配器。测量段落在**单线程**流程中用 `reset() → 干活 →
//! snapshot()` 夹住，净增量即该段落自己的分配——因为计数发生在分配器层，
//! 所有经 `Vec`/`String`/`Box` 触发的堆分配都被记录，无需改动业务代码。
//!
//! 注意：`#[global_allocator]` 每二进制只能有一个。examples/ex03、examples/ex06 与
//! project 各自内置一份（独立可跑；工程上可拆成共享 crate）。
//!
//! 为什么不带单元测试：进程级全局计数与 `cargo test` 的并行测试线程互相
//! 干扰（其他测试的分配也会进计数器），精确断言必须在单线程主程序的
//! 测量窗口里做——每个示例的 `main` 输出就是它的验证记录。

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

static ALLOCS: AtomicUsize = AtomicUsize::new(0);
static BYTES: AtomicUsize = AtomicUsize::new(0);

/// 计数分配器（包装 `System`）。
pub struct CountingAllocator;

/// 归零计数，开始一段干净的测量窗口。
pub fn reset() {
    ALLOCS.store(0, Ordering::SeqCst);
    BYTES.store(0, Ordering::SeqCst);
}

/// 返回 `(分配次数, 分配字节)` 快照。
pub fn snapshot() -> (usize, usize) {
    (ALLOCS.load(Ordering::SeqCst), BYTES.load(Ordering::SeqCst))
}

// SAFETY: 转发给 System，只附加原子计数，不引入额外不变量。
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::SeqCst);
        BYTES.fetch_add(layout.size(), Ordering::SeqCst);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        // realloc 也是分配入口：grow/shrink 都按一次新分配计数（对齐直观认知：
        // 凡是向分配器要新内存的路径都会被记录）
        ALLOCS.fetch_add(1, Ordering::SeqCst);
        BYTES.fetch_add(new_size.saturating_sub(layout.size()), Ordering::SeqCst);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

/// 进程唯一分配器。
#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;
