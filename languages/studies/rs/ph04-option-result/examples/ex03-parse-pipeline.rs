// examples/ex03-parse-pipeline.rs —— 一组解析函数用 ? 串联
// 来源：04-option-result.md 第 6 章示例 3
// 验证环境：rustc 1.92.0
// 编译：rustc ex03-parse-pipeline.rs -o /tmp/ex03-parse-pipeline
// 运行：/tmp/ex03-parse-pipeline
// 验证状态：已验证（rustc 1.92.0）

/// 把字符串解析为端口号，失败返回带原因的 Err
fn parse_port(s: &str) -> Result<u16, String> {
    s.parse::<u16>().map_err(|_| format!("'{}' is not a valid port number", s))
}

/// 端口语义校验：0 是保留端口，不可用
fn check_port_range(port: u16) -> Result<u16, String> {
    if port == 0 { Err("port 0 is reserved".to_string()) }
    else { Ok(port) }
}

/// 把服务名映射到知名端口
fn resolve_service_port(service: &str) -> Result<u16, String> {
    match service {
        "http" => Ok(80), "https" => Ok(443), "ssh" => Ok(22),
        other => Err(format!("unknown service: {}", other)),
    }
}

/// 输入既可以是数字端口，也可以是服务名——两条解析路径合并成一个 Result
fn get_port(input: &str) -> Result<u16, String> {
    if let Ok(num) = parse_port(input) { return check_port_range(num); }
    resolve_service_port(input) // 尝试解析为服务名
}

fn main() {
    for input in &["8080", "0", "https", "99999", "unknown"] {
        match get_port(input) {
            Ok(port) => println!("'{}' -> port {}", input, port),
            Err(e) => eprintln!("'{}' -> error: {}", input, e),
        }
    }
}
