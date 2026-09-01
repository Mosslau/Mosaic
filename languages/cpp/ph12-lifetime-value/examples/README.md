# examples —— 对象生命周期、值类别与所有权深入阶段完整示例

验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra`。ex01~ex04、ex06 在两种编译器下均编译**零警告**并运行验证（已验证）；ex05 为故意出错示例，默认构建零警告，危险路径（`-DPH12_DANGLING`）编译产生 3 条预期告警、ASan 可在运行期抓出 UB——告警与 ASan 输出均为实测记录。**全部产物输出到 /tmp，验证后清理，仓库不落二进制**（本目录只含源码）。

| 文件 | 说明 | 构建/运行 |
|------|------|-----------|
| `ex01-value-categories.cpp` | 值类别判别：`decltype((expr))` 编译期分类 lvalue/prvalue/xvalue | `./ex01` 打印每个表达式类别 |
| `ex02-temp-lifetime.cpp` | 临时对象生命周期：完整表达式边界、`const&`/`&&` 延长、函数参数边界、子对象绑定 | `./ex02` 打印 ctor/dtor 顺序 |
| `ex03-rvo-nrvo.cpp` | RVO/NRVO 实测：保证省略 vs NRVO vs `return std::move` 反模式，多 -O 级别对比 | `./ex03-O0` / `./ex03-O2` / `./ex03-anti` |
| `ex04-order.cpp` | 构造顺序与销毁顺序：局部、派生类（基类→成员→构造体）、函数局部静态、命名空间静态 | `./ex04` 打印构造/析构顺序 |
| `ex05-dangling.cpp` | 故意出错：返回局部对象/临时对象的引用与视图；编译告警 + ASan 抓 use-after-return | 见下方命令（默认零警告） |
| `ex06-ownership.cpp` | 所有权转移与借用式接口：unique_ptr 转移、const&/string_view/span 借用、值语义拷贝 | `./ex06` 打印所有权流转 |

## 示例 1：值类别判别（ex01-value-categories.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex01-value-categories.cpp -o /tmp/ex01
/tmp/ex01
```

本机实测输出（已验证，Apple clang 21 与 Homebrew clang 21 输出一致）：

```text
== 表达式值类别实测（decltype((expr)) 判别）==

x                                  -> lvalue
42                                 -> prvalue
s                                  -> lvalue
s + "!"                            -> prvalue
std::move(s)                       -> xvalue
lref                               -> lvalue
rref                               -> lvalue
"literal"                          -> lvalue
static_cast<std::string&&>(s)      -> xvalue
std::string{"temp"}                -> prvalue
&x                                 -> prvalue
```

要点：**值类别是表达式的属性，不是对象的属性**——同一个对象 `s` 出现在不同表达式里类别不同（`s` 是 lvalue、`std::move(s)` 是 xvalue、`s + "!"` 是 prvalue）；两个"坑"：有名字的右值引用 `rref` 是 **lvalue**（它本身可被取地址、可再被赋值），字符串字面量 `"literal"` 是 **lvalue**（`const char[N]` 数组，不是 prvalue）。

## 示例 2：临时对象生命周期（ex02-temp-lifetime.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex02-temp-lifetime.cpp -o /tmp/ex02
/tmp/ex02
```

本机实测输出（已验证，两种编译器输出一致）：

```text
[1] 完整表达式边界：未绑定的临时对象在语句结束时析构
  before
  ctor expr-temp
  dtor expr-temp
  after
[2] const& 绑定：生命周期延长到引用离开作用域
  ctor extended
  using r: extended
  dtor extended
[2] scope end
[3] && 绑定：右值引用同样延长
  ctor rref-ext
  using r: rref-ext
  dtor rref-ext
[3] scope end
[4] 函数参数：临时对象活到调用语句结束（不跨语句延长）
  ctor arg-temp
  observe arg-temp
  dtor arg-temp
[4] after call
[5] 绑定到临时对象的成员：延长的是整个临时对象
  ctor sub
  using member: sub
  dtor sub
[5] scope end
[6] 边界：延长只作用于绑定的引用本身（悬空场景见 ex05）
  done
