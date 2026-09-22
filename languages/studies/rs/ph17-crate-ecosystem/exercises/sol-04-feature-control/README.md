# sol-04-feature-control —— 练习 4 参考实现说明

> 参考实现（先自己做再看）。配套主文档 3.9（feature flags 语义）。
> 验证环境：rustc/cargo 1.92.0；依赖 crates.io 拉取（可配 rsproxy）——编译已验证（本机实测 cargo build 通过）；运行需联网访问 httpbin.org，未验证。

## 改动前后对照（练习 4 的答案主体）

### 改造前

```toml
[dependencies]
reqwest = "0.12"
tokio = { version = "1", features = ["full"] }
```

`cargo tree --depth 1` 观察点（预期，随版本漂移）：

- reqwest 默认特性含 `native-tls` → 依赖树出现 `openssl-sys`（系统 OpenSSL 绑定），部署要装 OpenSSL 或静态编译
- tokio `full` 等价于一次开 rt-multi-thread / macros / net / time / io-util / sync / signal / process / fs / …数十个特性，编译时间与产物体积全包

### 改造后（见 Cargo.toml）

```toml
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls", "json"] }
tokio = { version = "1", default-features = false, features = ["rt-multi-thread", "macros"] }
```

`cargo tree --depth 1` 观察点（预期）：

- `openssl-sys` 消失，TLS 走 `rustls`（纯 Rust，无系统库依赖）
- tokio 只剩 rt-multi-thread + macros 两组的依赖

记录方式：改前改后各跑一次 `cargo tree --depth 1` 与 `cargo tree -e features | grep -E "tokio|reqwest"`，把两次输出粘贴进答案即可完成对照要求。

## 「加一问」答案：另一个 crate 强制要求 tokio/rt 时

**会出现。** 关掉默认特性只影响「你自己声明的开关」；feature 统一（并集）规则下，依赖图里任何一个依赖方开了 `tokio/rt`，最终构建的 tokio 就带 `rt`——你的 `default-features = false` 挡不住别人的开关（主文档 3.9 语义点 2 / 4.2）。这正是「控制 feature 范围」的边界：你能控制的只有自己声明的部分，全图并集才是实际生效的集合；要确认实际生效集合，跑 `cargo tree -e features`。
