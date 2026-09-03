// 修复版（与同目录 error.rs 对照）。思路：缩短借用作用域 = 让「最后一次使用」提前。
// 用 { } 块把只读区间显式收口，块结束处借用结束，之后对 items 的写操作畅通无阻。
// （这里 NLL 本来也能让借用随 println 提前结束；写成块是「肉眼可见地收口」，便于对照。）
// 验证：rustc --edition 2021 fix.rs -o /tmp/e04-long-borrow-scope-fix && /tmp/e04-long-borrow-scope-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let mut items = vec![1, 2, 3];
    {   // 只读借用区：一进一出，区间清清楚楚
        let a = &items[0];
        let b = &items[1];
        println!("{a} + {b}"); // 借用最后一次使用在块内
    }   // a/b 的借用在这里结束
    items.push(4); // 借用已收口，允许 &mut
    println!("len = {}", items.len());
}
