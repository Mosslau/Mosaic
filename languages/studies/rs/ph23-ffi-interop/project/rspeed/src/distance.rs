//! 向量距离计算：纯 Rust 核心，被 pyo3 绑定层薄封装（src/lib.rs）。
//!
//! 教学点：返回 `Option<f64>` 而不是 `f64`——长度不一致、空向量、零向量在
//! 「没有结果」上是一致的，用 None 表达；绑定层再把 None 翻译成 Python 异常。
//! 这也是 rust-patterns 的「Parse, don't validate」在数值 API 的体现：先校验、后计算。
//! 验证环境：cargo/rustc 1.92.0；本机实测「已验证」。

/// 余弦相似度。任一输入为空、长度不一致或范数为零时返回 None。
pub fn cosine_similarity_inner(a: &[f64], b: &[f64]) -> Option<f64> {
    if a.is_empty() || a.len() != b.len() {
        return None;
    }
    let mut dot = 0.0;
    let mut na = 0.0;
    let mut nb = 0.0;
    for (x, y) in a.iter().zip(b) {
        dot += x * y;
        na += x * x;
        nb += y * y;
    }
    if na == 0.0 || nb == 0.0 {
        return None; // 零向量没有「方向」，余弦无定义
    }
    Some(dot / (na * nb).sqrt())
}

/// 欧氏距离。任一输入为空或长度不一致时返回 None。
pub fn euclidean_inner(a: &[f64], b: &[f64]) -> Option<f64> {
    if a.is_empty() || a.len() != b.len() {
        return None;
    }
    Some(
        a.iter()
            .zip(b)
            .map(|(x, y)| (x - y) * (x - y))
            .sum::<f64>()
            .sqrt(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-12
    }

    #[test]
    fn cosine_same_and_orthogonal() {
        let v = [1.0, 2.0, 3.0];
        assert!(approx(cosine_similarity_inner(&v, &v).unwrap(), 1.0));
        assert!(approx(
            cosine_similarity_inner(&[1.0, 0.0, 0.0], &[0.0, 1.0, 0.0]).unwrap(),
            0.0
        ));
    }

    #[test]
    fn cosine_matches_definition() {
        let a = [3.0, 4.0, 0.0];
        let b = [0.0, 1.0, 0.0];
        let got = cosine_similarity_inner(&a, &b).unwrap();
        let want = (3.0 * 0.0 + 4.0 * 1.0) / (5.0 * 1.0);
        assert!(approx(got, want));
    }

    #[test]
    fn invalid_inputs_return_none() {
        assert_eq!(cosine_similarity_inner(&[], &[]), None);
        assert_eq!(cosine_similarity_inner(&[1.0], &[1.0, 2.0]), None);
        assert_eq!(cosine_similarity_inner(&[0.0, 0.0], &[1.0, 1.0]), None);
        assert_eq!(euclidean_inner(&[], &[1.0]), None);
        assert_eq!(euclidean_inner(&[1.0], &[1.0, 2.0]), None);
    }

    #[test]
    fn euclidean_known_value() {
        assert!(approx(
            euclidean_inner(&[0.0, 0.0], &[3.0, 4.0]).unwrap(),
            5.0
        ));
        assert!(approx(
            euclidean_inner(&[1.0, 2.0], &[1.0, 2.0]).unwrap(),
            0.0
        ));
    }

    #[test]
    fn large_vectors_agree_with_naive_sum() {
        // 与显式循环的参考实现对照（防迭代器/融合引入偏差）
        let n = 100_000;
        let a: Vec<f64> = (0..n).map(|i| i as f64 * 0.001).collect();
        let b: Vec<f64> = (0..n).map(|i| (n - i) as f64 * 0.0005).collect();
        let mut naive = 0.0f64;
        for i in 0..n {
            naive += a[i] * b[i];
        }
        assert!(approx(
            cosine_similarity_inner(&a, &b).unwrap(),
            naive
                / (a.iter().map(|x| x * x).sum::<f64>() * b.iter().map(|x| x * x).sum::<f64>())
                    .sqrt()
        ));
    }
}
