# examples —— const 正确性与接口设计阶段完整示例

验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra`。六个示例在两种编译器下**零警告、输出逐字节一致**。ex04 的 `-DPH14_CONST_UB` 为故意出错路径（修改真正 const 对象，UB），必须单独编译运行，实测 O0 下 Bus error: 10（SIGBUS，退出码 138）。**全部产物输出到 /tmp，验证后清理，仓库不落二进制**（本目录只含源码）。

| 文件 | 说明 | 构建/运行 |
|------|------|-----------|
| `ex01-top-level-low-level-const.cpp` | 顶层 const vs 底层 const：`const int` / `const int*` / `int* const`，拷贝与转换规则，`static_assert` 编译期验证 | `./ex01` 打印六组类型规则 |
| `ex02-const-member-functions.cpp` | const 成员函数（Con.2）：const 对象只能调 const 成员、const/非 const 重载、返回 `const&`、`std::as_const` | `./ex02` 打印 const/非 const 行为对照 |
| `ex03-const-reference-params.cpp` | const 引用参数（F.16）：按值 vs `const&` 的拷贝计数、`const&` 绑定临时对象 | `./ex03` 打印拷贝/零拷贝对照 |
| `ex04-mutable-and-const-cast.cpp` | mutable 缓存正例 + const_cast 气味反例/正例对照；`-DPH14_CONST_UB` 危险路径（UB） | `./ex04`；危险路径命令见下方 |
| `ex05-logical-vs-physical-const.cpp` | 逻辑 const vs 物理 const：mutable 懒缓存、mutable 互斥锁、const 指针"路径只读" | `./ex05` 打印四组对照 |
| `ex06-readonly-view.cpp` | 只读视图设计：`std::string_view` / `std::span<const T>` 观察不拥有、零拷贝 | `./ex06` 打印视图行为 |

## 示例 1：顶层 const 与底层 const（ex01-top-level-low-level-const.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex01-top-level-low-level-const.cpp -o /tmp/ph14-ex01
/tmp/ph14-ex01
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 顶层 const：对象本身不可变
  const int x = 42;（x=42，本身只读）
[2] 底层 const：指向的对象不可通过该指针修改
  const int* p 指向非 const 的 value=7（*p 只读）
  value 被别处改为 8，通过 p 读到 8（只读路径看到变化）
[3] 指针自身的顶层 const：int* const
  int* const q：*q=10（指针只读、指向的对象可写）
[4] 拷贝时顶层 const 脱落、底层 const 保留
  auto copied = cx 推导为 int（顶层 const 脱落）
  auto cp2 = cp 推导为 const int*（底层 const 保留）
[5] 转换方向：非 const → const 安全（收窄权限）；反向禁止
  int* → const int* 允许（编译期特征 1）；const int* → int* 禁止（特征 0）
[6] 函数参数：顶层 const 不影响函数类型（重载决议忽略它）
  void f(const int) 与 void f(int) 是同一个函数——不能靠它重载
```

要点：**顶层 const 管"对象本身"，底层 const 管"指向的对象"**——[2] 底层 const 只约束当前路径（对象被别处改，只读路径看得到）；[4] 拷贝/`auto` 推导时顶层 const 脱落、底层 const 保留（`decltype` 用 `static_assert` 编译期验证）；[5] 非 const → const 是权限收窄（隐式允许），反向必须 `const_cast`（接口气味）；[6] 顶层 const 不进入函数类型，不能靠它重载。

## 示例 2：const 成员函数（ex02-const-member-functions.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex02-const-member-functions.cpp -o /tmp/ph14-ex02
/tmp/ph14-ex02
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 非 const 对象：可变与非可变成员都能调
  sensor-1 reading=38.0
  s.access() -> non-const access()
[2] const 对象：只能调 const 成员（cs.calibrate 编译期拒绝）
  sensor-const reading=22.0
  cs.access() -> const access()
[3] 返回引用：const 版本返回 const&（可变句柄被没收）
  cs.id() 类型 = const std::string&；s.id() 类型 = std::string&
[4] 可变句柄的后果：非 const 对象可改名，const 对象不可
  s.id() 被改为 renamed（非 const 句柄）；cs.id() 只能读
[5] std::as_const（C++17）：把可变句柄临时当 const 用
  std::as_const(s).access() -> const access()
```

要点：**不修改对象状态的成员函数应标 const（Con.2）**——[1][2] const 对象只能调 const 成员，非 const 对象优先选非 const 重载；[3][4] 返回引用时 const 版本返回 `const&`（`decltype` 断言类型），可变句柄被没收；[5] `std::as_const` 临时强制 const 路径（读多写少的场景用它显式表达"这里只读"）。

## 示例 3：const 引用参数（ex03-const-reference-params.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex03-const-reference-params.cpp -o /tmp/ph14-ex03
/tmp/ph14-ex03
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 反例：按值传大对象（每次调用一次拷贝）
  Payload ctor（data.size=4）
  Payload copy-ctor（拷贝了 4 个 int）
  sum_by_value = 4
[2] 正例：const& 传大对象（零拷贝）
  sum_by_const_ref = 4
[3] const& 绑定临时对象：表达式直接用，无需先造具名变量
  r = motor-v1（const& 可绑定右值临时对象）
[4] const& 的只读承诺：函数体内无法修改实参
  sum_by_const_ref 内部若写 p.data[0] = 0 会编译失败——接口即契约
```

要点：**输入大对象优先用 const 引用（F.16）**——[1] 按值传参每次调用复制一次（`copy-ctor` 实测），[2] `const&` 零拷贝；[3] `const&` 可绑定右值临时对象（生命周期延长详见 ph12）；[4] `const&` 的只读承诺由编译器执行，函数体无法修改实参——接口即契约。

