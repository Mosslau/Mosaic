// exercises/sol-02-pin-dependency/src/main.rs —— 练习 2 参考实现：添加第三方 crate 并固定版本
// 解析 JSON 用户列表，serde_json 精确锁定 =1.0.108
// 验证环境：rustc 1.92.0 + cargo 1.92.0，依赖 serde 1.0.197 / serde_json =1.0.108（需网络拉取）
// 编译：cargo build（在 sol-02-pin-dependency/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct User {
    name: String,
    age: u32,
}

#[derive(Debug, Deserialize)]
struct UserList {
    users: Vec<User>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let json = r#"{"users":[{"name":"alice","age":30},{"name":"bob","age":25}]}"#;
    let list: UserList = serde_json::from_str(json)?;
    println!("用户数: {}", list.users.len());
    let mut names: Vec<&str> = list.users.iter().map(|u| u.name.as_str()).collect();
    names.sort();
    println!("按名字排序: {:?}", names);
    let mut by_age: Vec<(&str, u32)> =
        list.users.iter().map(|u| (u.name.as_str(), u.age)).collect();
    by_age.sort_by_key(|(_, age)| *age);
    println!("按年龄排序: {:?}", by_age);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deserialize_user_list() {
        let json = r#"{"users":[{"name":"carol","age":40}]}"#;
        let list: UserList = serde_json::from_str(json).unwrap();
        assert_eq!(list.users.len(), 1);
        assert_eq!(list.users[0].name, "carol");
        assert_eq!(list.users[0].age, 40);
    }

    #[test]
    fn empty_users_ok() {
        let json = r#"{"users":[]}"#;
        let list: UserList = serde_json::from_str(json).unwrap();
        assert!(list.users.is_empty());
    }
}
