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
// 实测输出（本进程 stdout；断言通过前会先把本二进制以 --verify 再跑一遍做程序化比对）：
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

// 两段日志块：字段值混用 &str / u16 / bool 与字面量——{:?} 统一打印。
// 父进程与 --verify 子进程都先执行它：子进程打印完即返回，stdout 就是宏生成的全部输出。
fn print_blocks() {
    // 1. 三种不同类型的字段混用（&str / u16 / bool）
    let user = "ada";
    let port: u16 = 8080;
    log_fields!("login", user = user, port = port, ok = true);

    // 2. 字段值直接写字面量也成立
    log_fields!("purchase", item = "rs-book", qty = 3);
}

fn main() {
    print_blocks();

    // 3. 程序化断言：宏生成的 println! 直接写进程 stdout，单进程内没有稳定 API 能把
    //    已打印的文本读回来，所以把本二进制以 --verify 参数再跑一遍（子进程），
    //    拿它捕获到的 stdout 与手写 println 的期望文本逐字符比较。
    if std::env::args().nth(1).as_deref() == Some("--verify") {
        return; // 子进程模式：上面已打印两段日志块，stdout 即宏输出，到此结束
    }
    let out = std::process::Command::new(std::env::current_exe().unwrap())
        .arg("--verify")
        .output()
        .unwrap(); // 演示程序：spawn/等待失败直接 panic 可接受
    assert!(out.status.success(), "子进程运行失败");
    let macro_out = String::from_utf8(out.stdout).unwrap();

    // 手写对照：若把两段日志块用手写 println 输出，得到的文本应逐字符一致。
    // 期望文本里的 {:?} 与宏内部完全同型（"ada"、8080u16、true、"rs-book"、3）。
    let expected = format!(
        "event = {}\n  user = {:?}\n  port = {:?}\n  ok = {:?}\nevent = {}\n  item = {:?}\n  qty = {:?}\n",
        "login", "ada", 8080u16, true, "purchase", "rs-book", 3
    );
    assert_eq!(macro_out, expected, "log_fields! 的 stdout 与手写 println 输出不一致");

    println!("断言通过：log_fields! 与手写 println 输出一致");
}
