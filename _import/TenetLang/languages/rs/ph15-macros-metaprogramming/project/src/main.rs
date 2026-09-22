// 来源：languages/rs/ph15-macros-metaprogramming/project/README.md
// 说明：event-hub demo——自包含验收：宏定义新事件（跨 crate 使用 #[macro_export]）、
//       统一打印（宏生成 render()）、统一序列化（serde derive 内部标签）、反序列化往返、
//       未知 kind 报错（thiserror derive 错误类型）。
// 验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 + serde_json 1.0.151 + thiserror 2.0.20
//          （rsproxy 拉取，Cargo.lock 锁定）
// 编译/运行（在 project 目录）：
//   CARGO_TARGET_DIR=/tmp/ph15-project-target cargo run
// 验证状态：已验证（编译零警告；输出为实测）

use event_hub::{define_events, Event, HubError, HubEvent, Login, OrderPlaced, PaymentFailed};

// 用宏在「使用方 crate」（main 二进制）再定义一类新事件：
// 演示 #[macro_export] 导出的宏跨 crate 可用；impl $crate::Event 的路径由 $crate 保证。
define_events! {
    DownloadFinished => "download_finished" {
        file: String,
        bytes: u64,
    },
}

fn main() {
    // 1. 统一打印：宏为每类事件生成的 render()
    println!("== 1. 统一打印（define_events! 生成 render()）==");
    let events: Vec<Box<dyn Event>> = vec![
        Box::new(Login {
            user: "ada".into(),
            ok: true,
        }),
        Box::new(OrderPlaced {
            order_id: 9001,
            amount: 2,
        }),
        Box::new(PaymentFailed {
            order_id: 9001,
            reason: "insufficient_funds".into(),
        }),
        Box::new(DownloadFinished {
            file: "/tmp/rust.tar.gz".into(),
            bytes: 12345,
        }),
    ];
    for e in &events {
        println!("  {}", e.render());
    }
    assert_eq!(events[0].kind(), "login");
    assert_eq!(events[3].kind(), "download_finished");

    // 2. 统一序列化：serde derive 内部标签（kind 字段自动生成，与宏的 kind() 一致）
    println!("== 2. 统一序列化（HubEvent 内部标签 kind）==");
    let hub_events = vec![
        HubEvent::Login(Login {
            user: "ada".into(),
            ok: true,
        }),
        HubEvent::OrderPlaced(OrderPlaced {
            order_id: 9001,
            amount: 2,
        }),
        HubEvent::PaymentFailed(PaymentFailed {
            order_id: 9001,
            reason: "insufficient_funds".into(),
        }),
    ];
    let jsons: Vec<String> = hub_events
        .iter()
        .map(|e| serde_json::to_string(e).unwrap())
        .collect();
    for (i, j) in jsons.iter().enumerate() {
        println!("  {}. {j}", i + 1);
    }
    assert_eq!(
        jsons[0],
        r#"{"kind":"login","user":"ada","ok":true}"#
    );

    // 3. 反序列化往返：JSON -> HubEvent -> 断言一致
    println!("== 3. 反序列化往返 ==");
    let back: HubEvent = serde_json::from_str(&jsons[0]).unwrap();
    println!("  round-trip 一致 = {}", back == hub_events[0]);
    assert_eq!(back, hub_events[0]);

    // 4. 未知 kind：serde 报错 -> #[from] 自动转成 HubError::Json
    println!("== 4. 未知 kind 报错（thiserror derive 错误类型）==");
    match serde_json::from_str::<HubEvent>(r#"{"kind":"nuke","user":"x"}"#) {
        Err(e) => {
            let err = HubError::from(e); // From<serde_json::Error> 由 #[from] 生成
            println!("  {err}");
            assert!(matches!(err, HubError::Json(_)));
        }
        Ok(_) => panic!("未知 kind 竟然解析成功了"),
    }

    // 5. HubEvent::render 分发到宏生成的 render()
    println!("== 5. HubEvent 分发打印 ==");
    println!("  {}", hub_events[1].render());
    assert_eq!(hub_events[1].render(), "[order_placed] order_id=9001 amount=2");

    println!("\ndemo 断言全部通过");
}
