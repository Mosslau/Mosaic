# examples —— Clippy、rustfmt、CI 与代码质量阶段完整示例

对应主文档 `21-code-quality-ci.md` 第 6 章的示例清单。本阶段的示例分两类：**可直接运行的 crate/脚本**（ex01~ex03/ex06，全部在 cargo 1.92.0 本机实测）与 **GitHub Actions workflow 配置**（ex04/ex05，需远端 runner，未在本环境实际运行验证，仅做 YAML 静态解析与人工核对）。被测/演示对象刻意选「ph19/ph20 同款风格的小代码」当待治理对象——质量门禁的内容不换代码域，换「怎么让 warning 清零并守住清零」。

验证环境：rustc/cargo/clippy **1.92.0**、rustfmt **1.8.0**（macOS arm64，rustup 管理），bash 3.2+，edition 2021。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR=/tmp/ph21-target`），仓库零二进制残留。

## 示例清单与运行命令

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| `ex01-fmt-diff` | 3.1 | rustfmt 门禁：`before/` 与 `src/` 双版本，复现 `cargo fmt --check` 红/绿与退出码 | 已验证 |
| `ex02-clippy-lint-levels`（内含 4 个独立子 crate） | 3.2/3.3 | lint 等级动物园：`ex02a` 默认组 warn（裸 clippy 退出 0 / `-D` 退出非零）、`ex02b` correctness deny、`ex02c` pedantic/nursery 开启方式、`ex02d` restriction 逐条开 | 已验证 |
| `ex03-lint-exception-discipline` | 3.4 | lint 例外纪律：带理由 `#[allow]` + `#[expect]` 契约（含 `expect-demo` 子 crate 演示期望落空） | 已验证 |
| `ex04-ci-workflow` | 3.5 | 最小质量门禁 workflow：checkout → toolchain → fmt/clippy/test 三连 step | 未在本环境实际运行验证（无 runner）；YAML 静态解析通过 |
| `ex05-matrix-cache` | 3.6 | 矩阵（OS × 工具链）与缓存：rust-cache 版 + 手写 actions/cache 对照版 | 未在本环境实际运行验证（无 runner）；YAML 静态解析通过 |
| `ex06-local-check-script` | 3.7 | workspace 根 `scripts/check.sh` 本地门禁 + 手写 pre-commit hook 示例 + pre-commit 框架配置示例 | 脚本/hook 逻辑已验证；pre-commit 框架未安装未验证 |

```bash
# 通用运行方式（在对应示例目录内执行）
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph21-target

# ex01：fmt 门禁红/绿（before 是 src 的精确未格式化版）
cd examples/ex01-fmt-diff
cargo fmt --check                    # exit=0（src/ 已格式化）
cp before/main.rs src/main.rs
cargo fmt --check                    # exit=1（diff + 门禁红）
cargo fmt                            # 自动治理
cargo fmt --check                    # exit=0
git checkout -- src/main.rs          # 或手动还原 src/main.rs 与本文件一致

# ex02a：裸 clippy（warning 但 exit 0） vs -D warnings（exit 101）
cd ../ex02-clippy-lint-levels/ex02a-default-warn-zoo
cargo clippy --message-format short
cargo clippy -- -D warnings; echo $?

# ex02b：correctness deny（eq_op 自我比较，裸跑即 error）
cd ../ex02b-correctness-deny
cargo clippy

# ex02c：pedantic / nursery 开启才响
cd ../ex02c-pedantic-nursery
cargo clippy                                        # exit=0，零输出
cargo clippy -- -W clippy::pedantic                 # unnecessary_wraps
cargo clippy -- -W clippy::nursery                  # missing_const_for_fn

# ex02d：restriction 逐条开
cd ../ex02d-restriction
cargo clippy -- -W clippy::unwrap_used              # unwrap 禁令
cargo clippy -- -W clippy::indexing_slicing         # 裸下标禁令

# ex03：例外纪律主 crate 全绿三连 + expect-demo 期望落空
cd ../../ex03-lint-exception-discipline
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
cd expect-demo && cargo clippy                        # 1 个 warning：expectation unfulfilled

# ex06：workspace 本地门禁（绿 / 红两种状态见 README 内脚本实验）
cd ../../ex06-local-check-script
./scripts/check.sh
```

