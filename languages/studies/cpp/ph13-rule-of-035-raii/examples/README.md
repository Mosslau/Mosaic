# examples —— Rule of 0/3/5 与 RAII 进阶阶段完整示例

验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra`。ex01、ex03、ex05、ex06 在两种编译器下输出逐字节一致；ex02、ex04 仅指针地址不同（`data=0x…` / `delete 0x…` 每次运行变化，属正常）。ex02 的 `-DPH13_SHALLOW` 为故意出错路径，必须用 `-fsanitize=address` 编译（实测 ASan 报 double-free，进程 SIGABRT 退出码 134）。**全部产物输出到 /tmp，验证后清理，仓库不落二进制**（本目录只含源码）。

| 文件 | 说明 | 构建/运行 |
|------|------|-----------|
| `ex01-rule-of-zero.cpp` | Rule of Zero（C.20）：成员全值类型，五个特殊成员全交编译器；`static_assert` 编译期验证 | `./ex01` 打印逐成员拷贝/移动/dtor |
| `ex02-rule-of-five.cpp` | Rule of Five（C.21）：手写析构的 `HeapBuffer` 五函数全定义；`-DPH13_SHALLOW` 对照"只写析构"的 double-free | `./ex02`；危险路径见下方命令 |
| `ex03-raii-file.cpp` | RAII 资源封装（R.1）：`FILE*` 句柄类，异常路径析构兜底，句柄移动进容器 | `./ex03` 打印 open/close 时序 |
| `ex04-custom-deleter.cpp` | 自定义 deleter：函数指针 / 仿函数 / lambda / 有状态 deleter 的 `sizeof` 差异（EBO） | `./ex04` 打印各形态 sizeof |
| `ex05-unique-ptr-c-resource.cpp` | `unique_ptr` 管理 C 资源：`FILE*` / POSIX fd / malloc，异常路径 close 兜底 | `./ex05` 打印 fopen/close/read |
| `ex06-exception-safety.cpp` | 异常安全资源释放：构造中途失败（裸指针 vs unique_ptr）、强保证 copy-and-swap、基本保证对照 | `./ex06` 打印存活计数与捕获 |

## 示例 1：Rule of Zero（ex01-rule-of-zero.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex01-rule-of-zero.cpp -o /tmp/ph13-ex01
/tmp/ph13-ex01
```

本机实测输出（已验证，两种编译器一致；Tracer 成员观察逐成员行为）：

```text
[1] 按值返回（ph12 的保证省略，此处 0 拷贝 0 移动）
  Tracer ctor motor
[2] 拷贝构造：逐成员深拷贝（tracer 被 copy，data 内容独立）
  Tracer copy-ctor motor
  a.id=motor a.data.size=3 | b.id=motor-copy b.data.size=4
[3] 移动构造：逐成员移动（tracer 被 move，源置空）
  Tracer move-ctor motor
  moved-from b.id 长度=0（合法但未指定，实测为空）
  c.id=motor-copy c.data.size=4
[4] 作用域结束：c/a 逆序析构，成员逐个体面释放
  Tracer dtor motor
  Tracer dtor 
  Tracer dtor motor
```

要点：**Rule of Zero = 编译器生成的五个特殊成员就是正确答案**（C.20）——`Widget` 的成员全是值类型（`string`/`Tracer`/`vector`），编译器生成的拷贝是**逐成员深拷贝**、移动是**逐成员移动**、析构是**逐成员析构**，没有任何裸资源需要手动管理；[1] 演示 ph12 的保证省略（0 拷贝 0 移动），[3] 移动后源对象"合法但未指定"（实测 `b.id` 为空）、析构安全。

## 示例 2：Rule of Five（ex02-rule-of-five.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex02-rule-of-five.cpp -o /tmp/ph13-ex02
/tmp/ph13-ex02
# 危险路径（故意出错，必须 ASan 编译，否则 double-free 是未定义行为）：
c++ -std=c++20 -Wall -Wextra -DPH13_SHALLOW -fsanitize=address -g \
    ex02-rule-of-five.cpp -o /tmp/ph13-ex02-shallow
/tmp/ph13-ex02-shallow
```

本机实测输出（已验证；`data=0x…` 地址每次运行不同）：

```text
[1] 构造 + 拷贝构造（深拷贝，内存地址不同）
  ctor    size=4 data=0x100265fd0
  copy    size=4 data=0x100266010 (from 0x100265fd0)
  a.first=7 b.first=7（各自独立内存）
