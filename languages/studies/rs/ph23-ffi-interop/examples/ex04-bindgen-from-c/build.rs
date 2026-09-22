//! ex04 的 build.rs：三步自动化 —— bindgen 生成绑定、clang 编译 C 实现、把静态库路径告诉 rustc。
//!
//! 教学点：bindgen 的惯用姿势是挂在 build.rs 里「构建期扫描头文件」，生成的绑定
//! 写入 OUT_DIR（不落仓库）；C 侧实现用 `cc`/`ar` 命令当场编译。真实工程里若 C 库
//! 是系统库/第三方库，通常只需 `cargo:rustc-link-lib` 指到它，无需亲自编译（本示例
//! 为自包含，把 C 实现也一并编了）。
//!
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）；本机实测「已验证」。

use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR set by cargo"));

    // 1. bindgen：扫描头文件 → 生成 Rust 绑定到 OUT_DIR/bindings.rs
    let bindings = bindgen::Builder::default()
        .header("include/vector_math.h")
        // 让 bindgen 为它「读到」的系统头文件向 cargo 声明依赖，
        // 头文件变更时自动触发 build.rs 重跑
        .parse_callbacks(Box::new(bindgen::CargoCallbacks::new()))
        .generate()
        .expect("bindgen 生成绑定失败");
    bindings
        .write_to_file(out_dir.join("bindings.rs"))
        .expect("写入 bindings.rs 失败");

    // 2. 编译 C 实现：vector_math.c → .o → libvector_math.a（-Iinclude 让引号 include 找到头文件）
    let obj = out_dir.join("vector_math.o");
    let cc_status = Command::new("cc")
        .args([
            "-O2",
            "-Wall",
            "-Wextra",
            "-Iinclude",
            "-c",
            "c_src/vector_math.c",
            "-o",
        ])
        .arg(&obj)
        .status()
        .expect("无法启动 cc（macOS 的 cc 即 clang）");
    assert!(cc_status.success(), "cc -c vector_math.c 失败");
    let archive = out_dir.join("libvector_math.a");
    let ar_status = Command::new("ar")
        .args(["rcs"])
        .arg(&archive)
        .arg(&obj)
        .status()
        .expect("无法启动 ar");
    assert!(ar_status.success(), "ar 打包失败");

    // 3. 告知 rustc 去哪里找、链什么
    println!("cargo:rustc-link-search=native={}", out_dir.display());
    println!("cargo:rustc-link-lib=static=vector_math");

    // 源文件变更触发重建
    println!("cargo:rerun-if-changed=include/vector_math.h");
    println!("cargo:rerun-if-changed=c_src/vector_math.c");
}
