# exercises —— C++ 测试、静态分析与代码规范阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。练习 1~4 与 roadmap ph16「练习」小节一一对应（给核心类写测试 / 配置 clang-tidy / 开启 ASan/TSan 构建 / 生成覆盖率报告）；练习 5 覆盖「学习内容」中的 clang-format。参考实现在 `sol-*` 文件中，做完再看。

> ⚠️ 练习 3 的 Sanitizer 构建在本机一律用 Apple clang（`c++`）：Homebrew clang 21.1.8 的 ASan 运行时初始化即挂起、TSan 崩溃（examples/ex04 Makefile 文件头有实测记录）。

## 练习 1：给核心类写测试（★★）

- **目标**：为一个有状态、有异常路径的 `BankAccount` 类写出覆盖「正常路径 + 异常路径 + 边界」的测试
- **要求**：
    - 被测类（自己实现）：`deposit(cents)` / `withdraw(cents)` / `balance()`；存款非正数、取款透支都抛 `std::invalid_argument`
    - 测试至少 5 个用例：开户余额、存款累加、取款扣减、**透支后余额不变**（异常的路径与状态不变性都要测）、负额存款
    - 断言工具任选：examples/ex01 的 mini 框架、自写断言助手，或已装 GoogleTest/Catch2 就用真框架
    - 测试程序的**退出码**必须反映成败（0 全过 / 非 0 有失败）——这是 CI 能接住的信号
- **验收**：`c++ -std=c++20 -Wall -Wextra` 零警告，运行输出与退出码和 `sol-01-bank-account-test.cpp` 文件头一致
- **提示**：测异常不只测「抛没抛」，还要测「抛了之后对象状态对不对」（参考实现 `sol-01-bank-account-test.cpp`）

## 练习 2：配置 clang-tidy（★★）

- **目标**：写出一份 `.clang-tidy` 配置，并把一段代码修到在该配置下零告警
- **要求**：
    - 配置至少覆盖三个检查族：`bugprone-*` / `modernize-*` / `performance-*`，并设 `WarningsAsErrors: '*'`（告警即失败）
    - 代码素材：自己写一个「小类层次 + 遍历求和」程序（或改造 examples/ex02 的坏版本），先跑出告警，再逐条修复到零告警
    - 用一句话解释每条修复对应的 C++ Core Guidelines 规则（如 C.128 重写必标 override）
- **验收**：`clang-tidy <你的文件> --config-file=<你的配置> -- -std=c++20` 零告警、退出码 0；参考实现 `sol-02.clang-tidy` + `sol-02-tidy-clean.cpp` 已验证（clang-tidy 21.1.8 零告警）
- **提示**：多态基类「只有 =default 析构」会被 special-member-functions 误伤，配置里用 `AllowSoleDefaultDtor: true` 豁免（见 sol-02.clang-tidy 注释）

## 练习 3：开启 ASan/TSan 构建（★★）

- **目标**：给同一份含「内存负载 + 并发负载」的程序配出 normal / ASan+UBSan / TSan 三种构建，并全部零报告跑过
- **要求**：
    - 程序含：vector 填充求和（内存负载）、两线程各累加一万次的计数器（并发负载，用 `std::scoped_lock`/`lock_guard` 保护）
    - 三条构建命令（或一个三目标 Makefile）：基线 / `-fsanitize=address,undefined -fno-sanitize-recover=all` / `-fsanitize=thread`
    - 用一句话解释：为什么 ASan 与 TSan 必须是两个独立二进制（ph15 3.5：都拦截同一批运行时函数，不能同进程共存）
- **验收**：三个二进制都输出 `sum=500500 counter=20000`、退出码 0、零 Sanitizer 报告（与 `sol-03-sanitizer-builds.cpp` 文件头一致）
- **提示**：Sanitizer 构建的用途是「在插桩下复跑负载」——代码没 bug 时报告就该是零，零报告是验收标准而非「没起作用」（参考实现 `sol-03-sanitizer-builds.cpp`）

## 练习 4：生成覆盖率报告（★★★）

- **目标**：走通 LLVM source-based coverage 三步流（插桩编译 → 运行收集 → llvm-cov 出报告），读懂报告并补测试消缺口
- **要求**：
    - 被测函数：多分支纯函数（如温度分档 `classify_temp`，边界 0/15/28 度）
    - 先只写「正常路径」测试，跑一次 `llvm-cov report`，记录未覆盖的分支；再补边界用例把 `classify_temp` 行/区域覆盖推到 100%
    - 用 `llvm-cov show --show-line-counts-or-regions` 看逐行计数，指认报告里「为什么测试文件的失败打印分支永远盖不到」
- **验收**：`llvm-cov report` 中 `classify_temp` 行覆盖 100%；能口头解释 TOTAL 行覆盖率为什么不是 100%（参考实现 `sol-04-coverage-report.cpp`，含三步命令）
- **提示**：覆盖率的价值是「发现没测到的路」，不是「追 100% 的数字」；失败打印分支盖不到是健康的（参考实现 `sol-04-coverage-report.cpp`）

## 练习 5：clang-format 格式化与格式门禁（★）

- **目标**：把一段乱格式代码用 clang-format 一次格式化，并用 `--dry-run --Werror` 搭起 CI 可用的格式门禁
- **要求**：把下面这段代码（保存为 `messy.cpp`）用 `clang-format --style=file:../examples/ex03.clang-format` 格式化；再用 `--dry-run --Werror` 验证产物零违规；说明这两个命令在 CI 里分别扮演什么角色

    ```cpp
    #include <cstdio>
    #include <vector>
    static int count_even(const std::vector<int>& values){
    int count=0;
    for(const int v:values){if(v%2==0){++count;}}
    return count;}
    int main(){
    const std::vector<int> values{1,2,3,4,5,6,7,8,9,10,11,12};
    std::printf("evens=%d\n",count_even(values));
    return 0;}
    ```

- **验收**：格式化产物 `clang-format --dry-run --Werror` 零输出、退出码 0；编译运行输出 `evens=6`（与 `sol-05-formatted.cpp` 一致）
- **提示**：格式化不需要手工对齐空格——工具的权威输出即标准，「格式化不应靠人工争论」（roadmap 必会概念）

> **提示**：练习 1~5 分别对应主文档 3.1（单元测试）/ 3.2（clang-tidy）/ 3.4（Sanitizer 工程化）/ 3.5（覆盖率）/ 3.3（clang-format）。覆盖率与 Sanitizer 的命令模板也可直接抄 examples/ex04、ex05 的 Makefile。
