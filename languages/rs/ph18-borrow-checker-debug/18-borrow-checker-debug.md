# Rust Borrow Checker 调试专项阶段

> 面向「读懂编译器」方向：本阶段把 borrow checker 从「拦路的编译器」变成「可沟通的同事」——从 E0382/E0499/E0502/E0597 四条主错误码起步，学会定位真实冲突、用缩短借用作用域/字段级借用/索引快照/拥有化等手段重构出干净的所有权流，最终沉淀一套「错误码 → 修法家族」的系统化调试方法。

## 1. 概述

本阶段对应 roadmap 第 18 节，目标是**系统掌握借用检查错误的定位与重构方法**。它是所有权学习线（ph02 所有权、ph08 生命周期）的「实战收口」：ph02/ph08 教规则，本阶段教「规则被违反时，编译器怎么告诉你、你该怎么修」。定位上承接 ph17 主文档末尾的承诺——把 ph17 评审新依赖时遇到的所有权冲突、以及日常写代码积攒的借用错误，升级成「看错误码知道是哪一类冲突、看定位知道借用活到哪、按修法家族选修复路线」的完整手艺。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 错误号地图 | E0382 / E0499 / E0502 / E0597 四条主线 + E0503 / E0505 / E0506 / E0507 / E0508 / E0509 / E0515 / E0596 / E0716 扩展，按「借用规则家族」分组（3.1） |
| move 类冲突 | use of moved value（E0382）、借用中 move（E0505）、从共享引用/容器后 move（E0507/E0508/E0509）（3.2/3.6） |
| 可变借用排他 | 双 &mut（E0499）、两阶段借用的边界与原理（3.3） |
| 共享/可变冲突 | 先读后写、迭代器旁路等 E0502 家族（3.4） |
| 生命周期类 | borrowed value does not live long enough（E0597）、临时值（E0716）、返回局部引用（E0515）（3.5） |
| 活跃借用范围 | NLL 视角：借用活到「最后一次使用」；缩短借用作用域（3.6） |
| 字段级借用 | 拆分结构体字段借用、整体方法与字段借用（3.7） |
| 值 vs 借用 | 索引或临时变量取副本、Copy 快照（3.8） |
| 拥有化决策 | 必要时引入拥有数据、重构优先于 clone、何时 clone 可接受（3.9/5） |
| 底层原理 | lifetime 是类型的一部分、NLL 数据流分析、reservation/activation 两阶段、借用栈心智（4） |
| 场景与练习 | 何时 clone / 何时必须重构；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及**读懂并修复借用错误**——即「编译器报错 → 归因 → 选择修法家族 → 重构出干净所有权流」这一闭环，**不涉及内存布局、零拷贝与协议解析**（借用切片的零拷贝用法是 [ph19 内存布局、零拷贝与协议解析阶段](../ph19-memory-layout-zero-copy/19-memory-layout-zero-copy.md)的事）、**性能优化**（clone 的性能代价在本阶段只作「取舍判据」，实际剖析与基准属 [ph22 性能优化与 Profiling 阶段](../ph22-perf-profiling/22-perf-profiling.md)）、**跨语言 FFI**（所有权跨边界属 ph23 Rust FFI 与跨语言接口设计阶段，roadmap 第 23 节，目录待建）、**依赖与供应链安全**（ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建）。

同时与两条前置知识点划清边界：RefCell / Mutex 的**运行时**借用检查（`BorrowMutError`）属于 ph10 智能指针阶段，本阶段只讲编译期借用检查，二者机制不同——一个在编译期保证、一个把检查推迟到运行时并可能 panic；`unsafe` 与别名模型的正式语义（Stacked Borrows / Miri）属于 ph14 Unsafe Rust 与安全抽象阶段，本阶段 4.4 的「借用栈」只作为读代码的心智模型，不涉及 unsafe 语义。

## 2. 来源与演变

Borrow checker 不是 Rust 的半路补丁，而是语言从设计第一天就有的核心。Rust 0.x 时期（2010 年前后，Graydon Hoare 的设计）就确定了「所有权 + 借用 + 生命周期」的内存安全路线：不用 GC、不靠程序员手动释放，而是让编译器静态检查「谁拥有这块内存、谁在借用、借多久」。**设计哲学一句话加粗：内存安全不是运行时机制（GC / 引用计数）的产物，而是类型系统在编译期就能证明的性质。** 因此借用检查不是「一个 lint」，它和类型检查共享同一套编译基础设施——这就是本阶段读错误码时要有的第一层认知。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 0.x（pre-1.0） | 2010~2014 | 所有权/借用/生命周期进入语言设计；borrow checker 从原型走向可用 |
| Rust 1.0 | 2015 | 借用检查随 1.0 稳定；错误码（E0XXX）体系成型；生命周期基于**词法作用域**（lexical scopes），borrow 活到所在块结束，保守但简单 |
| RFC 2094 NLL | 2017 | 提出 non-lexical lifetimes：借用应活到「最后一次使用」而非块结束；检查改到基于 MIR 的数据流分析上 |
| Rust 1.31 + Edition 2018 | 2018-12 | NLL 稳定并全 edition 启用；一批「逻辑正确但旧检查器不接受」的代码被放行；borrow checker 时代进入 NLL 阶段 |
| 两阶段借用（RFC 2025 落地） | NLL 时代逐步定型 | `v.push(v.len())` 这类「方法可变借用 + 同表达式读自身」被放行：可变借用先「预留」、调用时再「激活」（详见 3.3/4.3） |
| 诊断增强 | 2019~2025 | 错误输出从「一行话」进化到多 span 标注（borrow 起点/冲突点/借用结束点）、`rustc --explain E0XXX`、常见修法建议（consider borrowing / cloning）；错误码编号保持稳定、语义不改名 |
| Edition 2021 | 2021-10 | 闭包析取捕获（RFC 2229）：闭包只捕获用到的字段，减少「为了用一字段却整值被捕获」的意外 move；`rustc --explain` 对借用族错误继续增强 |
| Polonius（下一代） | 2019 起，写作时仍实验 | 基于「位置」的分析比 NLL 更精确（条件分支、字段敏感、循环内的借用交替）；写作时仍在 nightly 以 `-Zpolonius` 实验，未默认启用——NLL 的模型与修法家族在本阶段依然有效 |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0（macOS arm64，rustup 管理） |

