//! ph25 ex07：pyo3 Python 加速模块（兑现 ph23 技能复用）
//!
//! 把 ph19 字节纪律（length-prefix frame 解析）与 ex05 的向量距离热路径
//! 暴露给 Python：`parse_frames` 把 `[len u32 小端][payload]*` 的字节流切成
//! payload 列表（长度不足/非法即抛 `ValueError`，不在边界上 panic）；`l2_distance`
//! 与 `bruteforce_topk` 用 Rust 算 L2 距离与暴力 top-k——计算循环全在 Rust，
//! Python 只做参数准备与结果消费（hot loop 不在解释器里跑）。
//!
//! 构建用 **abi3**（`abi3-py311`）：产物不链接 libpython，可在 3.11+ 任意解释器
//! 加载——本环境 3.13.12 的 sysconfig LIBDIR 指向不存在的 `/install/lib`
//! （可重定位 Python 构建），abi3 恰好绕开该问题（见 examples/README 说明）。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）+ Python 3.13.12
//!   （/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3）
//! - 构建：`cargo build --release`（pyo3 0.23.5 需联网拉取；macOS 下
//!   `.cargo/config.toml` 提供 `-undefined dynamic_lookup`，产物不链接 libpython）
//! - 验证：`PYTHONPATH=<so 所在目录> <python3.13> verify.py`（正确性 + 热路径对照）
//!   —— pyo3 extension-module crate 的 `cargo test` 需要嵌入解释器符号，
//!   本环境为可重定位 Python 不便嵌入，故测试走 Python 侧（verify.py 已验证）。
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04：构建成功 + Python 3.13 实际 import 调用）

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;

/// 把一个 length-prefix frame 字节流切成 payload 列表。
///
/// 帧格式（小端）：`[len: u32][payload len 字节]*`。这是 ph19 字节纪律的
/// Python 出口：长度字段来自不可信输入，先校验再切，坏了抛错而不是越界。
#[pyfunction]
fn parse_frames(data: &[u8]) -> PyResult<Vec<&[u8]>> {
    let mut frames = Vec::new();
    let mut pos = 0usize;
    while pos < data.len() {
        if data.len() - pos < 4 {
            return Err(PyValueError::new_err(format!(
                "偏移 {pos}：剩余 {} 字节不足一个 4 字节长度前缀（残尾）",
                data.len() - pos
            )));
        }
        let len =
            u32::from_le_bytes(data[pos..pos + 4].try_into().expect("切片长度已校验为 4")) as usize;
        pos += 4;
        if len > data.len() - pos {
            return Err(PyValueError::new_err(format!(
                "偏移 {pos}：帧声明 {len} 字节，实际只剩 {} 字节（截断/损坏）",
                data.len() - pos
            )));
        }
        frames.push(&data[pos..pos + len]);
        pos += len;
    }
    Ok(frames)
}

/// L2 距离纯函数（Rust 内部热路径，接收切片零拷贝）。
fn l2_slice(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b)
        .map(|(x, y)| (x - y) * (x - y))
        .sum::<f32>()
        .sqrt()
}

/// L2 距离（欧氏距离平方根）：Python 列表进、距离出，计算全在 Rust。
#[pyfunction]
fn l2_distance(a: Vec<f32>, b: Vec<f32>) -> PyResult<f32> {
    if a.len() != b.len() {
        return Err(PyTypeError::new_err(format!(
            "两个向量维度不同：{} vs {}",
            a.len(),
            b.len()
        )));
    }
    Ok(l2_slice(&a, &b))
}

/// 暴力 top-k：对 query 在 items 里全量算距离，返回按距离升序的前 k 个下标。
/// 对应 ex05 的 `brute_topk`，作为 Python 侧热路径（Rust 循环，无解释器开销）。
#[pyfunction]
fn bruteforce_topk(query: Vec<f32>, items: Vec<Vec<f32>>, k: usize) -> PyResult<Vec<usize>> {
    if items.is_empty() {
        return Ok(Vec::new());
    }
    if items.iter().any(|v| v.len() != query.len()) {
        return Err(PyTypeError::new_err(
            "items 中存在与 query 维度不一致的向量",
        ));
    }
    let mut scored: Vec<(f32, usize)> = items
        .iter()
        .enumerate()
        .map(|(i, v)| (l2_slice(&query, v), i))
        .collect();
    scored.sort_by(|a, b| a.0.total_cmp(&b.0));
    Ok(scored.into_iter().take(k).map(|(_, i)| i).collect())
}

/// 模块注册：`import ph25_accel` 后可调用上述三个函数。
#[pymodule]
fn ph25_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_frames, m)?)?;
    m.add_function(wrap_pyfunction!(l2_distance, m)?)?;
    m.add_function(wrap_pyfunction!(bruteforce_topk, m)?)?;
    m.add("__version__", "0.1.0")?;
    Ok(())
}
