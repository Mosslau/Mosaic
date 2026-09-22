# examples —— C++ 性能优化与 Profiling 阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`），C++20（libc++）。**全部示例已验证**（双编译器 `-Wall -Wextra` 本机实测：6 个示例编译零警告、运行通过、断言自测全绿、退出码 0）。代码写法以零警告为目标：无裸 new/delete（R.11）、RAII、`const` 优先（Con.1/ES.25）、无魔法数字（ES.45）。**构建产物一律输出到 /tmp，验证后清理，仓库不落二进制**。以下命令均在 examples/ 目录内执行。

计时类示例（ex01/ex03/ex05/ex06）的**数字是教学证据不是固定规格**：不同 CPU/编译器下相对趋势一致、绝对值会变——这正是主文档反复强调的「先测量、再下结论」。

| 文件 | 说明 | 编译/运行 | 验证状态 |
|------|------|-----------|----------|
| `ex01-cache-line.cpp` | cache locality：同一 64 MiB 矩阵按行（连续）/ 按列（跨步）/ 分块求和，实测局部性差距 | `clang++ -std=c++20 -O3 -Wall -Wextra ex01-cache-line.cpp -o /tmp/ph18cpp-ex01 && /tmp/ph18cpp-ex01` | 已验证（双编译器 -O3，本机列主序慢 ~5.6x） |
| `ex02-copy-elision-move.cpp` | 拷贝消除与移动语义：prvalue 保证消除 / NRVO / 条件返回退化移动 / vector 增长 reserve 效应 / push_back 移动 vs 拷贝计数 | `clang++ -std=c++20 -O1 -Wall -Wextra ex02-copy-elision-move.cpp -o /tmp/ph18cpp-ex02 && /tmp/ph18cpp-ex02` | 已验证（双编译器 -O1/-O3） |
| `ex03-profiling-demo.cpp` | 插桩式剖析（ScopeTimer）：数据管线三阶段多轮计时，输出耗时分布占比定位热点（采样剖析器的廉价替代） | `clang++ -std=c++20 -O2 -Wall -Wextra ex03-profiling-demo.cpp -o /tmp/ph18cpp-ex03 && /tmp/ph18cpp-ex03 [passes]` | 已验证（双编译器 -O2，本机字符串构建阶段占 ~72%） |
| `ex04-alloc-optim.cpp` | 分配次数优化：重载全局 operator new 计数，「+= 整串临时」vs「reserve + append」的分配次数与耗时对照 | `clang++ -std=c++20 -O2 -Wall -Wextra ex04-alloc-optim.cpp -o /tmp/ph18cpp-ex04 && /tmp/ph18cpp-ex04` | 已验证（双编译器 -O2，本机 24k→1 次分配、快 ~200x） |
| `ex05-simd-layout.cpp` | SIMD 友好布局：AoS 切片 → SoA → SoA 4 路累加 → NEON 的实测阶梯（布局 × 并行累加缺一不可） | `clang++ -std=c++20 -O3 -Wall -Wextra ex05-simd-layout.cpp -o /tmp/ph18cpp-ex05 && /tmp/ph18cpp-ex05` | 已验证（双编译器 -O3；arm64 NEON 路径经 `__aarch64__` 实测编译进二进制） |
| `ex06-bench-harness.cpp` | 微型 benchmark 工具 + 「模式 vs 裸写」（兑现 ph17 预告）：四路派发被编译器收敛到同速；pull 虚管道 vs 裸写约慢 5.6x | `clang++ -std=c++20 -O2 -Wall -Wextra ex06-bench-harness.cpp -o /tmp/ph18cpp-ex06 && /tmp/ph18cpp-ex06` | 已验证（双编译器 -O2） |

## 示例 1：cache locality（ex01-cache-line.cpp）

对应主文档 3.5 与 roadmap 学习内容「cache locality」。

```bash
# 1. 编译（必须 -O3——-O0 下差距会被编译质量掩盖）：
clang++ -std=c++20 -O3 -Wall -Wextra ex01-cache-line.cpp -o /tmp/ph18cpp-ex01
# 2. 运行：
/tmp/ph18cpp-ex01
```

教学要点：① 同一批数据、同一求和，仅访问顺序不同（连续 vs 16 KB 跨步 vs 分块），耗时差一个数量级；② 数据规模必须超出缓存（64 MiB > 本机 L2 4 MB），否则「整块常驻缓存」会掩盖访问模式差异；③ 被测计算的结果逐轮变化（每轮微调一个元素），防止编译器把测量循环整段外提——这是计时代码必守的纪律（见文件内注释）。

## 示例 2：拷贝消除与移动语义（ex02-copy-elision-move.cpp）

对应主文档 3.6 与 roadmap 学习内容「拷贝消除、移动语义」。

