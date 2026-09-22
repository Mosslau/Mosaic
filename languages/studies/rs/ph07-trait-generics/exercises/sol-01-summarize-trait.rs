// 来源：languages/rs/ph07-trait-generics/exercises/README.md 练习 1（为多个结构体实现同一个 trait）
// 说明：Summarize trait 含默认实现 headline；Article/Comment/Tweet 各自实现 summarize，Comment 覆盖 headline
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc sol-01-summarize-trait.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告，输出符合预期）

trait Summarize {
    fn summarize(&self) -> String;

    // 默认实现：基于 summarize 包装一层
    fn headline(&self) -> String {
        format!("[摘要] {}", self.summarize())
    }
}

struct Article { title: String, author: String }
struct Comment { user: String, body: String }
struct Tweet { user: String, content: String }

impl Summarize for Article {
    fn summarize(&self) -> String {
        format!("《{}》 by {}", self.title, self.author)
    }
}

impl Summarize for Comment {
    fn summarize(&self) -> String {
        format!("{}: {}", self.user, self.body)
    }

    // 覆盖默认实现：评论不需要"[摘要]"前缀
    fn headline(&self) -> String {
        format!("(评论) {}", self.summarize())
    }
}

impl Summarize for Tweet {
    fn summarize(&self) -> String {
        format!("@{}: {}", self.user, self.content)
    }
}

fn print_all<T: Summarize>(items: &[T]) {
    for item in items {
        println!("{} | {}", item.summarize(), item.headline());
    }
}

fn main() {
    let articles = vec![
        Article { title: String::from("Rust 泛型"), author: String::from("alice") },
        Article { title: String::from("trait 入门"), author: String::from("bob") },
    ];
    let comments = vec![
        Comment { user: String::from("carol"), body: String::from("讲得好") },
    ];
    let tweets = vec![
        Tweet { user: String::from("dave"), content: String::from("今天学了 where 子句") },
    ];

    print_all(&articles);
    print_all(&comments);
    print_all(&tweets);
}
