//! ex04：bindgen 从 C 头文件生成 Rust 绑定。
//!
//! 教学要点（对应主文档 3.8）：
//! - bindgen 扫描的是「普通 C 头文件」，生成的绑定长什么样由头文件决定；
//! - 生成物是 `unsafe extern "C" fn` 的裸声明（外加类型/常量），**必须**再包一层
//!   安全 API 才能给业务代码用——bindgen 管「翻译」，安全封装管「不变量」；
//! - 验证方式：同一批向量用 C 实现与纯 Rust 实现各算一遍，断言结果一致，
//!   证明绑定真的在调 C 库而不是「碰巧长得像」。
//!
//! 验证环境：cargo/rustc 1.92.0 + bindgen 0.71.1 + Apple clang 21.0.0；本机实测「已验证」。

// bindgen 生成的绑定是给机器看的，命名风格跟随 C 头文件，这里整体放行 lint。
#![allow(non_snake_case, non_camel_case_types, dead_code)]

/// 构建期由 build.rs 生成：include!(OUT_DIR/bindings.rs)
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

/// 安全封装层：不变量（长度相等、指针有效）在进入 unsafe 前全部检查完毕。
/// 一旦进入 bindgen 生成的 `vm_dot` 调用，soundness 就由这里的检查背书。
pub fn dot(a: &[f64], b: &[f64]) -> Option<f64> {
    if a.len() != b.len() {
        return None; // C 侧对长度不匹配无防护，这是 Rust 封装层的职责
    }
    // SAFETY: bindgen 保证签名匹配 C 声明；a/b 的裸指针由切片借用提供，
    // 长度相等且都 ≥ 0；调用期间切片仍被借用持有，C 侧只读。
    Some(unsafe { bindings::vm_dot(a.as_ptr(), b.as_ptr(), a.len()) })
}

/// 安全封装：欧氏距离。空切片在 C 侧返回 sqrt(0)=0，此处按约定也接受空输入。
pub fn euclidean(a: &[f64], b: &[f64]) -> Option<f64> {
    if a.len() != b.len() {
        return None;
    }
    // SAFETY: 同上，C 侧只读传入切片。
    Some(unsafe { bindings::vm_euclidean(a.as_ptr(), b.as_ptr(), a.len()) })
}

/// 纯 Rust 参考实现：用于验证绑定确实在调 C 实现。
fn dot_pure(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

fn euclidean_pure(a: &[f64], b: &[f64]) -> f64 {
    a.iter()
        .zip(b)
        .map(|(x, y)| (x - y) * (x - y))
        .sum::<f64>()
        .sqrt()
}

fn main() {
    // 模拟一个向量查询：query vs 两段 doc 向量
    let q = [1.0, 2.0, 3.0, 4.0];
    let d1 = [4.0, 3.0, 2.0, 1.0];
    let d2 = [0.5, 1.5, 2.5, 3.5];

    for (i, doc) in [&d1[..], &d2[..]].iter().enumerate() {
        let d = dot(&q, doc).expect("长度一致");
        let e = euclidean(&q, doc).expect("长度一致");
        // 与纯 Rust 实现对照，证明绑定调用的是同一份数学
        assert_eq!(d, dot_pure(&q, doc));
        assert_eq!(e, euclidean_pure(&q, doc));
        println!("doc{i}: dot={d:.4} euclidean={e:.4} (C 实现经 bindgen 调用)");
    }
    println!("bindgen 绑定与纯 Rust 参考实现结果一致，验证通过");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bound_c_math_matches_pure_rust() {
        let a: Vec<f64> = (0..1000).map(|i| i as f64 * 0.5).collect();
        let b: Vec<f64> = (0..1000).map(|i| 1000.0 - i as f64).collect();
        assert_eq!(dot(&a, &b), Some(dot_pure(&a, &b)));
        assert_eq!(euclidean(&a, &b), Some(euclidean_pure(&a, &b)));
    }

    #[test]
    fn mismatched_length_returns_none_without_ub() {
        assert_eq!(dot(&[1.0], &[1.0, 2.0]), None);
        assert_eq!(euclidean(&[], &[1.0]), None);
    }

    #[test]
    fn empty_slices_are_ok() {
        assert_eq!(dot(&[], &[]), Some(0.0)); // Σ 空 = 0
        assert_eq!(euclidean(&[], &[]), Some(0.0));
    }
}
