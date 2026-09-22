# examples —— C++ 未定义行为 UB 与内存安全阶段完整示例

验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），C++20（libc++）。六个示例的**默认构建**（无 `-D`）在两种编译器下 `-std=c++20 -Wall -Wextra` **零警告**（已验证）；输出一致性的说明：除 ex05（竞态输出本身不确定，见其文件头注释）外，其余示例双编译器输出一致；故意出错变体按各文件首行注释的「运行前提」编译，报告实测记录于下表与主文档第 6 章。**全部产物输出到 /tmp，验证后清理，仓库不落二进制**（本目录只含源码）。

## 关于故意出错的代码

本阶段主题是“识别 UB”，每个示例默认演示**安全写法**（零警告、可任意运行），故意出错路径用 `-DEX0N_*` 宏开关，与 ph12 ex05 / ph14 ex04 的“宏关默认、宏开危险”约定一致——**唯一例外是 ex05**：数据竞争要工具才能现形，其默认（无 `-D`）就是竞态版本、必须 `-fsanitize=thread` 编译运行（勿裸跑）；修复版反而用 `-DEX05_FIXED` 宏打开（宏开 = 安全版，极性与其他示例相反，见示例 5）：

- **UB 演示统一 `-O0`**：`-O0` 下访问形状与源码一一对应、行号稳定、报告可控。实测（Apple clang 21.0.0）本示例越界写在 `-O0`/`-O1`/`-O2` 三档 + ASan 下均报 `heap-buffer-overflow` + `WRITE of size 4`（退出码 134）——越界写后紧跟同下标 printf 读，写不会被折叠消除（C ph10 4.2 的“优化改变 UB 表现”演示是可整体折叠的表达式场景，见主文档 4.1）；`-O0` 不是防漏报的必要条件。
- **ASan/UBSan 变体**：必须用对应的 `-fsanitize` 编译运行，否则勿运行（裸跑行为不可预期）；本环境 ASan/UBSan/TSan 无法启动外部符号器（llvm-symbolizer 存在但 spawn 失败 errno 9），报告栈帧未符号化，但错误类型、访问大小、分配/释放信息完整。
- **TSan 说明**：数据竞争检测实测用 Apple clang 21.0.0（`c++`）的 `-fsanitize=thread`；Homebrew clang 21.1.8 的 TSan 运行时在本机 arm64 上不稳定（实测崩溃，exit 139），未用于 TSan 验证。
- **未初始化变量**：不在本目录单独演示——它的“报告”是编译期 `-Wuninitialized` 警告与垃圾值输出（见 exercises 练习 5 与 project 的 uninit 条目）；别名违规同样“工具抓不到”，靠规范与代码评审（ex06 正反例对照）。

| 文件 | 说明 | 构建/运行 | 验证状态 |
|------|------|-----------|----------|
| `ex01-vector-oob.cpp` | 越界访问：vector / std::array / C 数组三种形态与 ASan、UBSan 的覆盖差异；at() 与手动边界检查正解 | 默认 `c++ -std=c++20 -Wall -Wextra ex01-vector-oob.cpp -o /tmp/ph15-ex01 && /tmp/ph15-ex01`；变体见下 | 已验证（默认双编译器零警告；三变体报告实测） |
| `ex02-dangling-container.cpp` | 悬空引用与迭代器/引用失效：vector 扩容失效、容器销毁后引用（C++ 特有悬空源；返回局部引用属 ph12） | 默认同上；变体见下 | 已验证（默认零警告；两变体 ASan 报告实测，`-O0`~`-O2` 均触发） |
| `ex03-uaf-double-free.cpp` | use-after-free 与重复释放：裸 new/delete 生命周期误用；置空 / RAII / unique_ptr 正解 | 默认同上；变体见下 | 已验证（默认零警告；两变体 ASan 报告实测） |
| `ex04-use-after-move.cpp` | use-after-move 语义：moved-from“合法但未指定”（string 实测置空、unique_ptr 标准保证为空）；解引用 moved-from unique_ptr 是 UB | 默认同上；变体见下 | 已验证（默认零警告；UBSan/裸跑两报告实测） |
| `ex05-data-race.cpp` | 数据竞争：两线程无锁 ++shared（UB）；scoped_lock 修复版 | `c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread ex05-data-race.cpp -o /tmp/ph15-ex05 && /tmp/ph15-ex05`；修复版加 `-DEX05_FIXED` | 已验证（两变体零警告；TSan 报告 / 零报告实测，Apple clang） |
| `ex06-alias-align.cpp` | 类型别名与对齐：指针双关 / union 双关（C++ 中 UB）、未对齐访问（UBSan 报告）；std::bit_cast / memcpy 正解 | 默认同上；变体见下 | 已验证（默认零警告；变体实测：别名“碰巧正确”、未对齐 UBSan 报告） |

