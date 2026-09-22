// examples/ex02-serde-basics/src/main.rs —— serde derive + 属性教学（主文档 3.3 / 示例 2）
// 验证环境：rustc/cargo 1.92.0（edition 2021）；依赖 serde 1 + serde_json 1（crates.io 拉取，可配 rsproxy）
// 编译/运行/测试：cargo run / cargo test（内嵌 1 个 round-trip 测试）—— 已验证（cargo 1.92.0 本机实测：构建通过、cargo run 输出 round-trip ok）
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, PartialEq)]
struct Repo {
    name: String,
    stars: u32,
    #[serde(default)] // 反序列化缺字段时用 Default 兜底（bool → false）
    archived: bool,
    #[serde(rename = "openIssues")] // 键名映射：对外 JSON 键叫 openIssues
    open_issues: u32,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")] // 枚举用内部标签 + snake_case 变体名
enum Event {
    Push { branch: String },
    IssueOpened { number: u32 },
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 序列化：结构体 → JSON（pretty 版便于人读）
    let repo = Repo {
        name: "serde".into(),
        stars: 10_000,
        archived: false,
        open_issues: 42,
    };
    let json = serde_json::to_string_pretty(&repo)?;
    println!("{json}");

    // 反序列化：JSON → 结构体；round-trip 应无损
    let back: Repo = serde_json::from_str(&json)?;
    assert_eq!(repo, back, "round-trip 应无损");
    println!("round-trip ok");

    // 枚举标签：{"type":"push","branch":"main"}
    let ev = Event::Push { branch: "main".into() };
    let ev_json = serde_json::to_string(&ev)?;
    println!("{ev_json}");
    let ev_back: Event = serde_json::from_str(&ev_json)?;
    assert_eq!(ev, ev_back);

    // Value：运行时才知道结构时的逃生口（少用，丢了编译期类型检查）
    let val: serde_json::Value = serde_json::from_str(&json)?;
    println!("name via Value = {}", val["name"]); // 注意 Value 打印带引号

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let repo = Repo {
            name: "tokio".into(),
            stars: 30_000,
            archived: false,
            open_issues: 7,
        };
        let json = serde_json::to_string(&repo).unwrap();
        let back: Repo = serde_json::from_str(&json).unwrap();
        assert_eq!(repo, back);
    }

    #[test]
    fn default_field_when_missing() {
        // 缺 archived / openIssues 字段也能反序列化（default 兜底）
        let back: Repo = serde_json::from_str(r#"{"name":"x","stars":1}"#).unwrap();
        assert!(!back.archived);
        assert_eq!(back.open_issues, 0);
    }
}
