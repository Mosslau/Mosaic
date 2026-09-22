// 01 · 所有权与借用演示
// 运行：cargo run --bin 01_ownership
// 把被注释掉的代码取消注释，cargo build 会拒绝编译——亲眼看到 borrow checker。

fn main() {
    println!("== 所有权：一个值一个 owner ==");
    let s = String::from("tenet");
    let t = s; // move：所有权转移给 t
    println!("t owns: {t}");
    // println!("{s}"); // ❌ 编译错误：use of moved value

    println!("\n== 借用：借了还能用 ==");
    let s2 = String::from("borrow");
    println!("len = {}", string_len(&s2));
    println!("s2 仍可用: {s2}"); // 借用结束，owner 还在

    println!("\n== 可变借用：同一时刻只有一个 ==");
    let mut n = 42;
    let r = &mut n;
    *r += 1;
    println!("n = {n}");
    // let r2 = &mut n; // ❌ 编译错误：n 已被可变借用

    println!("\n== 作用域结束自动释放 ==");
    {
        let tmp = String::from("scoped");
        println!("在块内: {tmp}");
    } // tmp 在这里被释放，无需手动 free
    println!("块外看不到 tmp（已释放）");
}

fn string_len(s: &String) -> usize {
    s.len() // 借用者只读，不拥有
}
