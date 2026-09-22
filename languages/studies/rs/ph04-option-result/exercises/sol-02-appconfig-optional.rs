// exercises/sol-02-appconfig-optional.rs —— 练习 2 参考实现：AppConfig 可选配置项
// 来源：exercises/README.md 练习 2（基于第 6 章示例 2 扩展）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-02-appconfig-optional.rs -o /tmp/sol-02-appconfig-optional
// 运行：/tmp/sol-02-appconfig-optional
// 验证状态：已验证（rustc 1.92.0）

/// 应用配置：可选字段用 `Option` 表达"可能没设置"，读取时用组合子取默认值。
#[derive(Debug)]
struct AppConfig {
    host: String,
    port: u16,
    timeout_secs: Option<u32>,
    log_level: Option<String>,
    max_connections: Option<u32>,
    enable_tls: Option<bool>,
}

impl AppConfig {
    fn new(host: &str, port: u16) -> Self {
        AppConfig {
            host: host.to_string(),
            port,
            timeout_secs: None,
            log_level: None,
            max_connections: None,
            enable_tls: None,
        }
    }

    fn effective_timeout(&self) -> u32 {
        self.timeout_secs.unwrap_or(30)
    }

    fn effective_log_level(&self) -> &str {
        self.log_level.as_deref().unwrap_or("info")
    }

    /// 未设置最大连接数默认 100
    fn effective_max_connections(&self) -> u32 {
        self.max_connections.unwrap_or(100)
    }

    /// 未设置 TLS 开关默认关闭
    fn effective_enable_tls(&self) -> bool {
        self.enable_tls.unwrap_or(false)
    }
}

fn main() {
    let mut cfg = AppConfig::new("localhost", 8080);
    println!(
        "默认值: host={} port={} timeout={}s log={} max_connections={} tls={}",
        cfg.host,
        cfg.port,
        cfg.effective_timeout(),
        cfg.effective_log_level(),
        cfg.effective_max_connections(),
        cfg.effective_enable_tls(),
    );

    cfg.timeout_secs = Some(10);
    cfg.log_level = Some("debug".to_string());
    cfg.max_connections = Some(200);
    cfg.enable_tls = Some(true);
    println!(
        "更新后: host={} port={} timeout={}s log={} max_connections={} tls={}",
        cfg.host,
        cfg.port,
        cfg.effective_timeout(),
        cfg.effective_log_level(),
        cfg.effective_max_connections(),
        cfg.effective_enable_tls(),
    );
    println!("完整结构: {:?}", cfg);
}