**错误号为什么值得背？** borrow checker 的错误集中在 E0308 之后的 E0500~E0716 区间，每条错误码对应**一类借用规则违反**，编号跨版本稳定——这意味着「看错误码」比「逐字读报错」更快地把你带到正确的修法家族。rustc 为每条错误码维护了 `--explain` 文本，本阶段 3.1 的家族划分即以 `rustc --explain` 与实测报错为准。历史背景值得一提：NLL 之前，borrow 活到块结束，`let y = &x; let z = &mut x;`（y 之后不用）也会被拒；NLL 之后这类代码直接通过——**学习时请勿对着 2021 之前的博客练习「手动给借用划作用域」，先把 NLL 的「活到最后一次使用」内化**（该历史拒绝行为在 rustc 1.92 上无法复现，本环境未验证，依据 Rust 官方博客《Announcing Rust 1.31 and Rust 2018》）。

本文示例以 **rustc 1.92.0 / edition 2021** 为基线（edition 2021 自 Rust 1.56 起是生态事实默认，与 ph10~ph16 全仓库代码层一致——单文件示例统一 `--edition 2021`；NLL、两阶段借用等行为在 1.8x+ 稳定区间一致），验证工具链 **rustc/cargo 1.92.0（macOS arm64，rustup 管理）**。这个阶段的主题——借用规则、错误码语义、修法家族——是 Rust 最稳定的部分：E0502 在 1.0 时代的意思和今天一致，你今天学的「错误码 → 修法」映射五年后依然适用；会漂的只有诊断文本的措辞与个别新放行的模式（如未来 Polonius 默认启用），届时错误码仍是同一套语言。**代码验证状态**：examples/exercises/project 全部代码已在本机 rustc 1.92.0 实测（error 版逐一产生预期错误码、fix 版编译运行通过）并标注「已验证」。

## 3. 语法与参数

本章按「地图 → 逐族读透 → 修法工具箱」推进：3.1 给错误号地图与五大家族心智；3.2~3.5 逐族读 E0382 / E0499(+两阶段) / E0502 / E0597·E0716·E0515；3.6~3.9 是四件套修法工具箱（短借用作用域 / 字段级拆分 / 索引与临时变量 / 拥有化与重构优先于 clone），并全程用 NLL 视角解释「为什么这么修」；3.10 用 NLL 视角统观收口。章节代码的可运行完整版见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)。

### 3.1 错误号地图：先分清「五大家族」

借用错误看多了会发现它们不是零散的一百多条，而是**五条规则的违反**。map 第一列是家族，第二列是错误码，第三列是 rustc `--explain` 的一句话语义，第四列是常见触发形态，第五列指向本阶段的修法小节：

| 家族 | 错误码 | rustc 一句话语义 | 常见触发形态 | 修法方向 |
|------|--------|------------------|-------------|---------|
| ① move 后再用 | E0382 | 值在内容被 move 走后仍被使用 | 赋值/传参 move 后原变量再读 | 借用而非 move；必要时 clone（3.2/3.9） |
| ① move 后再用 | E0505 | 值在仍被借用时被 move 走 | 持有引用的同时 drop / 转移容器 | 先收口借用再 move（3.6） |
| ① move 后再用 | E0507 | 从共享引用后的内容里 move | `&Vec`/`HashMap` Index 后取元素 | clone / 拥有容器后 remove（3.9） |
| ① move 后再用 | E0508 | 从非 Copy 数组中 move 单个元素 | `arr[0]` 想拿走 String | into_iter 整体消费 / Vec（sol-01 case4） |
| ① move 后再用 | E0509 | 从实现 Drop 的类型里 move 字段 | 想拆走 Drop 结构体的一部分 | 消费式 `into_inner` + `mem::take`（project c01） |
| ② 可变借用排他 | E0499 | 同一数据同时被可变借用多于一次 | 两个活跃 &mut | 用完即止（NLL 收口）（3.3） |
| ② 可变借用排他 | E0503 | 值在被可变借用后仍被使用 | 显式 `&mut` 实参 + 同表达式再读 | 先快照再传（sol-01 case1） |
| ③ 共享/可变冲突 | E0502 | 已被一种 mutability 借用，又按另一种借用 | 借元素后 push / 整体方法挡字段 | 短作用域 / 字段级 / 索引快照（3.4/3.6~3.8） |
| ③ 共享/可变冲突 | E0506 | 在被借用时给该值赋值 | 持引用期间写字段/变量 | 先读后写分离（sol-01 case2） |
| ④ 借不到那么久 | E0597 | borrowed value does not live long enough | 借用逃出数据作用域 | 数据提升外层 / 拥有化（3.5） |
| ④ 借不到那么久 | E0716 | 临时值在借用活跃时被销毁 | 把 `&temp` 塞进集合/返回值 | 先建拥有变量 / 集合拥有数据（3.5） |
| ④ 借不到那么久 | E0515 | 返回引用指向局部变量 | 函数想返回局部 String 的引用 | 返回拥有值（3.5/project c03） |
| ⑤ 可变性缺失 | E0596 | 给非 mut 绑定开 &mut | 忘写 `mut` | 声明 `mut`（sol-01 case5） |

阅读建议：先用「家族」而不是「编号」组织记忆——报错时先问「这是 move 问题、排他问题、还是寿命问题」，再落编号。**E0500~E0510 里闭包捕获族（E0500/E0501 等）与少量冷门码本阶段不逐一展开**，其触发形态涉及闭包捕获规则，属于 ph09 集合、迭代器与函数式写法阶段与 ph15 宏与元编程阶段的分析面；遇到时用 `rustc --explain` 读原文即可。

**错误码读法三连**：报错第一行（错误码 + 动作对象）→ 多 span 标注（哪次借用发生、哪次冲突、借用何时结束）→ 末尾的 help 提示（`consider using clone` / `consider changing this to be mutable` 等）。**help 提示要批判地听**：`consider using clone` 只是编译器给出的「最小改动」，是否采纳取决于 3.9/5 的成本判断——这正是本阶段与「照着 help 改」式学习的分水岭。

**一次完整 walkthrough（读 E0499 的真实报错）**——`examples/e02-multiple-mutable-borrow/error.rs` 在 rustc 1.92.0 下的完整输出（已验证）：

