# exercises —— Rule of 0/3/5 与 RAII 进阶阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），编译命令 `c++ -std=c++20 -Wall -Wextra`。练习 2/3/4 与 roadmap ph13「练习」小节的三个承诺（封装 FILE 指针、封装 socket 句柄、改造手动释放资源的旧代码）一一对应，练习 1/5 覆盖「学习内容」中的 Rule 抉择与异常安全资源释放。

## 练习 1：判断类是否需要自定义特殊成员函数（★）

- **目标**：对下列 4 个类逐个做出 Rule of 0/3/5 抉择（哪些特殊成员必须手写、哪些交给编译器），并用 `static_assert` + 运行期输出验证你的判断

  ```cpp
  // [A] 纯值成员
  struct Record { std::string key; std::vector<int> values; };
  // [B] 持有裸资源（FILE*，析构要 fclose）
  class LogFile { /* 你来定 */ };
  // [C] 含 std::mutex 成员
  class Counter { /* 你来定 */ };
  // [D] 多态基类 + 派生类
  class Shape { /* 你来定 */ };
  ```

- **要求**：
  - 对每个类写注释说明结论：Rule of 0 / Rule of 5 / move-only，以及依据（成员是否管理资源、是否持有裸资源、是否要当多态基类）
  - 用 `std::is_copy_constructible_v` / `std::is_move_constructible_v` 等特征断言验证；[C] 还应断言 `!is_copy_constructible`（mutex 隐式删除）
- **验收**：运行输出与 `sol-01-rule-quiz.cpp` 文件头一致（四个类的拷贝/移动特征 0/1 值）
- **提示**：判断口诀——① 成员是否自己管理资源？是 → Rule of 0；② 类自己持有裸资源？是 → 析构 + 拷贝/移动（C.21），资源所有权唯一时通常 move-only；③ 要当多态基类？是 → public virtual 析构（C.35），派生类回到 Rule of 0

## 练习 2：把 FILE* 封装成 RAII 类（★★）

- **目标**：实现一个 `TextFile` 类封装 `FILE*`：move-only、构造失败抛异常、析构自动 `fclose`、支持写多行与读回校验
- **要求**：
  - 构造：`fopen` 失败抛 `std::runtime_error`（E.2）；析构：`fclose`（E.16，不抛）；拷贝 `=delete`；移动 `noexcept`（窃取指针 + 源置空）
  - `put(line)` 写一行；`getline()` 读一行；`eof()` 查询
  - 写 5 行到临时文件再读回，逐行校验内容一致
  - **异常路径实测**：写入中途抛异常，验证 `close` 由析构兜底（打印顺序：close 先于 catch）
- **验收**：运行输出与 `sol-02-file-raii.cpp` 文件头一致（含异常路径的 close 时序）
- **提示**：被移动的源对象要置空指针，否则析构 double close；`fputs` 失败用 `EOF` 判断（参考实现 `sol-02-file-raii.cpp`）

## 练习 3：把 POSIX fd 封装成 RAII 句柄（★★★）

- **目标**：实现 `UniqueFd` 封装 POSIX fd（用 socketpair 演示）：move-only、析构 `close`、**用 `fcntl(F_GETFD)` 实测句柄确已关闭**、异常路径不泄漏
- **要求**：
  - `-1` 表示"无句柄"（fd 合法值从 0 起，不能套用指针的 `nullptr` 语义）；移动 `noexcept`；`release()` 放弃所有权
  - 用 `socketpair` 建立双向通道：一端 `write_all`、另一端 `read_some` 往返
  - 移动后旧句柄失效、新句柄接管；作用域结束后用 `fcntl(F_GETFD)` 实测原 fd 已 EBADF
  - **异常路径**：写已关闭的对端（先手动 `close` 对端），观察 EPIPE 异常与析构兜底
- **验收**：运行输出与 `sol-03-fd-raii.cpp` 文件头一致（fd 编号 3/4/5/6 每次运行可能不同，属正常）
- **提示**：先 `std::signal(SIGPIPE, SIG_IGN)` 否则进程直接被 SIGPIPE 杀死；`fcntl(fd, F_GETFD) == -1 && errno == EBADF` 即已关闭（参考实现 `sol-03-fd-raii.cpp`）

## 练习 4：改造手动释放资源的旧代码（★★★）

- **目标**：给定"malloc + 多处 early return"的 legacy 函数（每条错误路径都泄漏），用 `unique_ptr` + 自定义 deleter 改造，并用计数器证明每条路径都平衡
- **要求**：
  - 用计数分配器（`malloc`/`free` 各 `++` 计数器）把"泄漏"变成可观测数字
  - 改造后三条路径（正常 / step2 失败 / step3 失败）逐一运行，输出 `alloc=X free=Y 差值=0`
  - 注释里回答：旧代码 3 条路径要几组手动 `free` 配对？RAII 版要几组？
- **验收**：运行输出与 `sol-04-legacy-refactor.cpp` 文件头一致（三条路径差值全为 0）
- **提示**：`std::unique_ptr<void, CountedFree>` + 仿函数 deleter（`ex04` 的写法）；提前 `return` 时 deleter 自动兜底，无需逐路径配对（参考实现 `sol-04-legacy-refactor.cpp`）

## 练习 5：异常安全的资源类（★★★ 综合题）

- **目标**：实现 `Buffer` 资源类并验证两条性质——(a) 构造函数获取两个资源，第二个失败时第一个不泄漏；(b) `assign()` 提供**强保证**（copy-and-swap），失败时目标对象原封不动
- **要求**：
  - 成员用 `std::unique_ptr<Res>`（R.11 无裸 new/delete），`Res` 带静态存活计数（ctor `++`、dtor `--`）
  - 构造第二个资源失败时抛异常，实测存活计数归零（已构造成员逆序析构）
  - `assign` 用"按值传参 + `noexcept` swap"（copy-and-swap）；用"按需抛异常"的拷贝构造模拟失败，实测目标 `size` 不变
- **验收**：运行输出与 `sol-05-exception-safety.cpp` 文件头一致（构造失败存活=0；强保证失败时 `dst.size=64` 原封不动）
- **提示**：强保证的关键是"可能失败的操作都在 swap 之前完成"；swap 标记 `noexcept`（E.16）；参考实现 `sol-05-exception-safety.cpp`

**提示**：参考实现仅作对照，先独立完成再复盘。sol-* 文件头都带实测输出与验证状态（两种编译器一致）；练习 3 的 fd 编号、练习 5 的存活计数均实测记录。进阶玩法（可选）：把练习 4 的改造对象换成 `char*` 多资源场景再压一组路径；给练习 2 加一个"写 N 行到 10 万行"的规模测试观察 RAII 的稳定性。
