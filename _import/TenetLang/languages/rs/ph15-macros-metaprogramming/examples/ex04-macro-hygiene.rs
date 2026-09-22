// examples/ex04-macro-hygiene.rs —— 卫生性实测：宏内变量不泄漏到调用方；传入 ident 指向调用方（参数不卫生是特性）
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex04-macro-hygiene.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告；输出为实测）

// ① 卫生性：宏体内部声明 secret，调用方也声明同名 secret——互不干扰。
// 宏展开时，宏体自带的标识符被标记为「宏定义处」的语法上下文，
// 与调用方作用域里的同名变量是两个东西（概念：每个 token 带 syntax context）。
macro_rules! inner_secret {
    () => {{
        let secret = 42; // 宏体内造的标识符：卫生的，不污染调用方作用域
        println!("  （宏内部）secret = {secret}");
        secret
    }};
}

// ② 宏参数的 ident 不卫生（有意为之）：$v 展开时解析为「调用方」作用域里的那个变量，
// 所以宏可以读写调用方的局部变量——这是 Rust 宏「能当 inline 代码生成器」的钥匙。
macro_rules! bump {
    ($v:ident, $by:expr) => {
        $v += $by; // 这里的 $v 指向调用方作用域中的变量（参数由调用方提供）
    };
}

// ③ 宏里访问「调用方作用域的东西」必须显式传参：宏体里直接写 counter 会解析到
// 宏定义处的作用域（找不到就叫编译错误，见 examples/ex05-macro-errors.rs）。
// 下面演示「需要什么就传什么」的惯用法：
macro_rules! report {
    ($v:expr) => {
        println!("report: 调用方把 counter 传进来 = {}", $v);
    };
}

fn main() {
    // 1. 调用方有自己的 secret，宏内部也有自己的 secret
    let secret = 7;
    println!("1. 调用方先声明 secret = {secret}");
    let got = inner_secret!();
    println!("   调用方 secret 仍是 {secret}，宏返回的 got = {got}（互不干扰）");
    assert_eq!(secret, 7); // 宏没有改掉调用方的 secret
    assert_eq!(got, 42); // 宏内部 secret 是 42
    println!("   -> 断言通过：宏内变量未泄漏到调用方（卫生性）");

    // 2. 传入的 ident 指向调用方变量：宏能改它（参数不卫生是特性）
    let mut counter = 0;
    bump!(counter, 5);
    println!("2. bump!(counter, 5) 后 counter = {counter}（宏通过参数修改调用方变量）");
    assert_eq!(counter, 5);

    // 3. 需要调用方作用域的值时显式传入
    counter += 1;
    report!(counter);
    assert_eq!(counter, 6);
    println!("3. 断言通过：显式传参是宏与调用方交换数据的唯一通道");
}
