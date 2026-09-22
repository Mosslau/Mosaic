// examples/ex02-status-from-str.rs —— 字符串状态码改为 enum：from_str/as_str 双向转换，消除魔法字符串
// 来源：05-pattern-match.md 第 6 章示例 2
// 验证环境：rustc 1.92.0，零第三方依赖
// 编译：rustc ex02-status-from-str.rs -o /tmp/ex02-status-from-str
// 运行：/tmp/ex02-status-from-str
// 验证状态：已验证（rustc 1.92.0）

/// 状态枚举：PartialEq 供 assert_eq! 做值比较。
#[derive(Debug, PartialEq)]
enum Status {
    Active,
    Inactive,
    Suspended,
}

impl Status {
    /// 字符串 -> enum：未知字符串返回带原因的 Err（边界转换，错误显式处理）。
    fn from_str(s: &str) -> Result<Status, String> {
        match s {
            "active" => Ok(Status::Active),
            "inactive" => Ok(Status::Inactive),
            "suspended" => Ok(Status::Suspended),
            other => Err(format!("unknown status: '{}'", other)),
        }
    }

    /// enum -> 字符串：唯一出口，杜绝拼写错误。
    fn as_str(&self) -> &str {
        match self {
            Status::Active => "active",
            Status::Inactive => "inactive",
            Status::Suspended => "suspended",
        }
    }
}

fn main() {
    // 字符串安全转换
    assert_eq!(Status::from_str("active"), Ok(Status::Active));
    assert!(Status::from_str("deleted").is_err());

    // 枚举 -> 字符串
    println!("{}", Status::Suspended.as_str());

    // 不再能写错字符串 —— 类型系统保证
    let s = Status::Active;
    match s {
        Status::Active => println!("do activate"),
        Status::Inactive => println!("do deactivate"),
        Status::Suspended => println!("do suspend"),
    }
    // 如果未来加 Status::Deleted，编译器立刻报错——强制你更新所有 match
}
