# examples —— 智能指针阶段完整示例

对应主文档 `10-smart-pointers.md` 第 6 章示例 1~6 的完整可运行版本。全部为单文件、零第三方依赖（智能指针全在 `std`，不依赖 cargo 联网）。验证环境：rustc 1.92.0（macOS arm64），统一用 `rustc --edition 2021` 单文件编译。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-box-recursive-list.rs` | 示例 1 | Box 堆分配与递归类型：`enum List` 用 `Box<List>` 打破无限大小（不用 Box 报 E0072），实现 `len`/`sum`，Drop 自动释放整条链 | `rustc --edition 2021 ex01-box-recursive-list.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-drop-order.rs` | 示例 2 | Drop 析构顺序三条规则：变量声明逆序、结构体先 impl Drop 体再按字段声明顺序、`std::mem::drop` 提前触发（输出顺序已实测） | `rustc --edition 2021 ex02-drop-order.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-rc-shared-config.rs` | 示例 3 | Rc 引用计数共享只读配置：`Rc::clone` 只增计数不拷贝数据，`strong_count` 实测 1 → 3 → 2，参数写 `&Config` 走 deref coercion | `rustc --edition 2021 ex03-rc-shared-config.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-refcell-combo.rs` | 示例 4 | RefCell 内部可变性（`&self` 下写日志）+ BorrowMutError 运行期 panic（`catch_unwind` 捕获）+ `Rc<RefCell<T>>` 组合模式 | `rustc --edition 2021 ex04-refcell-combo.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-arc-mutex-counter.rs` | 示例 5 | `Arc<Mutex<u64>>` 线程间计数：8 线程 × 1000 次 = 8000（实测），`assert_eq!` 兜底 | `rustc --edition 2021 ex05-arc-mutex-counter.rs -o /tmp/ex05` | `/tmp/ex05` |
| `ex06-weak-break-cycle.rs` | 示例 6 | Weak 打破循环引用：树结构强/弱计数实测（root 1/1、leaf 2/0），父先释放后 `upgrade()` 返回 `None`；后半段故意演示循环泄漏（drop 不触发） | `rustc --edition 2021 ex06-weak-break-cycle.rs -o /tmp/ex06` | `/tmp/ex06` |

## 关于"故意出错 / 故意演示"的代码

- `ex04-refcell-combo.rs`：被注释的「裸跑」代码块（两个 `borrow_mut` 同时存活）**故意运行会 panic**——块内首行注释已写明；想看 panic 用文件中 `catch_unwind` 包裹的版本。注意运行该文件时 **stderr 会打印一行 `RefCell already borrowed`**，这是被 `catch_unwind` 捕获的 panic 消息（程序退出码为 0，正常继续）——panic 消息文本为实测结果（`borrow` 撞上可变借用时是 `RefCell already mutably borrowed`）。
- `ex06-weak-break-cycle.rs`：后半段**故意演示循环引用内存泄漏**——两个 `Rc` 互指，句柄 drop 后 `Drop` 不触发、计数停留 1/1。泄漏发生在进程内，进程退出时由操作系统回收，无实际危害；运行前提已在块内首行注释写明。

## 运行产物

编译产物输出到 `/tmp/`，验证后已删除，仓库内不留任何二进制文件。

六个示例均已在本环境编译零警告并运行验证（已验证：rustc 1.92.0，`rustc --edition 2021` 单文件编译）。`ex05` 的多线程 `Arc` drop 顺序由调度决定、不做断言（顺序不定），只断言确定性的最终计数 8000。
