// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 3
// 说明：Rc 引用计数共享：Rc::clone 只增计数（O(1)）不拷贝数据，最后一个 Rc 离开
//       作用域计数归零才释放堆上数据；strong_count 输出数字已实测。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex03-rc-shared-config.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告，strong 计数输出 1 -> 3 -> 2，与注释一致）

use std::rc::Rc;

#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    pool_size: u32,
}

// 参数写 &Config 而非 &Rc<Config>：调用方可传 Rc、Box 或裸引用——deref coercion 的价值
fn print_config(cfg: &Config) {
    println!("connect {}:{} pool={}", cfg.host, cfg.port, cfg.pool_size);
}

fn main() {
    let cfg = Rc::new(Config {
        host: String::from("127.0.0.1"),
        port: 5432,
        pool_size: 16,
    });
    println!("strong = {}", Rc::strong_count(&cfg)); // 1（只有变量 cfg 一个强引用）

    // Rc::clone 只增引用计数，堆上的 Config 始终只有一份（对比 String::clone 深拷贝）
    let cfg_a = Rc::clone(&cfg);
    let cfg_b = cfg.clone(); // 等价写法
    println!("strong = {}", Rc::strong_count(&cfg)); // 3

    // deref coercion：&Rc<Config> 自动解引用成 &Config
    print_config(&cfg);
    print_config(&cfg_a);
    print_config(&cfg_b);

    // drop 掉一个引用：计数回落，数据仍在（还有两个强引用）
    drop(cfg_a);
    println!("strong = {}", Rc::strong_count(&cfg)); // 2
}
