// exercises/sol-03-endpoint-pipeline.rs —— 练习 3 参考实现：parse_endpoint 解析管线
// 来源：exercises/README.md 练习 3
// 验证环境：rustc 1.92.0
// 编译：rustc sol-03-endpoint-pipeline.rs -o /tmp/sol-03-endpoint-pipeline
// 运行：/tmp/sol-03-endpoint-pipeline
// 验证状态：已验证（rustc 1.92.0）

/// 极简 host 校验：非空即可（完整 IP 校验属于 ph13 网络编程阶段，这里不展开）
fn parse_ip(host: &str) -> Result<String, String> {
    let host = host.trim();
    if host.is_empty() {
        Err("host 不能为空".to_string())
    } else {
        Ok(host.to_string())
    }
}

/// 把字符串解析为端口号
fn parse_port(raw: &str) -> Result<u16, String> {
    raw.trim().parse::<u16>().map_err(|e| format!("'{}' 不是合法端口: {}", raw, e))
}

/// 端口语义校验：0 是保留端口
fn check_port_range(port: u16) -> Result<u16, String> {
    if (1..=65535).contains(&port) {
        Ok(port)
    } else {
        Err(format!("端口 {} 超出范围 1~65535", port))
    }
}

/// 三个解析函数用 `?` 串联成一条管线：任一步失败立即短路返回
fn parse_endpoint(host: &str, port: &str) -> Result<(String, u16), String> {
    let host = parse_ip(host)?;
    let port = parse_port(port)?;
    let port = check_port_range(port)?;
    Ok((host, port))
}

fn main() {
    let cases = [
        ("127.0.0.1", "8080"), // 合法
        ("localhost", "0"),    // 端口 0，范围校验失败
        ("", "80"),            // 空 host，ip 校验失败
        ("::1", "abc"),        // 端口非数字，解析失败
    ];
    for (host, port) in cases {
        match parse_endpoint(host, port) {
            Ok((h, p)) => println!("'{}:{}' -> ok, endpoint = (host: {}, port: {})", host, port, h, p),
            Err(e) => eprintln!("'{}:{}' -> 错误: {}", host, port, e),
        }
    }
}
