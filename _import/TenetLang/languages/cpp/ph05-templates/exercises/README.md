# exercises —— 模板与泛型编程阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17（g++ 兼容）。练习 3 涉及 concept 用 `-std=c++20`，其余 `-std=c++17`。
> 建议完成顺序：1 → 2 → 3 → 4 → 5。

## 练习 1：泛型 Max（★）

**目标**：写函数模板 `my_max`，支持同类型 `int` / `double` / `std::string`，再为混合类型补一个返回 `std::common_type_t` 的版本。

**要求**：

- 单 `T` 版本：`template<typename T> const T& my_max(const T& a, const T& b)`
- 双参类型版本：`template<typename T, typename U>` 返回 `std::common_type_t<T, U>`，让 `my_max(3, 4.5)` 编译通过（`common_type<int, double>` 为 `double`）
- 用 `assert` 或 `static_assert` 验证四组调用：`my_max(3, 7) == 7`、`my_max(3.14, 2.71) == 3.14`、`my_max("abc", "xyz")` 的 string 版、混合 `my_max(3, 4.5) == 4.5`
- `-Wall -Wextra` 编译零警告

**验收**：四组调用全部通过断言；能说清只写单 `T` 版本时 `my_max(3, 4.5)` 为什么编译失败（模板实参推导冲突）。

## 练习 2：泛型 Stack（★★）

**目标**：实现 `Stack<T>` 类模板，底层用 `std::vector<T>`，遵守 Rule of Zero（C.20）。

**要求**：

- 成员函数：`push`（含 `const T&` 与 `T&&` 两个重载）、`pop`（`std::move` 移出栈顶后 `pop_back`）、`top`（const / 非 const 两个重载）、`empty`、`size`
- 能 `const` 的成员函数全标 `const`（Con.2）
- 禁止裸 `new`/`delete`：成员只有 `std::vector<T>`，不写析构/拷贝/移动（Rule of Zero）
- `main` 中用 `int` 和 `std::string` 两组数据验证 LIFO 顺序

**验收**：`int` 栈压入 10/20/30 后按 30/20/10 弹出；`string` 栈行为一致；编译零警告。

## 练习 3：concept 约束泛型函数（★★）

**目标**：自定义 concept + requires 约束一个泛型求和函数，替代 enable_if / SFINAE。

**要求**：

- 自定义 `template<typename T> concept Numeric = std::integral<T> || std::floating_point<T>;`
- 用简写形式写 `template<Numeric T> T sum(const std::vector<T>&)`
- 再用 `requires` 子句写一个等价版本（两种写法都出现）
- `assert` 验证：`sum({1, 2, 3}) == 6`、`sum({1.5, 2.5}) == 4.0`
- 用**注释**（不要写进可运行代码）说明 `std::vector<std::string>` 传给 `sum` 时的报错（constraints not satisfied）

**验收**：两种写法求和正确；能解释 concept 相比 `enable_if` 的错误信息差异。

## 练习 4：简单 Optional（★★★）

**目标**：用 `std::unique_ptr<T>` 实现一个最小 `Optional<T>`（值或空两态）。

**要求**：

- 默认构造为空；值构造为有值（`T` 的拷贝与移动各一个构造函数）
- `bool has_value() const`、`explicit operator bool() const`
- `T& value()` 与 `const T& value() const`：空时 `throw std::logic_error`
- `T& operator*()` 与 `const T& operator*() const`：前置条件非空，不做检查
- `reset()` 清空
- 拷贝构造 / 拷贝赋值 = 深拷贝（`unique_ptr` 不可拷贝，需手写，Rule of Five，C.21）；移动构造 / 移动赋值 = 默认
- `main` 验证：空态 `has_value()` 为 false、空态 `value()` 抛异常（`catch` 确认）、拷贝互不影响、移动转移、`reset` 后为空

**验收**：两态行为正确；拷贝后修改互不影响；空态 `value()` 抛出 `std::logic_error`；编译零警告。

> **提示**：`std::unique_ptr` 的完整语义属于 ph06 智能指针阶段，这里只借用它的 RAII 释放能力——这正是「先会用、再深究」的模板阶段写法。

## 练习 5：简单 TMP 模板元编程（★★★）

**目标**：编译期计算——递归实例化 + typelist 基本变换，全程零运行时代码。

**要求**：

- `Factorial<N>`：递归实例化 + `Factorial<0>` 全特化
- `Fibonacci<N>`：双递归 + 两个全特化终止
- `template<typename... Ts> struct TypeList {};`
- `Length<List>`：偏特化 + `sizeof...(Ts)`
- `Contains<T, List>`：C++17 折叠表达式 `(std::is_same_v<T, Ts> || ...)`
- 全部用 `static_assert` 验证（`Factorial<5> == 120`、`Fibonacci<10> == 55`、`Length<TypeList<int, double, char>> == 3`、`Contains` 正反例）

**验收**：所有 `static_assert` 编译通过即为验证成功；能解释模板元编程为什么用「递归」而非「循环」。
