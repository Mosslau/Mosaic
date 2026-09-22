// 来源：languages/rs/ph13-file-network-sys/exercises/README.md 练习 2
// 说明：read_dir 递归遍历目录树，统计文件数/目录数/总字节数——Path/PathBuf 与
//       fs::metadata 的综合运用（对应主文档 3.2、3.3）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-02-dir-size.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告；3 文件 / 2 目录（含根） / 26 字节为实测确定值）

use std::fs::{self, DirEntry};
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Default, PartialEq)]
struct Stat {
    files: u64,
    dirs: u64, // 含传入的根目录本身
    bytes: u64,
}

/// 递归统计 path 下的文件/目录/总字节数
fn walk(path: &Path, stat: &mut Stat) -> io::Result<()> {
    stat.dirs += 1; // path 本身是目录
    for entry in fs::read_dir(path)? {
        let entry: DirEntry = entry?; // 迭代器每项也是 Result
        let p: PathBuf = entry.path();
        let meta = entry.metadata()?; // 注意：metadata() 会跟随符号链接，如需不跟随用 symlink_metadata
        if meta.is_dir() {
            walk(&p, stat)?; // 递归进子目录
        } else if meta.is_file() {
            stat.files += 1;
            stat.bytes += meta.len();
        }
    }
    Ok(())
}

fn main() -> io::Result<()> {
    // 造已知目录树：
    // /tmp/ph13-sol02/
    // ├── a.txt        (10 字节 "0123456789")
    // └── sub/
    //     ├── b.txt    (6 字节 "abcdef")
    //     └── c.log    (10 字节 "0123456789")
    let root = PathBuf::from("/tmp/ph13-sol02");
    let _ = fs::remove_dir_all(&root); // 幂等清理
    fs::create_dir_all(root.join("sub"))?;
    fs::write(root.join("a.txt"), "0123456789")?;
    fs::write(root.join("sub/b.txt"), "abcdef")?;
    fs::write(root.join("sub/c.log"), "0123456789")?;

    let mut stat = Stat::default();
    walk(&root, &mut stat)?;
    println!("统计: {stat:?}");
    assert_eq!(stat, Stat { files: 3, dirs: 2, bytes: 26 });

    // join 拼接验证：root.join("sub/b.txt") 存在且是文件
    let deep = root.join("sub").join("b.txt");
    assert!(deep.is_file());
    println!("deep path = {:?}", deep);
    assert_eq!(deep.extension().unwrap(), "txt");

    fs::remove_dir_all(&root)?;
    println!("断言通过");
    Ok(())
}
