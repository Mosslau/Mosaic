# exercises —— Edition、工具链与版本管理阶段练习

完成顺序建议：按 1~3 顺序完成，对应主文档第 3 章 3.4/3.6/3.3。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。

三题与 roadmap 练习一一对应：练习 1 = 「为项目固定 toolchain」，练习 2 = 「检查依赖的 MSRV」，练习 3 = 「执行一次 Edition 迁移演练」。

## 练习 1：为项目固定 toolchain（★）

- **目标**：为一个假想项目写一份 `rust-toolchain.toml`，让任何成员 clone 后 `cargo build` 自动使用同一条工具链（roadmap 练习「为项目固定 toolchain」）
- **要求**：
  - 通道钉到 stable 并携带 `rustfmt`、`clippy` 组件（缺失时 rustup 自动补齐）
  - 注释里说明：若团队要求精确复现，channel 应改写成什么形态（精确版本号/按日期快照），以及代价（缺失时 rustup 联网下载）
  - 注释里给出验证方法（`rustup show` 应显示 overridden by）
- **验收**：把文件放到任意目录下执行 `rustup show`，active toolchain 显示 `active because: overridden by '<目录>/rust-toolchain.toml'`；本机已装 stable 时 `rustc --version` 正常输出版本（参考实现 `sol-01-rust-toolchain.toml` 已实测）

## 练习 2：检查依赖的 MSRV（★★）

- **目标**：写一个脚本 `check_msrv.sh`，对任意 cargo 工程列出依赖树中每个包声明的 `rust-version`（MSRV），并汇总出「依赖要求的最高 MSRV」（roadmap 练习「检查依赖的 MSRV」）
- **要求**：
  - 用 `cargo metadata --format-version 1` 拿依赖树元数据，用 python3（或 jq）解析 JSON，逐包打印 `name version rust-version`
  - 汇总一行：本 crate 的 rust-version（若声明）与全部依赖中的最大 MSRV
  - 脚本能跑通主文档示例 4 的对照工程（edition 2024 + rust-version 1.85 + 依赖 home）
  - 加分项：若环境里有 cargo-msrv，附 `cargo msrv show` / `cargo msrv list` 的对照输出
- **验收**：对含 `home = "0.5"` 依赖的工程运行，输出含 `home 0.5.11: rust-version = 1.81` 与汇总行（参考实现 `sol-02-check-msrv.sh` 已实测）

## 练习 3：执行一次 Edition 迁移演练（★★★）

- **目标**：把一份 2015 edition 的代码徒手（借助 `cargo fix`）迁到 2024，记录每一步谁改了什么（roadmap 练习「执行一次 Edition 迁移演练」；examples/ex03 是演示版，本题代码不同）
- **要求**：起点代码（2015 edition，自行建 crate）：

  ```rust
  use std::io;

  extern "C" { fn abs(input: i32) -> i32; }

  fn parse_nonneg(input: &str) -> Result<u32, io::Error> {
      let n = try!(input.parse::<u32>().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad number")));
      Ok(n)
  }

  fn describe(f: &Fn(i32) -> i32) -> String {
      format!("abs(-3) = {}", f(-3))
  }

  fn main() {
      let async = "pending";
      let n = parse_nonneg("7").expect("parse");
      println!("{} {} {}", async, n, describe(&|x| unsafe { abs(x) }));
  }
  ```

  - 依次迁移 2015 → 2018 → 2021 → 2024：每步 `cargo fix --edition --allow-no-vcs`（演练目录不在 git 中；真实项目用 git 干净工作区代替该参数）+ 手工 bump Cargo.toml 的 edition + 手工处理 cargo fix 不做的改动
  - 记录每一步 cargo fix 自动修了什么、还剩什么警告/错误、你手工改了什么
  - 终点：`RUSTFLAGS="-D warnings" cargo build` 零警告且运行输出 `pending 7 abs(-3) = 3`
- **验收**：四段迁移记录齐全；至少观察到三个实证点——① `try!` 被转成 `r#try!` 而非 `?`（转 `?` 要手工）；② `cargo fix --edition` 打印 Migrating Cargo.toml 但不改写它；③ 2021→2024 会把裸 `extern` 块改成 `unsafe extern`（参考实现 `sol-03-edition-migration.sh` 已实测）

提示：练习 1 练「工具链钉死」的文件形态，练习 2 练「MSRV 元数据在哪」，练习 3 练「edition 迁移的人机分工」——三题做完覆盖 roadmap 必会概念（Edition 不是编译器版本 / MSRV / 锁文件的应用与库差异 / 工具链可复现）中的前三条；锁文件策略的动手部分在 examples/ex05 与 project/ 里。
