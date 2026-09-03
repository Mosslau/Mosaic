# ph18 阶段项目：借用错误练习集（borrow-error-drill）

对应 roadmap 第 18 节推荐项目「借用错误练习集：每个案例包含错误版、修复版和解释」。落地为一个**可自动验证的案例集工程**：`cases/` 收录起步案例，`verify.sh` 把「error 版报出预期错误码 + fix 版通过」变成一条可重复、可进 CI 的命令 —— 未来每遇到一个新借用错误，就往里加一个案例，让它成为你自己的「借用心智档案」。

## 需求

1. 案例结构：每个案例一个目录，含 `error.rs`（**故意编译失败**，文件头写教学说明 + 机器可读标记行 `// expect-error: E0XXX`）、`fix.rs`（修复版，可编译运行）、`explain.md`（错误解释：错误版为什么被拒、修复版的所有权/借用流向）—— 三件套齐全才算一个案例。
2. 自动验证：`verify.sh` 遍历 `cases/*/`，断言每个 `error.rs` 编译失败且诊断里出现声明码、每个 `fix.rs` 编译通过；产物全部落系统临时目录，不污染仓库。任何一条失败则脚本返回非 0。
3. 练习性：新案例必须**自己先不看 fix.rs 试修**，`explain.md` 是修完后对照用的（题解分离与 exercises/ 同一纪律）。
4. 全部基于 `std` + `rustc --edition 2021` 单文件，离线可用，不引入 Cargo 工程与依赖。

## 起步案例（本仓库已交付）

| 案例 | 错误码 | 一句话场景 | 解释文件 |
|------|--------|-----------|---------|
| `cases/c01-drop-partial-move/` | E0509 | 从实现 Drop 的类型里 move 出字段 | `explain.md` |
| `cases/c02-hashmap-move-out/` | E0507 | 从 `HashMap` 的 Index（共享引用）后 move 出元素 | `explain.md` |
| `cases/c03-return-local-ref/` | E0515 | 函数返回指向局部变量的引用 | `explain.md` |

## 如何加一个新案例（练习动作）

```bash
# 1. 建目录并复制三件套模板
cd project/cases
mkdir c04-your-error-code
# error.rs 模板要点：头注释写「本文件故意编译失败：期望错误码 E0XXX」+ // expect-error: E0XXX
# fix.rs 模板要点：头注释写修复思路 + 修复后所有权流向
# explain.md 模板要点：错误版 → 为什么这样设计 → 修复版 → 所有权流向
```

- **错误码挑选**：优先从主文档 3.1 错误号地图、examples 与 sol-01 之外找新码（E0500/E0501 闭包族、E0503/E0506 的使用/赋值冲突族等）；复用已有错误码也行，但场景必须新
- **自检**：`bash verify.sh` 全绿后再对照 explain.md 补解释
- **数量目标**：除起步 3 个外，至少再自建 2 个（合计 ≥5）；每案例解释要能回答「编译器为什么禁止它」，而不是只写「怎么改」

## 验收标准

- `bash project/verify.sh` 对本仓库起步案例输出全 PASS、退出码 0（已验证：rustc 1.92.0 本机实测通过）
- 学习者新增案例后 `verify.sh` 依旧全绿；任一 `error.rs` 报错码与声明不符、或 `fix.rs` 编不过，脚本都能明确点名失败项
- 每个 `explain.md` 至少包含「为什么这样设计 / 为什么编译器禁止 / 修复后所有权流向」三部分之一以上，且与 fix.rs 代码一致
- 整仓代码符合 rust-patterns：生产/修复代码无裸 `unwrap`（练习场景中的 `.unwrap_or(0)` / `.unwrap_or_default()` 为显式兜底，教学性覆盖已注释说明）

## 扩展方向（可选）

- 把 `verify.sh` 挂进 CI 作为回归闸门 —— 完整 CI 体系属 ph21 Clippy、rustfmt、CI 与代码质量阶段（roadmap 第 21 节，目录待建）
- 增加「按错误码检索」索引页，把主文档 3.1 地图、examples、sol-01 与 cases 四处的案例统一编目（为 analysis/ 的 Rust 借用检查设计解剖积累语料）
- 给案例标注「修法家族」（缩短作用域 / 索引快照 / clone / 拥有化 / 字段拆分 / 消费式 API），统计自己最常落入哪一族 —— 那是你所有权心智的薄弱点
