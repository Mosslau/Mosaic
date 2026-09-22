# ex04-reproducible-build —— 可复现构建双目录哈希对比

对应主文档 3.8。用一个零依赖 bin crate（`ph24-reprobin`）演示**可复现构建**的核心验证法：同一 commit + 同一工具链，在两个互不干扰的 `CARGO_TARGET_DIR` 各做一次干净构建，对比产物 SHA-256——一致即「同一 commit 长出同一个制品」。

## 验证状态

- **已验证**（本机 macOS arm64 / rustc/cargo 1.92.0，2026-09-04；产物哈希 `1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c`，两次构建完全相同）
- 零依赖 bin——无需联网、无需安装任何 cargo 子命令，`cargo build` 即可复现

## 目录结构

```text
ex04-reproducible-build/
├── Cargo.toml        # ph24-reprobin v1.2.3，零依赖
├── Cargo.lock        # 由 cargo build 生成（应用提交 lock 的惯例，ph16）
├── README.md         # 本文件
└── src/main.rs       # 固定文本输出（与构建环境无关的运行时计算）
```

## 运行命令与实测输出

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd ex04-reproducible-build

# 两次干净构建（独立 target 目录 = 两次「从零开始」的构建）
CARGO_TARGET_DIR=/tmp/ph24-t1 cargo build --release
CARGO_TARGET_DIR=/tmp/ph24-t2 cargo build --release

# 对比产物哈希
shasum -a 256 /tmp/ph24-t1/release/ph24-reprobin /tmp/ph24-t2/release/ph24-reprobin
# 实测输出：
# 1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  /tmp/ph24-t1/release/ph24-reprobin
# 1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  /tmp/ph24-t2/release/ph24-reprobin
```

运行产物（两目录任意一个）确认行为一致：

```bash
/tmp/ph24-t1/release/ph24-reprobin
# 输出：ph24-reprobin sum=38463566
```

## 为什么这能证明「可复现」

- **双目录 = 双倍干净**：两次构建互不共享增量缓存——若只在一个目录重编，增量缓存命中必然产生相同产物，不能证明任何事。双 `CARGO_TARGET_DIR` 相当于两台互不相干的构建机。
- **可复现构建 = lock + toolchain + 确定性三件齐全**：本示例的 lock（工程内提交）+ rust-toolchain（本例用系统 stable 1.92；生产用 rust-toolchain.toml 固定，ph16）+ rustc 确定性编译。任何一件缺失都可能让产物漂移。
- **可复现的边界**（破坏一致性的因素）：跨平台/跨 CPU 产物天然不同；`debug`/`release` 与 profile 参数（lto/codegen-units）不同即不同；`build.rs` 若嵌入路径/时间戳即破坏确定性。比较域应限定「同平台同 profile 同工具链」。

## 尝试破坏它（理解边界的好练习）

把 `src/main.rs` 的 `println!` 换成包含 `env!("CARGO_PKG_VERSION")` 之外的内容——例如在 `Cargo.toml` 里改 `version`，两个目录重新构建后哈希一起变（说明哈希对内容敏感）；改 `[profile.release]` 加 `opt-level` 差异，两目录产物即分道扬镳（说明 profile 是可复现性的输入参数）。
