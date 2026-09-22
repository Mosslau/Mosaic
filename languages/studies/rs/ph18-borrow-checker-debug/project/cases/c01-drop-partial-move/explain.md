# c01 —— E0509：从 Drop 类型里 move 出字段

**错误版**（`error.rs`）：`Droppable(Vec<u8>)` 实现了 `Drop`，此时把 `d.0` 这个字段单独
move 出去是被禁止的 —— drop 代码需要看到完整结构，字段被抽走会让它读到「半残」的值。

```
error[E0509]: cannot move out of type `Droppable`, which implements the `Drop` trait
```

**为什么这样设计**：`Drop` 的实现者在 `drop(&mut self)` 里假定自己能看到整个类型的每个字段。
允许部分 move 会让该假定失效（字段已经被搬走、只剩未初始化状态）。这是 Rust「类型不变量
优先于便利」的又一例 —— 教学增量见主文档 3.9。

**修复版**（`fix.rs`）：给类型加一个消费式方法 `into_inner(mut self)`，内部用
`std::mem::take(&mut self.0)` 把内容换成空默认值。`self` 始终结构完整，drop 照常执行，
数据安全转移。

**所有权流向**：`d`（拥有 `Vec<u8>`）→ 整个 move 进 `into_inner`（借由 `mem::take` 把
`Vec<u8>` 再 move 出来）→ 空壳 `self` 在函数返回时被 drop。
