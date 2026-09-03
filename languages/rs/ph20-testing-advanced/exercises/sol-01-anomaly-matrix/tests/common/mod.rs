//! sol-01 公共辅助：.hex 数据夹具解码（与 examples/ex02 同款约定：# 注释行 + 十六进制）。
#![allow(dead_code)]

use std::fs;
use std::path::{Path, PathBuf};

/// 夹具目录：相对 Cargo.toml（CARGO_MANIFEST_DIR），任何工作目录可跑。
pub fn fixtures_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures")
}

/// 解码一个 .hex 夹具：去掉 `#` 注释与空白后按字节十六进制解析。
pub fn decode_hex_fixture(name: &str) -> Vec<u8> {
    let path = fixtures_dir().join(name);
    let text = fs::read_to_string(&path).unwrap_or_else(|e| panic!("读夹具 {path:?}：{e}"));
    let compact: String = text
        .lines()
        .filter(|l| !l.trim_start().starts_with('#'))
        .flat_map(str::chars)
        .filter(|c| !c.is_whitespace())
        .collect();
    assert!(
        compact.len().is_multiple_of(2),
        "夹具 {name} 含奇数个 hex 字符"
    );
    (0..compact.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&compact[i..i + 2], 16)
                .unwrap_or_else(|e| panic!("夹具 {name} 非法 hex：{e}"))
        })
        .collect()
}