```text
error[E0499]: cannot borrow `score` as mutable more than once at a time
 --> error.rs:7:18
  |
6 |     let first = &mut score; // 第 1 个可变借用
  |                 ---------- first mutable borrow occurs here
7 |     let second = &mut score; // E0499：同一数据上出现第 2 个可变借用
  |                  ^^^^^^^^^^ second mutable borrow occurs here
8 |     *first += 1;
  |     ----------- first borrow later used here

For more information about this error, try `rustc --explain E0499`.
```

按「三连」拆解这份输出：**① 第一行**告诉你错误码（E0499 = 可变借用排他族）与动作（`score` 被第二次可变借用）；**② span 区**是编译器画出的借用图——第 6 行 `----------` 是 first 借用发生点、第 7 行 `^^^^^^^^^^` 是冲突点（second 借用的位置）、第 8 行 `----------` 是 first 的**最后一次使用**（它横跨了 second 的创建，所以两个借用区间重叠）；**③ 尾行**指路 `rustc --explain E0499` 看标准解释。学会读 span 后，修法几乎是自明的——让 first 的最后一次使用（第 8 行）挪到 second 创建之前，问题就消失（3.3 fix.rs 正是这么做的）。**本阶段要求能徒手复述这三段信息，而不是只看第一行就开改**。

### 3.2 E0382 use of moved value：move 之后原变量不可再读

最基础也最「好修」的一族：值被 move 走之后，原变量处于未初始化状态，任何使用（读、再 move、借用）都会被拒。报错第一行（rustc 1.92.0 实测）：

```text
error[E0382]: borrow of moved value: `title`
```

触发代码（`examples/e01-moved-value/error.rs`，完整版见该文件）：

```rust
// examples/e01-moved-value/error.rs —— 错误版：move 后仍读原变量（已验证：rustc 1.92.0 报 E0382）
fn main() {
    let title = String::from("hello");
    let taken = title;            // 所有权 move：title 让出堆上字符串
    println!("长度: {}", title.len()); // E0382：title 已不可用
    println!("内容: {taken}");
}
```

修复（`examples/e01-moved-value/fix.rs`）的思路是**先问自己到底要什么**：要「读内容」→ 用借用，所有权留在原地；要「同时两边都能用」且值本身是 Copy（i32、bool、&str 这类）→ 赋值本来就会复制，不触发 move。只有当两边都需要**长期持有同一份可变数据**时，才轮到 clone 或 Rc/Arc（3.9/5 讨论）——`let taken = title;` 之后又想要 `title`，多半是「其实根本不需要 move」。

**move 与 Copy 的分界**：`String`、`Vec` 等拥有堆缓冲的类型 move 即转移所有权；`i32` 等 Copy 类型赋值是拷贝。判断口诀：**实现了 `Copy` 的类型 move 等于复制，没实现的一律转移**。`&str` 是 Copy 的（它只是借用），所以 `let b = a;` 之后 `a` 还能用——这点常被新手误伤。

**部分 move 与闭包捕获**：结构体的字段可以单独 move（`let name = user.name;`，`user` 的其余字段仍可用），前提是结构体本身没实现 `Drop`（实现 Drop 则禁止部分 move，见 3.1 地图 E0509 行与 project/c01）。闭包用 `move` 关键字捕获时会把用到的变量整体/按字段搬进闭包（edition 2021 起析取捕获只搬用到的字段），搬走后再用原变量同样报 E0382。

### 3.3 E0499 与两阶段借用：可变借用的排他性

可变借用的核心规则：**同一时刻、同一数据，最多一个活跃的 `&mut`**。两个 `&mut` 都想「活到函数尾」，编译器就报 E0499（实测第一行）：

```text
error[E0499]: cannot borrow `score` as mutable more than once at a time
```

触发代码（`examples/e02-multiple-mutable-borrow/error.rs`）：

```rust
// examples/e02-multiple-mutable-borrow/error.rs —— 错误版：两个活跃 &mut（已验证：rustc 1.92.0 报 E0499）
fn main() {
    let mut score = 0i32;
    let first = &mut score;  // 第 1 个可变借用
    let second = &mut score; // E0499：同一数据上第 2 个可变借用
    *first += 1;
    *second += 2;
    println!("{first} {second}");
}
```

修复的关键是 NLL 视角（3.6/3.10）：**可变借用活到「最后一次使用」**。把 `first` 的最后一次使用提前，两次 `&mut` 的生命区间就不重叠：

```rust
// examples/e02-multiple-mutable-borrow/fix.rs —— 修复版：用完即止（已验证：rustc 1.92.0 编译运行通过）
fn main() {
    let mut score = 0i32;
    let first = &mut score;
    *first += 1;
    println!("first = {first}"); // first 最后一次使用 → 借用结束
    let second = &mut score;     // 前一个借用已结束，允许开新的 &mut
    *second += 2;
    println!("second = {second}");
}
```

**两阶段借用（two-phase borrows）** 是排他性的一条「方法论例外」，它解释了 `v.push(v.len())` 为什么能编译——按字面读，`push` 要 `&mut v`，`v.len()` 又要 `&v`，岂不是自相矛盾？机制是：方法调用对 receiver 的自动引用（autoref）产生的 `&mut` 不是立即生效，而是分两阶段——先「**预留**」（reservation，此时按共享借用对待，允许参数里读自己），参数全部求值完、真正进入方法体时才「**激活**」（activation，此时才按可变借用排他）。实测通过（`examples/e09-two-phase-borrow/main.rs`，已验证：rustc 1.92.0）：

```rust
let mut v = vec![1, 2, 3];
v.push(v.len()); // 对 v.len() 的读取发生在 push 的 &mut 激活之前
let mut x = 1;
x += x;          // 复合赋值运算符的隐式 &mut 同样两阶段
```

两阶段**只放行隐式可变借用**：方法 receiver 的自动引用、复合赋值运算符、实参位置的隐式可变重借用（按 rustc-dev-guide「two-phase borrows」所述，后一种本环境未逐一验证）；**源码里手写的 `&mut` 永远是普通可变借用、立即激活**。所以 `set(&mut x, x)` 会报 E0503（sol-01 case1）——手写 `&mut` 不享受两阶段。分清「编译器替你造的 &mut」与「你手写的 &mut」是本阶段重要增量。

### 3.4 E0502：共享借用与可变借用冲突——最常见的一道坎

E0502 是本阶段出现频率最高的错误码，跨越 3.6~3.8 三节修法。报错第一行（实测）：

```text
error[E0502]: cannot borrow `items` as mutable because it is also borrowed as immutable
```

触发形态（`examples/e03-shared-then-mut/error.rs`）——先不可变借用元素、借用在之后还要用、中间却要可变地改容器：

