// 来源：languages/rs/ph08-lifetimes/08-lifetimes.md 第 6 章示例 2
// 说明：结构体持有引用——只读配置视图，零拷贝借用原文，生命周期绑定输入文本
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex02-config-view.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告，输出符合预期）

// 从配置文本中借用字段的只读视图：零拷贝，生命周期绑定原文
struct ConfigView<'a> {
    host: &'a str,
    port: &'a str,
    retries: &'a str,
}

impl<'a> ConfigView<'a> {
    fn from_text(text: &'a str) -> ConfigView<'a> {
        let mut host: &'a str = "localhost";
        let mut port: &'a str = "8080";
        let mut retries: &'a str = "3";
        for line in text.lines() {
            if let Some((key, value)) = line.split_once('=') {
                match key.trim() {
                    "host" => host = value.trim(),
                    "port" => port = value.trim(),
                    "retries" => retries = value.trim(),
                    _ => {}
                }
            }
        }
        ConfigView { host, port, retries }
    }

    // 方法的省略规则第 3 条：&self 的生命周期自动赋给返回值，无需写 <'a>
    fn host(&self) -> &str { self.host }
    fn port(&self) -> &str { self.port }
    fn retries(&self) -> usize { self.retries.parse().unwrap_or(3) }
}

fn main() {
    let config_text = String::from("host=db-01.internal\nport=5432\nretries=5\n");
    let view = ConfigView::from_text(&config_text); // 借用 config_text，未复制任何字段
    println!("host={} port={}", view.host(), view.port());
    println!("retries as number: {}", view.retries());
    // view 的生命周期与 config_text 绑定：config_text 存活期间 view 才有效
}
