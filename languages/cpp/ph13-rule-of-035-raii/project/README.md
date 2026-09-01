# ph13 阶段项目：RAII 系统资源库（安全句柄封装）

对应 roadmap ph13 推荐项目第一个「RAII 系统资源库」（第二个「安全句柄封装」本质就是本库的形态——`raii/c_file.h` 封装 `FILE*`、`raii/unique_fd.h` 封装 POSIX fd）。项目是一个 **header-only 的 RAII 资源库 + 演示 CLI + 自测**：把「资源生命周期绑定对象生命周期」（R.1）、「move-only 表达唯一所有权」（R.20）、「构造失败抛异常、析构永不抛」（E.2/E.16）、「异常路径不泄漏」（E.6）四个本阶段核心规则固化成可直接复用的两个头文件，再用 demo 和自测证明这些性质成立。

## 需求

- `raii/c_file.h` —— `CFile`：`FILE*` 的 RAII 封装。构造即 `fopen`（失败抛 `std::runtime_error`），析构自动 `fclose`；**move-only**（拷贝 `=delete`，移动 `noexcept`）；提供 `read` / `write` / `eof`
- `raii/unique_fd.h` —— `UniqueFd`：POSIX fd 的 RAII 封装。`-1` 表示"无句柄"；移动 `noexcept`（E.16），析构/`close` 永不抛；提供 `get` / `release` / `write_all` / `read_some`
- `demo.cpp` —— 演示 CLI：`write`（CFile 写文件）/ `read`（CFile 读文件）/ `copy`（UniqueFd 分块复制），全部资源由 RAII 托管
- `test_raii.cpp` —— 自测：编译期断言 move-only + 8 组运行期检查（写读往返、打开失败抛异常、移动转移、release、pipe 往返、**异常路径 fd 计数归零**、复制往返内容一致）
- `Makefile` —— 构建 + 测试（含 ASan 变体）+ 运行 + 清理，产物隔离 `build/`
- `samples/hello.txt` —— 演示样例文件

## 功能清单

| 功能 | 说明 |
|------|------|
| RAII 封装 | 资源获取即初始化（R.1）：构造成功才拿到对象，析构必然释放 |
| move-only | 拷贝被显式删除（所有权唯一），移动 `noexcept`；被移动的对象处于"空句柄"态，析构安全 |
| 构造失败 | `fopen` / `open` 失败抛异常（E.2），不产生半成品对象 |
| 析构不抛 | `fclose` / `close` 与析构永不抛异常（E.16），栈展开时不二次中断 |
| 异常安全 | 写入中途抛异常时句柄由析构兜底；自测用 `/dev/fd` 计数实测 300 次开合（含 200 次异常路径）fd 计数回到基线 |
| 演示 CLI | `write` / `read` / `copy` 三个子命令，错误走 stderr 且退出码非零 |
| 自测 | 编译期 `static_assert`（不可拷贝、可移动）+ 运行期断言；普通版 + ASan 版都过 |
| 产物纪律 | 产物全在 `build/`，`make clean` 即净，仓库不落二进制 |

## 验收标准

- [ ] `make` 构建成功且零警告；`./build/raii-demo write /tmp/x.txt && ./build/raii-demo read /tmp/x.txt` 输出 3 行写入与读回内容
- [ ] `make test` 输出 `=== 自测结束：N 组检查，0 组失败 ===`、退出码 0；ASan 版同样通过（无 double-free/use-after-free）
- [ ] `./build/raii-demo copy samples/hello.txt /tmp/copy.txt` 输出 `copy N 字节`，读回与源一致；`read /tmp/不存在` 走 stderr、退出码 1
- [ ] 异常路径实测：写已关闭的管道抛异常后，fd 由析构关闭（`fcntl(F_GETFD)` 返回 EBADF）；200 次异常路径后 fd 计数回到基线（零泄漏）
- [ ] `make clean` 后目录只剩源码与样例数据，无 `build/` 残留
- [ ] 仅用标准库 + POSIX 系统调用；无裸 new/delete（R.11）；析构/移动 `noexcept`（E.16）；失败用异常表达（E.2）

## 扩展方向

- **自定义 deleter 版**：把 `UniqueFd` 换成 `std::unique_ptr<int, FdCloser>` 形态（`ex04`/`ex05` 的写法），对比"手写 RAII 类"与"unique_ptr + 自定义 deleter"两种资源封装的取舍——手写类接口更清晰（`get`/`release`/`read_some`），unique_ptr 版省掉五函数
- **共享所有权**：加一个 `SharedFd`（`std::shared_ptr` + 自定义 deleter，承接 ph06 智能指针），讨论"唯一所有权 vs 共享所有权"在句柄场景的适用性
- **网络句柄**：把 `UniqueFd` 用于 socket（`connect` / `send` / `recv` 封装），连接失败抛异常、析构自动 `close`——是 ph09 网络编程的基础设施
- **CMake 版**：把 Makefile 换成 CMake 组织（复用 ph10 的多目标写法），加 `-fsanitize=address` 的 Debug 配置
- **锁的 RAII 对照**：`std::lock_guard` 就是"RAII 锁"，对比"资源句柄 RAII"与"锁 RAII"的相同骨架（承接 ph08 并发编程）

## 验证环境

- Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra` 双编译器零警告
- 构建：`make`；测试：`make test`（含 ASan 变体）；演示：`make run`；清理：`make clean`
- 验证状态：已验证（双编译器零警告；普通版 + ASan 版自测全部通过；异常路径 fd 计数归零实测；demo 三子命令与错误路径退出码实测；clean 无残留；泄漏检测 LSan 在 macOS 不支持，fd 泄漏改用 `/dev/fd` 计数实测）
