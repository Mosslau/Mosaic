// 项目源码：受控缓冲区封装（SafeBuffer）——提供安全 API，内部用少量 unsafe 操作切片
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings src/main.rs -o /tmp/safebuf
// 运行：/tmp/safebuf            （自包含验收：断言 + 泄漏自检）
//       /tmp/safebuf --stress 1000000   （压力路径：100 万字节写入读出）
// 验证状态：已验证（编译零警告；demo 断言全部通过、泄漏计数归零；--stress 1000000 通过）

use std::alloc::{alloc, dealloc, realloc, Layout};
use std::ptr::NonNull;
use std::sync::atomic::{AtomicUsize, Ordering};

/// 全局分配计数：每成功 alloc/realloc 一次 +1，dealloc 一次 -1。
/// 程序结束时必须归零——这是本项目自带的「内存泄漏自检」。
static LIVE_ALLOCS: AtomicUsize = AtomicUsize::new(0);

/// 受控缓冲区：对外只有安全 API，内部用裸指针 + std::alloc 管理原始内存。
///
/// 不变量（由实现者维护，任何 unsafe 操作都建立在这些不变量上）：
/// - `len ≤ cap`
/// - `cap == 0` 时 `ptr` 为 `NonNull::dangling()` 占位，不 deref；
///   `cap > 0` 时 `ptr` 指向 `cap` 字节的合法分配，且未被释放
/// - 字节 `[0, len)` 均已初始化（write 写入），`[len, cap)` 未初始化、不得读取
pub struct SafeBuffer {
    ptr: NonNull<u8>,
    len: usize,
    cap: usize,
}

impl SafeBuffer {
    pub fn new() -> Self {
        SafeBuffer { ptr: NonNull::dangling(), len: 0, cap: 0 }
    }

    /// 扩容到至少 `need` 字节（倍增：0→8→16→32→…）。
    /// 不变量「ptr 指向 cap 字节分配」「旧字节拷贝保留」在此 unsafe 块内维护。
    fn reserve(&mut self, need: usize) {
        if need <= self.cap {
            return;
        }
        let new_cap = if self.cap == 0 { 8 } else { self.cap };
        let new_cap = (new_cap.max(need)).next_power_of_two();
        let new_layout = Layout::from_size_align(new_cap, 1).expect("布局合法");
        unsafe {
            if self.cap == 0 {
                let p = alloc(new_layout);
                assert!(!p.is_null(), "alloc 失败");
                LIVE_ALLOCS.fetch_add(1, Ordering::Relaxed);
                // SAFETY: p 由 alloc 分配、本类型独占；len == 0 无需拷贝
                self.ptr = NonNull::new(p).expect("指针非空");
            } else {
                let old_layout = Layout::from_size_align(self.cap, 1).expect("布局合法");
                // SAFETY: ptr 由 alloc/realloc 分配、尚未释放、长度合法；
                //         realloc 拷贝 min(旧,新) 字节，保留 [0, len) 已写内容
                let p = realloc(self.ptr.as_ptr(), old_layout, new_cap);
                assert!(!p.is_null(), "realloc 失败");
                self.ptr = NonNull::new(p).expect("指针非空");
            }
        }
        self.cap = new_cap;
    }

    /// 安全 API：追加一段字节
    pub fn write(&mut self, data: &[u8]) {
        let need = self.len + data.len();
        self.reserve(need);
        // SAFETY: 不变量 len ≤ cap 且 reserve 已保证容量；add 不越界
        unsafe {
            let dst = self.ptr.as_ptr().add(self.len);
            std::ptr::copy_nonoverlapping(data.as_ptr(), dst, data.len());
        }
        self.len = need;
    }

    /// 安全 API：追加单字节
    pub fn push_byte(&mut self, b: u8) {
        self.write(&[b]);
    }

    /// 安全 API：只读切片视图（不复制）
    pub fn as_slice(&self) -> &[u8] {
        if self.len == 0 {
            return &[];
        }
        // SAFETY: ptr 有效、[0, len) 已初始化，切片长度合法
        unsafe { std::slice::from_raw_parts(self.ptr.as_ptr(), self.len) }
    }

