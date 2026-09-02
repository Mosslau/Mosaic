// examples/ex01-macro-basics.rs —— macro_rules! 声明宏入门：定义/调用/三种括号/多臂匹配/stringify! 观察「宏收到 token」
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-macro-basics.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；输出为实测）

// macro_rules! 定义声明宏：名字 + 一条或多条「匹配臂」。
// 每条臂形如  (匹配模式) => { 展开代码 };  —— 与 match 的臂长得像，但匹配的是 token。
macro_rules! say {
    ($name:expr) => {
        // 展开体里的 $name 会被调用处传入的 token 原样替换
        println!("hello, {}!", $name);
    };
}

// 宏展开的位置可以是表达式位置：double!(10 + 11) 展开为 (10 + 11) * 2
macro_rules! double {
    ($x:expr) => {
        $x * 2 // 展开为一个表达式（末尾无分号）
    };
}

// 多臂宏：第一臂匹配字面量 0，第二臂匹配任意表达式（臂之间用 ; 分隔，从上到下先匹配先得）
macro_rules! classify {
    (0) => {
        "zero"
    };
    ($n:expr) => {
        "nonzero"
    };
}

// stringify! 把传入的 token 原样变成字符串字面量——证明宏收到的是「代码」不是「算好的值」
macro_rules! show {
    ($x:expr) => {
        println!("show: {} = {}", stringify!($x), $x)
    };
}

fn main() {
    // 1. 三种调用括号等价：() [] {}
    say!("rust");
    say!["rust"];
    say!{"rust"}

    // 2. 宏可以生成「语句」，也可以生成「表达式」
    let d = double!(10 + 11); // 展开为 (10 + 11) * 2，宏展开发生在编译期
    println!("double!(10 + 11) = {d}");

    // 3. 多臂匹配：调用处给什么 token，就命中哪条臂
    let tag = classify!(0); // 命中第一臂（字面量 0）
    let tag2 = classify!(42); // 命中第二臂（通用 expr）
    println!("classify!(0) = {tag}, classify!(42) = {tag2}");

    // 4. stringify! 原样打印代码——(10 + 11) 不是先算成 21 再传进来，
    //    宏在编译期先拿到「10 + 11」这串 token，展开后才轮到求值
    show!(10 + 11);
    show!(vec![1, 2, 3].len());
}