## 示例 4：mutable 与 const_cast（ex04-mutable-and-const-cast.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04
/tmp/ph14-ex04
# 危险路径（故意出错，ES.50 反例——修改真正 const 对象是 UB，勿裸跑）：
c++ -std=c++20 -Wall -Wextra -DPH14_CONST_UB ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04-ub
/tmp/ph14-ex04-ub
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] mutable 缓存（正例）：const 成员函数中缓存计算结果
  is_prime(17) 首次计算（写 mutable 缓存位）
  checker.is_prime(17) = true
  is_prime(17) 命中缓存（mutable 缓存位已就绪）
  checker.is_prime(17) = true（再次查询命中缓存）
  is_prime(18) 首次计算（写 mutable 缓存位）
  checker.is_prime(18) = false（新输入，重新计算）
[2] const_cast 气味（反例）：const& 参数被偷偷改写
  sneaky(x) 之后 x = 999（调用方以为只读，实际被改——接口承诺被破坏）
[3] 正例对照：用非 const 引用参数表达「要修改」
  update(y) 之后 y = 300（接口明说可写，无需任何 cast）
[4] 危险路径提醒：修改真正 const 对象是 UB（ES.50）
  用 -DPH14_CONST_UB 编译单独运行，实测结果见文件头注释/README
```

危险路径实测（`-DPH14_CONST_UB`，两种编译器一致）：O0 下写入只读段 → `Bus error: 10`（SIGBUS，进程退出码 138）；O2 下编译器把 `k` 常量折叠，写入不生效、打印 `k = 42`。两种表现都是**未定义行为**（ES.50 反例）——`const_cast` 修改真正 const 对象时，编译器有权假设 const 不变量。

要点：**mutable 是"物理可变、逻辑不变"的合法出口（[1] 缓存）**；**const_cast 通常是设计气味（[2] 破坏 const 承诺）**，需要修改就明说（[3] 非 const 引用，零 cast）——正反例对照：同一"要改"的意图，气味版靠 cast 撒谎，诚实版靠签名表达。

## 示例 5：逻辑 const 与物理 const（ex05-logical-vs-physical-const.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex05-logical-vs-physical-const.cpp -o /tmp/ph14-ex05
/tmp/ph14-ex05
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 物理 const：const 对象所有位冻结（Point p 的 x/y 不可写）
  p = (1.0, 2.0)（只读对象：p.x = 3 是编译错误）
[2] 逻辑 const：mutable 缓存 —— 第一次算、第二次命中，语义不变
  size() 首次计算（物理位被写：computed_ 置位）
  ls.size() = 4
  size() 命中缓存（物理位未变，逻辑结果稳定）
  ls.size() = 4
[3] 逻辑 const：mutable 互斥锁 —— 并发读的 const 成员函数也要同步
  st.average() = 15.0（const 成员函数内 scoped_lock 保护共享位）
[4] 对照：const 指针只约束「这条路径」，不冻结对象本身
  观察者（const int*）读到 7
  别处修改后，观察者（const int*）再读 50（路径只读，对象非冻结）
```

要点：**物理 const 是"位不可变"（[1]），逻辑 const 是"语义不变"（[2][3]）**——懒计算缓存（mutable）与互斥锁（mutable）都只改物理位、不改逻辑语义，是 const 成员函数里允许写 mutable 成员的正当理由（CP.20 的 RAII 锁）；[4] 底层 const 只是"这条路径只读"，不冻结对象本身。

## 示例 6：只读视图设计（ex06-readonly-view.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex06-readonly-view.cpp -o /tmp/ph14-ex06
/tmp/ph14-ex06
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] string_view 零拷贝：不同字符串形态统一进只读接口
  count_vowels(std::string) = 2
  count_vowels(C 字面量)    = 1
  count_vowels(string_view) = 5
  （string_view 内部只是 {指针, 长度}，三种形态都零拷贝）
[2] string_view 是「观察」：底层数据变，视图看到变（不拥有数据）
  view = Xbc（text 被改后视图跟着变）
[3] span 覆盖 vector / C 数组 / 裸指针+长度
  average(vector)     = 2.0
  average(C 数组)     = 5.0
  average(ptr+len)    = 5.0
[4] 接口即承诺：span<const T> 只读，span<T> 可写
  只读接口用 span<const double>；需要修改才暴露 span<double>（见主文档）
```

要点：**`string_view` / `span` 是"观察不拥有"的只读视图**（SL.str.2/SL.con.1）——[1] 一个只读接口零拷贝接受 `string` / C 字面量 / `string_view` 三种形态；[2] 视图不拥有数据，底层变视图跟着变；[3] `span<const double>` 覆盖 vector / C 数组 / 裸指针+长度。

> ⚠️ 视图的生命周期必须短于数据源：`string_view` / `span` 悬挂是 ph12 讲过的借用式接口的延伸，悬挂后解引用属 UB（ph15 未定义行为与内存安全阶段，目录待建）。

## 双编译器验证记录

| 示例 | Apple clang 21.0.0 | Homebrew clang 21.1.8 | 备注 |
|------|--------------------|-----------------------|------|
| ex01 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 六组类型规则 + static_assert |
| ex02 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | const/非 const 重载对照 |
| ex03 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 拷贝计数 vs 零拷贝 |
| ex04 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 危险路径 O0 SIGBUS（退出码 138）、O2 常量折叠打印 42 |
| ex05 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 懒缓存命中 + 互斥锁 |
| ex06 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 视图零拷贝 + span 覆盖三种来源 |

验证用构建产物全部位于 /tmp，仓库无 .o/可执行文件残留。
