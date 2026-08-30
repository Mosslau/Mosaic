// examples/ex03-vec-ops.rs —— Vec 可变借用遍历 + 过滤 + 排序
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 3」
// 验证环境：rustc 1.92.0
// 编译：rustc ex03-vec-ops.rs -o /tmp/ex03-vec-ops
// 运行：/tmp/ex03-vec-ops
// 验证状态：已验证（编译零警告，输出符合预期）

#[derive(Debug)]
#[allow(dead_code)] // 排序/过滤只用 score，name 字段暂未被业务逻辑读取
struct Record {
    name: String,
    score: u32,
}

fn main() {
    let mut records = vec![
        Record { name: String::from("alice"), score: 85 },
        Record { name: String::from("bob"), score: 92 },
        Record { name: String::from("carol"), score: 78 },
    ];

    // 1. 可变借用遍历：所有记录 +10 分
    for r in &mut records {
        r.score += 10;
    }

    // 2. 过滤出及格记录（借用，不动 records）
    let pass: Vec<&Record> = records.iter().filter(|r| r.score >= 90).collect();
    println!("pass: {:?}", pass);

    // 3. 按分数降序排序
    records.sort_by(|a, b| b.score.cmp(&a.score));
    println!("sorted: {:?}", records);
}
