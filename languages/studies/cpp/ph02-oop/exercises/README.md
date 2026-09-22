# ph02 面向对象 OOP 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。编译统一加 `-Wall -Wextra -std=c++17`。
> 遵循 C++ Core Guidelines：优先 RAII、const 正确、不裸 new/delete、构造函数用成员初始化列表。

## 练习 1：学生类（★）

**目标**：用 class 封装一个学生记录。

**要求**：实现 `Student` 类，私有成员为姓名、学号、成绩；构造函数用成员初始化列表；提供 `print()` 和 `passed()`（成绩 ≥ 60）两个 const 成员函数；在 `main` 中构造若干学生并演示。

**验收**：`Student{"Alice", 101, 85.0}` 打印 `Alice [101]: 85`，`passed()` 返回 true；学号 102 成绩 55.0 的学生 `passed()` 返回 false。

## 练习 2：Page / Block / Segment / VectorIndex 建模（★★）

**目标**：用组合为存储引擎做简单建模。

**要求**：`Page` 持有一段数据字符串并能报告大小；`Block` 组合多个 `Page`（`std::vector<Page>`），`total_size()` 汇总；`Segment` 组合多个 `Block` 并汇总；再实现一个 `VectorIndex`：内部用 `std::vector<int>` 存键，`insert(int key)` 追加，`find(int key)` 返回下标（找不到返回 -1）。

**验收**：两个 Page（"row1"、"row2-data"）装入一个 Block 再装入 Segment，`total_size()` 输出 13；`VectorIndex` 插入 10、20、30 后 `find(20)` 返回 1、`find(99)` 返回 -1。

## 练习 3：Logger 类（★★）

**目标**：掌握 static 成员与 const 成员函数。

**要求**：实现 `Logger` 类，构造时传入模块名；提供 `info(msg)` 输出 `[INFO] [<模块>] <msg>`；用 `static` 成员统计全部实例共写了多少条日志，`static` 成员函数 `log_count()` 读取。

**验收**：两个 Logger（模块 storage、network）各写两条日志后，`Logger::log_count()` 输出 4。

## 练习 4：IStorage / IIndex / IExecutor 接口（★★★）

**目标**：用抽象类定义接口，用多态接入不同实现。

**要求**：定义三个抽象基类——`IStorage`（`write(int, string)` / `read(int)`）、`IIndex`（`insert(int)` / `contains(int)`）、`IExecutor`（`execute(const string& plan)`），全部带虚析构函数；各给一个实现类（如 `MemoryStorage` 用 `unordered_map`、`VectorIndex` 用 `vector`、`ScanExecutor` 打印计划）；写一个接受 `IExecutor&` 的自由函数 `run_plan` 演示动态分派。

**验收**：`MemoryStorage` 写入 page 1 后能读回原文；`VectorIndex` 插入后 `contains` 判断正确；`run_plan(scan_executor, "table_scan users")` 输出派生类的执行信息。
