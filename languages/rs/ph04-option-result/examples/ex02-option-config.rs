// examples/ex02-option-config.rs —— 用 Option 处理可选配置项
// 来源：04-option-result.md 第 6 章示例 2
// 验证环境：rustc 1.92.0
// 编译：rustc ex02-option-config.rs -o /tmp/ex02-option-config
// 运行：/tmp/ex02-option-config
// 验证状态：已验证（rustc 1.92.0）

/// 应用配置：timeout 与 log_level 是可选项，未设置时用默认值。
/// 用 `Option` 表达"配置项可能缺失"，用组合子取默认值，而不是裸 `unwrap` panic。
#[derive(Debug)]
#[allow(dead_code)] // 字段可能仅用于 Debug 打印，教学示例容忍
struct AppConfig {
    host: String,
    port: u16,
    timeout_secs: Option<u32>,
    log_level: Option<String>,
}

impl AppConfig {
    fn new(host: &str, port: u16) -> Self {
        AppConfig { host: host.to_string(), port, timeout_secs: None, log_level: None }
    }

    /// 未设置超时默认 30 秒：`unwrap_or` 提供急求值默认值
    fn effective_timeout(&self) -> u32 {
        self.timeout_secs.unwrap_or(30)
    }

    /// 未设置日志级别默认 "info"：`as_deref` 把 `Option<String>` 转成 `Option<&str>` 再取默认
    fn effective_log_level(&self) -> &str {
        self.log_level.as_deref().unwrap_or("info")
    }
}

fn main() {
    let mut cfg = AppConfig::new("localhost", 8080);
    println!(
        "defaults: timeout={}s log={}",
        cfg.effective_timeout(),
        cfg.effective_log_level()
    );

    cfg.timeout_secs = Some(10);
    cfg.log_level = Some(String::from("debug"));
    println!("updated: {:?}", cfg);
}