```rust
// examples/e03-shared-then-mut/error.rs —— 错误版：借元素后 push（已验证：rustc 1.92.0 报 E0502）
fn main() {
    let mut items = vec![1, 2, 3];
    let first = &items[0]; // 不可变借用：first 引用 items 中的元素
    items.push(4);         // E0502：items 仍有活跃不可变借用，不能同时可变借用
    println!("first = {first}");
}
```

**注意区分 E0502 与 E0503**：这里 `println!("{first}")` 用的是**借用**（`&items[0]` 的产物）去读，冲突发生在「再借出一次可变借用」上，报 E0502；而 E0503（`cannot use x because it was mutably borrowed`）是可变借用仍活跃时**直接使用原变量的值**（不经过借出）。一个在「借出」环节被拦，一个在「使用」环节被拦。

E0502 的修法家族按「你想保留什么」分叉：只想保留**值** → 索引/临时变量取副本（3.8，Copy 类型零成本）；只想保留**一段读取区间** → 缩短借用作用域，让借用先结束（3.6）；读写对象是**结构体里不重叠的字段** → 字段级借用（3.7）；值很大或必须原地引用 → 拆结构体让数据分家，或必要时 clone（3.9/5）。迭代器场景下的 E0502（边 `iter()` 边 push）也归此族——`items.iter()` 生成的迭代器借了整个 `items`，解法同样是让迭代器在修改前先耗尽/丢弃。

### 3.5 E0597 / E0716 / E0515：借不到那么久（生命周期类）

这三个错误码讲同一件事：**引用指向的数据活不到引用被用完的那一刻**。rustc 按「数据以什么形态死掉」区分：普通局部变量先死 → E0597；临时值（语句结束就死）先死 → E0716；直接在函数返回点把局部引用交出去 → E0515。修法共性：**让数据活得更久（提升拥有者）或让返回值不携带借用（拥有化）**。

**E0597——借用逃出数据的作用域**。实测第一行：

```text
error[E0597]: `config` does not live long enough
```

触发代码（`examples/e05-borrowed-lifetime/error.rs`）：

```rust
// examples/e05-borrowed-lifetime/error.rs —— 错误版：借用外逃内层作用域（已验证：rustc 1.92.0 报 E0597）
fn main() {
    let stem;                       // 计划在外层使用的借用（Option<&str>）
    {
        let config = String::from("demo.conf"); // config 的生命周期被限制在这个块内
        stem = config.split('.').next(); // E0597：把借用 config 的 Option<&str> 交到外层
    } // config 在此 drop，stem 却还要活到下面的 println
    println!("stem = {stem:?}");
}
```

修法（`examples/e05-borrowed-lifetime/fix.rs`）：A 把拥有数据的变量提升到与借用同一作用域（数据活得够久，借用自然合法）；B 数据只能来自内层时用 `map(str::to_owned)` 让结果拥有数据、切断借用链。这与 ph08 生命周期阶段讲的「拥有数据可简化生命周期」是同一原理在错误修复侧的落地。

**E0716——引用临时值**。`&String::from(...)` 引用的临时值在语句结束就被销毁。实测第一行：

```text
error[E0716]: temporary value dropped while borrowed
```

触发与修复（`examples/e07-temporary-lifetime/`）：

```rust
// examples/e07-temporary-lifetime/error.rs —— 错误版：把对临时值的引用塞进集合（已验证：rustc 1.92.0 报 E0716）
let mut tags: Vec<&str> = Vec::new();
tags.push(&String::from("hot")); // E0716：临时 String 在本语句结束即 drop
```

```rust
// examples/e07-temporary-lifetime/fix.rs —— 修复版：先建拥有变量 / 集合拥有数据（已验证：rustc 1.92.0）
let hot = String::from("hot"); // 拥有变量活得够久
tags.push(&hot);
let mut owned_tags: Vec<String> = Vec::new(); // 集合拥有 String，切掉借用链
owned_tags.push(String::from("cold"));
```

> ⚠️ **临时值生命周期延长（temporary lifetime extension）有个反直觉的坑**：`let x = &temp_expr();` 这类把引用直接绑给 let 的写法，编译器会把临时值延长到块结束，不报错；但只要引用绕了一道（函数实参、塞进集合、作为返回值），延长就不适用——这就是「`&String::from(...)` 单独绑着能过、塞进 `Vec` 就报 E0716」的原因。判断标准：**引用是否被「直接」绑给一个 let 绑定**，否则别指望延长。

**E0515——返回局部引用**。E0597 的「直接返回」特例（实测）：

```text
error[E0515]: cannot return value referencing local variable `combined`
```

```rust
// project/cases/c03-return-local-ref/error.rs —— 错误版：返回拼接出的局部 String 的引用（已验证：rustc 1.92.0 报 E0515）
fn best_of<'a>(a: &'a str, b: &'a str) -> &'a str {
    let combined = format!("{a}|{b}"); // 函数内拥有的局部 String
    combined.as_str()                  // E0515：不能返回对局部变量的引用
}
```

修法一句话：**拼接出的是「新数据」，没有现成的借用来源，想传出去只能移交所有权**——返回类型改成 `String`（project/c03 fix.rs）。判断函数该返回引用还是拥有值的口诀（衔接 ph08）：返回的东西「本来就是调用方数据的一部分」→ 返回引用；「是函数新造的」→ 返回拥有值。

### 3.6 活跃借用范围与短借用作用域：把借用的寿命「画」出来

NLL 的准确说法：**借用从创建点活到最后一次使用（last use），而非块结束**。绝大多数「报错但直觉上没问题」的代码，问题出在「最后一次使用被放在了冲突操作之后」。修复这类 E0502 的通用动作是**缩短借用作用域**，两个等价的执行手段：

- **重排**：把借用的最后一次使用挪到冲突操作之前（NLL 自动收口）
- **显式块**：用 `{ }` 把只读区间圈起来，让人眼和编译器都看清边界

对照（`examples/e04-long-borrow-scope/`，已验证）：

```rust
// examples/e04-long-borrow-scope/error.rs —— 错误版：两个借用横跨 push（已验证：rustc 1.92.0 报 E0502）
let a = &items[0];   // 借用区间从这里开始……
let b = &items[1];
items.push(4);       // E0502：push 需要 &mut，而 a/b 在 push 之后仍要使用
println!("{a} + {b}");
```

