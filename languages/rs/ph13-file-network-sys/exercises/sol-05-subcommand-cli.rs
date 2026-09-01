// 来源：languages/rs/ph13-file-network-sys/exercises/README.md 练习 5
// 说明：手写「子命令式」命令行解析器——tool add <名> [-n 次数] / tool list / tool remove <名>，
//       解析结果建模为 enum（让非法组合无法表示，rust-patterns：Make illegal states
//       unrepresentable）。这是 clap Subcommand 的裸机版。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-05-subcommand-cli.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告；各分支解析结果与错误消息为实测）

/// 子命令解析结果：每种子命令只携带自己需要的字段
#[derive(Debug, PartialEq)]
enum Cmd {
    Add { name: String, count: u32 },
    List,
    Remove { name: String },
}

const USAGE: &str = "用法: tool <add <名> [-n 次数] | list | remove <名>>";

fn parse(args: &[String]) -> Result<Cmd, String> {
    // args 已去掉程序名
    let sub = args.first().ok_or_else(|| format!("缺少子命令\n{USAGE}"))?;
    match sub.as_str() {
        "add" => {
            let rest = &args[1..];
            let mut name: Option<String> = None;
            let mut count = 1u32;
            let mut i = 0;
            while i < rest.len() {
                match rest[i].as_str() {
                    "-n" | "--count" => {
                        i += 1;
                        let v = rest.get(i).ok_or_else(|| format!("-n 缺少值\n{USAGE}"))?;
                        count = v
                            .parse()
                            .map_err(|_| format!("无效次数 {v:?}\n{USAGE}"))?;
                    }
                    s if s.starts_with('-') => return Err(format!("未知选项 {s:?}\n{USAGE}")),
                    s => {
                        if name.is_some() {
                            return Err(format!("多余参数 {s:?}\n{USAGE}"));
                        }
                        name = Some(s.to_string());
                    }
                }
                i += 1;
            }
            let name = name.ok_or_else(|| format!("add 缺少 <名>\n{USAGE}"))?;
            Ok(Cmd::Add { name, count })
        }
        "list" => {
            if args.len() > 1 {
                return Err(format!("list 不接受参数\n{USAGE}"));
            }
            Ok(Cmd::List)
        }
        "remove" => match args.len() {
            2 => Ok(Cmd::Remove { name: args[1].clone() }),
            1 => Err(format!("remove 缺少 <名>\n{USAGE}")),
            _ => Err(format!("remove 只接受 1 个参数\n{USAGE}")),
        },
        other => Err(format!("未知子命令 {other:?}\n{USAGE}")),
    }
}

/// 便捷入口：从字符串数组解析（模拟 env::args().skip(1)）
fn p(argv: &[&str]) -> Result<Cmd, String> {
    let v: Vec<String> = argv.iter().map(|s| s.to_string()).collect();
    parse(&v)
}

fn main() {
    // ===== 正常路径 =====
    assert_eq!(
        p(&["add", "写笔记", "-n", "3"]).unwrap(),
        Cmd::Add { name: "写笔记".to_string(), count: 3 }
    );
    println!("1. add: {:?}", p(&["add", "写笔记", "-n", "3"]).unwrap());
    assert_eq!(p(&["add", "x"]).unwrap(), Cmd::Add { name: "x".to_string(), count: 1 });
    println!("2. add 缺省 count=1: {:?}", p(&["add", "x"]).unwrap());
    assert_eq!(p(&["list"]).unwrap(), Cmd::List);
    assert_eq!(p(&["remove", "x"]).unwrap(), Cmd::Remove { name: "x".to_string() });
    println!("3. list / remove 解析通过");

    // ===== 错误路径 =====
    let cases: &[(&[&str], &str)] = &[
        (&[], "缺少子命令"),
        (&["add"], "add 缺少"),
        (&["add", "x", "-n"], "-n 缺少值"),
        (&["add", "x", "-n", "abc"], "无效次数"),
        (&["list", "extra"], "list 不接受参数"),
        (&["delete", "x"], "未知子命令"),
    ];
    for (argv, expect_prefix) in cases {
        let e = p(argv).unwrap_err();
        let first = e.lines().next().unwrap();
        assert!(first.contains(expect_prefix), "{first} 应包含 {expect_prefix}");
        println!("4. {:?} → {}", argv, first);
    }
    println!("断言通过");
}
