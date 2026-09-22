# ph03 内存模型 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。编译统一加 `-Wall -Wextra -std=c++17`。

## 练习 1：简单 String 类（★★★）

**目标**：手写一个管理堆内存的 String 类，掌握五函数（拷贝构造 / 拷贝赋值 / 移动构造 / 移动赋值 / 析构）。

**要求**：

- 成员：`char* data_` 和 `size_t size_`（保存不含 `\0` 的长度）
- 构造函数 `explicit String(const char* s = "")`：按 `s` 长度分配堆内存并复制
- 拷贝构造、拷贝赋值：**深拷贝**（分配独立堆内存），拷贝赋值需自赋值安全
- 移动构造、移动赋值：标 `noexcept`，转移 `data_` 后把源对象 `data_` 置 `nullptr`、`size_` 置 `0`，移动赋值需自移动安全
- 析构：释放 `data_`
- 提供 `const char* c_str() const` 和 `size_t size() const`

**验收**：拷贝后修改一个对象不影响另一个；移动后源对象 `c_str()` 返回空串、`size()` 为 0；自赋值 / 自移动后对象内容不变。

## 练习 2：动态数组类（★★）

**目标**：手写一个固定容量的动态数组类，掌握深拷贝。

**要求**：

- 成员：`int* data_`、`size_t capacity_`、`size_t size_`
- 构造函数 `explicit DynArray(size_t cap)`：按容量分配 `int` 数组，`size_` 初始为 0
- `bool push(int val)`：容量满返回 `false`，否则追加并返回 `true`
- `int at(size_t i) const`：越界返回 `-1`
- `size_t size() const`、`size_t capacity() const`
- 拷贝构造、拷贝赋值（**深拷贝**）、析构

**验收**：深拷贝后修改拷贝对象不影响原对象；容量满 `push` 返回 `false`；越界 `at` 返回 `-1`。

## 练习 3：支持移动构造的 Buffer（★★）

**目标**：手写一个支持移动构造 / 移动赋值的 Buffer，掌握移动语义与 `noexcept`。

**要求**：

- 成员：`char* data_` 和 `size_t size_`
- 构造函数 `explicit Buffer(size_t size)`：分配 `size` 字节的 `char` 数组
- `char* data()` 与 `const char* data() const`、`size_t size() const`
- 拷贝构造、拷贝赋值（**深拷贝**）
- 移动构造、移动赋值（标 `noexcept`）：转移后源对象 `data_` 置 `nullptr`、`size_` 置 `0`
- 析构：释放 `data_`

**验收**：移动后源对象 `size()` 为 0、`data()` 为 `nullptr`；目标对象持有原数据；`static_assert` 能证明移动构造是 `noexcept`（可选，见 sol-03）。

## 练习 4：用 RAII 管理文件句柄（★★）

**目标**：用 RAII 封装 `std::FILE*`，实现文件自动关闭。

**要求**：

- 封装一个类（如 `WalFile`），成员 `std::FILE* file_`
- 构造函数打开文件（追加模式 `"ab"`），失败时记录错误
- 析构自动 `fflush` + `fclose`
- **禁止拷贝、允许移动**：移动构造 / 移动赋值后源对象 `file_` 置 `nullptr`
- 提供 `bool append(const std::string& key, const std::string& value)`（追加一行 `key\tvalue`）、`bool flush()`、`explicit operator bool() const`

**验收**：对象离开作用域后文件自动关闭；回读文件内容与写入一致；移动后源对象 `operator bool()` 为 `false`。