```rust
// examples/e04-long-borrow-scope/fix.rs —— 修复版：块内收口（已验证：rustc 1.92.0 编译运行通过）
{   // 只读借用区
    let a = &items[0];
    let b = &items[1];
    println!("{a} + {b}"); // 借用最后一次使用在块内
}   // 借用在这里结束
items.push(4); // 借用已收口，允许 &mut
```

同一家族还有两个「借用未收口就动容器」的错误码：**E0505**（借引用时把容器 move/drop 走，`examples/e06-move-while-borrowed/`，实测 `cannot move out of items because it is borrowed`，修法 = 先把引用的最后一次使用提前再 move）与 **E0506**（持引用时给同一值赋值，sol-01 case2，实测 `cannot assign to fancy.num because it is borrowed`，修法 = 读与写分开语句）。三者共性是**借用的活跃区间盖过了对同一数据的结构性操作**——先收口，再操作，问题自解。

> 本阶段的「作用域」只谈**编译期借用活跃区间**；运行时作用域（线程、async 任务、锁的临界区）属于 ph12 并发与异步阶段。这里把借用心智练好，ph12 理解「锁持有期 = 可变借用的运行时版」会顺很多。

### 3.7 字段级借用与拆分结构体：把冲突对象从「整个结构」缩小到「一个字段」

Rust 允许**同时借用一个结构体的不同字段**（只要字段路径不重叠），这是消除 E0502 的第三个杠杆。注意规则边界：字段级拆分只在「直接以字段为借出单位」时成立；一旦走**整体方法**（`fn foo(&self)` / `fn foo(&mut self)`），编译器按整个 `self` 计算借用——哪怕方法只碰一个字段。

`examples/e08-field-level-borrow/` 演示了这条边界（已验证）：

```rust
// error.rs —— 错误版：整体 &self / &mut self 方法粒度太粗（已验证：rustc 1.92.0 报 E0502）
let label = s.name_str(); // 经 &self 方法借整个 s（即使只读 name 字段）
s.hit();                  // E0502：还需要 &mut self，与上面的借用冲突
```

```rust
// fix.rs —— 修复版 B：字段级借用（已验证：rustc 1.92.0 编译运行通过）
let label_b = &b.name; // 只借字段 name
b.hits += 1;           // 改字段 hits：两个字段不重叠，借用检查放行
```

**修法家族对照**：借 `s.name_str()`（整体 `&self`）再调 `s.hit()`（整体 `&mut self`）→ E0502，有三种路线：① 重排（把读取先做完）；② 把读取改成字段级借用（只借 `&s.name`），让修改落在别的字段；③ 如果读取本身就是方法、改的又是别的字段，就把**结构体拆开**（平行数组或更小的结构体组合），让「读的名字」与「改的分数」落在不同字段容器上（exercises/sol-03 修法 3 的 TeamSplit 演示了这种数据结构级重构）。路线③的成本是数据模型要按「访问模式」设计——取舍见 5 节。

### 3.8 索引或临时变量：把「借用」换成「值」

第四个杠杆最朴素：**当只需要一个值、不需要引用关系时，别借，取副本。** 对 `Copy` 类型（`i32`、`bool`、`&str`……）用下标取副本**零成本**：

```rust
// examples/e03-shared-then-mut/fix.rs —— 修复版：索引取 Copy 副本（已验证：rustc 1.92.0）
let first = items[0]; // 取出 Copy 副本，与 items 再无借用关系
items.push(4);        // 可变借用畅通
println!("first = {first}，现在共 {} 项", items.len());
```

非 Copy 类型取不出「副本」——`items[0]` 对 `Vec<String>` 返回的是借用，想 move 出来会报 E0507（`cannot move out of index of Vec<String>`，sol-01 case3），此时要么显式 `.clone()`（成本判断见 3.9/5），要么换成「先算下标、分步借/改」的索引模式。exercises/sol-03 修法 2 展示了完整形态：先用一个**不携带借用**的函数算出下标（`top_idx` 内部借用即收口，返回 `usize`），打印名字的借用只活在本语句，随后再用下标做 `&mut` 修改——「临时变量」承载下标、「短借用」承载读取，各司其职。

### 3.9 必要时引入拥有数据：重构优先于 clone

E0507 / E0597 / E0716 / E0515 有个共同的深层修法：**引入拥有数据**——把 `&T` 换成 `T`、把 `&str` 换成 `String`、把「存引用的结构体」换成「存拥有的结构体」、把「返回引用」换成「返回拥有值」。它的本质不是「避开借用检查」，而是**让数据的生命周期与使用方式对齐**：谁要长期持有，谁就该拥有。

| 形态 | 引用版本（易触发错误） | 拥有版本（干净所有权流） |
|------|----------------------|------------------------|
| 函数返回 | 返回局部 `String` 的 `&str`（E0515） | 返回 `String` |
| 结构体字段 | 持有 `&'a str`（生命周期参数传染整个结构体，ph08 已讲） | 持有 `String` |
| 内层数据外传 | 把内层借用交给外层（E0597） | 用 `to_owned()`/clone 让外传值拥有数据 |
| 函数参数 | `&mut Vec<String>` 想移出元素（E0507） | 接收拥有 `Vec`，内部 `remove` |

**重构优先于 clone（refactor over clone）** 是 rust-patterns 的显式反模式告诫：`.clone()` 只是把冲突「压」下去，没有回答「为什么这里需要两份数据」。一条可辩护的修复顺序（对应 rust-patterns「Borrow, don't clone」）：

1. **先试借用**（3.2）——只读就用 `&`，别急着 clone；
2. **再试缩短/拆分**（3.6~3.8）——短借用、字段级、索引快照；
3. **然后考虑重构数据结构**（3.7 拆结构体、3.9 拥有化）——让借用关系从根上消失；
4. **最后才轮到 clone**——并要能说出理由（见 5 节判据），否则它只是把问题推给运行时。

> ⚠️ 不要把 `clone` 污名化：clone 是语言的一部分，问题只在「**无理由**的 clone」。判断有没有理由的判据见 5 节。另外注意与 `Copy` 的区别——`Copy` 是编译器按位复制、隐式发生且零成本心智；`clone` 是显式方法调用、可能深拷贝堆数据（`String::clone` 一定分配），语义上允许自定义。

### 3.10 NLL 视角统观：借用到底活到哪

