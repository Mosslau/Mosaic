// build.rs —— 把 #[cxx::bridge] 生成桥 + 手写 C++ 源一起编进静态库
// 验证环境：rustc/cargo 1.92.0；首次构建需网络拉取 cxx crate（本机拉取成功，版本 1.0.199）
fn main() {
    cxx_build::bridge("src/main.rs")
        .file("src/cpp_side.cc")
        .include("src")  // cpp_side.h 所在目录（生成桥源与手写 .cc 都要找到它）
        .flag_if_supported("-std=c++20")
        .compile("cpp_side");
    println!("cargo:rerun-if-changed=src/main.rs");
    println!("cargo:rerun-if-changed=src/cpp_side.cc");
    println!("cargo:rerun-if-changed=src/cpp_side.h");
}
