# c02 —— E0507：从共享引用（HashMap Index）后面 move 数据

**错误版**（`error.rs`）：`map["a"]` 走 `Index` trait，返回的是共享引用 `&String`；把它直接
赋给 `let v` 等于尝试从共享引用后面 move —— 调用方只有「读」的权利，没有「拿走」的权利。

```
error[E0507]: cannot move out of index of `HashMap<String, String>`
```

**为什么这样设计**：Rust 的引用分「共享（只读）」与「可变（独占）」两种权利。`&V` 只授出读权，
move 却需要所有权；让 `&V` 背后的值能被搬走等于允许共享引用失效，编译器在编译期就拦下。
（教学增量：这条规则与 `Vec` 下标、`&str` 后面的内容同源，是整条 E0503~E0507 家族的共同
心智 —— 见主文档 3.1 错误号地图。）

**修复版**（`fix.rs`）：想保留 map 就 `clone`（复制一份）；想把值真正搬走，就让调用方交出
`HashMap` 的所有权，用 `remove` 移出元素。

**所有权流向**：A 方案 `map` 与 `v` 各自持有一份（clone）；B 方案 `HashMap` 的所有权被
消费，`remove` 把其中一个元素的所有权移交出来。
