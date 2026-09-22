# exercises —— C++ 未定义行为 UB 与内存安全阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。练习 1/2/3 与 roadmap ph15「练习」小节一一对应（修复悬空引用示例 / 用 ASan/UBSan 检查项目 / 梳理 vector 迭代器失效场景）；练习 4/5 覆盖「学习内容」中的 use-after-move 语义风险与未初始化变量（roadmap「C++ UB 示例集」推荐项目由本阶段 project/ 整体落地）。参考实现在 `sol-*` 文件中，做完再看。

> ⚠️ 练习 2/4 的“坏版本复现”必须用 Sanitizer 编译运行（`-fsanitize=address` / `-fsanitize=undefined -fno-sanitize-recover=all`），**不要裸跑**坏版本——那是故意写错的 UB 代码。

## 练习 1：修复“缓存容器元素指针”的悬空引用（★）

- **目标**：给定一个在构造时缓存 `&names_.front()`、随后可能 `push_back` 扩容的类（缓存指针随重分配悬空），修复为不悬空版本并解释修复思路
- **要求**：
  - 坏版本（自己照抄理解，勿提交为答案）：`Registry` 成员 `const std::string* first_` 指向 `names_.front()`；`add()` 扩容后 `first()` 解引用悬空指针
  - 用一句话解释：为什么 vector 的引用/指针会随 `push_back` 失效（重分配 → 旧缓冲区释放）
  - 修复版：不缓存容器元素指针——需要元素时按下标现取（`at()`）或按值返回（值语义）；演示“扩容后逐元素访问正常”与“clear() 不影响之前按值取出的副本”
- **验收**：坏版本（参照 examples/ex02 的 `-DEX02_REALLOC`）ASan 报 `heap-use-after-free`；修复版 `c++ -std=c++20 -Wall -Wextra` 零警告，加 `-fsanitize=address,undefined` 复跑零报告，输出与 `sol-01-fix-container-dangling.cpp` 文件头一致
- **提示**：容器元素指针是“借来的眼睛”，生命周期由容器管理；结构性修改后一律刷新（参考实现 `sol-01-fix-container-dangling.cpp`）

## 练习 2：用 ASan 检查并修复越界与 use-after-free（★★）

- **目标**：写一个同时含“vector 越界写”与“delete 后使用”的程序，用 ASan 复现、读懂报告（错误类型 + READ/WRITE 大小）、逐个修复
- **要求**：
  - 坏版本：`std::vector<int> scores = {1,2,3}; scores[3] = 100;`（cap=3，运行期下标越界写）+ `int* p = new int(42); delete p; *p = 7;`（use-after-free），每处加注释说明“为什么是 UB”
  - 用 `-fsanitize=address -O0 -g` 编译运行，记录错误类型与 READ/WRITE 大小；注意第一个 UB 会让程序中止——**一次修一个、逐个复现**（先修越界再看 UAF）
  - 修复版：越界用 `at()`（越界抛异常，定义行为）或先判后取；堆对象用 `unique_ptr`（消灭裸 delete，R.11）
- **验收**：坏版本 ASan 报 `heap-buffer-overflow`（WRITE of size 4）与（修掉越界后）`heap-use-after-free`（WRITE of size 4）；修复版零警告、ASan/UBSan 复跑零报告、退出码 0，输出与 `sol-02-fix-oob-uaf.cpp` 文件头一致
- **提示**：`operator[]` 不检查边界是设计（性能），`at()` 是检查版；释放交给 RAII 就没有“提前释放又继续用”的窗口（参考实现 `sol-02-fix-oob-uaf.cpp`）

## 练习 3：梳理 vector 迭代器/引用失效场景（★★）

- **目标**：梳理 `std::vector` 的迭代器/引用失效规则（哪些操作使它们失效、失效范围多大），写出“边遍历边修改”的安全姿势
- **要求**：
  - 写出失效速查表（push_back 扩容 / insert / erase / clear / reserve 各自让什么失效；不重分配时修改点之前是否还有效）
  - 演示三个安全姿势：erase 循环用返回值接住下一个迭代器；边遍历边插入用“先收集后插入”；用 `reserve` 避免隐性扩容失效
  - 用一句话说明：使用已失效迭代器为什么是 UB（标准保证失效 = 解引用已释放/失效对象）
- **验收**：`c++ -std=c++20 -Wall -Wextra` 零警告，ASan/UBSan 复跑零报告，运行输出（删偶数结果、插入结果、cap 变化）与 `sol-03-vector-invalidation.cpp` 文件头一致
- **提示**：失效是“标准承诺”，不是“崩溃预警”——失效后使用不保证崩；结构性修改后一律刷新（参考实现 `sol-03-vector-invalidation.cpp`）

## 练习 4：use-after-move 识别与 moved-from 纪律（★★★）

- **目标**：识别“把 moved-from 对象当仍拥有数据使用”的 UB，修复为安全写法；说清 moved-from 对象“能做什么、不能做什么”
- **要求**：
  - 坏版本：`auto up = std::make_unique<int>(42); auto moved = std::move(up); ...; *up`（解引用 moved-from 的 unique_ptr），注释说明为什么是 UB
  - 用 `-fsanitize=undefined -fno-sanitize-recover=all` 编译复现并记录报告（勿裸跑）；对比裸跑表现
  - 修复版：使用前判空 / `reset` 重建；moved-from 对象只做析构/重新赋值/状态无关操作；演示 string 的 moved-from 实测（size=0）但说明这是“未指定”而非标准承诺
- **验收**：坏版本 UBSan 报 `reference binding to null pointer`；修复版零警告、UBSan 复跑零报告，输出与 `sol-04-use-after-move.cpp` 文件头一致
- **提示**：`[lib.types.movedfrom]`：moved-from 是“合法但未指定”；unique_ptr 是少数**指定** moved-from 状态（空）的类型；别把 libc++ 实测的“置空”写成标准保证（参考实现 `sol-04-use-after-move.cpp`）

## 练习 5：未初始化变量的识别与修复（★★）

- **目标**：识别“读取未初始化变量”的 UB，用编译期警告定位，用 C++ 的初始化护栏修复
- **要求**：
  - 坏版本：`int x;` + `struct Stats { int hits, misses; }; Stats s;`，读 `x` 与 `s.hits`，注释说明为什么是 UB（不确定值）与为什么 `s.hits` 多数情况下编译器不警告
  - 用 `c++ -std=c++20 -Wall -Wextra -O1` 编译观察 `-Wuninitialized` 警告（编译器第一道防线）；运行时观察垃圾值
  - 修复版：声明即初始化（`int x = 0;`）+ 默认成员初始化器（`int hits = 0;`），演示分支输出稳定
- **验收**：坏版本触发 `-Wuninitialized`；修复版零警告、输出稳定（`x=0`、`hits=0 misses=0`），与 `sol-05-uninit-fix.cpp` 文件头一致
- **提示**：ES.20「总是初始化对象」；成员未初始化编译器常拦不到——默认成员初始化器让“构造即全初始化”成为编译期事实（参考实现 `sol-05-uninit-fix.cpp`）

> **提示**：练习 1~5 分别对应主文档 3.2（容器悬空）/ 3.1+3.3（越界、UAF）/ 3.1+4.2（失效规则）/ 3.4（use-after-move）/ 3.7（未初始化）的知识；未初始化与别名两类“工具抓不到的坑”在 project/ 中还有完整演示。所有 Sanitizer 报告请在 sol 文件注释里对照自己的实测输出。
