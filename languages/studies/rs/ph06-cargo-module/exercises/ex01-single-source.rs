// exercises/ex01-single-source.rs —— 练习 1 起点：单文件温度记录统计程序（待拆分）
// 输入格式：每行 "ts\tcity\ttemp"（制表符分隔）
// 验证环境：rustc 1.92.0，纯标准库
// 编译：rustc ex01-single-source.rs -o /tmp/ex01-single-source
// 运行：/tmp/ex01-single-source
// 练习目标：把它拆成 model / parser / service 三层多文件结构，行为不变
// 验证状态：已验证（rustc 1.92.0）

use std::collections::BTreeMap;

struct CityTemp {
    ts: u64,
    city: String,
    temp: f64,
}

fn parse_line(line: &str) -> Option<CityTemp> {
    let mut parts = line.split('\t');
    let ts = parts.next()?.parse().ok()?;
    let city = parts.next()?.to_string();
    let temp = parts.next()?.parse().ok()?;
    Some(CityTemp { ts, city, temp })
}

fn parse_all(input: &str) -> Vec<CityTemp> {
    input.lines().filter_map(parse_line).collect()
}

fn avg_by_city(records: &[CityTemp]) -> BTreeMap<String, f64> {
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

fn main() {
    let input = "1700000000\tbeijing\t25.5\n1700000100\tshanghai\t28.0\n\
                 1700000200\tbeijing\t26.5\n1700000300\tshanghai\t27.5";
    let records = parse_all(input);
    println!("总记录数: {}", records.len());
    let earliest = records.iter().map(|r| r.ts).min();
    if let Some(ts) = earliest {
        println!("最早时间戳: {}", ts);
    }
    for (city, avg) in avg_by_city(&records) {
        println!("{}: {:.1}", city, avg);
    }
}
