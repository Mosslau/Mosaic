// ex04-stats-ffi.rs —— Rust extern "C" 裸 FFI 调 C++ 导出的 C ABI（单文件 rustc 直链）
// 验证环境：rustc 1.92.0（~/.cargo/bin）；前置：先按 ex01 编出 /tmp/libvtest.dylib
// 构建/运行（在 examples/ 目录内）：
//   export PATH="$HOME/.cargo/bin:$PATH"
//   rustc -O ex04-stats-ffi.rs -L /tmp -l vtest -o /tmp/ph20-ex04
//   /tmp/ph20-ex04
// 验证状态：已验证（本机实测：编译零警告、断言全绿、退出码 0）
// 教学点（主文档 3.4/3.8/4.4）：
//   - extern "C" 签名与 ex01-stats-c-api.h 逐字一致（手抄签名，无头文件可 include）
//   - 所有 FFI 调用 unsafe；把裸指针收进 Stats（RAII 壳），Drop 归还库内销毁
//   - 错误码翻译成 Result<T, i32>，业务代码零 unsafe
use std::os::raw::c_long;

// 错误码与 C 头保持一致（手抄；bindgen 可自动生成，见主文档 3.4 说明）
const VTEST_ERR_EMPTY: i32 = 2;

// opaque 句柄在 Rust 侧 = 不透明指针 + ZST 类型标记
#[repr(C)]
struct VtestStats {
    _private: [u8; 0],
}

extern "C" {
    fn vtest_stats_create() -> *mut VtestStats;
    fn vtest_stats_destroy(s: *mut VtestStats);
    fn vtest_stats_version() -> i32;
    fn vtest_stats_add(s: *mut VtestStats, value: f64) -> i32;
    fn vtest_stats_count(s: *const VtestStats, out: *mut c_long) -> i32;
    fn vtest_stats_mean(s: *const VtestStats, out: *mut f64) -> i32;
}

// RAII 包装：Drop 保证任何退出路径都归还库内销毁（主文档 3.8 规则 3）
struct Stats {
    raw: *mut VtestStats,
}

impl Stats {
    fn new() -> Option<Stats> {
        let raw = unsafe { vtest_stats_create() };
        (!raw.is_null()).then(|| Stats { raw })
    }
    fn add(&mut self, value: f64) -> Result<(), i32> {
        let rc = unsafe { vtest_stats_add(self.raw, value) };
        if rc == 0 { Ok(()) } else { Err(rc) }
    }
    fn count(&self) -> Result<i64, i32> {
        let mut out: c_long = 0;
        let rc = unsafe { vtest_stats_count(self.raw, &mut out) };
        if rc == 0 { Ok(out as i64) } else { Err(rc) }
    }
    fn mean(&self) -> Result<f64, i32> {
        let mut out = 0.0f64;
        let rc = unsafe { vtest_stats_mean(self.raw, &mut out) };
        if rc == 0 { Ok(out) } else { Err(rc) }
    }
}

impl Drop for Stats {
    fn drop(&mut self) {
        unsafe { vtest_stats_destroy(self.raw) }
    }
}

fn main() {
    let ver = unsafe { vtest_stats_version() };
    assert!(ver >= 1, "version check failed");

    let mut s = Stats::new().expect("create failed");
    s.add(2.0).expect("add ok");
    s.add(4.0).expect("add ok");
    s.add(6.0).expect("add ok");
    let (n, m) = (s.count().unwrap(), s.mean().unwrap());
    assert_eq!(n, 3);
    assert!((m - 4.0).abs() < 1e-9);

    // 错误路径：空对象 mean → Err(VTEST_ERR_EMPTY)，Drop 自动归还两个对象
    let err = Stats::new().expect("create").mean().unwrap_err();
    assert_eq!(err, VTEST_ERR_EMPTY);

    println!("rust FFI OK: count={n} mean={m:.1} empty_err={err}");
}
