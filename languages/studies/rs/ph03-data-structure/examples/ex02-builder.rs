// examples/ex02-builder.rs —— impl 方法 + 构建器模式（self 接收者）
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 2」
// 验证环境：rustc 1.92.0
// 编译：rustc ex02-builder.rs -o /tmp/ex02-builder
// 运行：/tmp/ex02-builder
// 验证状态：已验证（编译零警告，输出符合预期）

#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    timeout_secs: u32,
}

impl Config {
    // 关联函数（无 self 接收者），返回默认配置
    fn new() -> Self {
        Config {
            host: String::from("localhost"),
            port: 8080,
            timeout_secs: 30,
        }
    }

    // 构建器方法：self（消耗）接收者，支持链式调用
    fn host(mut self, host: impl Into<String>) -> Self {
        self.host = host.into();
        self
    }

    fn port(mut self, port: u16) -> Self {
        self.port = port;
        self
    }

    fn timeout(mut self, secs: u32) -> Self {
        self.timeout_secs = secs;
        self
    }
}

fn main() {
    let default = Config::new();
    let cfg = Config::new()
        .host("api.example.com")
        .port(443)
        .timeout(10);

    // 显式读字段，避免 dead_code 警告
    println!("default: {}:{} ({}s)", default.host, default.port, default.timeout_secs);
    println!("custom:  {}:{} ({}s)", cfg.host, cfg.port, cfg.timeout_secs);
}