```

要点：**临时对象默认在"完整表达式"结束时析构**（[1] `ctor` 与 `dtor` 夹住语句本身、不跨语句）；**绑定到 `const T&` 或 `T&&` 时延长到引用离开作用域**（[2][3] `dtor` 出现在 `scope end` 之后）；**函数参数不跨语句延长**（[4] 参数临时对象在调用语句结束即析构——传临时对象给 `const&` 参数在调用期间是安全的）；绑定到临时对象的成员（子对象）时，延长的是**整个完整临时对象**（[5]）。

## 示例 3：RVO/NRVO 实测（ex03-rvo-nrvo.cpp）

```bash
c++ -std=c++20 -Wall -Wextra -O0 ex03-rvo-nrvo.cpp -o /tmp/ex03-O0
c++ -std=c++20 -Wall -Wextra -O2 ex03-rvo-nrvo.cpp -o /tmp/ex03-O2
/tmp/ex03-O0
/tmp/ex03-O2
# 反模式用例（预期 1 条告警 -Wpessimizing-move）：
c++ -std=c++20 -Wall -Wextra -DPH12_ANTIPATTERN ex03-rvo-nrvo.cpp -o /tmp/ex03-anti
/tmp/ex03-anti
```

本机实测输出（已验证，两种编译器一致；`-O0`/`-O2`/`-O3` 结果相同）：

```text
# 默认构建（-O0/-O2/-O3，零警告）：
[RVO prvalue]
  ctor
  got id=0
  dtor
[NRVO named]
  ctor
  got id=0
  dtor
[return std::move 反模式用例未启用]

# -DPH12_ANTIPATTERN 构建（1 条预期告警：moving a local object in a return statement prevents copy elision）：
[return std::move]
  ctor
  MOVE
  dtor
  got id=0
  dtor
```

`-fno-elide-constructors` 对照（C++20 下保证省略不受影响，NRVO 被关闭；C++14 下无保证省略）：

```text
# c++ -std=c++20 -fno-elide-constructors（默认构建）：
[RVO prvalue]   ctor / got id=0 / dtor                      ← 保证省略：-fno-elide 关不掉
[NRVO named]    ctor / MOVE / dtor / got id=0 / dtor        ← NRVO 被关闭 → 出现一次移动

# c++ -std=c++14 -fno-elide-constructors（默认构建，演示 C++17 之前的行为）：
[RVO prvalue]   ctor / MOVE / dtor / MOVE / dtor / got id=0 / dtor   ← 两次移动
[NRVO named]    ctor / MOVE / dtor / MOVE / dtor / got id=0 / dtor   ← 两次移动
```

要点：**C++17 起纯右值返回的拷贝省略是保证的**（`RVO prvalue` 在 `-O0` 到 `-O3` 全程零拷贝零移动，`-fno-elide-constructors` 也关不掉）；**NRVO 是允许不保证的优化**——本机 clang 21 在 `-O0` 也做 NRVO（`NRVO named` 零移动），但标准不保证；**`return std::move(p)` 是反模式**——把命名对象变 xvalue 后编译器无法 NRVO，必然一次移动，clang 直接告警 `-Wpessimizing-move`；C++14 无保证省略，`-fno-elide-constructors` 下 RVO/NRVO 都变成两次移动——这正是 C++17 把保证省略写进标准的原因。

## 示例 4：构造顺序与销毁顺序（ex04-order.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex04-order.cpp -o /tmp/ex04
/tmp/ex04
```

本机实测输出（已验证，两种编译器输出一致）：

```text
  StaticB ctor
  StaticA ctor
[1] 作用域局部对象：按声明序构造、逆序析构
  MemberA ctor
  MemberB ctor
  scope body
  MemberB dtor
  MemberA dtor
[1] scope end
[2] 派生类：基类 → 成员（声明序）→ 构造体；析构逆序
  Base ctor
  MemberB ctor
  MemberA ctor
  Derived body
  using d
  Derived body end
  MemberA dtor
  MemberB dtor
  Base dtor
[2] scope end
[3] 函数局部静态：首次调用构造，退出时析构（构造完成逆序）
  StaticA ctor
  StaticB ctor
  first call: statics ready
  second call: statics ready
[4] 命名空间作用域静态：main 之前已构造
  main body end
  StaticB dtor
  StaticA dtor
  StaticA dtor
  StaticB dtor
```

要点：作用域局部对象按声明序构造、**逆序析构**（[1]）；派生类构造顺序固定为**基类 → 成员（按声明顺序，与初始化列表书写顺序无关）→ 构造函数体**，析构严格逆序（[2]，实测 `MemberB` 虽在初始化列表先写，仍按声明序 `b_` 先构造）；函数局部静态**首次调用时才构造**、之后复用（[3] 两次调用只构造一次）；命名空间作用域静态在 `main` 之前构造；程序退出时**全部静态对象按"构造完成"的逆序统一析构**（[4] 结尾：函数局部静态先析构、命名空间静态后析构——因为函数局部静态构造完成得更晚）。