```bash
# 1. 编译（-O1 及以上，复制消除需优化器配合）：
clang++ -std=c++20 -O1 -Wall -Wextra ex02-copy-elision-move.cpp -o /tmp/ph18cpp-ex02
# 2. 运行：
/tmp/ph18cpp-ex02
```

教学要点：① C++17 起「按值返回 prvalue」是**语言保证**的零拷贝零移动，不是优化开关；② NRVO（具名返回值优化）通常生效但非强制；③ 条件返回无法 NRVO 时退化为一次移动而非拷贝；④ `vector` 不 reserve 时重分配会移动全部存量元素（257 个元素移动 511 次），reserve 一次到位后零移动；⑤ `push_back(临时)` 走移动、`push_back(左值)` 走拷贝——成本差两个量级。

## 示例 3：插桩式剖析（ex03-profiling-demo.cpp）

对应主文档 3.3 与 roadmap 学习内容「CPU profile」中「无剖析器时的替代方案」。

```bash
# 1. 编译：
clang++ -std=c++20 -O2 -Wall -Wextra ex03-profiling-demo.cpp -o /tmp/ph18cpp-ex03
# 2. 运行（可传 passes 参数缩短演示，如 /tmp/ph18cpp-ex03 1）：
/tmp/ph18cpp-ex03
```

教学要点：① 没有 perf/Tracy 时，ScopeTimer 插桩是起步手段——把管线切成阶段、多轮累计、输出占比表，热点一目了然；② 本机 1M 行 × 2 轮实测：字符串构建占 ~72%，是显然的优化对象；③ 插桩计时回答「哪一阶段总时长最长」，采样剖析器才回答「哪一行最热」——两者互补，别越界解读；④ 计时阶段内不混入 iostream 输出、被测输入逐轮变化，否则数据失真。

## 示例 4：分配次数优化（ex04-alloc-optim.cpp）

对应主文档 3.7 与 roadmap 学习内容「分配次数优化」。

```bash
# 1. 编译：
clang++ -std=c++20 -O2 -Wall -Wextra ex04-alloc-optim.cpp -o /tmp/ph18cpp-ex04
# 2. 运行：
/tmp/ph18cpp-ex04
```

教学要点：① 重载全局 `operator new` 计数是「数分配」的通用手法（本示例按区域清零/读出，RAII 收口）；② 基线 `result = result + tok + ','` 每轮造整段临时串：20k 词条约 24k 次分配、O(n²) 字符搬运；③ 优化版先算总长 `reserve` 一次、再 `append`：1 次分配、线性拷贝，本机快约 200 倍；④ 优化不是玄学——分配次数本身是可量化的指标，先数出来再动手。

## 示例 5：SIMD 友好的内存布局（ex05-simd-layout.cpp）

对应主文档 3.8 与 roadmap 学习内容「SIMD 友好的内存布局」。

```bash
# 1. 编译（-O3）：
clang++ -std=c++20 -O3 -Wall -Wextra ex05-simd-layout.cpp -o /tmp/ph18cpp-ex05
# 2. 运行：
/tmp/ph18cpp-ex05
```

教学要点：① 同一语义 Σx² 四档实测（6M 点，本机）：AoS 切片 3.53 ms → SoA 标量 3.38 ms（布局变化但单累加器依赖链还在，几乎没快）→ SoA 4 路累加 0.98 ms → NEON 0.66 ms（≈5.3x）；② 结论：**布局是 SIMD 的必要条件而非充分条件**——连续数据 + 打断累加依赖链两者同时到位才兑现向量宽度；③ 编译器自动向量化的机会来自 ③ 的结构，手写 NEON（`__aarch64__` 门控）只是保底；x86-64 编译时 NEON 内核自动退化为标量并打印提示，SoA vs AoS 的布局结论依然成立。

## 示例 6：微型 benchmark 工具 + 模式 vs 裸写（ex06-bench-harness.cpp）

对应主文档 3.9/3.10 与 roadmap 学习内容「向量距离计算 benchmark（工具方法）」及 ph17「模式 vs 裸写」预告的兑现。

```bash
# 1. 编译：
clang++ -std=c++20 -O2 -Wall -Wextra ex06-bench-harness.cpp -o /tmp/ph18cpp-ex06
# 2. 运行：
/tmp/ph18cpp-ex06
```

教学要点：① benchmark 工具三要素——预热、多轮取最优（min 对噪声最稳）、ns/op 归一化；② 实测（本机 -O2）：直调 / 函数指针 / std::function / 虚函数四路被内联与去虚化收敛到 0.6–0.8 ns/op（最慢/最快 1.27x）——**编译器看得见的间接几乎免费**；③ 同语义的过滤聚合，pull 模型虚管道（ph17 执行器同款 Scan→Filter 形态）比裸写单循环慢 ~5.6x——成本显形在状态藏在堆对象、跨 next() 迁移、编译器无法恢复的运行时结构；④ 两条结论合读 = 别凭「模式贵/免费」的直觉，先测再定（roadmap 必会概念「先测量，再优化」）。
