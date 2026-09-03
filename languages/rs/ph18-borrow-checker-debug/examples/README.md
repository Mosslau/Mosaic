# examples —— Borrow Checker 调试专项阶段完整示例

对应主文档 `18-borrow-checker-debug.md` 第 6 章示例 1~9。本阶段示例采用**「错误案例集」形态**：每个案例一个目录，含 `error.rs`（**故意编译失败**，文件头声明期望错误码与教学用途）+ `fix.rs`（对照修复版，可通过编译并运行）。故意编译失败的文件被组织在各自子目录中、用 `rustc` 单文件编译，**不构成 Cargo 工程、不污染任何 `cargo build`**；全部基于 `std`，离线可用。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理）。**验证说明**：9 个示例的 error 版已逐一实测产生预期错误码、fix/main 版已实测编译通过并运行，全部标注「已验证」。

## 示例清单

| 目录 | 对应主文档 | 演示错误码 | 说明 | 验证状态 |
|------|-----------|-----------|------|---------|
| `e01-moved-value/` | 3.2 | E0382 | 值被 move 后原变量仍被使用；修复 = 只读就用借用 | 已验证 |
| `e02-multiple-mutable-borrow/` | 3.3 | E0499 | 同一数据同时存在两个可变借用；修复 = 用完即止（NLL 收口） | 已验证 |
| `e03-shared-then-mut/` | 3.4 | E0502 | 先不可变借用再 push；修复 = 索引取 Copy 副本 | 已验证 |
| `e04-long-borrow-scope/` | 3.6 | E0502 | 长借用横跨修改点；修复 = 代码块显式收口借用区间 | 已验证 |
| `e05-borrowed-lifetime/` | 3.5 | E0597 | 借用外逃内层作用域；修复 = 数据提升外层 / to_owned 拥有化 | 已验证 |
| `e06-move-while-borrowed/` | 3.6 | E0505 | 借用中把容器 move 走；修复 = 借用收口后再 move | 已验证 |
| `e07-temporary-lifetime/` | 3.5 | E0716 | 把对临时值的引用塞进集合；修复 = 先建拥有变量 / 集合拥有数据 | 已验证 |
| `e08-field-level-borrow/` | 3.7 | E0502 | 整体 `&self`/`&mut self` 方法粒度太粗；修复 = 重排 / 字段级借用 | 已验证 |
| `e09-two-phase-borrow/` | 3.3 | —（正面示例） | 两阶段借用：`v.push(v.len())`、`x += x` 为何被放行 | 已验证 |

## 运行方式（每个案例通用两段命令）

```bash
# 1. 验证 error 版产生预期错误码（命令以 e01 为例；在各自目录内执行）
cd examples/e01-moved-value
rustc --edition 2021 error.rs        # 应报 error[E0382]，退出码非 0

# 2. 编译并运行 fix 版（-o 输出到 /tmp，避免在仓库目录留下二进制）
rustc --edition 2021 fix.rs -o /tmp/e01-moved-value-fix && /tmp/e01-moved-value-fix
```

- error 版文件头注释写明了期望错误码；若你看到的错误码与注释不一致，说明你的 rustc 版本
  与本文基线（1.92.0）差异较大 —— 也正好练一遍「读懂错误」本身
- e09 只有 `main.rs`（正面示例，无 error 版）：`cd examples/e09-two-phase-borrow && rustc --edition 2021 main.rs -o /tmp/ph18-e09 && /tmp/ph18-e09`

## 阅读顺序建议

先读 error 版、自己说出「为什么被拒」再翻 fix 版：e01（move）→ e02（双 &mut）→ e03（共享/可变冲突）→
e04（作用域收口）→ e05/e07（生命周期类：E0597/E0716）→ e06（借用中 move）→ e08（字段级）→ e09（两阶段，补 e03 的心智）。

## 验证状态汇总

- e01~e09：全部已验证（rustc 1.92.0 本机实测：error 版产生预期错误码、fix/main 版编译运行通过）
- 与 exercises/sol-01 互补：examples 覆盖 E0382 / E0499 / E0502 / E0505 / E0597 / E0716，
  sol-01 覆盖 E0503 / E0506 / E0507 / E0508 / E0596，project/ 覆盖 E0507(HashMap) / E0509 / E0515
