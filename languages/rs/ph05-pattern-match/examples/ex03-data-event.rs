// examples/ex03-data-event.rs —— 数据事件处理器：五种事件类型 match 穷尽分发，matches! 统计分布
// 来源：05-pattern-match.md 第 6 章示例 3（roadmap ph05 推荐项目原型）
// 验证环境：rustc 1.92.0，零第三方依赖
// 编译：rustc ex03-data-event.rs -o /tmp/ex03-data-event
// 运行：/tmp/ex03-data-event
// 验证状态：已验证（rustc 1.92.0）

/// 数据平台的五种事件类型：写入、删除、更新、过期、告警。
#[derive(Debug)]
enum DataEvent {
    Write { key: String, value: Vec<u8> },
    Delete { key: String },
    Update { key: String, value: Vec<u8>, old_version: u64 },
    Expire { key: String, at: u64 },
    Alert { level: String, message: String },
}

/// 逐事件处理：match 穷尽覆盖全部五种变体，为每种事件生成不同日志。
fn process(event: &DataEvent) {
    match event {
        DataEvent::Write { key, value } =>
            println!("写入: key={}, 大小={}B", key, value.len()),
        DataEvent::Delete { key } =>
            println!("删除: key={}", key),
        DataEvent::Update { key, value, old_version } =>
            println!("更新: key={}, 大小={}B, 旧版本={}", key, value.len(), old_version),
        DataEvent::Expire { key, at } =>
            println!("过期: key={}, 过期时间={}", key, at),
        DataEvent::Alert { level, message } => {
            let prefix = if level == "critical" { "!! 严重" } else { "  提示" };
            println!("{} [{}]: {}", prefix, level, message);
        }
    }
}

fn main() {
    let events = vec![
        DataEvent::Write { key: "user:1".into(), value: vec![1, 2, 3] },
        DataEvent::Update { key: "user:1".into(), value: vec![4, 5, 6], old_version: 1 },
        DataEvent::Delete { key: "temp:99".into() },
        DataEvent::Expire { key: "session:42".into(), at: 1_723_159_200 },
        DataEvent::Alert { level: "critical".into(), message: "磁盘空间不足".into() },
    ];
    for event in &events {
        process(event);
    }
    // matches! 统计：只计数 Write 变体，不关心其携带数据
    let write_count = events.iter()
        .filter(|e| matches!(e, DataEvent::Write { .. }))
        .count();
    println!("Write 事件数: {}", write_count);
}
