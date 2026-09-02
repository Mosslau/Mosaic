// examples/crates/src/bin/ex07-thiserror-derive.rs —— thiserror derive 实测：#[derive(Error)] + #[error] 模板 + #[from]
// 验证环境：rustc 1.92.0（macOS arm64）；thiserror 2.x（rsproxy 拉取，Cargo.lock 锁定）
// 编译/运行（在 examples/crates 目录）：
//   CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex07-thiserror-derive
// 验证状态：已验证（编译零警告；输出为实测）

use std::fs;
use thiserror::Error;

// #[derive(Error)] 需要同时 derive Debug（std::error::Error: Debug + Display 是编译期强制）
#[derive(Debug, Error)]
pub enum AppError {
    // 具名字段用 {name} 引用；元组字段用 {0} 引用（模板写法见主文档 3.6）
    #[error("配置文件不存在: {path}")]
    ConfigNotFound { path: String },
    #[error("端口 {port} 越界（合法范围 1-65535）")]
    InvalidPort { port: u32 },
    #[error("网络错误: {0}")]
    Network(String),
    // #[from]：自动生成 From<io::Error>，`?` 遇到 io::Error 自动转成 AppError::Io；
    // 同时自动成为 source() 的错误链下一环（io::Error 实现了 std::error::Error）
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),
}

fn read_cfg(path: &str) -> Result<String, AppError> {
    Ok(fs::read_to_string(path)?) // io::Error 经 #[from] 生成的 From 自动转换
}

fn main() {
    // 1. Display 由 #[error] 消息模板生成
    let e1 = AppError::ConfigNotFound {
        path: "/etc/app.toml".into(),
    };
    println!("1. {e1}");
    let e2 = AppError::InvalidPort { port: 70000 };
    println!("2. {e2}");
    let e3 = AppError::Network("connection refused".into());
    println!("3. {e3}");

    // 2. std::error::Error 已自动实现：可以装箱成 dyn Error
    let err_box: Box<dyn std::error::Error> = Box::new(e3);
    println!("4. 装箱成 dyn Error 可用: {err_box}");

    // 3. #[from] + ?：io::Error 自动转换（读不存在的文件）
    let bad = std::env::temp_dir().join("ph15-thiserror-does-not-exist.tmp");
    let bad = bad.to_str().unwrap();
    match read_cfg(bad) {
        Err(AppError::Io(io)) => println!("5. `?` 自动转换: io.kind() = {:?}", io.kind()),
        other => panic!("预期 AppError::Io，实际 {other:?}"),
    }

    // 4. 错误链：AppError::Io 的 source() 是原始 io::Error（thiserror 自动接线）
    let e = read_cfg(bad).unwrap_err();
    let mut chain: Vec<String> = Vec::new();
    let mut cur: Option<&dyn std::error::Error> = Some(&e);
    while let Some(err) = cur {
        chain.push(err.to_string());
        cur = err.source();
    }
    println!("6. source 错误链: {chain:?}");
    println!("7. 断言通过：链长度为 2（外层 Display + 内层 io::Error）");
    assert_eq!(chain.len(), 2);
}
