//! rspeed —— ph23 综合项目：为 Python 提供向量距离计算与 RAG chunk 处理的加速库。
//!
//! 架构（roadmap 第 23 节「Rust 加速库」推荐项目的落地形态）：
//! - **核心层**：`distance` / `chunk` 两个纯 Rust 模块，零依赖、可被 `cargo test` 全覆盖；
//! - **绑定层**：`#[cfg(feature = "python")]` 门控的 pyo3 包装——Python 可见的只是
//!   一层薄封装，核心算法与绑定解耦（与 ex04/ex06 的「安全封装」纪律一致）。
//!
//! 加速对象的取舍（对应主文档 5 节「何时用 FFI」）：
//! - 向量距离：逐元素浮点运算，Python 逐元素循环的解释开销远大于算术本身——典型加速点；
//! - RAG chunk：文本切分在 Python 里要逐字符决策，交给 Rust 后 Python 侧只剩一次调用。
//!
//! 验证环境：cargo/rustc 1.92.0 + pyo3 0.23.5 + Python 3.13.12；本机实测「已验证」。

pub mod chunk;
pub mod distance;

#[cfg(feature = "python")]
mod pybind {
    use crate::chunk::{chunk_text_inner, ChunkError};
    use crate::distance::{cosine_similarity_inner, euclidean_inner};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    /// 余弦相似度。核心层返回 Option（长度不一致/零向量 → None），
    /// 绑定层把 None 翻译成 Python 的 ValueError——Rust 侧不 panic。
    #[pyfunction]
    fn cosine_similarity(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
        cosine_similarity_inner(&a, &b).ok_or_else(|| {
            PyValueError::new_err("vectors must be non-empty, same length, and non-zero")
        })
    }

    /// 欧氏距离。
    #[pyfunction]
    fn euclidean(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
        euclidean_inner(&a, &b)
            .ok_or_else(|| PyValueError::new_err("vectors must be non-empty and same length"))
    }

    /// 字符窗口切分文本（RAG chunk 的最小形态），返回 list[str]。
    #[pyfunction]
    fn chunk_text(text: &str, chunk_size: usize, overlap: usize) -> PyResult<Vec<String>> {
        chunk_text_inner(text, chunk_size, overlap).map_err(|e: ChunkError| match e {
            ChunkError::ZeroChunkSize => PyValueError::new_err("chunk_size must be > 0"),
            ChunkError::OverlapTooLarge => PyValueError::new_err("overlap must be < chunk_size"),
        })
    }

    #[pymodule]
    fn rspeed(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(cosine_similarity, m)?)?;
        m.add_function(wrap_pyfunction!(euclidean, m)?)?;
        m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
        Ok(())
    }
}
