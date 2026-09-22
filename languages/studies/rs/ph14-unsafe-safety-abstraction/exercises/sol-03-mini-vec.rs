// 来源：languages/rs/ph14-unsafe-safety-abstraction/exercises/README.md 练习 3
// 说明：最小安全抽象封装——用 std::alloc 手写 MiniVec（i32 版），对外只有安全 API，
//       内部用 unsafe 管理原始分配（alloc/realloc/dealloc + 裸指针写读），
//       不变量（ptr 有效 / len ≤ cap / Drop 必释放）由实现者维护。
//       对应 roadmap 练习「为 unsafe 抽象写边界测试」与推荐项目「受控缓冲区封装」的迷你版。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-03-mini-vec.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告；Drop 释放路径正确，无内存泄漏——可用 Miri 进一步验证，本环境未装 nightly 未跑）
// 验证块（实测输出，rustc 1.92.0 macOS arm64）：
//   1. MiniVec: len=17, cap=32, 扩容后内容完整
//   2. get(16) = Some(16), get(17) 越界 = None
//   3. pop() = Some(16), len = 16
//   断言通过
//   （push 0..16 共 17 个：cap 增长序列 0→4→8→16→32；扩容后 as_slice 内容与 0..17 一致）

use std::alloc::{alloc, dealloc, realloc, Layout};
use std::ptr::NonNull;

struct MiniVec {
    ptr: NonNull<i32>, // 指向分配：cap == 0 时为 dangling() 占位（合法、不 deref）
    len: usize,        // 已用元素数（不变量：len ≤ cap）
    cap: usize,        // 分配容量（不变量：ptr 按 cap 分配，或 cap == 0）
}

impl MiniVec {
    fn new() -> Self {
        MiniVec { ptr: NonNull::dangling(), len: 0, cap: 0 }
    }

    /// 扩容：0→4→8→16→…（倍增）。不变量「ptr 指向 cap 大小的分配」在 unsafe 内维护
    fn grow(&mut self) {
        let new_cap = if self.cap == 0 { 4 } else { self.cap * 2 };
        let new_layout = Layout::array::<i32>(new_cap).expect("布局合法");
        unsafe {
            if self.cap == 0 {
                let p = alloc(new_layout);
                // SAFETY: alloc 返回的指针由本类型独占管理，len == 0 无需拷贝
                self.ptr = NonNull::new(p as *mut i32).expect("分配失败");
            } else {
                let old_layout = Layout::array::<i32>(self.cap).expect("布局合法");
                // SAFETY: realloc 会拷贝 min(old,new) 字节，保持已有元素完整
                let p = realloc(self.ptr.as_ptr() as *mut u8, old_layout, new_layout.size());
                self.ptr = NonNull::new(p as *mut i32).expect("分配失败");
            }
        }
        self.cap = new_cap;
    }

    /// 安全 API：追加元素（可能触发扩容）
    fn push(&mut self, v: i32) {
        if self.len == self.cap {
            self.grow();
        }
        // SAFETY: 不变量保证 len < cap，ptr.add(len) 在分配内
        unsafe { self.ptr.as_ptr().add(self.len).write(v) };
        self.len += 1;
    }

    /// 安全 API：按索引读取（越界返回 None，不 panic）
    fn get(&self, idx: usize) -> Option<i32> {
        if idx >= self.len {
            return None;
        }
        // SAFETY: 已检查 idx < len ≤ cap
        Some(unsafe { self.ptr.as_ptr().add(idx).read() })
    }

    fn len(&self) -> usize {
        self.len
    }

    fn capacity(&self) -> usize {
        self.cap
    }

    /// 安全 API：以切片视图暴露（内部 unsafe 构造引用，不变量保证切片长度合法）
    fn as_slice(&self) -> &[i32] {
        // SAFETY: ptr 有效且 len ≤ cap，from_raw_parts 的切片长度合法
        unsafe { std::slice::from_raw_parts(self.ptr.as_ptr(), self.len) }
    }

    /// 安全 API：弹出末尾元素
    fn pop(&mut self) -> Option<i32> {
        if self.len == 0 {
            return None;
        }
        self.len -= 1;
        // SAFETY: len-1 < cap，元素已初始化（push 才写）
        Some(unsafe { self.ptr.as_ptr().add(self.len).read() })
    }
}

impl Drop for MiniVec {
    fn drop(&mut self) {
        if self.cap > 0 {
            unsafe {
                let layout = Layout::array::<i32>(self.cap).expect("布局合法");
                // SAFETY: ptr 由 alloc/realloc 分配且尚未释放（本类型独占）
                dealloc(self.ptr.as_ptr() as *mut u8, layout);
            }
        }
        // 若忘记 dealloc（或不写 Drop），每次扩容的旧内存都会泄漏——「谁分配谁释放」
    }
}

fn main() {
    let mut v = MiniVec::new();
    for i in 0..17 {
        v.push(i as i32);
    }
    {
        let s = v.as_slice();
        // 扩容后内容完整：0..17 全部按序保存
        assert_eq!(s, &(0..17).collect::<Vec<i32>>()[..]);
        println!("1. MiniVec: len={}, cap={}, 扩容后内容完整", v.len(), v.capacity());
    }
    assert_eq!(v.get(16), Some(16));
    assert_eq!(v.get(17), None); // 越界 → None（安全 API 不 panic）
    println!("2. get(16) = Some(16), get(17) 越界 = None");

    assert_eq!(v.pop(), Some(16));
    assert_eq!(v.len(), 16);
    println!("3. pop() = Some(16), len = {}", v.len());
    println!("断言通过");
    // main 结束 v.drop() 自动释放 32 个 i32 的分配
}
