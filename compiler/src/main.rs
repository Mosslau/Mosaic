//! Tenet 编译器命令行入口（clang / rustc 风格）。
//!
//!   tenet build <file> [-o <out>]   编译为原生二进制（LLVM IR → clang 链接）
//!   tenet run   <file>              编译并直接运行
//!   tenet ir    <file>              只输出 LLVM IR（调试用）

use std::io::Write;
use std::path::Path;
use std::process::{Command, ExitCode};

use tenet::TenetError;

const USAGE: &str = "用法:\n  tenet build <file> [-o <out>]\n  tenet run <file>\n  tenet ir <file>";

/// 运行时库：字符串拼接与比较（链接时与编译产物一起编入）。
const RUNTIME_C: &str = r#"
#include <stdlib.h>
#include <string.h>

char* tenet_concat(const char* a, const char* b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = malloc(la + lb + 1);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}

int tenet_strcmp(const char* a, const char* b) {
    return strcmp(a, b);
}
"#;

fn read_file(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| format!("无法读取文件 {path}: {e}"))
}

fn write_temp(name: &str, content: &str) -> Result<std::path::PathBuf, String> {
    let dir = std::env::temp_dir();
    let path = dir.join(format!(
        "tenet-{}-{name}",
        std::process::id()
    ));
    let mut f = std::fs::File::create(&path).map_err(|e| e.to_string())?;
    f.write_all(content.as_bytes()).map_err(|e| e.to_string())?;
    Ok(path)
}

fn clang_bin() -> String {
    std::env::var("TENET_CLANG").unwrap_or_else(|_| "clang".to_string())
}

/// 把 .ll 链接成原生二进制。
fn link(ir_path: &std::path::Path, runtime_path: &std::path::Path, out: &str) -> Result<(), String> {
    let status = Command::new(clang_bin())
        .args([ir_path.to_str().unwrap(), runtime_path.to_str().unwrap(), "-o", out])
        .status()
        .map_err(|e| format!("无法执行 clang（需要安装 LLVM，或设置 TENET_CLANG 指定路径）: {e}"))?;
    if !status.success() {
        return Err("clang 链接失败".into());
    }
    Ok(())
}

fn build(src_path: &str, out: &str) -> Result<(), String> {
    let src = read_file(src_path)?;
    let ir = tenet::compile_to_ir(&src).map_err(|e: TenetError| e.to_string())?;

    // 调试：保留 IR 到 out.ll 旁边
    let ir_path = write_temp("out.ll", &ir)?;
    let runtime_path = write_temp("runtime.c", RUNTIME_C)?;
    link(&ir_path, &runtime_path, out)?;
    let _ = std::fs::remove_file(&ir_path);
    let _ = std::fs::remove_file(&runtime_path);
    Ok(())
}

fn default_output(src_path: &str) -> String {
    let p = Path::new(src_path);
    p.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "a.out".into())
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };

    match cmd.as_str() {
        "ir" => {
            if args.len() != 2 {
                eprintln!("{USAGE}");
                return ExitCode::from(2);
            }
            let src = match read_file(&args[1]) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("{e}");
                    return ExitCode::FAILURE;
                }
            };
            match tenet::compile_to_ir(&src) {
                Ok(ir) => {
                    print!("{ir}");
                    ExitCode::SUCCESS
                }
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::FAILURE
                }
            }
        }
        "build" => {
            if args.len() < 2 || args.len() > 4 {
                eprintln!("{USAGE}");
                return ExitCode::from(2);
            }
            let src_path = &args[1];
            let mut out = default_output(src_path);
            if let Some(i) = args.iter().position(|a| a == "-o") {
                if let Some(o) = args.get(i + 1) {
                    out = o.clone();
                }
            }
            match build(src_path, &out) {
                Ok(()) => {
                    println!("已生成可执行文件: {out}");
                    ExitCode::SUCCESS
                }
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::FAILURE
                }
            }
        }
        "run" => {
            if args.len() != 2 {
                eprintln!("{USAGE}");
                return ExitCode::from(2);
            }
            let src_path = &args[1];
            let bin = std::env::temp_dir().join(format!("tenet-run-{}", std::process::id()));
            if let Err(e) = build(src_path, bin.to_str().unwrap()) {
                eprintln!("{e}");
                return ExitCode::FAILURE;
            }
            let status = match Command::new(&bin).status() {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("运行失败: {e}");
                    return ExitCode::FAILURE;
                }
            };
            let _ = std::fs::remove_file(&bin);
            match status.code() {
                Some(code) => ExitCode::from(code as u8),
                None => ExitCode::FAILURE,
            }
        }
        _ => {
            eprintln!("{USAGE}");
            ExitCode::from(2)
        }
    }
}
