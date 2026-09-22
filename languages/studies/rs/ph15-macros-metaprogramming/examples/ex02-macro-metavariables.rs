// examples/ex02-macro-metavariables.rs —— 片段分类符实测：expr/ident/ty/pat/literal；多臂匹配「先匹配先得」
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-macro-metavariables.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；输出为实测）

use std::collections::HashMap; // 拿来当 :ty 片段传进宏

// :expr —— 一个表达式（最常见的片段分类符）
macro_rules! show {
    ($x:expr) => {
        println!("show: {} = {}", stringify!($x), $x)
    };
}

// :ident —— 一个标识符（变量名/函数名/字段名…）。这里拿调用方给的名字「造」一个变量：
macro_rules! let_var {
    ($name:ident = $init:expr) => {
        let $name = $init;
    };
}

// :ty —— 一个类型。展开后写进类型位置：
macro_rules! typed_let {
    ($name:ident: $t:ty = $init:expr) => {
        let $name: $t = $init;
    };
}

// :pat —— 一个模式。展开进 matches! 的模式位置：
macro_rules! matches_some {
    ($v:expr, $p:pat) => {
        matches!($v, $p) // std::matches! 本身也是声明宏——「宏展开成宏调用」合法
    };
}

// :literal —— 一个字面量（数字/字符串/字符/布尔）。这里拿它当常量用：
macro_rules! assert_big {
    ($lit:literal) => {
        assert!($lit > 100, "字面量 {} 不够大", $lit);
    };
}

// 多臂匹配 + 先匹配先得：第一臂匹配字面量 0，第二臂匹配任意表达式
macro_rules! is_zero {
    (0) => {
        println!("is_zero!(0)      -> 命中第一臂（字面量 0）");
    };
    ($x:expr) => {
        println!(
            "is_zero!({}) -> 命中第二臂（通用 expr），值 = {}",
            stringify!($x),
            $x
        );
    };
}

fn main() {
    // 1. :expr
    show!(10 + 11);
    show!(vec![1, 2, 3].len());

    // 2. :ident —— 宏展开在 main 的语句位置声明了一个普通变量，调用方作用域可见
    let_var!(counter = 41);
    println!("let_var!(counter = 41) 之后 counter = {counter}");

    // 3. :ty —— 具体类型与泛型类型都能传
    typed_let!(bignum: u32 = 40 + 2);
    println!("typed_let!(bignum: u32 = 40 + 2) 之后 bignum = {bignum}");
    typed_let!(map: HashMap<String, u32> = HashMap::new());
    println!(
        "typed_let! 传泛型类型当 :ty 也成立：map.is_empty() = {}",
        map.is_empty()
    );

    // 4. :pat
    println!(
        "matches_some!(Some(7), Some(_)) = {}",
        matches_some!(Some(7), Some(_))
    );
    println!(
        "matches_some!(None::<i32>, Some(_)) = {}",
        matches_some!(None::<i32>, Some(_))
    );

    // 5. :literal
    assert_big!(8080); // u16 端口字面量 > 100 通过
                       // assert_big!(8); // 若取消注释：断言失败 panic（把字面量 8 展开进 assert! 条件）

    // 6. 多臂匹配的顺序
    is_zero!(0);
    is_zero!(7);
}
