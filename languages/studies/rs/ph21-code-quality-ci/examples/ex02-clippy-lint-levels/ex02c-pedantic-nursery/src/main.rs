// ex02c pedantic / nursery 组：两段「默认全绿」的代码，分别演示「显式 -W 才会响」的
// opt-in 组。用普通注释而非 doc 注释，避免 rustdoc 类 lint 在 -W pedantic 下刷屏。
//
// 本机实测（cargo/clippy 1.92.0）：
//   cargo clippy --bin ex02c-pedantic-nursery                       → 退出 0，零输出（默认不开）
//   cargo clippy --bin ex02c-pedantic-nursery -- -W clippy::pedantic
//       → warning: clippy::unnecessary_wraps：返回值无必要包一层 Result
//   cargo clippy --bin ex02c-pedantic-nursery -- -W clippy::nursery
//       → warning: clippy::missing_const_for_fn：本可写成 const fn
// 两点教学：① pedantic/nursery 默认 allow，不显式 -W 永不响——它们不会混进 -D warnings；
//           ② 同一函数 unnecessary_wraps 在 pedantic 组、missing_const_for_fn 在 nursery 组
//           ——分组归属要按工具链实测，别背旧文档（主文档 3.3/4.1）。

// pedantic 组候选：函数永远返回 Ok，包一层 Result 无意义（unnecessary_wraps）。
// 真实工程里这类「签名先写成 Result、实现从不 Err」很常见；治理方向是让签名诚实。
fn lookup_name(id: u32) -> Result<String, ()> {
    Ok(format!("user-{id}"))
}

// nursery 组候选：纯函数不读外部状态，可标 const fn（missing_const_for_fn，1.92 实测在 nursery）。
fn double(x: i32) -> i32 {
    x * 2
}

fn main() {
    println!("{:?}", lookup_name(7));
    println!("{}", double(21));
}
