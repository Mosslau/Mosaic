# exercises —— 现代 C++ 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17（g++ 兼容）。练习 3 涉及 `<format>`/`<print>` 用 `-std=c++23`，其余用 `-std=c++17`。
> 建议完成顺序：1 → 2 → 3 → 4 → 5。

## 练习 1：用 unique_ptr 管理对象（★）

**目标**：用 `unique_ptr` 管理一个动态对象，验证离开作用域自动释放，并尝试转移所有权。

**要求**：

- 定义带构造/析构日志的 `Resource` 类（构造打印 `Resource(...) 构造`，析构打印 `Resource(...) 析构`）
- 用 `std::make_unique` 在作用域内创建，验证作用域结束自动析构——全程无手写 `delete`
- 用 `std::move` 转移所有权，验证转移后原 `unique_ptr` 为 null
- 用 `static` 声明对比：裸 `new`/`delete` 写法需要手动释放，`unique_ptr` 把释放绑定到生命周期
- 禁止裸 `new`/`delete`（R.11）

**验收**：运行输出可见对象在离开作用域时自动析构；move 后原指针 `operator bool` 为 false；`g++ -Wall -Wextra -std=c++17` 编译零警告。

## 练习 2：用 optional 表示查找结果（★★）

**目标**：实现查找函数用 `std::optional` 表达"可能不存在"，并比较与返回哨兵值（`-1`/空串）两种写法的差异。

**要求**：

- 写 `std::optional<int> find_score(const std::map<std::string, int>&, const std::string& name)`：存在返回成绩，不存在返回 `std::nullopt`
- 主程序分别验证：`has_value()`、解引用 `*r`、`value_or(default)`
- 调用一个不存在的 key，确认 `has_value()` 为 false
- 用注释说明：为什么返回 `-1`（成绩可能真是 -1？不，成绩非负）或空串比 `optional` 差——哨兵值把"值"与"不存在"混在一个类型里

**验收**：存在与不存在两种情况行为正确；`value_or` 返回默认值；编译零警告。

## 练习 3：用 std::format 重写字符串拼接（★★）

**目标**：把一段 `std::cout << ... << ...` 的字符串拼接重写为 `std::format`，输出一致且类型安全。

**要求**：

- 定义 `std::vector<std::tuple<int, std::string, double>>` 存放 `(id, name, score)`
- 先用 iostream 拼接打印，再用 `std::format`/`std::println` 重写，两种写法输出同样的数据（精度由 `{:.2f}` 说明符控制）
- 演示格式化说明符：`{:.2f}` 两位小数、`{:<8}` 左对齐
- 用注释（不写进可运行代码）说明：`std::format("{} {}", 42)` 与 `std::format("{:d}", 3.14)` 会在**编译期**报错
- 标准 `-std=c++23`（`<print>` 不可用时把 `std::println` 换成 `std::cout << std::format(...)` 即可降级为 C++20）

**验收**：两种写法输出一致；`std::format` 版本编译零警告；能说清编译期校验相对 printf 的改进。

## 练习 4：用 lambda 定义排序规则（★★）

**目标**：用 lambda 定义 `std::sort` 的排序规则，并 capture 一个外部阈值做过滤。

**要求**：

- 定义 `struct Task { int priority; std::string name; };`
- 用 lambda 按 priority **降序**排序
- 按值捕获一个阈值 `min_priority`，过滤出满足条件的任务
- 再写一个按引用捕获的 lambda（修改外部计数变量），对比两种捕获的语义
- 不能为 Task 手写比较运算符——排序规则用 lambda 就地定义

**验收**：排序结果降序正确；阈值过滤正确；按引用捕获能修改外部变量；编译零警告。

## 练习 5：用 variant 表示多种状态（★★★）

**目标**：用 `std::variant` 表示消息/设备多种状态，用 `std::visit` 统一处理当前活跃分支。

**要求**：

- 定义三种消息：`Text{std::string content}`、`Number{double value}`、`Error{int code; std::string reason;}`
- 用 `using Message = std::variant<Text, Number, Error>;` 组装
- 写 `describe(const Message&)` 用 `std::holds_alternative` + `std::get` 安全访问，返回字符串
- 用 `std::visit` + `if constexpr` 统一处理当前活跃分支（参考 `std::decay_t<decltype(s)>` + `std::is_same_v`）
- 验证 `index()` 与活跃分支对应
- 附加：写一个 `throw_bad_variant_access` 注释说明 `std::get<T>` 在分支不符时抛 `std::bad_variant_access`

**验收**：三种消息 `describe` 输出正确；`std::visit` 输出正确；`index()` 正确；编译零警告。

> **提示**：练习 1~5 与主文档第 6 章示例 1/3/5/2/4 主题一一对应——先独立完成，再对照 `examples/` 检查。`sol-*` 为参考实现，均复用自对应示例（头注释已注明）。