## 示例 5：悬空引用（ex05-dangling.cpp，故意出错）

```bash
# 默认构建：零警告，只打印复现指引
c++ -std=c++20 -Wall -Wextra ex05-dangling.cpp -o /tmp/ex05
/tmp/ex05

# 危险路径：3 条预期告警 + ASan 运行期抓取（macOS 必须显式开启 use-after-return 检测）
c++ -std=c++20 -Wall -Wextra -DPH12_DANGLING -fsanitize=address -g ex05-dangling.cpp -o /tmp/ex05-danger
ASAN_OPTIONS=detect_stack_use_after_return=1 /tmp/ex05-danger
```

本机实测（已验证，Apple clang 21.0.0）：

```text
# 危险路径编译告警（3 条，编译退出码 0）：
ex05-dangling.cpp:25:12: warning: reference to stack memory associated with local variable 's' returned [-Wreturn-stack-address]
ex05-dangling.cpp:30:12: warning: returning reference to local temporary object [-Wreturn-stack-address]
ex05-dangling.cpp:36:12: warning: address of stack memory associated with local variable 's' returned [-Wreturn-stack-address]

# ASan 运行（ASAN_OPTIONS=detect_stack_use_after_return=1）：
ERROR: AddressSanitizer: stack-use-after-return on address 0x...
READ of size 1 at 0x... thread T0
SUMMARY: AddressSanitizer: stack-use-after-return ... in std::__1::basic_string<...>::__is_long() const
```

要点：**返回局部对象/临时对象的引用是"能编译、能运行、结果随机"的 UB**——`-Wall` 下的 `-Wreturn-stack-address` 是第一道防线（本机实测 3 种写法都会告警）；ASan 是第二道防线，但 **macOS 的 ASan 默认不检测 use-after-return**（实测不设 `ASAN_OPTIONS` 时程序"看似正常"直接通过，设了 `detect_stack_use_after_return=1` 才在读取处报错）——"看起来正常"正是悬空引用的危险所在。安全写法：按值返回（值语义）、借用式接口（ex06）、`const&` 延长的合法边界（ex02）。

## 示例 6：所有权转移与借用式接口（ex06-ownership.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex06-ownership.cpp -o /tmp/ex06
/tmp/ex06
```

本机实测输出（已验证，两种编译器输出一致）：

```text
[1] 按值返回 unique_ptr：所有权从工厂转移给调用方
  Blob{motor}
[2] string_view 借用：不拷贝、不拥有
  view: motor
[3] sink 转移：所有权交给函数，之后 b 为空
  Blob{motor}
  b == nullptr: yes
[4] span 借用容器内存
  span sum = 10
[5] 值语义：拷贝是深拷贝，互不影响
  a=original  c=original!
```

要点：**所有权应通过类型体现**——`std::unique_ptr<Blob>` 表达独占所有权（R.20，转移靠移动语义），裸指针/`const&`/`string_view`/`span` 表达"借用"（R.3：裸指针不拥有、不负责释放）；`make_blob` 按值返回 unique_ptr 是零拷贝的所有权转移（C++17 保证省略 + 移动）；`sink(std::move(b))` 转移后 `b` 变为"合法但空"（`b == nullptr`，析构安全、无双重释放）；**值语义让代码更简单**（[5]：拷贝即深拷贝，`c` 与 `a` 互不影响——传值、返回、存容器都无需手动管理）。

## 双编译器验证记录

| 示例 | Apple clang 21.0.0 | Homebrew clang 21.1.8 | 备注 |
|------|--------------------|-----------------------|------|
| ex01 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | decltype 判别 11 个表达式 |
| ex02 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 6 个生命周期场景 |
| ex03 | ✅ 零警告（-O0/-O2/-O3）；反模式构建 1 条预期告警 | ✅ 同左 | C++20/C++14 + `-fno-elide-constructors` 矩阵 |
| ex04 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 4 类对象的构造/析构顺序 |
| ex05 | ✅ 默认零警告；危险路径 3 条预期告警 + ASan 抓取 | ✅ 默认零警告 | 故意出错，ASan 需 `detect_stack_use_after_return=1` |
| ex06 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 所有权转移/借用/值语义 |

验证用构建产物全部位于 /tmp，仓库无 .o/可执行文件残留。
