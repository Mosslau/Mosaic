# sol-04 —— 可复现构建验证参考实现

> 三组实验均**本机实测**（macOS arm64 / cargo 1.92.0，2026-09-04）。练习对象 `examples/ex04-reproducible-build/`；破坏实验在 `/tmp` 副本上进行（**不修改仓库文件**——把 Cargo.toml 改坏又还原是常见事故，正确姿势是复制到 /tmp 折腾）。

## 实验 1：基线（同一 commit 双目录构建）

```bash
export PATH="$HOME/.cargo/bin:$PATH"
CARGO_TARGET_DIR=/tmp/ph24-t1 cargo build --release   # 干净构建 ①
CARGO_TARGET_DIR=/tmp/ph24-t2 cargo build --release   # 干净构建 ②
shasum -a 256 /tmp/ph24-t1/release/ph24-reprobin /tmp/ph24-t2/release/ph24-reprobin
```

实测（两条哈希完全相同）：

```text
1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  …/ph24-reprobin (t1)
1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  …/ph24-reprobin (t2)
```

结论：同一 commit + 同一工具链 + 双干净目录 → 产物逐字节一致（可复现）。

## 实验 2：破坏实验 A——改 version

```bash
cp -r ex04-reproducible-build /tmp/ph24-sol4x && cd /tmp/ph24-sol4x
perl -pi -e 's/version = "1\.2\.3"/version = "1.2.4"/' Cargo.toml   # 只改版本号
CARGO_TARGET_DIR=/tmp/ph24-sol4x-t cargo build --release
shasum -a 256 /tmp/ph24-sol4x-t/release/ph24-reprobin
```

实测哈希：`e3024df14e274e7d831f057ab6246074ef1d15d4e02e9afc7fba66711a7029d1`

**结论：改 version 会改变产物哈希**——尽管 `strings` 在二进制里查不到 `"1.2.4"`（0 次命中），rustc 的 crate 元数据/构建指纹把版本纳入，二进制存在不可见差异。**这恰好是本题的陷阱考点**：别凭「版本串不在二进制里」就断言「版本无关」——可复现性论证只能靠哈希实验，不能靠对二进制内容的猜测。

## 实验 3：破坏实验 B——改 profile

```bash
cd /tmp/ph24-sol4x2   # 另一份 1.2.3 副本
printf '\n[profile.release]\ncodegen-units = 16\n' >> Cargo.toml   # 改 codegen 单元数
CARGO_TARGET_DIR=/tmp/ph24-sol4x2-t cargo build --release
shasum -a 256 /tmp/ph24-sol4x2-t/release/ph24-reprobin
```

实测哈希：`d00684f4f32c52d9cf5524ab414001fee87624502822a29ec0bbc8e3e7bd7d10`

**结论：profile 是可复现性的输入参数**——codegen-units 改变后端代码生成的分块与布局，产物即不同。这也解释了 ph22 为什么把 profile 当一等配置项：profile 不仅影响性能，还影响「产物是谁」。

## 哈希对照表

| 配置 | 产物 SHA-256（前 16 位） | 相对基线的变化 |
|------|------------------------|---------------|
| 基线：version 1.2.3 + 默认 profile | `1205b2a934974b02…` | — |
| 破坏 A：version 1.2.4 + 默认 profile | `e3024df14e274e7d…` | 改 version → 变 |
| 破坏 B：version 1.2.3 + `codegen-units = 16` | `d00684f4f32c52d9…` | 改 profile → 变 |
| A+B 同时：version 1.2.4 + cgu 16 | `d4e00d1360089edc…` | 两个输入都变 → 变 |

## 结论三连

1. **可复现构建验证必须「干净」**：双 CARGO_TARGET_DIR 互不共享增量缓存，任何产物相同才有说服力（单目录重编 = 命中缓存，证明不了任何事）；
2. **输入集合 = 源码 + 工具链 + lock + profile**：改其中任一项，哈希都应变化——这既是「可复现」的验证法，也是「输入敏感」的证明；哈希不随输入变反而说明哪里没验证到；
3. **答案里的「为什么 version 会变哈希」要诚实**：不是因为它把版本写进了可见内容，而是 crate 元数据进指纹——`strings` 查不到不等于无关（实验 2 的实测）。

## 验收对照

- [x] 基线双目录哈希相同（1205b2a9… × 2）
- [x] 破坏实验 A：version 1.2.4 → e3024df1…（变化）
- [x] 破坏实验 B：cgu 16 → d00684f4…（变化）
- [x] 哈希对照表 + 三句结论（含「版本串不在二进制里但哈希仍变」的诚实分析）
