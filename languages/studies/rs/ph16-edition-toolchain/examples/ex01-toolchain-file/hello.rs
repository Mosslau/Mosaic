// examples/ex01-toolchain-file/hello.rs —— rust-toolchain.toml 实战的「被编译物」
// 验证环境：rustc 1.92.0（macOS arm64，rustup 管理的 stable）
// 验证步骤（在本目录下执行，观察 rustup 的目录级 override 生效）：
//   1. rustup show          # active toolchain 一行应显示 "overridden by .../rust-toolchain.toml"
//   2. rustc --version      # 走 rust-toolchain.toml 选中的通道
//   3. rustc --edition 2021 -D warnings hello.rs -o /tmp/ph16-ex01-hello
//   4. /tmp/ph16-ex01-hello
// 验证状态：已验证（输出为实测）

fn main() {
    // rustc 不提供「打印自身版本」的标准库 API，版本信息由上面的 rustc --version 给出；
    // 这里只证明：代码确实是被 rust-toolchain.toml 选中的那条工具链编译并运行的。
    println!("hello from the toolchain pinned by rust-toolchain.toml");
    println!("1 + 1 = {}", 1 + 1);
}
