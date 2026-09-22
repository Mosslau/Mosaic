// exercises/sol-03-message-dispatch.rs —— 练习 3 参考实现：match 处理不同消息类型
// 来源：exercises/README.md 练习 3（roadmap 承诺「用 match 处理不同消息类型」）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-03-message-dispatch.rs -o /tmp/sol-03-message-dispatch
// 运行：/tmp/sol-03-message-dispatch
// 验证状态：已验证（rustc 1.92.0）

/// 聊天消息的五种类型，各携带该类型所需的数据。
#[derive(Debug, Clone, PartialEq)]
enum Message {
    Text(String),
    File { name: String, size: u64 },
    Join { room: String },
    Leave,
    Quit,
}

/// 逐消息分发处理：match 穷尽覆盖全部变体（没有 `_ =>`），
/// 新增变体（如 Message::Mention）时编译器强制在此更新。
fn handle_message(msg: &Message) -> String {
    match msg {
        Message::Text(text) => format!("[text]  普通消息: {}", text),
        Message::File { name, size } => format!("[file]  文件上传: {} ({}B)", name, size),
        Message::Join { room } => format!("[join]  加入房间: {}", room),
        Message::Leave => "[leave] 离开房间".to_string(),
        Message::Quit => "[quit]  退出会话".to_string(),
    }
}

fn main() {
    let msgs = vec![
        Message::Text("hello".into()),
        Message::File { name: "a.txt".into(), size: 1024 },
        Message::Join { room: "rust-聊天室".into() },
        Message::Text("再见".into()),
        Message::Leave,
        Message::Quit,
    ];
    for m in &msgs {
        println!("{}", handle_message(m));
    }

    // matches! 统计：只计数 Text，不关心文本内容
    let text_count = msgs.iter().filter(|m| matches!(m, Message::Text(_))).count();
    println!("\nText 消息数: {}", text_count);
    assert_eq!(text_count, 2);
    println!("全部断言通过");
}
