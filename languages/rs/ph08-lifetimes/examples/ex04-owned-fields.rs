// 来源：languages/rs/ph08-lifetimes/08-lifetimes.md 第 6 章示例 4
// 说明：把不必要的引用字段改成拥有字段——String 替代 &'a str，生命周期参数整体消失
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex04-owned-fields.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告，输出符合预期）

// 改造前：引用字段，生命周期传播到所有使用方
// struct Config<'a> { name: &'a str, version: &'a str }
// impl<'a> Config<'a> {
//     fn name(&self) -> &str { self.name }
// }

// 改造后：拥有字段，生命周期参数整体消失
// 代价：每次构造多一次堆分配与拷贝；换来结构体不依赖外部数据的存活
#[derive(Debug)]
struct Config {
    name: String,
    version: String,
}

impl Config {
    fn new(name: &str, version: &str) -> Self {
        Config {
            name: name.to_string(),     // 拷贝一份，从此自给自足
            version: version.to_string(),
        }
    }
    // 方法内借用 self，依然可以返回 &str，不涉及结构体的生命周期参数
    fn name(&self) -> &str { &self.name }
    fn version(&self) -> &str { &self.version }
}

fn main() {
    let cfg = Config::new("cache", "3.2.1");
    println!("{:?}", cfg); // Debug
    println!("{} v{}", cfg.name(), cfg.version());
    // 拥有字段的结构体可以自由移动、进集合、跨线程，不再受借用约束
    let cfgs = vec![cfg];
    println!("count: {}", cfgs.len());
}
