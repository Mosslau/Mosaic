//! ph24-relpipe：安全发布流水线演示 crate（project 层）。
//!
//! 提供 crc8 / sum_bytes / checksum_hex 三个函数，作为 release-check.sh 流水线的被测对象。
//! 依赖最小集：`hex`（零传递依赖）——让 audit / deny / license 检查有真实的依赖树可扫。

/// CRC-8（多项式 0x07，初值 0）逐字节校验。
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

/// 求字节和（u64，不取模溢出由类型承载）。
pub fn sum_bytes(data: &[u8]) -> u64 {
    data.iter().map(|&b| u64::from(b)).sum()
}

/// 把字节和编码成十六进制串（使用 `hex` 依赖，演示「有第三方依赖的发布物」）。
pub fn checksum_hex(data: &[u8]) -> String {
    hex::encode(sum_bytes(data).to_le_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc8_reference() {
        assert_eq!(crc8(b""), 0x00);
        assert_eq!(crc8(b"hello"), 0x92);
    }

    #[test]
    fn sum_reference() {
        assert_eq!(sum_bytes(b"\x01\x02\x03"), 6);
        assert_eq!(sum_bytes(b""), 0);
    }

    #[test]
    fn checksum_hex_roundtrip() {
        // sum_bytes(b"\x01\x02\x03") = 6 = 0x0600000000000000（小端 8 字节）
        assert_eq!(checksum_hex(b"\x01\x02\x03"), "0600000000000000");
    }
}
