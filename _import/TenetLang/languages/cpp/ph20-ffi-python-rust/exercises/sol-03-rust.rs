// sol-03-rust.rs —— 练习 3 Rust 侧：extern "C" 手抄签名 + Result 翻译
// 验证环境：rustc 1.92.0（~/.cargo/bin）；前置：先编出 /tmp/libgeo.dylib
// 构建/运行（exercises/ 目录内）：
//   export PATH="$HOME/.cargo/bin:$PATH"
//   rustc -O sol-03-rust.rs -L /tmp -l geo -o /tmp/sol03
//   /tmp/sol03
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
// 教学点：手抄 extern "C" 签名（与 sol-03-geo-lib.cpp 的错误码约定逐字一致）；
//         错误码翻译成 Result<T, i32>；数组跨边界 = 指针 + 长度（&[f64] 的 as_ptr）。
const GEO_OK: i32 = 0;
const GEO_ERR_NULL: i32 = 1;
const GEO_ERR_DIM: i32 = 2;

extern "C" {
    fn geo_version() -> i32;
    fn geo_dist_l2(a: *const f64, b: *const f64, dim: i64, out: *mut f64) -> i32;
}

fn dist_l2(a: &[f64], b: &[f64]) -> Result<f64, i32> {
    assert_eq!(a.len(), b.len(), "input dims must match");
    let mut out = 0.0f64;
    let rc = unsafe { geo_dist_l2(a.as_ptr(), b.as_ptr(), a.len() as i64, &mut out) };
    if rc == GEO_OK {
        Ok(out)
    } else {
        Err(rc)
    }
}

fn main() {
    assert!(unsafe { geo_version() } >= 1, "version check failed");

    let a = [0.0f64, 0.0];
    let b = [3.0f64, 4.0];
    let d = dist_l2(&a, &b).expect("dist ok");
    assert!((d - 5.0).abs() < 1e-9);
    println!("dist_l2((0,0),(3,4)) = {d:.1}");

    // 错误路径：Rust 侧长度 0 → dim <= 0 → 错误码 2；空切片 as_ptr 也非空，
    // 但库按 dim 判定，正好演示「错误码语义由库定、Rust 只负责翻译」。
    let empty: [f64; 0] = [];
    let err = dist_l2(&empty, &empty).unwrap_err();
    assert_eq!(err, GEO_ERR_DIM);

    // 错误路径 2：空指针由库判空 → 错误码 1（NULL 检查在 C ABI 内先于 try）
    let err_null =
        unsafe { geo_dist_l2(std::ptr::null(), std::ptr::null(), 4, std::ptr::null_mut()) };
    assert_eq!(err_null, GEO_ERR_NULL);

    println!("sol-03 rust OK");
}
