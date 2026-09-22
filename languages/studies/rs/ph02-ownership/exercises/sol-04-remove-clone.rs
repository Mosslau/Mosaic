// exercises/sol-04-remove-clone.rs —— 练习 4 参考解：去 clone 重写 join_words
// 验证环境：rustc 1.92.0
// 编译：rustc sol-04-remove-clone.rs -o sol04
// 运行：./sol04
// 已验证：本环境编译零警告，输出拼接结果，words 调用后仍可用
//
// 所有权流向对比：
// 改动前：调用方把 Vec<String> move 进函数；循环里每个 String 被 clone 两次，
//         堆数据复制 O(n) 次，函数结束 Vec 连同原数据一起 drop。
// 改动后：调用方只借出 &[String]；函数只读借用每个元素，零 clone、零额外堆分配
//         （除返回值 out 外）；调用结束后 words 的 ownership 仍归调用方。

/// 借用切片拼接单词，全程不 clone
fn join_words(words: &[String]) -> String {
    let mut out = String::new();
    for w in words {
        if !out.is_empty() {
            out.push(' ');
        }
        out.push_str(w); // &String 自动解引用为 &str
    }
    out
}

fn main() {
    let words = vec![
        String::from("a"),
        String::from("bb"),
        String::from("ccc"),
    ];

    let joined = join_words(&words); // 只借用，words 保留 ownership
    println!("joined: {}", joined);
    println!("words still usable: {:?}", words);
}