用 NLL 语言把前面所有修法重讲一遍，你会得到统一的心智：**borrow 是 MIR 数据流上的一个「区间」，从创建点到最后一次使用**。因此：

- 报 E0502/E0499，是**两个区间重叠**且 mutability 不兼容；
- 「缩短作用域」（3.6）是**让区间终点提前**；
- 「块内收口」是**给区间画上显式终点**，防止读者（和未来的你）误以为借用活到块尾；
- 报 E0597/E0716/E0515，是**区间终点超过了数据生命周期**——区间比数据长寿，必须让数据长寿或让区间内不依赖数据（拥有化）；
- 两阶段借用（3.3）是**给区间加内部结构**：预留段按共享、激活段按可变。

一个反例检验你是否真的懂了 NLL（`examples/` 之外的课堂例子，本机已验证编译通过）：

```rust
fn main() {
    let mut x = 5;
    let y = &x;    // 不可变借用 x
    let z = &mut x; // 为什么这里不报错？—— y 的借用活不到 z 的创建点（y 之后无使用）
    *z += 1;
    println!("{z}");
}
```

如果把 `println!("{y}")` 加回 `z` 之后，`y` 的最后一次使用被挪到 `z` 之后 → 立刻报 E0502。**NLL 之下没有「词法上很危险」的代码，只有「borrow 区间真的重叠」的代码**——这是本阶段最值得内化的认知切换。

**迭代器是 E0502 的高发现场**：`items.iter()` 生成的迭代器借**整个** `items`，只要迭代器还活着就不能修改容器。教学片段（本机已验证：下块报 E0502、修法块编译运行通过）：

```rust
// 错误形态：迭代器借整个 items，push 与它后续的使用重叠
let iter = items.iter();   // 借整个 items
items.push(0);             // E0502：iter 之后还要用（for 循环）
for x in iter {
    println!("{x}");
}
```

```rust
// 修法：让迭代器的借用只活在循环内（循环体结束即收口），随后再修改
for x in items.iter() {    // 借用只活在循环内
    println!("{x}");
}                          // 借用收口
items.push(0);             // 允许
```

这条与 roadmap ph09 练习「迭代器与借用冲突（复现 E0502 并修复）」呼应——ph09 让你「复现」，本阶段让你「系统化修复」。

### 3.11 调试流程收口：五步检查法

把全章装进一条可重复的执行流，遇到借用错误时按序走：

1. **复现并锁定第一行**：读 `error[E0XXX]:` 的动作描述与 `-->` 定位，不要跳过直接看 help；
2. **归因家族**：对照 3.1 地图问「这是 move 后用、可变排他、共享/可变冲突、还是寿命不足？」——家族决定修法工具箱的方向；
3. **读 span 画区间**：在报错里找出三个点——借用发生点、冲突点、最后一次使用点，判断是「区间重叠」还是「区间比数据长寿」；
4. **按家族选第一修法**：move 后用 → 先想借用；区间重叠 → 短作用域/字段级/索引快照；比数据长寿 → 提升拥有者或拥有化；全程守住「重构优先于 clone」的顺序（3.9）；
5. **编译后自我复盘三问**：这次改动引入新的 clone 了吗？如果有，clone 的理由经得起 5 节三条判据吗？如果下次再见到同类报错，第一反应应该是哪一步？

五步法的终点不是「编译通过」，而是**「所有权流」说得清**——练习 1 的「修复后所有权流向一句话」和 project/ 每案例 explain.md 的「所有权流向」小节，都是把这个要求固化成文字。建议把这五步抄在 project/verify.sh 旁边，作为你自己加案例时的检查单。

## 4. 底层原理

### 4.1 类型系统视角：lifetime 是类型的一部分

`&'a mut T` 的完整读法是「一个带有生命周期参数 `'a` 的引用类型」。借用检查本质是**类型推断的一个分支**：编译器先给每个引用分配 region 变量（lifetime 占位），再检查 region 之间的包含关系（subtyping：短 lifetime 可以 coerced 成较长的使用场景吗？不行——只能反过来），最后把所有约束联立求解。报错码里的每一行 span 都对应一条约束：

```text
例子：let first = &items[0];  items.push(4);
      ├─ 借出 &'a Vec<i32>            ├─ 需要 &'b mut Vec<i32>
      └─ 约束：'a 必须覆盖 println!("{first}") 的使用点（与 'b 冲突）
```

为什么说 E0515 / E0597 是「类型错误」而非「运行时错误」？因为 **region 约束在编译期可判定**：函数签名（`fn f<'a>(...) -> &'a str`）就是一份「返回值 lifetime 由谁提供」的契约，编译器检查实现时发现局部变量不满足契约 → 报错。ph08 已讲契约怎么写；本阶段补的是「违约时编译器怎么描述」。

### 4.2 NLL 数据流分析：borrow 是 MIR 上的区间

NLL 的检查对象不是源码的语法树，而是 **MIR（Mid-level Intermediate Representation）**——一种把控制流、作用域、临时值都显式化的中间表示。借用检查在 MIR 上做**数据流分析**：为每个借用（rustc 内部称 loan）计算「从创建到释放的活跃区间」，再做**冲突检查**——同一时刻同一内存位置，活跃的可变借用数 ≤1、且与活跃共享借用不同时存在。

```text
源码                                        MIR（示意）
items.push(items.len());   ──▶   _1 = &mut items;          // 可变借用 loan L1 创建
                                     _2 = (&items).len();   // 共享读取：与 L1 冲突？
                                     Vec::push(_1, _2);     // L1 在此激活/使用
  ↑ push 的 &mut 是方法自动引用 → 两阶段：L1 在 _2 求值阶段只是「预留」
```

NLL 数据流比词法作用域精确的关键：**区间终点取最后一次使用，而不是块的右花括号**——这就是 3.6 里「把 println 挪前一行代码就过了」的底层原因。Polonius（未来方向）进一步把「区间包含」升级为「位置敏感」分析，能放行更多条件分支/字段级模式（写作时在 nightly 实验，未默认启用，本阶段不依赖它）。

### 4.3 两阶段借用的实现：reservation 与 activation

rustc-dev-guide「two-phase borrows」对两阶段的描述可浓缩成三个事实：