## 每个示例的看点

- **ex01**：`cargo fmt` 只处理标准源目录（`before/` 放 src 外就不被扫描）；`--check` 用「diff 是否为空 + 退出码」当门禁断言。`before/main.rs` 是 `src/main.rs` 的精确未格式化版——`cp` 回去、`cargo fmt` 治理后与仓库参考版**字节一致**（已实测验证）。
- **ex02a**：四个故意携带的默认 lint（needless_range_loop/manual_map 实测属 style、too_many_arguments 属 complexity、手写拷贝循环属 perf）。核心观察：**裸 `cargo clippy` warning 一堆却退出 0**——这正是门禁必须 `-D warnings` 的原因。
- **ex02b**：`eq_op`（变量与自己比较）属 correctness 组，**默认 deny**，裸跑 clippy 直接 error——不需要 `-D` 就拦住「粘贴变量名 typo」这类真 bug。
- **ex02c**：同一份干净代码在默认/`-W pedantic`/`-W nursery` 三种跑法下输出从零到两处不同 lint——演示 opt-in 组「不显式开就不响」以及分组归属按工具链版本漂移（missing_const_for_fn 本机 1.92 在 nursery）。
- **ex02d**：`.unwrap()`（unwrap_used）与裸下标（indexing_slicing）默认零输出；按条 `-W` 才拦。若整组 `-W clippy::restriction` 会喷几十条禁令并报警 blanket_clippy_restriction_lints——restriction 的正确姿势是逐条开（主文档 3.3）。
- **ex03**：全绿主 crate 里三个「站得住」的例外——`#[allow(clippy::too_many_arguments)]`（固定列数解码入口，带理由注释）、`#[expect(clippy::manual_map)]`（预期触发）、测试里 `#[allow(clippy::out_of_bounds_indexing)]`（故意越界契约测试）。`expect-demo` 子 crate 专门演示「期望落空」：代码已重构为 `.map` 后 `#[expect]` 反报 `unfulfilled_lint_expectations`——这就是它优于 `#[allow]` 的地方。
- **ex04**：最小质量门禁 workflow。fmt/clippy/test 三个独立 step = 三个日志折叠单位，失败直接定位。
- **ex05**：`matrix-cache.yml`（rust-cache，矩阵 cell 自动独立缓存 key）与 `handwritten-cache.yml`（手写 actions/cache：key 必须含 OS + rustc 版本 + Cargo.lock hash 三要素）互为对照。
- **ex06**：`scripts/check.sh` 用 `set -euo pipefail` 保证「失败即停」，workspace 门禁命令形态为 `cargo fmt --all --check` / `clippy --all-targets --workspace -- -D warnings` / `test --workspace`；绿态退出 0、注入 lint 后在第二步退出 101（均实测）。`hooks/pre-commit-sample` 是同一逻辑的 git hook 版本。

> ⚠️ ex04/ex05 的 workflow 需要 GitHub Actions 远端 runner，**未在本环境实际运行验证**；YAML 已用 Ruby psych 静态解析通过、并按官方 action 用法人工核对。action 主版本（`@v4`/`@v2`/`@stable`）会演进，使用前以 GitHub marketplace 的当前主版本为准并考虑 pin 到 commit。

## 阅读顺序建议

按主文档教学增量推进：ex01（fmt 门禁长什么样）→ ex02（clippy 各等级分别响什么）→ ex03（响了的 lint 怎么例外管理）→ ex04/ex05（把这些规则编进 CI、矩阵与缓存）→ ex06（合成本地一条命令）。每看完一组示例就去 `exercises/` 做对应一题。

## 验证状态汇总

- ex01~ex03/ex06：已验证（cargo 1.92.0 / rustfmt 1.8.0 本机实测；红/绿状态按示例设计分别验证退出码）
- ex04/ex05：未在本环境实际运行验证（无 GitHub runner）；YAML 静态解析通过
- pre-commit 框架（`.pre-commit-config.yaml`）：本机未安装框架，未实际运行验证
