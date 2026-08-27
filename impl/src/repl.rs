//! 交互式 REPL：逐行读取、执行、打印结果。
//!
//! 简易多行支持：花括号不闭合时继续读取下一行，
//! 直到括号配平或遇到真正的语法错误。

use std::io::{self, Write};

use crate::ast::Stmt;
use crate::error::TResult;
use crate::interpreter::Interpreter;
use crate::parser::Parser;

const BANNER: &str = r#"
🏛 Tenet REPL — 万语归宗，探语言之本源
输入 Tenet 语句，`exit` 或 Ctrl-D 退出。
"#;

/// 运行 REPL，直到用户退出或读到 EOF。
pub fn run() -> TResult<()> {
    let mut interp = Interpreter::new();
    let stdin = io::stdin();
    let mut buffer = String::new();

    println!("{BANNER}");
    loop {
        if buffer.is_empty() {
            print!("tenet> ");
        } else {
            print!("     > ");
        }
        io::stdout().flush().ok();

        let mut line = String::new();
        match stdin.read_line(&mut line) {
            Ok(0) => {
                println!();
                break;
            }
            Ok(_) => {}
            Err(e) => {
                eprintln!("读取输入失败: {e}");
                break;
            }
        }
        let trimmed = line.trim();
        if trimmed == "exit" || trimmed == "quit" {
            break;
        }
        buffer.push_str(&line);

        // 括号未配平 → 继续收集输入
        if !balanced(&buffer) {
            continue;
        }

        let src = std::mem::take(&mut buffer);
        match Parser::parse(&src) {
            Ok(program) => {
                if let Err(e) = run_parsed(&mut interp, &program) {
                    eprintln!("{e}");
                }
            }
            Err(e) => {
                // REPL 习惯不写分号：若错误只是「期望 `;` 但遇到 EOF」，补上分号重试
                let trimmed = src.trim_end();
                if e.message.contains("`;`")
                    && e.pos.as_ref().map_or(false, |p| p.line >= line_count(&src))
                    && !trimmed.ends_with(';')
                {
                    match Parser::parse(&format!("{src};")) {
                        Ok(program) => {
                            if let Err(run_err) = run_parsed(&mut interp, &program) {
                                eprintln!("{run_err}");
                            }
                            continue;
                        }
                        Err(_) => eprintln!("{e}"),
                    }
                } else {
                    eprintln!("{e}");
                }
            }
        }
    }
    Ok(())
}

/// 执行解析结果：单条非 print 表达式 → 求值回显；否则作为程序执行。
fn run_parsed(interp: &mut Interpreter, program: &crate::ast::Program) -> TResult<()> {
    if program.stmts.len() == 1 {
        if let Stmt::Expr(expr) = &program.stmts[0] {
            if !matches!(expr, crate::ast::Expr::Call { callee, .. } if callee == "print") {
                let v = interp.eval_expr(expr)?;
                if !matches!(v, crate::value::Value::Nil) {
                    println!("{}", v);
                }
                return Ok(());
            }
        }
    }
    interp.run_program(program)
}

/// 统计源码中的行数（用于判断错误是否在最后一行）。
fn line_count(src: &str) -> usize {
    src.lines().count()
}

/// 粗略判断花括号 / 括号 / 方括号是否配平（忽略字符串与注释内的括号）。
fn balanced(src: &str) -> bool {
    let mut stack = Vec::new();
    let mut chars = src.chars().peekable();
    let mut in_str = false;
    while let Some(c) = chars.next() {
        if in_str {
            if c == '\\' {
                chars.next();
            } else if c == '"' {
                in_str = false;
            }
            continue;
        }
        match c {
            '"' => in_str = true,
            '(' | '{' | '[' => stack.push(c),
            ')' | '}' | ']' => {
                let open = match c {
                    ')' => '(',
                    '}' => '{',
                    _ => '[',
                };
                if stack.pop() != Some(open) {
                    return true; // 配不上，交给 parser 报错
                }
            }
            _ => {}
        }
    }
    !in_str && stack.is_empty()
}
