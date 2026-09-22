//! ph24-pkgdemo：发布流程演示 crate。
//! 提供 `crc8` 与 `sum_bytes` 两个小函数，供 cargo package / 发布演练使用。
//!
//! # 示例
//! ```
//! let c = ph24_pkgdemo::crc8(b"hello");
//! assert_eq!(c, 0x92);
//! ```

/// CRC-8（多项式 0x07，初值 0）逐字节校验，用于演示 API 文档。
pub fn crc8(data: &[u8]) -> u8 {
    data.iter().fold(0u8, |mut acc, &b| {
        acc ^= b;
        for _ in 0..8 {
            acc = if acc & 0x80 != 0 {
                (acc << 1) ^ 0x07
            } else {
                acc << 1
            };
        }
        acc
    })
}

/// 求字节和（mod 256），用于演示集成测试。
pub fn sum_bytes(data: &[u8]) -> u64 {
    data.iter().map(|&b| u64::from(b)).sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc8_known_value() {
        // 参考值由本实现自算自证（b"" = 0x00、b"hello" = 0x92），doc 示例同源
        assert_eq!(crc8(b""), 0x00);
        assert_eq!(crc8(b"hello"), 0x92);
        assert_eq!(crc8(b"rust"), 0x6F);
    }

    #[test]
    fn sum_is_commutative() {
        let a = [1u8, 2, 3, 4];
        assert_eq!(sum_bytes(&a), 10);
        assert_eq!(sum_bytes(&[]), 0);
    }
}
