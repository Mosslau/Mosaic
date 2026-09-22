# c03 —— E0515：返回指向局部变量的引用

**错误版**（`error.rs`）：`best_of` 想把两个输入拼成一段新文本再返回引用。拼接产物
`combined` 是函数内的局部 `String`，函数一返回就被销毁 —— 返回的 `&str` 指向悬垂内存。

```
error[E0515]: cannot return value referencing local variable `combined`
```

**为什么这样设计**：`E0597`（borrowed value does not live long enough）讲的是「借用逃出数据
生命周期」的一般形态；`E0515` 是它的「直接返回局部引用」特例，编译器单独命名以便一眼认出。
底层原因一致：**新造的数据没有借用来源，想传出去就只能移交所有权**。（与 examples/e05 的
块作用域外逃借用对照学习。）

**修复版**（`fix.rs`）：把返回类型从 `&'a str` 改成 `String` —— 引用换成拥有值，生命周期
问题消失。

**所有权流向**：`a`/`b` 只被读取（借用）→ 拼接出新 `String`（拥有）→ 所有权返回给调用方
→ 调用方决定它何时销毁。
