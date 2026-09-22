// 修复版（与同目录 error.rs 对照）。两种策略，任选其一：
//  A 让「拥有数据的变量」与借用同处一个作用域 —— 数据活得够久，借用自然合法；
//  B 数据只能来自内层时，把借用转成拥有的 String（to_owned），切掉借用链。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e05-borrowed-lifetime-fix && /tmp/e05-borrowed-lifetime-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    // A：把 config 提升到外层作用域，借用与数据同寿
    let config = String::from("demo.conf");
    let stem = config.split('.').next(); // Option<&str> 借用 config，config 活得比它久
    println!("A: stem = {stem:?}");

    // B：数据来自内层时，借用后立即 to_owned，让返回值不携带借用
    let stem_b;
    {
        let name = String::from("log.txt");
        stem_b = name.split('.').next().map(str::to_owned); // Option<String>：拥有数据
    } // name 在此 drop 无妨 —— stem_b 不再借用它
    println!("B: stem_b = {stem_b:?}");
}