[2] 拷贝赋值（先造新资源再释放旧的）
  ctor    size=2 data=0x100265ef0
  copy=   size=4 data=0x100265f00
[3] 移动构造（窃取指针，源置空）
  move    size=4 data=0x100266010 (源已置空)
  b.size=0 d.size=4 d.first=7
[4] 移动赋值（释放自身 + 窃取）
  ctor    size=1 data=0x100265ef0
  move=   size=4 data=0x100266010 (源已置空)
[5] 作用域结束：e/c/a 逆序析构；被移空的 b/d 析构安全（free(nullptr)）
  dtor    size=4 data=0x100266010
  dtor    size=0 data=0x0
  dtor    size=4 data=0x100265f00
  dtor    size=0 data=0x0
  dtor    size=4 data=0x100265fd0
```

危险路径实测（ASan，Apple clang 21.0.0）：`SUMMARY: AddressSanitizer: double-free … in ShallowBuffer::~ShallowBuffer()`，进程 SIGABRT（退出码 134）——**只写析构不写拷贝，拷贝就是逐成员浅拷贝，两个对象持同一指针，作用域结束 double free**。这正是 Rule of Five（C.21）的存在理由：手写析构管理资源时，拷贝/移动必须一并处理。

## 示例 3：RAII 文件封装（ex03-raii-file.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex03-raii-file.cpp -o /tmp/ph13-ex03
/tmp/ph13-ex03
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 正常路径：作用域结束自动 fclose
  open  /tmp/ph13-ex03-demo.txt (w)
  close（析构自动调用）
[2] 异常路径：异常穿越作用域，析构照常执行（E.6）
  open  /tmp/ph13-ex03-demo.txt (w)
  即将抛异常…
  close（析构自动调用）
  捕获: 模拟处理失败
[3] 所有权转移：句柄移动进容器，旧对象置空
  open  /tmp/ph13-ex03-demo.txt (a)
  move（句柄易主，源置空）
  pool 大小=1
  close（析构自动调用）
[4] 读回验证内容确实落盘
  open  /tmp/ph13-ex03-demo.txt (r)
  文件内容: line-1
appended
  close（析构自动调用）
[5] 临时文件已删除
```

要点：**RAII = 资源生命周期绑定对象生命周期**（R.1）——[2] 异常穿越作用域时 `close` 照常执行且**先于 catch 打印**（栈展开先析构局部对象再进入 catch）；[3] 句柄 move-only，移动进容器后旧对象置空、只有持有者析构时释放，不会 double close。

## 示例 4：自定义 deleter（ex04-custom-deleter.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex04-custom-deleter.cpp -o /tmp/ph13-ex04
/tmp/ph13-ex04
```

本机实测输出（已验证；`sizeof` 为 arm64 平台实测值，`0x…` 地址每次运行不同）：

```text
[1] 默认 deleter：sizeof(unique_ptr<Widget>) = 8（一个裸指针）
[2] 函数指针 deleter：类型编码进 unique_ptr，占两词
  sizeof = 16（指针 + 函数指针）
  raw_delete(函数指针 deleter): delete 0x100b62050
[3] 无状态仿函数 deleter：空基类优化（EBO），仍是一词
  sizeof = 8（实测与裸指针相同）
  WidgetDeleter: delete 0x100b62050
[4] 无捕获 lambda deleter：同样零开销
  sizeof = 8（实测与裸指针相同）
  lambda deleter: delete 0x100b62050
[5] 有状态 deleter：大小随状态增长（指针 + label）
  sizeof = 16（指针 + 状态成员）
  LoggingFree[malloc-64B]: free 0x100b61f10
[6] 对照：shared_ptr 的 deleter 走类型擦除（存进控制块）
  两者同为 shared_ptr<Widget>，sizeof 均为 16
  WidgetDeleter: delete 0x100b61ff0
  raw_delete(函数指针 deleter): delete 0x100b62050
