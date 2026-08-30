// exercises/sol-03-unit-tests/src/lib.rs —— 练习 3 参考实现：为库 crate 编写单元测试
// 整数统计库：sum / avg / min / max，空输入返回 Option::None
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-03-unit-tests/ 目录内执行）
// 测试：cargo test
// 质量门禁：cargo fmt --check && cargo clippy -- -D warnings && cargo test
// 验证状态：已验证（rustc 1.92.0）

pub fn sum(nums: &[i64]) -> i64 {
    nums.iter().sum()
}

pub fn avg(nums: &[i64]) -> Option<i64> {
    if nums.is_empty() {
        return None;
    }
    Some(sum(nums) / nums.len() as i64)
}

pub fn min(nums: &[i64]) -> Option<i64> {
    nums.iter().copied().min()
}

pub fn max(nums: &[i64]) -> Option<i64> {
    nums.iter().copied().max()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sum_normal() {
        assert_eq!(sum(&[1, 2, 3]), 6);
        assert_eq!(sum(&[-1, -2, 3]), 0);
    }

    #[test]
    fn sum_single() {
        assert_eq!(sum(&[42]), 42);
    }

    #[test]
    fn avg_normal() {
        assert_eq!(avg(&[2, 4, 6]), Some(4));
    }

    #[test]
    fn avg_single() {
        assert_eq!(avg(&[7]), Some(7));
    }

    #[test]
    fn avg_negative() {
        assert_eq!(avg(&[-4, -6]), Some(-5));
    }

    #[test]
    fn min_max_normal() {
        assert_eq!(min(&[3, 1, 2]), Some(1));
        assert_eq!(max(&[3, 1, 2]), Some(3));
    }

    #[test]
    fn empty_input_returns_none() {
        let empty: [i64; 0] = [];
        assert_eq!(avg(&empty), None);
        assert_eq!(min(&empty), None);
        assert_eq!(max(&empty), None);
    }
}
