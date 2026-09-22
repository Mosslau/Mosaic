# exercises —— 智能指针阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~6 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。全部为单文件、零第三方依赖（智能指针全在 `std`，不依赖 cargo 联网），统一用 `rustc --edition 2021` 单文件编译。

## 练习 1：用 Box 构建递归链表（★）

- **目标**：掌握 `Box<T>` 打破递归类型无限大小（E0072）的用法，理解"递归 = 指针间接"
- **要求**：
  - 定义 `enum List { Cons(i32, Box<List>), Nil }`（**不许去掉 Box**——去掉会报 E0072，可先试一次观察报错）
  - 实现 `len()` 与 `sum()` 两个递归方法
  - 构建链表 `1 -> 2 -> 3 -> 4 -> Nil`，打印 `len` 与 `sum`，并用 `assert_eq!` 断言
  - 不写裸 `unwrap`
- **验收**：`rustc --edition 2021 sol-01-box-recursive-list.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出 `len = 4, sum = 10`

## 练习 2：用 Rc 共享只读配置（★）

- **目标**：掌握 `Rc::clone` 的共享语义（O(1) 只增计数不拷贝数据），理解 deref coercion 让函数参数写 `&T` 更通用
- **要求**：
  - 定义 `Config { host: String, port: u16, pool_size: u32 }`
  - `Rc::new` 只调用一次，再 `Rc::clone` 两次，得到三个句柄
  - 打印函数签名写 `&Config`（不是 `&Rc<Config>`），三个句柄都能传进去
  - 用 `Rc::strong_count` 分别在 clone 前、clone 后打印计数，并 `assert_eq!` 断言 clone 后为 3
- **验收**：`rustc --edition 2021 sol-02-rc-shared-config.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出 `strong = 1` → `strong = 3` → 三行 connect → `strong = 2`

## 练习 3：RefCell 内部可变性：惰性缓存 + 借用冲突（★★）

- **目标**：掌握"`&self` 接口下修改内部状态"（内部可变性），并亲眼确认运行时借用检查的 panic 时机与消息
- **要求**：
  - 实现 `Cache`：字段 `value: RefCell<Option<i32>>`，`get(&self, compute: impl Fn() -> i32) -> i32` 第一次调用执行 `compute` 并缓存，之后直接返回缓存值（**证明 `compute` 只执行一次**：闭包内 `println!` 只应打印一次）
  - 制造借用冲突：`let _r = cell.borrow();` 存活时调 `cell.borrow_mut()`——**编译能通过**，运行期 panic；用 `panic::catch_unwind` 捕获并打印捕获结果
  - 在代码注释中写明 panic 消息文本（实测是 `RefCell already borrowed`）
  - 注意：运行本练习时 **stderr 会打印一行 `RefCell already borrowed`**，这是被 `catch_unwind` 捕获的 panic 消息（panic 钩子仍会输出，程序退出码为 0，正常继续）——与主文档第 6 章示例 4 的说明一致
- **验收**：`rustc --edition 2021 sol-03-refcell-cache.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；`compute 执行` 只出现一次；输出 `v1 = 42, v2 = 42` 与「借用冲突：BorrowMutError panic 已被 catch_unwind 捕获」

## 练习 4：用 Arc\<Mutex\<_\>\> 做线程间计数（★★）

- **目标**：掌握"线程间共享可变状态"的标准组合，理解为什么 `Arc` 与 `Mutex` 缺一不可
- **要求**：
  - 定义 `const NTHREADS: u64 = 8;` 与 `const ITERS: u64 = 1000;`，开 8 个线程各累加 1000 次
  - 每线程 `Arc::clone` + `move` 闭包，循环内 `lock().unwrap()` 修改
  - 所有句柄 `join` 后用 `assert_eq!(final_value, NTHREADS * ITERS)` 断言（**期望值动态计算，不许手写 8000**）
- **验收**：`rustc --edition 2021 sol-04-arc-mutex-counter.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；输出 `total = 8000`，断言通过

## 练习 5：用 Weak 打破循环引用（★★★）

- **目标**：识别"双向引用"结构中的强弱边，用 `Weak` 消除循环泄漏，并用计数与 Drop 打印验证
- **要求**：
  - 定义 `Node { name, value, parent: RefCell<Weak<Node>>, children: RefCell<Vec<Rc<Node>>> }`（**parent 必须是 Weak**）
  - 构建 `root` + 两个叶子：root 的 children 强引用两个叶子，两个叶子的 parent 弱引用 root
  - 打印并核对计数：root `strong=1 weak=2`，每个叶子 `strong=2`
  - 给 `Node` 实现 `Drop` 打印释放；先 `drop(root)`，随后断言两个叶子的 `upgrade()` 都返回 `None`（父已释放），再显式 `drop` 两个叶子
  - **验收要点：全过程所有节点都打印了 drop，无泄漏**
- **验收**：`rustc --edition 2021 sol-05-weak-tree.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；输出依次为 root `1 / 2`、leaf1/leaf2 `2`、`leaf1 的父节点 root value = 100`、`drop Node root`、两行「upgrade() 返回 None」、`drop Node leaf1`、`drop Node leaf2`

> **提示**：练习 1~5 覆盖主文档第 6 章示例 1~6 的主题（示例是"看"，练习是"做"）。卡壳时先回读主文档 3.x 对应小节（3.1 Box、3.3 Drop、3.4 Rc、3.6 RefCell、3.7 Arc/Mutex、3.8 Weak），最后再看 `sol-*`。