## 示例 1：越界访问（ex01-vector-oob.cpp）

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex01-vector-oob.cpp -o /tmp/ph15-ex01 && /tmp/ph15-ex01
# 2. 越界写（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX01_VEC_OOB ex01-vector-oob.cpp -o /tmp/ph15-ex01-vec && /tmp/ph15-ex01-vec
# 3. std::array 越界读（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX01_STD_ARRAY ex01-vector-oob.cpp -o /tmp/ph15-ex01-arr && /tmp/ph15-ex01-arr
# 4. C 数组越界写（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX01_CARRAY ex01-vector-oob.cpp -o /tmp/ph15-ex01-carr && /tmp/ph15-ex01-carr
```

本机实测（Apple clang 21.0.0，-O0/-O1/-O2 -g）：`v[idx]=100`（size=3/cap=3，运行期下标）→ ASan 报 **`ERROR: AddressSanitizer: heap-buffer-overflow`** + `WRITE of size 4` + "located 0 bytes after 12-byte region"，退出码 134，**三档实测均触发**（越界写后紧跟同下标 printf 读，写不会被折叠消除；`-O0` 只是统一演示级别——行号稳定、报告可控，不是防漏报）。`std::array<int,3> a; a[3]`（运行期下标）→ ASan 报 `stack-buffer-overflow` + `READ of size 4`，退出码 134（同代码 UBSan 静默——`operator[]` 在标准库实现内部，未被 UBSan 插桩）。C 数组 `int c[3]; c[idx]=7` → UBSan 报 **`runtime error: index 3 out of bounds for type 'int[3]'`**，退出码 134。安全对照（默认运行）：`at()` 越界抛 `std::out_of_range`（定义行为）、手动边界检查先判后取——“两种工具都要用，各有盲区”是本示例的结论。

## 示例 2：悬空引用与迭代器/引用失效（ex02-dangling-container.cpp）

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex02-dangling-container.cpp -o /tmp/ph15-ex02 && /tmp/ph15-ex02
# 2. 扩容后旧引用失效（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX02_REALLOC ex02-dangling-container.cpp -o /tmp/ph15-ex02-r && /tmp/ph15-ex02-r
# 3. 容器销毁后引用（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX02_CONTAINER_DEAD ex02-dangling-container.cpp -o /tmp/ph15-ex02-d && /tmp/ph15-ex02-d
```

本机实测（Apple clang 21.0.0，-O0~-O2 均触发）：`{1,2,3}`（cap=3）`push_back(4)` 扩容 cap→6（实测 libc++ 2 倍增长），旧引用 `r` 读 → ASan 报 **`ERROR: AddressSanitizer: heap-use-after-free`** + `READ of size 4`，退出码 134；`delete` 持有元素的容器后读引用 → 同上 `heap-use-after-free` + `READ of size 1`，退出码 134。安全对照（默认运行）：扩容后每次现取下标、`reserve` 预留容量、先拷贝值再让容器走——引用/迭代器“随容器状态刷新”的三条纪律。

