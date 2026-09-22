# exercises —— 对象生命周期、值类别与所有权深入阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），编译命令 `c++ -std=c++20 -Wall -Wextra`。练习 1/3/4 与 roadmap ph12「练习」小节的三个承诺一一对应，练习 2/5 覆盖「学习内容」中的值类别与所有权转移/借用式接口。

## 练习 1：预测并验证临时对象生命周期（★）

- **目标**：写出三种场景的观察程序（未绑定临时对象 / `const&` 绑定 / 作为函数参数传入 `const&`），**先预测 ctor/dtor 打印顺序，再运行验证**，并解释每条规则
- **要求**：
  - 用一个打印 `ctor`/`dtor` 的类型（含拷贝/移动构造打印）观察三种场景
  - 三种场景各写一段独立代码，预测打印顺序并写明依据
  - 运行程序，对照你的预测，找出预测错误的地方并解释
- **验收**：能说出三个结论——未绑定临时对象何时析构、`const&` 绑定后何时析构、函数参数临时对象活到什么时候；参考实现实测输出见 `sol-01-lifetime-predict.cpp` 文件头
- **提示**：关键规则是"完整表达式"与"延长"——未绑定临时对象在完整表达式（语句）结束时析构；绑定 `const T&`/`T&&` 时延长到引用离开作用域；作为参数传入时活到调用语句结束。想混淆自己，可以在场景 B 里把引用传进另一个函数再"逃逸"出来——那是 ex05 的悬空场景

## 练习 2：值类别判定（★★）

- **目标**：用 `decltype((expr))` 判别技巧写一个分类器，对表达式清单逐项报告 lvalue / prvalue / xvalue；先凭直觉预测，再运行核对
- **要求**：
  - 至少包含 12 个表达式，覆盖：变量名、字面量、`++x` 与 `x++`、条件表达式（两侧 lvalue）、下标、取地址、返回引用的函数调用、直接构造临时、`static_cast<T&&>`、`std::move`、有名字的右值引用、字符串字面量、比较运算
  - 对每个表达式先写下你的预测，再运行核对
  - 必须解释两个"坑"：有名字的右值引用是 lvalue；字符串字面量是 lvalue
- **验收**：分类器输出与文档 3.1 节表格一致；能解释每个表达式的类别为什么如此（尤其两个"坑"）
- **提示**：`decltype((expr))` 是未求值上下文——`lvalue → T&`、`xvalue → T&&`、`prvalue → T`；用 `std::is_lvalue_reference_v` / `std::is_rvalue_reference_v` 判断。参考实现见 `sol-02-value-category-quiz.cpp`

## 练习 3：对比传值 / 引用 / 移动的拷贝与移动次数（★★）

- **目标**：统计"按值传参"、"`const&` 传参"、"右值引用传参"在传入左值/右值时各发生几次拷贝、几次移动，形成对比表，并解释何时按值传参反而更优
- **要求**：
  - 用一个带静态计数器的类型（拷贝构造 `++copies`、移动构造 `++moves`）统计
  - 覆盖 6 个调用：`by_value` 传左值 / 传右值、`by_const_ref` 传左值 / 传右值（临时）、`by_rvalue_ref` 传右值、`Counted b = make()`（按值返回初始化）
  - 输出一张对比表（参考实现格式：`by_value(lvalue)             copy=1 move=0`）
  - 写一段话回答：什么场景下 `by_value` 比 `const&` + 拷贝更划算？什么场景下 `const&` 明显更优？
- **验收**：6 行统计输出与参考实现一致（`sol-03-param-passing.cpp` 文件头有实测值）；能解释"传值 + 右值 = 1 次移动"与"`const&` = 0 拷贝 0 移动"分别适用于什么调用方式
- **提示**：区分"调用方让出对象"（sink 语义，`std::move` 传入，1 次移动）与"调用方还要保留原对象"（必须拷贝）；`Counted b = make()` 是 C++17 保证省略，0 拷贝 0 移动

## 练习 4：改造返回悬空引用的代码（★★★）

- **目标**：下列工厂函数返回 `const&`，实为悬空引用（返回绑定到临时对象的引用，临时对象在 return 语句结束时销毁）。改造为不悬空的接口并说明理由

  ```cpp
  // 原始（有 bug，勿这样写）：
  const std::string& config_path(const std::string& base) {
      return base + "/config.json";
  }
  ```

- **要求**：
  - 先编译原始版本，记录编译器告警（`-Wall -Wextra` 下应有 `-Wreturn-stack-address`）
  - 改造为不悬空的接口；改造后编译零警告、运行输出 `path = /etc/app/config.json`
  - 在注释/说明里回答：为什么"按值返回"是首选？为什么不要改成"返回 `std::string_view` 的引用"来绕？
- **验收**：能复述原始版本的告警文本；改造版零警告且输出正确；能解释 `string_view` 不拥有数据、数据源销毁后视图照样悬空
- **提示**：按值返回 prvalue 由 C++17 保证省略（见 `examples/ex03`），零拷贝零移动；若调用方只需要读，再从返回值上取 `string_view`，并保证视图寿命短于数据源（参考实现见 `sol-04-fix-dangling.cpp`）

## 练习 5：所有权接口重构（★★★ 综合题）

- **目标**：现有 `Session` 用裸指针 `Profile*` 持有配置并手写 `new`/`delete`，所有权不清且拷贝赋值有双重释放风险。重构为"所有权通过类型体现"的现代写法

  ```cpp
  // 原始（有 bug，勿这样写）：
  class Session {
  public:
      Session(const char* name) : profile_(new Profile(name)) {}
      ~Session() { delete profile_; }
      Session(const Session& o) : profile_(new Profile(*o.profile_)) {}  // 深拷贝
      // 没有拷贝赋值！Session a; Session b = a; b = a; → 指针被复制 → double free
      const Profile& profile() const { return *profile_; }
  private:
      Profile* profile_;
  };
  ```

- **要求**：
  - `Profile` 用 `std::unique_ptr` 持有（`std::make_unique`，R.11 无裸 new/delete）
  - 借用接口：`profile()` 返回 `const Profile&`、`name()` 返回 `std::string_view`，不拷贝不转移
  - 演示所有权转移：`sessions.push_back(std::move(s1))` 后从容器访问
  - 用 `-fsanitize=address` 编译运行验证无越界/use-after-free/double-free（泄漏检测需 Linux，macOS 的 ASan 不支持 LSan，如实标注）
- **验收**：编译零警告；运行输出三行（`name = alice` / `moved name = alice` / `size = 1`）；ASan 运行无地址错误报告；能说明为什么 `Session` 不可拷贝是"特性"不是"缺陷"
- **提示**：`unique_ptr` 是 move-only——拷贝被隐式删除，`Session s2 = s1;` 会编译报错（可注释掉验证）；转移所有权就是移动，零拷贝；这是 roadmap 推荐项目②「所有权关系重构练习」的最小形态（参考实现见 `sol-05-ownership-refactor.cpp`）

**提示**：参考实现仅作对照，先独立完成再复盘。sol-* 文件头都带实测输出与验证状态；练习 4 的原始版告警文本与练习 5 的 ASan 结论已在 sol 文件头如实标注（本机 macOS 不支持 LeakSanitizer）。进阶玩法（可选）：把练习 2 的分类器扩展成"覆盖 glvalue/rvalue 复合类别"版本；给练习 5 加一个 `std::shared_ptr` 变体对比"共享所有权"的适用场景（承接 ph06 智能指针）。
