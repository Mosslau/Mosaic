// 04 · Option/Result 错误处理演示
// 运行：cargo run --bin 04_option_result

/// 用 Option 消除"空值"：找不到就返回 None，调用方必须处理
fn first_char(s: &str) -> Option<char> {
    s.chars().next() // 空字符串 → None
}

/// 用 Result 表达可失败操作；? 让错误自动向上传播
fn parse_num(s: &str) -> Result<i64, String> {
    s.trim()
        .parse::<i64>()
        .map_err(|_| format!("`{s}` 不是合法整数"))
}

fn parse_and_double(s: &str) -> Result<i64, String> {
    let n = parse_num(s)?; // Err 直接 return，Ok 解包
    Ok(n * 2)
}

fn main() {
    println!("== Option：没有 null ==");
    match first_char("tenet") {
        Some(c) => println!("首字符: {c}"),
        None => println!("空字符串"),
    }
    match first_char("") {
        Some(c) => println!("首字符: {c}"),
        None => println!("空字符串没有首字符（无需崩溃）"),
    }

    println!("\n== Result + ?：错误显式传播 ==");
    match parse_and_double("21") {
        Ok(v) => println!("21 * 2 = {v}"),
        Err(e) => println!("失败: {e}"),
    }
    match parse_and_double("abc") {
        Ok(v) => println!("abc * 2 = {v}"),
        Err(e) => println!("失败: {e}"),
    }

    println!("\n== match 穷尽性：忘了处理 None/Err 就编译不过 ==");
    println!("（上面每个 match 都覆盖了全部分支——这是编译器强制要求的）");
}
