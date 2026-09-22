// 来源：languages/rs/ph11-error-handling/exercises/README.md 练习 1
// 说明：Option/Result 组合子重构——用 map/and_then/or_else/ok_or_else/? 替代嵌套 match。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-01-combinator-refactor.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告；输出已实测）

// 1) 解析 "key=value" 配置行：ok_or_else 把「缺分隔符」转成错误消息，? 直接传播
fn parse_key_value(line: &str) -> Result<(&str, &str), String> {
    let (k, v) = line
        .split_once('=')
        .ok_or_else(|| format!("第 {:?} 行缺少 '=' 分隔符", line))?;
    Ok((k.trim(), v.trim()))
}

// 2) 查配置：find_map 逐个尝试解析并匹配 key；找不到返回错误消息
//    （对比嵌套 match 版：match parse { Ok((k,v)) => if k==key {...}, Err(_) => 继续 }）
fn lookup<'a>(lines: &[&'a str], key: &str) -> Result<&'a str, String> {
    lines
        .iter()
        .find_map(|line| match parse_key_value(line) {
            Ok((k, v)) if k == key => Some(Ok(v)),
            Ok(_) => None,          // 不是目标 key：继续下一行
            Err(_) => None,         // 坏行：练习要求忽略（真实工程可改为记录后继续）
        })
        .unwrap_or_else(|| Err(format!("配置项 {key:?} 不存在")))
}

// 3) 端口解析：and_then 链式「先解析行，再解析数字」；or_else 失败时给默认值
fn parse_port(line: &str) -> Result<u16, String> {
    parse_key_value(line)
        .and_then(|(k, v)| {
            if k == "port" {
                v.parse::<u16>().map_err(|e| format!("端口不是数字: {e}"))
            } else {
                Err(format!("不是端口行: {k:?}"))
            }
        })
}

fn main() {
    let cfg = ["host = 127.0.0.1", "port = 8080", "debug = true"];

    // ? 的用法：lookup 返回 Result，main 里 match 处理
    for key in ["host", "port", "nope"] {
        match lookup(&cfg, key) {
            Ok(v) => println!("lookup {key:4} -> {v}"),
            Err(e) => println!("lookup {key:4} -> ERR {e}"),
        }
    }

    // and_then + or_else 的组合
    match parse_port("port = 8080") {
        Ok(p) => println!("parse_port ok   -> {p}"),
        Err(e) => println!("parse_port err  -> ERR {e}"),
    }
    let fallback = parse_port("port = not-a-number")
        .or_else(|e| { println!("  (port 行解析失败，记一笔: {e})"); Ok::<u16, String>(3000) })
        .unwrap();
    println!("parse_port fallback -> {fallback}");

    // 断言兜底（与上方输出一致，已实测）
    assert_eq!(lookup(&cfg, "host").unwrap(), "127.0.0.1");
    assert_eq!(lookup(&cfg, "nope").unwrap_err(), "配置项 \"nope\" 不存在");
    assert_eq!(parse_port("port = 8080").unwrap(), 8080);
    assert_eq!(fallback, 3000);
    println!("全部断言通过");
}