## 示例 3：use-after-free 与重复释放（ex03-uaf-double-free.cpp）

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex03-uaf-double-free.cpp -o /tmp/ph15-ex03 && /tmp/ph15-ex03
# 2. delete 后写（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX03_UAF ex03-uaf-double-free.cpp -o /tmp/ph15-ex03-u && /tmp/ph15-ex03-u
# 3. 双重 delete（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX03_DOUBLE_FREE ex03-uaf-double-free.cpp -o /tmp/ph15-ex03-d && /tmp/ph15-ex03-d
```

本机实测（Apple clang 21.0.0，-O0~-O2 与 ASan+UBSan 组合构建均触发）：`delete p; *p = 1` → ASan 报 **`ERROR: AddressSanitizer: heap-use-after-free`** + `WRITE of size 4`，退出码 134；`delete p; delete p` → 报 **`ERROR: AddressSanitizer: attempting double-free`**，退出码 134。安全对照（默认运行）：delete 后立即置空（`delete nullptr` 合法）、RAII 让释放点唯一、`unique_ptr` 表达独占所有权（R.11/R.20）——“消灭裸 delete”是 C++ 的根治思路，与 C 的“小心地 free”形成对照（衔接 C ph10）。

## 示例 4：use-after-move 语义（ex04-use-after-move.cpp）

```bash
# 1. 默认（语义对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex04-use-after-move.cpp -o /tmp/ph15-ex04 && /tmp/ph15-ex04
# 2. 解引用 moved-from 的 unique_ptr（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX04_DEREF_MOVED ex04-use-after-move.cpp -o /tmp/ph15-ex04-u && /tmp/ph15-ex04-u
```

本机实测（Apple clang 21.0.0）：默认运行——moved-from 的 `std::string` 实测 `size=0`（libc++ 行为；标准层面是“合法但未指定”，不得写成“标准保证为空”），重新赋值正常；moved-from 的 `unique_ptr` 保证为空（`get()==nullptr`，标准指定）。危险路径——解引用 moved-from `unique_ptr` → UBSan 报 **`runtime error: reference binding to null pointer of type 'int'`**（位于 `unique_ptr.h` 的 `operator*`），退出码 134；去掉 UBSan 裸跑（-O0）实测 **Segmentation fault，退出码 139**——两种表现都是 UB 的合法形态。

## 示例 5：数据竞争（ex05-data-race.cpp）

```bash
# 1. 竞态版本（故意出错，必须 -fsanitize=thread，勿裸跑）：
c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread ex05-data-race.cpp -o /tmp/ph15-ex05 && /tmp/ph15-ex05
# 2. 修复版本（scoped_lock，TSan 零报告）：
c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread -DEX05_FIXED ex05-data-race.cpp -o /tmp/ph15-ex05-f && /tmp/ph15-ex05-f
```

本机实测（Apple clang 21.0.0，-fsanitize=thread）：竞态版本 TSan 报 **`WARNING: ThreadSanitizer: data race`** + `Write of size 4 ... by thread T2` / `Previous write of size 4 ... by thread T1`（同一地址的读改写无同步），退出码 134；修复版本（`std::scoped_lock` 保护，CP.2/CP.20）TSan 零报告、输出确定 `shared=200000`、退出码 0。裸跑对照：-O0 下竞态版本退出码 0 但值不定（本机 6 次实测：122984 / 117974 / 120359 / 112912 / 126519 / 110862，均小于 200000）；-O1 下实测 6 次恰为 200000（编译器把累加优化进寄存器）——“碰巧对”不能证明无竞态，必须 TSan 复跑（roadmap 必会概念：数据竞争在 C++ 中是 UB）。

## 示例 6：类型别名与对齐（ex06-alias-align.cpp）

```bash
# 1. 默认（正解对照：std::bit_cast / memcpy，零警告）：
c++ -std=c++20 -Wall -Wextra ex06-alias-align.cpp -o /tmp/ph15-ex06 && /tmp/ph15-ex06
# 2. 指针双关（故意出错：别名违规，工具抓不到，输出是"碰巧正确"的 UB 表现）：
c++ -std=c++20 -Wall -Wextra -O2 -DEX06_PUN_PTR ex06-alias-align.cpp -o /tmp/ph15-ex06-p && /tmp/ph15-ex06-p
# 3. union 双关（故意出错：C++ 中读非活动成员是 UB；可任意编译运行，勿当规范）：
c++ -std=c++20 -Wall -Wextra -O2 -DEX06_PUN_UNION ex06-alias-align.cpp -o /tmp/ph15-ex06-u && /tmp/ph15-ex06-u
# 4. 未对齐访问（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX06_MISALIGN ex06-alias-align.cpp -o /tmp/ph15-ex06-m && /tmp/ph15-ex06-m
```

本机实测（Apple clang 21.0.0）：默认运行输出 `bits=3f800000 back=1.0`（bit_cast）、`bits=3f800000`（memcpy）、读出 `11223344`——均为定义行为。指针双关（`reinterpret_cast<uint32_t*>(&float)`）实测 `-O0`/`-O2` 均输出 `3f800000`——与正解相同，是**“碰巧正确”**的 UB 表现（本次 clang 未按别名假设重排；换代码形状/编译器即可能不同，判断依标准）；union 读非活动成员同样输出 `3f800000`、UBSan 零报告（工具抓不到；注意 GCC/Clang 把 union 双关当扩展接受，C 中为惯用法——C++ 标准只豁免 common initial sequence）。未对齐访问（`buf+1` 上写 uint32_t）→ UBSan 报 **`runtime error: store to misaligned address ... for type 'std::uint32_t' ... which requires 4 byte alignment`**，退出码 134；同代码 arm64 裸跑实测正常输出——**硬件容忍 ≠ 不是 UB**。
