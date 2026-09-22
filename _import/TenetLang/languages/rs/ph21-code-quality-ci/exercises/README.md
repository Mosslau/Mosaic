# exercises —— Clippy、rustfmt、CI 与代码质量阶段练习

三题与 roadmap 第 21 节练习一一对应。每题一个参考实现目录 `sol-XX/`，**先自己做，做完再看**。每题标注难度（★~★★★）。练习对象可以取自己以前阶段的 crate，也可以直接用题目里指出的本阶段现有材料（examples/ex02a 是故意携带 lint 的治理前 crate、examples/ex06 是质量全绿的 workspace——当治理对象正合适）。

验证环境：rustc/cargo/clippy **1.92.0**、rustfmt **1.8.0**（macOS arm64，rustup 管理），bash 3.2+。参考实现的通用质量闸门一致：

```bash
# 在任一 sol-XX 目录内执行
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph21-target
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

## 练习 1：给项目加 fmt/clippy/test CI（★★）

**目标**：把一个质量全绿的 crate 接入 GitHub Actions 质量门禁（roadmap 练习「给项目加 fmt/clippy/test CI」）。
**要求**：取 `examples/ex06-local-check-script`（workspace）或自己之前的 crate，新建 `.github/workflows/ci.yml`：包含 checkout → 安装工具链（含 rustfmt/clippy 组件）→ 三个独立 step（`cargo fmt --check` → `cargo clippy --all-targets -- -D warnings` → `cargo test`）；CI 无法在本机跑，因此再写一个 `verify-local.sh` 把三个 run 原样在本地依次执行，验证 CI 命令确实可行。
**提示**：三个门禁必须拆 step（失败可定位）；`-D warnings` 与 `--all-targets` 缺一不可（主文档 3.2/3.5）；workspace 用 `--all`/`--workspace` 变体（ex06 的 check.sh 里见过两种形态）。
**验收**：`ci.yml` 能被 YAML 解析；`./verify-local.sh` 本地退出 0；能说出「为什么拆三个 step」「为什么 clippy 不裸跑」。
参考实现：`sol-01-fmt-clippy-ci/`。

## 练习 2：清理 clippy warnings（★★★）

**目标**：把一段故意带 lint 的代码治理到零告警（roadmap 练习「清理 clippy warnings」）。
**要求**：治理下面的「治理前代码」（可自建 crate 或取 `examples/ex02a` 的整文件），跑 `cargo clippy` 看清触发清单，然后逐条修到 `cargo clippy --all-targets -- -D warnings` 全绿；**每个残留例外（如果你留了）必须带理由注释**。治理前代码（故意携带 lint）：

```rust
// 治理前：你能数出几条 warning？分别属于哪个组？
fn total_key_chars(records: &[Record]) -> usize {
    let mut total = 0;
    for i in 0..records.len() {          // style：needless_range_loop
        total += records[i].key.chars().count();
    }
    total
}

fn longest_key(records: &Vec<Record>) -> Option<&str> {   // style：ptr_arg（应 &[Record]）
    let mut best: Option<&Record> = None;
    for i in 0..records.len() {
        match &best {
            None => best = Some(&records[i]),
            Some(cur) if records[i].key.len() > cur.key.len() => best = Some(&records[i]),
            Some(_) => {}
        }
    }
    best.map(|r| r.key.as_str())          // 提示：这个 match 也能更迭代替身化……
}
```

**提示**：治理方向与 rust-patterns 同源——手写下标循环 → 迭代器链；`&Vec<T>` → `&[T]`；把 match 改写为 `.map`/`.max_by_key`。先跑 `cargo clippy` 把 lint 名与主文档 3.3 的分组表对起来，再动手。
**验收**：治理后 `cargo clippy --all-targets -- -D warnings` 全绿；能逐个说出「每条 lint 属于哪个组、默认级别是什么、为什么原代码触发它」。
参考实现：`sol-02-cleanup-warnings/`（`record-tool` 为治理后全绿版；`before/main.rs` 是该题治理前整文件样例）。

## 练习 3：配置 pre-commit 或本地检查脚本（★★）

**目标**：把门禁三连固化成一条本地命令 + 提交钩子（roadmap 练习「配置 pre-commit 或本地检查脚本」）。
**要求**：任选一个 crate，写 `scripts/check.sh`（`set -euo pipefail`；fmt → clippy `-D warnings` → test，失败即停、输出能看出卡在哪一步）；再提供一个手写 pre-commit hook 样例（安装进 `.git/hooks` 的说明）；若熟悉 pre-commit 框架可另附 `.pre-commit-config.yaml`。把 lint 策略写进 `[lints.clippy]`（Cargo.toml），阈值放 clippy.toml。
**提示**：`set -euo pipefail` 三个保险丝缺一不可（主文档 3.7）；单 crate 与 workspace 的命令形态不同（一个不加后缀、一个 `--all`/`--workspace`）；pre-commit 框架本机未安装——写了 `.pre-commit-config.yaml` 就要如实标注「未验证」。
**验收**：干净状态下 `./scripts/check.sh` 退出 0；人为注入一条 lint 后脚本在对应步骤非零退出；能解释「为什么本地 hook 可以被绕过、最终裁判是谁」。
参考实现：`sol-03-local-check-setup/`（`cfg-app` 内含脚本、hook 样例、`[lints.clippy]` 与 clippy.toml）。

做完三题后，你对「门禁命令 → lint 分级/例外 → CI 与本地脚本」都有了肌肉记忆——去 `project/` 把它们合成一份可直接复用的 CI 模板。
