// 来源：languages/rs/ph10-smart-pointers/exercises/README.md 练习 2
// 说明：用 Rc 共享只读配置——Rc::new 一次、Rc::clone 两次，堆上 Config 只有一份；
//       打印函数参数写 &Config，调用方传 &Rc<Config> 走 deref coercion；
//       用 strong_count 观察共享生命周期（实测 1 -> 3）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-02-rc-shared-config.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告，输出 strong = 1 / 3 / 2，断言通过）

use std::rc::Rc;

#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    pool_size: u32,
}

fn print_config(cfg: &Config) {
    println!("connect {}:{} pool={}", cfg.host, cfg.port, cfg.pool_size);
}

fn main() {
    let cfg = Rc::new(Config {
        host: String::from("127.0.0.1"),
        port: 5432,
        pool_size: 16,
    });
    println!("strong = {}", Rc::strong_count(&cfg)); // 1

    let cfg_a = Rc::clone(&cfg);
    let cfg_b = cfg.clone();
    println!("strong = {}", Rc::strong_count(&cfg)); // 3
    assert_eq!(Rc::strong_count(&cfg), 3);

    // &Rc<Config> 自动解引用为 &Config（deref coercion），函数签名因此更通用
    print_config(&cfg);
    print_config(&cfg_a);
    print_config(&cfg_b);

    drop(cfg_a);
    println!("strong = {}", Rc::strong_count(&cfg)); // 2
}
