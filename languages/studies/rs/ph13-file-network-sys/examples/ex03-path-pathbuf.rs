// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 3
// 说明：Path 与 PathBuf——借用 vs 拥有、push/join 拼接、文件名/扩展名/父目录提取、
//       组件分解、跨平台分隔符（不硬编码 '/'）。Path 之于 PathBuf，类似 str 之于 String。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-path-pathbuf.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告；MAIN_SEPARATOR 等输出为 macOS 实测，Windows 上为 '\'）

use std::path::{Component, Path, PathBuf};

fn main() {
    // ===== 1. Path（借用视图）vs PathBuf（拥有、可修改） =====
    let p: &Path = Path::new("/var/log/app.log"); // 只是字符串的视图，零开销
    let mut pb: PathBuf = PathBuf::from("/var/log"); // 堆上拥有，可拼接
    pb.push("app.log"); // push 自动插入分隔符
    println!("1. Path={p:?}  PathBuf={pb:?}");
    assert_eq!(p, pb.as_path());

    // ===== 2. 提取部件：文件名 / 词干 / 扩展名 / 父目录 =====
    println!("2. file_name={:?}", p.file_name().unwrap()); // Option<&OsStr>
    println!("2. file_stem={:?}", p.file_stem().unwrap()); // "app"
    println!("2. extension={:?}", p.extension().unwrap()); // "log"
    println!("2. parent={:?}", p.parent().unwrap()); // "/var/log"

    // ===== 3. 组件分解：跨平台语义的正确打开方式 =====
    print!("3. components: ");
    for c in p.components() {
        match c {
            Component::RootDir => print!("[根] "),
            Component::Normal(s) => print!("[{:?}] ", s),
            _ => print!("[其他] "),
        }
    }
    println!();

    // ===== 4. 拼接规则：push 遇到绝对路径会「整体替换」 =====
    let mut a = PathBuf::from("/base/dir");
    a.push("sub/file.txt"); // 相对路径 → 追加
    println!("4. push 相对: {a:?}");
    let mut b = PathBuf::from("/base/dir");
    b.push("/abs/other"); // 绝对路径 → 整个替换！常见陷阱
    println!("4. push 绝对: {b:?}");
    assert_eq!(b, PathBuf::from("/abs/other"));

    // ===== 5. 判断与转换 =====
    let p2 = Path::new("/tmp");
    println!("5. is_absolute={} is_dir={} exists={}", p2.is_absolute(), p2.is_dir(), p2.exists());
    // to_str() 返回 Option——路径可能不是合法 UTF-8（Unix 上路径是字节序列）
    println!("5. to_str={:?}", p2.to_str());

    // ===== 6. 跨平台分隔符：绝不硬编码 '/' 或 '\\' =====
    println!("6. MAIN_SEPARATOR = {:?}", std::path::MAIN_SEPARATOR);
    // 拼接永远用 push/join，不要用 format!("{}/{}", a, b)
    let cfg = Path::new("config").join("app.toml"); // join 返回新 PathBuf（不动原值）
    println!("6. join: {cfg:?}");

    // ===== 7. PathBuf 的 from 接受各种字符串 =====
    let from_str = PathBuf::from("a/b/c"); // &str
    let from_string = PathBuf::from(String::from("a/b/c")); // String
    assert_eq!(from_str, from_string);
    println!("7. 两种构造相等: {from_str:?}");
}
