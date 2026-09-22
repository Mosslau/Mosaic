// 来源：languages/rs/ph15-macros-metaprogramming/exercises/README.md 练习 4
// 说明：serde derive 序列化练习（roadmap 练习「用 serde derive 生成序列化代码」落地）——
//       为「页面分析事件」建模（嵌套结构体 + 外标签 enum），derive 序列化/反序列化并断言。
//       struct 用 rename_all = "snake_case"；enum 外标签形态（externally tagged，
//       variant 名做外层键）；referrer 字段 #[serde(default)]（缺失字段用 Default）。
// 验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 + serde_json 1.0.151（rsproxy 拉取，Cargo.lock 锁定）
// 编译/运行（在 exercises/crates 目录）：
//   CARGO_TARGET_DIR=/tmp/ph15-exercises-target cargo run --bin sol-04-serde-derive
// 验证状态：已验证（编译零警告；下方输出为实测）
//
// 实测输出：
//   1. {"page_view":{"user_id":7,"page":"/rust/macros","duration_ms":1200,"referrer":"https://example.com"}}
//   2. {"page_view":{"user_id":8,"page":"/home","duration_ms":300,"referrer":""}}
//   3. {"signup":{"user_id":9,"plan":"pro"}}
//   4. 反序列化往返一致 = true
//   5. 缺失 referrer 字段: referrer = ""（#[serde(default)] 生效）
//   断言通过：序列化文本、往返一致性、default 行为全部符合预期

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
struct PageView {
    user_id: u64,
    page: String,
    duration_ms: u32,
    // 缺失字段时用 Default::default()（String 的空串）——老数据可以缺这个字段
    #[serde(default)]
    referrer: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Event {
    PageView(PageView), // 外标签：JSON 里以 variant 名（page_view）为键
    Signup { user_id: u64, plan: String },
}

fn main() {
    let events = vec![
        Event::PageView(PageView {
            user_id: 7,
            page: "/rust/macros".into(),
            duration_ms: 1200,
            referrer: "https://example.com".into(),
        }),
        Event::PageView(PageView {
            user_id: 8,
            page: "/home".into(),
            duration_ms: 300,
            referrer: String::new(),
        }),
        Event::Signup {
            user_id: 9,
            plan: "pro".into(),
        },
    ];

    // 1~3. 序列化：每个事件一行 JSON（derive 生成代码的输出可精确断言）
    let jsons: Vec<String> = events
        .iter()
        .map(|e| serde_json::to_string(e).unwrap())
        .collect();
    for (i, j) in jsons.iter().enumerate() {
        println!("{}. {j}", i + 1);
    }
    assert_eq!(
        jsons[0],
        r#"{"page_view":{"user_id":7,"page":"/rust/macros","duration_ms":1200,"referrer":"https://example.com"}}"#
    );
    assert_eq!(
        jsons[2],
        r#"{"signup":{"user_id":9,"plan":"pro"}}"#
    );

    // 4. 反序列化往返
    let back: Event = serde_json::from_str(&jsons[0]).unwrap();
    println!("4. 反序列化往返一致 = {}", back == events[0]);
    assert_eq!(back, events[0]);

    // 5. 缺失 referrer 字段：default 兜底
    let json_missing = r#"{"page_view":{"user_id":10,"page":"/p","duration_ms":5}}"#;
    let ev: Event = serde_json::from_str(json_missing).unwrap();
    let referrer = match ev {
        Event::PageView(pv) => pv.referrer.clone(),
        _ => unreachable!("这个 JSON 只能是 PageView"),
    };
    println!("5. 缺失 referrer 字段: referrer = {referrer:?}（#[serde(default)] 生效）");
    assert_eq!(referrer, "");

    println!("断言通过：序列化文本、往返一致性、default 行为全部符合预期");
}
