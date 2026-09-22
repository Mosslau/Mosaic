// examples/ex05-macro-errors.rs —— 声明宏典型编译错误实测（故意编译失败，勿期待编译通过）
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译（预期失败）：rustc --edition 2021 -D warnings ex05-macro-errors.rs -o /tmp/ex05
// 一次编译即可同时看到三个错误（rustc 1.92.0 实测，完整错误文本见 examples/README）。
// 验证状态：已验证（三个错误的错误文本均为本环境实测后写入）

// 错误 1：两个独立的 repetition 在同一层重复里混用，展开次数不一致。
// zip_bad!(1, 2, 3; 10, 20) 中 a 重复 3 次、b 重复 2 次，
// 而 $( println!("{} {}", $a, $b); )* 只有一层重复——编译器不知道以谁为准。
macro_rules! zip_bad {
    ($($a:expr),*; $($b:expr),*) => {
        // 实测错误：error: meta-variable `a` repeats 3 times, but `b` repeats 2 times
        $( println!("a={} b={}", $a, $b); )*
    };
}

// 错误 2：展开体里引用了未在匹配模式中声明的元变量（$undeclared）。
macro_rules! use_undeclared {
    ($x:expr) => {
        // 实测错误：error: expected expression, found `$`（$undeclared 不是臂声明的元变量）
        println!("{}", $x + $undeclared);
    };
}

// 错误 3：卫生性边界——宏体里直接写 total，解析发生在「宏定义处」作用域，
// 调用方 demo_hygiene 里的局部 total 并不会被看到（卫生性）；要引用调用方的东西必须传参。
// 实测错误：error[E0425]: cannot find value `total` in this scope（定位到宏调用处）
macro_rules! add_to {
    ($x:expr) => {
        $x + total
    };
}

fn demo_zip_bad() {
    zip_bad!(1, 2, 3; 10, 20);
}

fn demo_undeclared() {
    use_undeclared!(5);
}

fn demo_hygiene() {
    let total = 100; // 调用方有 total，但宏体里的 total 不指向它（卫生性）
    let r = add_to!(1);
    println!("{r}");
}

fn main() {
    demo_zip_bad();
    demo_undeclared();
    demo_hygiene();
}