（共享所有权完整语义属 ph06，这里只对照 deleter 的类型差异）
```

要点：**unique_ptr 的删除策略是类型的一部分**——函数指针 deleter 让 `unique_ptr` 占两词；**无状态仿函数 / 无捕获 lambda deleter 经空基类优化（EBO）仍是裸指针大小、零开销**；有状态 deleter 大小随状态增长；`shared_ptr` 的 deleter 走**类型擦除**（存进控制块），同一类型 `shared_ptr<Widget>` 可挂不同 deleter 而类型不变。

## 示例 5：unique_ptr 管理 C 资源（ex05-unique-ptr-c-resource.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex05-unique-ptr-c-resource.cpp -o /tmp/ph13-ex05
/tmp/ph13-ex05
```

本机实测输出（已验证，两种编译器一致；fd 编号每次运行可能不同）：

```text
[1] unique_ptr 管理 FILE*（roadmap §13 示例的完整版）
  fopen 成功（fclose 已绑定为 deleter）
[2] unique_ptr 管理 POSIX fd
  fopen 成功（fclose 已绑定为 deleter）
  read 27 字节: via unique_ptr
second line
  close(fd=3)（deleter 自动调用）
[3] 异常路径：fd 打开后抛异常，close 照常执行（E.6）
  fd 已打开，即将抛异常…
  close(fd=3)（deleter 自动调用）
  捕获: 读取中出错（fd 已在栈展开时关闭）
[4] unique_ptr 管理 malloc 内存
  malloc 由 unique_ptr 托管
[5] 临时文件已删除
```

要点：**`unique_ptr` + 自定义 deleter 是"不写 RAII 类"时的资源封装捷径**（R.20）——`decltype(&std::fclose)` 把释放函数编码进类型；fd 用无状态仿函数 `FdCloser` 包装 `close`；[3] 异常路径下 deleter 在栈展开时兜底，`close` 先于 `catch` 执行。

## 示例 6：异常安全资源释放（ex06-exception-safety.cpp）

```bash
c++ -std=c++20 -Wall -Wextra ex06-exception-safety.cpp -o /tmp/ph13-ex06
/tmp/ph13-ex06
```

本机实测输出（已验证，两种编译器一致）：

```text
[1] 反例：裸指针 + 构造函数中途抛异常 → 泄漏（存活不归零）
  Res ctor A（存活 1）
  捕获: 第二个资源获取失败
  此时 Res 存活 = 1（应为 1：A 泄漏了）
[2] 正例：unique_ptr 成员 + 构造函数中途抛异常 → 零泄漏
  Res ctor A（存活 1）
  Res dtor A（存活 0）
  捕获: 第二个资源获取失败
  此时 Res 存活 = 0（A 已随成员析构释放）
[3] 正常构造：两个资源都成功
  Res ctor A（存活 1）
  Res ctor B（存活 2）
  Res dtor B（存活 1）
  Res dtor A（存活 0）
  此时 Res 存活 = 0
[4] 强保证：copy-and-swap —— 拷贝失败时目标原封不动
  捕获 bad_alloc: dst 仍是 original（强保证成立）
  正常赋值成功: dst=updated
  要点：可能失败的操作都在 swap 之前完成；swap 标记 noexcept（E.16）
[5] 基本保证对照：Fragile::assign 先清空再拷贝，中途失败对象已受损
  f.value=new（正常路径无恙；异常路径只保证不泄漏、不保证原值）
```

要点：**构造函数中途抛异常时，析构不会执行（对象尚未构造完成），已构造的成员会逆序析构**——裸指针成员（[1] 存活计数残留 1，`A` 泄漏）vs `unique_ptr` 成员（[2] 存活归零）；**强保证 = copy-and-swap**：在临时对象上完成全部可能失败的操作，再 `noexcept` swap 换入（[4] 拷贝失败时 `dst` 原封不动）；基本保证只承诺"不泄漏、对象合法"（[5]）。

## 双编译器验证记录

| 示例 | Apple clang 21.0.0 | Homebrew clang 21.1.8 | 备注 |
|------|--------------------|-----------------------|------|
| ex01 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 保证省略 + 逐成员拷贝/移动 |
| ex02 | ✅ 零警告；危险路径 ASan 报 double-free，SIGABRT 退出码 134 | ✅ 零警告，输出一致 | 地址值每次运行不同 |
| ex03 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 异常路径 close 先于 catch |
| ex04 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | sizeof 8/16/8/8/16/16 |
| ex05 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | fd 编号每次运行不同 |
| ex06 | ✅ 零警告，输出一致 | ✅ 零警告，输出一致 | 存活计数 + 强保证实测 |

验证用构建产物全部位于 /tmp，仓库无 .o/可执行文件残留。