1. **触发条件**：只有特定隐式可变借用会产生两阶段——方法调用的自动引用（`x.push(...)` 的 `&mut`）、复合赋值运算符、实参位置的隐式可变重借用；源码手写的 `&mut` 一律普通可变借用。
2. **两个点**：`reservation`（预留点，借用在 MIR 临时变量上创建）与 `activation`（激活点，通常是调用本身）。预留后、激活前，该借用按**共享借用**参与冲突检查——所以参数里读自己是允许的。
3. **规则落点**：若在激活点有与它冲突的活跃可变借用 → 报错；预留点有冲突的可变借用 → 也报错。本质是「把排他性的开始时间推迟到真正动手之前」。

`v.push(v.len())` 在 NLL 之前（无两阶段）会被当普通 `&mut` 与 `&` 冲突拒绝；两阶段放行后成为惯用法。理解 4.3 后，3.3 的 E0499（两个手写 `&mut`）与 E0503（手写 `&mut` + 同表达式读）为什么不受两阶段保护，就一目了然了。

### 4.4 「借用栈」心智模型：重借用像栈一样后进先出

读代码时，把活跃的借用想象成叠在数据上的「借用栈」：**每次重借用（reborrow）往里压一层，内层不能比外层活得久**。

```text
let mut data = ...;
let r1 = &mut data;        // 栈底：对 data 的可变借用 L1
{   let r2 = &mut *r1;     // 压栈：从 L1 重借用出 L2（r1 被「暂停」）
    *r2 += 1;
}                          // L2 出栈（r2 生命周期结束）
*r1 += 1;                  // L1 恢复可用
```

这个模型解释了三件事：为什么重借用内层结束后外层还能用（出栈即恢复）；为什么「内层借用逃逸到外层」必被拒（违反后进先出）；以及为什么 3.7 的字段级借用是例外——不同字段是**并排的两个栈**而非同一根栈，天然不冲突。

> 严谨性声明：编译期的借用检查按 4.1~4.3 的 region/数据流做，**不存在运行时的借用栈**。「借用栈」是便于人脑推理的心智模型；把它形式化为内存对象的别名模型（Stacked Borrows）是 `unsafe`/Miri 语义的一部分，**属于 ph14 Unsafe Rust 与安全抽象阶段**，本阶段只用其直觉层面，不涉及其形式语义。

## 5. 使用场景

**什么时候 clone 可接受，什么时候必须重构**，是本阶段最重要的工程判断。判据不是「能不能编译」，而是「这份复制由谁买单、多久一次、买了什么」：

| 场景 | 推荐动作 | 理由 |
|------|---------|------|
| 循环体内对大结构 clone 以满足借用检查 | **必须重构**（缩短作用域/索引/拥有化） | 每次迭代一次堆分配，代价随规模线性放大；clone 只是把冲突推后 |
| 把数据送进集合/跨 API 边界，边界本来就要拥有值 | clone 可接受 | 复制发生在「所有权交接点」，语义上必要（见 3.9 的 remove 对照） |
| 低频一次性读取（初始化时读一次配置） | clone 可接受 | 一次性成本，换来代码直白 |
| 只需要 `Copy` 值（i32/bool/&str） | **优先索引/快照，不是 clone** | Copy 零成本，clone 概念上多余 |
| 数据由你设计，冲突频发 | **必须重构结构**（拆结构体/拥有化） | 数据模型与访问模式不匹配，clone 治标不治本 |
| 性能敏感热路径 | **必须重构** | 分配次数是 [ph22 性能优化与 Profiling 阶段](../ph22-perf-profiling/22-perf-profiling.md)的首要优化对象，先在这里把 clone 消灭掉 |
| 原型/教学代码、可读性优先 | clone 可接受 | 先跑通再优化；但要注释「此处 clone 是临时的，正式版应…… 」 |

一句话决策：**clone 之前先回答三个问题——这份数据多大？多久一次？除了 clone 还有没有不改变数据结构的办法？** 都答不上来就重构。rust-patterns 的反模式清单里「.clone() 只是为了满足 borrow checker」排在显眼位置，与本阶段的口径一致。

**跨语言对比（为 analysis/ 积累素材）**：

- **C++**：`std::unique_ptr` 的 move 语义 ≈ Rust 的 move，但 C++ 没有编译期借用检查——悬垂引用（dangling reference）是 UB，靠程序员纪律与 sanitizer 事后发现；`const&` 类似共享借用但没有「借用活跃区间」的编译期概念，迭代器失效（vector 扩容后旧迭代器）是运行期 bug。Rust 把 C++ 的「迭代器失效」「悬垂」「数据竞争」统一提前到编译期。
- **GC 语言（Java / C# / Go / Python / JavaScript）**：所有引用默认「共享 + 可空」，GC 保证对象不被提前回收，因此没有悬垂；代价是**没有编译期可变排他**——同一对象的并发读写靠锁/原子/运行时检查，正确性依赖程序员，数据竞争是运行时问题。Rust 的 &mut 排他 ≈ 语言内置的「写锁」，但检查发生在编译期、零运行时开销。
- **Swift**：ARC 引用计数 + 值语义，有编译期 exclusivity 检查（重叠访问检测）但覆盖面与严格度弱于 Rust 的借用检查；Rust 是唯一把「别名 + 可变」作为编译期类型错误的主流系统语言。
- 对 Tenet 合成的启示：**「权限（读/写/独占）+ 生命周期」作为类型系统的一部分，而不是运行时机制**，是 Rust 内存安全的制度根源——一个可辩护的「别名异或可变」规则 + 位置敏感的生命周期分析，比 GC 或 ARC 都更接近零成本与可证明安全。

## 6. 代码示例

本节展示示例的关键片段，完整文件在 [`examples/`](./examples/) 目录。验证环境：rustc/cargo 1.92.0（macOS arm64）；**验证说明**：e01~e09 全部已验证（error 版逐一实测产生预期错误码、fix/main 版实测编译运行通过），示例为纯 `std` 单文件、离线可用。结构上采用「错误案例集」形态——每个案例一个目录，`error.rs`（故意编译失败，文件头声明期望错误码）+ `fix.rs`（修复版），README 给出逐案例验证命令。

