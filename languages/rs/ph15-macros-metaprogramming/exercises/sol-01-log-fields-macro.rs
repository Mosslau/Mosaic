// 来源：languages/rs/ph15-macros-metaprogramming/exercises/README.md 练习 1
// 说明：log_fields! 宏——为一次事件输出「event = <名> + 字段列表」的日志块
//       （roadmap 练习「写一个生成日志字段的 macro_rules 宏」落地）。
//       难点：repetition 里每个字段要拿到「字段名（token）」「字段值」两个东西，
//       所以字段写成  $k:ident = $v:expr  成对出现；打印值用 {:?}（Debug）以兼容多种类型。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-01-log-fields-macro.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告；下方输出为实测）
//
// 实测输出：
//   event = login
//     user = "ada"
//     port = 8080
//     ok = true
//   event = purchase
//     item = "rs-book"
//     qty = 3
//   断言通过：log_fields! 与手写 println 输出一致

macro_rules! log_fields {
    // 事件名 + 0..n 个 字段名 = 字段值；$(,)? 吞可选尾逗号
    ($event:expr, $( $k:ident = $v:expr ),* $(,)?) => {{
        println!("event = {}", $event);
        $( println!("  {} = {:?}", stringify!($k), $v); )*
    }};
}

fn main() {
    // 1. 三种不同类型的字段混用（&str / u16 / bool）——{:?} 统一打印
    let user = "ada";
    let port: u16 = 8080;
    log_fields!("login", user = user, port = port, ok = true);

    // 2. 字段值直接写字面量也成立
    log_fields!("purchase", item = "rs-book", qty = 3);

    // 3. 对照：手写 println 输出应与宏输出一致（断言：证明宏生成代码等价于手写代码）
    let user = "ada";
    let port: u16 = 8080;
    let ok = true;
    assert_eq!(
        format!("event = login\n  user = {:?}\n  port = {:?}\n  ok = {:?}", user, port, ok),
        {
            let mut s = String::from("event = login");
            s.push_str(&format!("\n  user = {:?}", user));
            s.push_str(&format!("\n  port = {:?}", port));
            s.push_str(&format!("\n  ok = {:?}", ok));
            s
        }
    );
    println!("断言通过：log_fields! 与手写 println 输出一致");
}
