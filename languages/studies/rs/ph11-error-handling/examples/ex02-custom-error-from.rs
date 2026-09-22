// examples/ex02-custom-error-from.rs —— 自定义错误类型 + From 转换（Display + Error + From 三步走），主文档第 6 章示例 2
// 说明：自定义错误类型 + From 转换（纯 std 手写「三步走」：Display + Error + From）。
//       ? 运算符的 From 自动转换让 ParseIntError 无缝变成 PortError；
//       source() 暴露底层原因（错误链的第一环）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-custom-error-from.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；输出、Debug 与错误链遍历均为实测结果）

use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

// 自定义错误枚举：每个变体是一种失败模式，闭集——调用方可以 match 穷尽
#[derive(Debug)]
enum PortError {
    MissingColon(String),   // 没有 ":" 分隔符（携带输入原文）
    BadPort(ParseIntError), // 端口不是数字（包装标准库错误，错误链的第一环）
    OutOfRange(u16),        // 端口超出 1-65535
}

// 第一步：Display——写「给人看的消息」，每条都定位到具体输入
impl fmt::Display for PortError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PortError::MissingColon(s) => write!(f, "缺少冒号分隔符: {s:?}"),
            PortError::BadPort(e) => write!(f, "端口号不是数字: {e}"),
            PortError::OutOfRange(p) => write!(f, "端口号 {p} 超出 1-65535"),
        }
    }
}

// 第二步：Error——进错误链；source() 只对「包装了底层错误」的变体返回 Some
impl Error for PortError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            PortError::BadPort(e) => Some(e), // 暴露底层 ParseIntError
            _ => None,
        }
    }
}

// 第三步：From——让 `?` 能把 ParseIntError 自动转成 PortError（编译期零开销）
impl From<ParseIntError> for PortError {
    fn from(e: ParseIntError) -> Self {
        PortError::BadPort(e)
    }
}

fn parse_addr(s: &str) -> Result<(String, u16), PortError> {
    let (host, port) = s
        .split_once(':')
        .ok_or_else(|| PortError::MissingColon(s.to_string()))?; // ok_or_else 手动构造错误
    let port: u16 = port.parse()?; // ParseIntError -> PortError：走 From 自动转换
    if port == 0 {
        return Err(PortError::OutOfRange(port)); // 语义校验失败：直接返回
    }
    Ok((host.to_string(), port))
}

fn main() {
    for input in ["127.0.0.1:8080", "localhost:abc", "no-colon-here", "127.0.0.1:0"] {
        match parse_addr(input) {
            Ok((h, p)) => println!("OK   {input:14} -> {h}:{p}"),
            Err(e) => println!("ERR  {input:14} -> {e}"),
        }
    }

    // Debug 输出（开发者视角，含内部结构）
    let err = parse_addr("localhost:abc").unwrap_err();
    println!("Debug = {err:?}");

    // 错误链遍历：source() 逐层走到根因（Display 写「这一层」，source 指「底层」）
    let mut cur: Option<&(dyn Error + 'static)> = Some(&err);
    while let Some(e) = cur {
        println!("链层: {e}");
        cur = e.source();
    }
}