| 示例 | 对应主文档 | 演示错误码 | 一句话说明 |
|------|-----------|-----------|-----------|
| [`examples/e01-moved-value/`](./examples/e01-moved-value/) | 3.2 | E0382 | move 后读原变量；修复 = 借用 |
| [`examples/e02-multiple-mutable-borrow/`](./examples/e02-multiple-mutable-borrow/) | 3.3 | E0499 | 双 &mut；修复 = 用完即止 |
| [`examples/e03-shared-then-mut/`](./examples/e03-shared-then-mut/) | 3.4/3.8 | E0502 | 借元素后 push；修复 = 索引取 Copy 副本 |
| [`examples/e04-long-borrow-scope/`](./examples/e04-long-borrow-scope/) | 3.6 | E0502 | 长借用横跨修改点；修复 = 块内收口 |
| [`examples/e05-borrowed-lifetime/`](./examples/e05-borrowed-lifetime/) | 3.5 | E0597 | 借用外逃作用域；修复 = 数据提升 / 拥有化 |
| [`examples/e06-move-while-borrowed/`](./examples/e06-move-while-borrowed/) | 3.6 | E0505 | 借用中 move 容器；修复 = 先收口再 move |
| [`examples/e07-temporary-lifetime/`](./examples/e07-temporary-lifetime/) | 3.5 | E0716 | 引用临时值；修复 = 拥有变量 / 集合拥有数据 |
| [`examples/e08-field-level-borrow/`](./examples/e08-field-level-borrow/) | 3.7 | E0502 | 整体方法粒度太粗；修复 = 重排 / 字段级 |
| [`examples/e09-two-phase-borrow/`](./examples/e09-two-phase-borrow/) | 3.3 | —（正面） | 两阶段借用放行的两种形态 |

### 示例 3：E0502 的错误版与修复版（`examples/e03-shared-then-mut/`）

```rust
// examples/e03-shared-then-mut/error.rs —— 错误版（已验证：rustc 1.92.0 报 E0502）
fn main() {
    let mut items = vec![1, 2, 3];
    let first = &items[0]; // 不可变借用
    items.push(4);         // E0502：与活跃的不可变借用冲突
    println!("first = {first}");
}
```

```text
error[E0502]: cannot borrow `items` as mutable because it is also borrowed as immutable
```

```rust
// examples/e03-shared-then-mut/fix.rs —— 修复版：索引取 Copy 副本（已验证：rustc 1.92.0）
fn main() {
    let mut items = vec![1, 2, 3];
    let first = items[0]; // 取副本，不再持有借用
    items.push(4);
    println!("first = {first}，现在共 {} 项", items.len());
}
```

验证命令（完整命令见 examples/README.md）：

```bash
# 1. 验证 error 版产生预期错误码
cd examples/e03-shared-then-mut
rustc --edition 2021 error.rs          # 应报 error[E0502]，退出码非 0
# 2. 编译并运行 fix 版（-o 输出到 /tmp，避免污染仓库）
rustc --edition 2021 fix.rs -o /tmp/ph18-e03-fix && /tmp/ph18-e03-fix
```

其余示例的 error 版首行报错原文（均已在 rustc 1.92.0 实测）：E0382 `borrow of moved value: title`；E0499 `cannot borrow score as mutable more than once at a time`；E0597 `config does not live long enough`；E0505 `cannot move out of items because it is borrowed`；E0716 `temporary value dropped while borrowed`。练习侧的补充错误码（exercises/sol-01、project/cases）覆盖 E0503 / E0506 / E0507 / E0508 / E0509 / E0515 / E0596，首行原文见对应 error.rs 与各 explain.md。

## 7. 总结

### 关键要点

- **错误码是按规则家族组织的，不是零散编号**：move 后用（E0382/E0505/E0507/E0508/E0509）、可变排他（E0499/E0503）、共享/可变冲突（E0502/E0506）、寿命不足（E0597/E0716/E0515）、可变性缺失（E0596）——先归因家族，再选修法（3.1）
- **修法工具箱五件套**：① 只读就借用不 move（E0382）② 缩短借用作用域/块内收口（E0502/E0505/E0506）③ 字段级借用与拆结构体（整体方法粒度太粗时）④ 索引/临时变量把借用换成值（Copy 零成本）⑤ 必要时引入拥有数据（E0597/E0716/E0515/E0507），并遵循**重构优先于 clone**（3.6~3.9）
- **NLL 是统观一切的视角**：借用是 MIR 上的区间，活到「最后一次使用」；报错 = 区间重叠（mutability 不兼容）或区间比数据长寿（3.10/4.2）
- **两阶段借用只放行隐式 &mut**：`v.push(v.len())` 能过，`set(&mut x, x)` 报 E0503——手写 &mut 立即激活（3.3/4.3）
- **clone 的判据**：数据多大、多久一次、有没有不改结构的办法；答不上来就重构（5）
- **E0597/E0716/E0515 是一族**：数据形态不同（局部/临时/直接返回），修法相同——让数据长寿或让结果不携带借用（3.5）

### 阶段验收清单

- [ ] 能对着 rustc 报错说出「错误码 → 家族 → 冲突点」，而不是只会照 help 改（能解释 help 建议为什么不一定该采纳）
- [ ] 遇到 E0502 能给出至少两种修法（短作用域 / 索引快照 / 字段级），并说清各自改了什么
- [ ] 能解释 NLL：同一个 E0502 代码，把 println 挪到 push 前为什么就能过
- [ ] 能说清两阶段借用放行什么、不放行什么（手写 &mut 不在其列）
- [ ] 能判断何时 clone 可接受（背得出 5 节三条判据）
- [ ] 能为一组「先读后写」冲突在 clone / 索引 / 拆结构体之间做有依据的三选一（练习 3 验收）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题对应 roadmap 练习：收集 5 个借用错误并写修复说明、把长借用拆成短作用域、比较 clone/索引/拆结构体三种修复方式。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**借用错误练习集**——把「错误版 + 修复版 + 解释」沉淀成可被 `verify.sh` 自动验证的案例集工程（roadmap 推荐项目落地）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 跨语言对比

- Rust 把「谁拥有 + 谁在借 + 借多久」做成编译期类型约束（错误码即约束违反的索引）；C++ 的引用/迭代器失效是运行期 UB、GC 语言把别名问题推迟到运行时锁——**「编译期别名异或可变」是 Rust 独有且零运行时成本的制度设计**（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

[**ph19 内存布局、零拷贝与协议解析阶段**](../ph19-memory-layout-zero-copy/19-memory-layout-zero-copy.md)——本阶段修好的「借用」正是零拷贝的地基：当你用切片 `&[u8]` 直接借用网络缓冲、而不复制成 Vec 时，就是在吃透 E0507/E0597 之后，让借用为自己省下每一次分配。届时把本阶段的「拥有化 vs 借用」判断搬到字节层，就是零拷贝协议解析的核心手艺。
