// ex04-cxx-bridge 的 cxx 双向桥：Rust 与 C++ 互相调用（主文档 3.4/4.5）
// 验证环境：cxx crate 1.0.199 + rustc/cargo 1.92.0（Apple clang 21.0.0 作 C++ 编译器）
// 构建/运行（ex04-cxx-bridge/ 目录内）：
//   export PATH="$HOME/.cargo/bin:$PATH"
//   cargo run
// 验证状态：已验证（本机 cargo fetch 拉取成功、编译零警告、双向调用断言全绿）
// 教学点：
//   - unsafe extern "C++"：Rust 调 C++（签名以 include! 的 cpp_side.h 为准）
//   - extern "Rust"：C++ 回调 Rust（cxx 生成 C++ 侧声明，见生成的 .../main.rs.h）
//   - 类型翻译：Rust Vec/String/&str ↔ C++ rust::Vec/rust::String/rust::Str
#[cxx::bridge]
mod ffi {
    // ---- C++ 侧实现、Rust 侧调用（include! 指向 C++ 头）----
    unsafe extern "C++" {
        include!("cpp_side.h");
        fn cpp_sum(values: &Vec<i64>) -> i64;
        fn cpp_describe(name: &str) -> String;
        // cpp_compose 在 C++ 里回调 rust_triple —— 双向证据
        fn cpp_compose(x: i32) -> i32;
    }

    // ---- Rust 侧实现、C++ 侧回调（cxx 自动生成 C++ 声明）----
    extern "Rust" {
        fn rust_triple(x: i32) -> i32;
        fn rust_greeting(who: &str) -> String;
    }
}

// extern "Rust" 的实现，放普通 Rust 代码里
fn rust_triple(x: i32) -> i32 {
    x * 3
}

fn rust_greeting(who: &str) -> String {
    format!("hello {who}, from Rust")
}

fn main() {
    let sum = ffi::cpp_sum(&vec![1, 2, 3, 4, 5]);
    println!("cpp_sum = {sum}");  // 15：Rust → C++
    let desc = ffi::cpp_describe("Alice");
    println!("cpp_describe = {desc}");  // "hello Alice, from Rust"：Rust → C++ → Rust
    let comp = ffi::cpp_compose(7);
    println!("cpp_compose(7) = {comp}");  // 3*7+1 = 22：C++ 内部回调 rust_triple
    assert_eq!(sum, 15);
    assert!(desc.contains("Alice") && desc.contains("from Rust"));
    assert_eq!(comp, 22);
    println!("cxx bidirectional OK");
}
