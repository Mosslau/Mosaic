// exercises/sol-01-split-project/src/service.rs —— 练习 1 参考实现：聚合服务层
// 拆分自 exercises/ex01-single-source.rs 的 avg_by_city
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-01-split-project/ 目录内执行）
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use crate::model::CityTemp;
use std::collections::BTreeMap;

pub fn avg_by_city(records: &[CityTemp]) -> BTreeMap<String, f64> {
    let mut sum = BTreeMap::new();
    let mut count = BTreeMap::new();
    for r in records {
        *sum.entry(r.city.clone()).or_insert(0.0) += r.temp;
        *count.entry(r.city.clone()).or_insert(0usize) += 1;
    }
    sum.into_iter()
        .map(|(c, s)| {
            let n = count[&c] as f64; // 先借用（此时 c 尚未移动）
            (c, s / n)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::CityTemp;

    fn record(ts: u64, city: &str, temp: f64) -> CityTemp {
        CityTemp { ts, city: city.to_string(), temp }
    }

    #[test]
    fn avg_by_city_computes_means() {
        let records = vec![
            record(1, "beijing", 25.5),
            record(2, "beijing", 26.5),
            record(3, "shanghai", 28.0),
        ];
        let avgs = avg_by_city(&records);
        assert!((avgs["beijing"] - 26.0).abs() < 1e-9);
        assert!((avgs["shanghai"] - 28.0).abs() < 1e-9);
    }

    #[test]
    fn avg_by_city_empty_input() {
        assert!(avg_by_city(&[]).is_empty());
    }
}
