// exercises/sol-04-iflet-whilelet-matches.rs —— 练习 4 参考实现：if let / while let / matches! 精简
// 来源：exercises/README.md 练习 4
// 验证环境：rustc 1.92.0
// 编译：rustc sol-04-iflet-whilelet-matches.rs -o /tmp/sol-04-iflet-whilelet-matches
// 运行：/tmp/sol-04-iflet-whilelet-matches
// 验证状态：已验证（rustc 1.92.0）

/// 本地事件枚举：只关心 Write 时，其余变体静默跳过。
#[derive(Debug)]
enum Event {
    Write(String, i32),
    Delete(String),
    Expire(String),
}

fn main() {
    let events = vec![
        Event::Write("a".into(), 1),
        Event::Delete("b".into()),
        Event::Write("c".into(), 2),
        Event::Expire("d".into()),
    ];

    // 1. if let —— 只处理 Write，其余变体不匹配即跳过（等价于单分支 match）
    for e in &events {
        if let Event::Write(key, size) = e {
            println!("[if let] 写入 {}: {}B", key, size);
        }
    }

    // 1b. match —— 需要处理全部变体时用 match（穷尽性检查兜底），
    //     这里读出 Delete/Expire 的 key，与上面的 if let 形成对比
    for e in &events {
        match e {
            Event::Write(key, _) => println!("[match]  write   {}", key),
            Event::Delete(key) => println!("[match]  delete  {}", key),
            Event::Expire(key) => println!("[match]  expire  {}", key),
        }
    }

    // 2. while let —— 持续 pop 直到栈空（等价于 loop + match break）
    let mut stack: Vec<&str> = vec!["c", "b", "a"];
    println!("[while let] 出栈:");
    while let Some(top) = stack.pop() {
        println!("  pop {}", top);
    }

    // 3. matches! —— 一行 bool 统计各类型事件个数
    let write_count = events.iter().filter(|e| matches!(e, Event::Write(..))).count();
    let expire_count = events.iter().filter(|e| matches!(e, Event::Expire(_))).count();
    println!("\nWrite 事件 {} 个, Expire 事件 {} 个", write_count, expire_count);

    // 断言验证
    assert_eq!(write_count, 2);
    assert_eq!(expire_count, 1);
    assert!(stack.is_empty());
    println!("全部断言通过");
}
