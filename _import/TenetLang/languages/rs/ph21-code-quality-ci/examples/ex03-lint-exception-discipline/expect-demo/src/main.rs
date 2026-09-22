// expect-demo —— #[expect] 期望落空的行为演示（红态 crate，见 Cargo.toml 头注释）。
//
// 本机实测（cargo/clippy 1.92.0）：
//   cargo clippy                                   → 通过但有 1 个 warning（期望落空）
//   cargo clippy -- -D warnings                    → 失败（把这条 warning 当错误）
// 输出核心行：
//   warning: this lint expectation is unfulfilled
//    = note: `#[warn(unfulfilled_lint_expectations)]` on by default

// 期望被满足：manual_map 确实会在此触发，expect 静默通过（无警告）。
#[expect(clippy::manual_map)]
fn satisfied(o: Option<u32>) -> Option<u32> {
    match o {
        Some(v) => Some(v + 1),
        None => None,
    }
}

// 期望落空：这里已经直接用了 o.map(...)，manual_map 不会再触发——
// expect 反过来报「期望未兑现」，提醒你这条例外已经不需要了，请删除或改写。
#[expect(clippy::manual_map)]
fn no_longer_triggers(o: Option<u32>) -> Option<u32> {
    o.map(|v| v + 1)
}

fn main() {
    println!("{:?} {:?}", satisfied(Some(1)), no_longer_triggers(Some(2)));
}
