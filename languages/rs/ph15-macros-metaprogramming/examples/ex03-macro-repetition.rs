// examples/ex03-macro-repetition.rs —— repetition（重复展开）实测：$(…)* / + / ?、分隔符、尾逗号、参数计数
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-macro-repetition.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告；输出为实测）

// my_vec!：复刻标准库 vec! 的最小版。
// 两条臂分工：空调用走 () 臂（避免「0 次 push」让 mut 变成 unused）；非空调用走重复臂，
// 模式 $( $x:expr ),+ 表示「1 个或多个表达式、用逗号分隔」，$(,)? 再吞掉可选尾逗号。
macro_rules! my_vec {
    () => {
        Vec::new() // 空调用单独一臂：省掉不必要的 mut
    };
    ($($x:expr),+ $(,)?) => {{
        let mut v = Vec::new();
        $( v.push($x); )+ // 至少 1 个元素，这里至少展开 1 句 push
        v
    }};
}

// echo_args!：重复展开 + 枚举：把每个参数的名字（token 原样）与值成对打印。
// 要求所有 $x 是同一类型（vals 是数组）。
macro_rules! echo_args {
    ($($x:expr),* $(,)?) => {{
        let names = [$(stringify!($x)),*]; // stringify 数组：参数代码原样
        let vals = [$($x),*]; // 值数组
        for (i, n) in names.iter().enumerate() {
            println!("  arg {i}: {n} = {}", vals[i]);
        }
    }};
}

// count_args!：编译期数出参数个数。经典技巧：给每个参数生成一个 ()，
// 数组长度就是参数个数（@unit 是「私有辅助臂」约定，避免与用户输入撞车）。
macro_rules! count_args {
    ($($x:expr),* $(,)?) => {
        <[()]>::len(&[$(count_args!(@unit $x)),*])
    };
    (@unit $x:expr) => {
        ()
    };
}

// min_len_2!：+ 表示「至少 1 个」。第一个参数用 $first 显式点名，
// 后面至少跟 1 个参数（总参数数 ≥ 2）——多臂之外，重复符号本身也能表达约束。
macro_rules! min_len_2 {
    ($first:expr, $($rest:expr),+ $(,)?) => {{
        let vals = [$first, $($rest),*];
        vals.len()
    }};
}

fn main() {
    // 1. 复刻 vec!：调用处 4 个元素 -> 展开 4 句 push
    let v = my_vec![1, 2, 3, 4];
    println!("1. my_vec![1, 2, 3, 4] = {:?}, len = {}", v, v.len());

    // 2. * 允许 0 个元素
    let e: Vec<i32> = my_vec![];
    println!("2. my_vec![]（0 个元素）= {:?}", e);

    // 3. $(,)? 吞尾逗号：两种写法等价
    let v2 = my_vec![1, 2, 3,];
    let v3 = my_vec![1, 2, 3];
    assert_eq!(v2, v3);
    println!("3. 带尾逗号 my_vec![1, 2, 3,] 与 my_vec![1, 2, 3] 结果一致（断言通过）");

    // 4. 重复展开 N 份打印语句（arg i 是 names 数组的下标，不是宏计数）
    echo_args!(1, 2 + 3, 4 * 10);

    // 5. 编译期参数计数（a/b/c/d/e 不需要预先定义——宏只数 token 不碰值）
    println!("5. count_args!(a, b, c, d, e) = {}", count_args!(a, b, c, d, e));

    // 6. + 至少一个：总参数数 ≥ 2
    println!(
        "6. min_len_2!(1, 2, 3) 参数个数 = {}（两个参数也接受: {}）",
        min_len_2!(1, 2, 3),
        min_len_2!(1, 2)
    );
}