    /// 安全 API：可变切片视图
    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        if self.len == 0 {
            return &mut [];
        }
        // SAFETY: 同上；&mut self 独占访问保证无别名
        unsafe { std::slice::from_raw_parts_mut(self.ptr.as_ptr(), self.len) }
    }

    /// 安全 API：按索引读取（越界返回 None）
    pub fn get(&self, idx: usize) -> Option<u8> {
        if idx >= self.len {
            return None;
        }
        // SAFETY: idx < len，字节已初始化
        Some(unsafe { *self.ptr.as_ptr().add(idx) })
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn capacity(&self) -> usize {
        self.cap
    }

    /// 安全 API：清空（保留容量，便于复用）
    pub fn clear(&mut self) {
        self.len = 0;
    }

    /// 安全 API：迭代器（借用底层切片）
    pub fn iter(&self) -> std::slice::Iter<'_, u8> {
        self.as_slice().iter()
    }
}

impl Drop for SafeBuffer {
    fn drop(&mut self) {
        if self.cap > 0 {
            unsafe {
                let layout = Layout::from_size_align(self.cap, 1).expect("布局合法");
                // SAFETY: ptr 由 alloc/realloc 分配、尚未释放、本类型独占
                dealloc(self.ptr.as_ptr(), layout);
            }
            LIVE_ALLOCS.fetch_sub(1, Ordering::Relaxed);
        }
    }
}

/// 自包含验收：断言 + 泄漏自检
fn demo() {
    let mut buf = SafeBuffer::new();
    assert_eq!(buf.len(), 0);
    assert_eq!(buf.capacity(), 0);

    // 写入并跨扩容验证内容完整（0→8→16→32 三次扩容）
    buf.write(b"hello ");
    buf.write(b"rust ");
    buf.write(b"unsafe");
    assert_eq!(buf.as_slice(), b"hello rust unsafe");
    assert_eq!(buf.len(), 17);
    assert_eq!(buf.capacity(), 32);
    println!("1. 写入 17 字节（跨 3 次扩容 0→8→16→32），内容完整: len={}, cap={}", buf.len(), buf.capacity());

    // 安全 API 边界：get 越界返回 None；可变切片就地修改
    assert_eq!(buf.get(0), Some(b'h'));
    assert_eq!(buf.get(15), Some(b'f'));
    assert_eq!(buf.get(16), Some(b'e'));
    assert_eq!(buf.get(17), None); // 越界
    buf.as_mut_slice()[0] = b'H';
    assert_eq!(buf.as_slice(), b"Hello rust unsafe");
    println!("2. get 边界（get(17) 越界 = None）+ as_mut_slice 就地修改 OK");

    // clear 后复用容量
    buf.clear();
    assert_eq!(buf.len(), 0);
    assert_eq!(buf.capacity(), 32); // 容量保留
    buf.push_byte(1);
    buf.push_byte(2);
    assert_eq!(buf.as_slice(), &[1, 2]);
    println!("3. clear 保留容量，push_byte 复用 OK");

    // 迭代器
    let total: usize = buf.iter().map(|&b| b as usize).sum();
    assert_eq!(total, 3);
    println!("4. iter 求和 = {total}");

    // 泄漏自检：drop 后分配计数归零
    drop(buf);
    let live = LIVE_ALLOCS.load(Ordering::Relaxed);
    assert_eq!(live, 0, "存在未释放分配（泄漏）：{live}");
    println!("5. 泄漏自检: drop 后 LIVE_ALLOCS = {live}");

    println!("demo 断言通过");
}

/// 压力路径：N 字节写入后全量读出校验
fn stress(n: usize) {
    let mut buf = SafeBuffer::new();
    for i in 0..n {
        buf.push_byte((i % 251) as u8); // 每次 push 都可能触发扩容
    }
    assert_eq!(buf.len(), n);
    for i in 0..n {
        assert_eq!(buf.get(i), Some((i % 251) as u8));
    }
    println!("stress: {n} 字节 push 后逐一校验通过（cap = {}）", buf.capacity());
    drop(buf);
    assert_eq!(LIVE_ALLOCS.load(Ordering::Relaxed), 0, "stress 后存在泄漏");
    println!("stress 断言通过（泄漏归零）");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() >= 2 && args[1] == "--stress" {
        let n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(100_000);
        stress(n);
    } else {
        demo();
    }
}
