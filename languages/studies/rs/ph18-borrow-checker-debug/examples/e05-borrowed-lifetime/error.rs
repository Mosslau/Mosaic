// 本文件故意编译失败：期望错误码 E0597（borrowed value does not live long enough）。
// 场景：内层作用域创建的 String，其借用被「外逃」到外层作用域 —— 外层用完时数据已 drop。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0597]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let stem; // 计划在外层使用的借用（Option<&str>）
    {
        let config = String::from("demo.conf"); // config 的生命周期被限制在这个块内
        stem = config.split('.').next(); // E0597：把借用 config 的 Option<&str> 交到外层
    } // config 在此 drop，stem 却还要活到下面的 println
    println!("stem = {stem:?}");
}
