//! team-template 二进制入口：打印问候语与工具链信息。

use std::env;

fn main() {
    let name = env::args().nth(1).unwrap_or_default();
    println!("{}", team_template::greeting(&name));
    let (major, minor) = team_template::MSRV;
    println!("template MSRV: Rust {major}.{minor}（见 Cargo.toml rust-version）");
}
