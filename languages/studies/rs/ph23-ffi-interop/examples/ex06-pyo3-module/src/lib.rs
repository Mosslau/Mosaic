//! ex06：pyo3 —— 把 Rust 函数包装成 Python 扩展模块。
//!
//! 教学要点（对应主文档 3.10）：
//! - `#[pyfunction]` 标记可导出函数、`#[pymodule]` 标记模块初始化函数；
//!   参数/返回值在 Python 对象与 Rust 值之间按 pyo3 的类型转换规则自动翻译。
//! - 标量（i64/f64/&str）零成本进出；`Vec<T>` 需要复制（从 Python list 拷成 Rust Vec）；
//!   GIL 与转换边界的概念见主文档 4.4。
//! - `extension-module` feature 表示「不链接 libpython」——这是给 Python 加载的
//!   扩展模块的标配；本示例刻意只暴露数值计算，不触碰会 panic 的路径
//!   （pyo3 把 Rust panic 转成 Python 异常，具体机制见主文档 3.10 的边界说明）。
//!
//! 验证环境：cargo/rustc 1.92.0 + pyo3 0.23.5 + Python 3.13.12；本机实测「已验证」。

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// 计算余弦相似度（向量维度不一致时抛 ValueError 而不是 panic）。
#[pyfunction]
fn cosine_similarity(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    if a.len() != b.len() || a.is_empty() {
        return Err(PyValueError::new_err(
            "vectors must be non-empty and same length",
        ));
    }
    let mut dot = 0.0;
    let mut na = 0.0;
    let mut nb = 0.0;
    for (x, y) in a.iter().zip(&b) {
        dot += x * y;
        na += x * x;
        nb += y * y;
    }
    if na == 0.0 || nb == 0.0 {
        return Err(PyValueError::new_err(
            "zero vector has no defined cosine similarity",
        ));
    }
    Ok(dot / (na * nb).sqrt())
}

/// 欧氏距离。
#[pyfunction]
fn euclidean(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    if a.len() != b.len() {
        return Err(PyValueError::new_err("vectors must have same length"));
    }
    Ok(a.iter()
        .zip(&b)
        .map(|(x, y)| (x - y) * (x - y))
        .sum::<f64>()
        .sqrt())
}

/// 按字符窗口切分文本（RAG chunk 的最小形态）：固定 chunk 长度 + overlap 字符重叠。
/// 返回 Vec<String>——pyo3 自动转成 Python list[str]。
#[pyfunction]
fn chunk_text(text: &str, chunk_size: usize, overlap: usize) -> PyResult<Vec<String>> {
    if chunk_size == 0 {
        return Err(PyValueError::new_err("chunk_size must be > 0"));
    }
    if overlap >= chunk_size {
        return Err(PyValueError::new_err("overlap must be < chunk_size"));
    }
    let chars: Vec<char> = text.chars().collect();
    if chars.len() <= chunk_size {
        return Ok(vec![text.to_string()]);
    }
    let step = chunk_size - overlap;
    let mut chunks = Vec::new();
    let mut start = 0;
    while start < chars.len() {
        let end = (start + chunk_size).min(chars.len());
        chunks.push(chars[start..end].iter().collect());
        if end == chars.len() {
            break;
        }
        start += step;
    }
    Ok(chunks)
}

/// 模块初始化：把上面的函数注册成 Python 模块 ex06_geo 的属性。
#[pymodule]
fn ex06_geo(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(cosine_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(euclidean, m)?)?;
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    Ok(())
}
