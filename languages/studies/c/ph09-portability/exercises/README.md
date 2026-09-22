# exercises —— C 标准、编译器与可移植性阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~3 顺序完成。三题与 roadmap ph09「练习」小节一一对应。参考实现在 `sol-*` 文件中，做完再看。

## 练习 1：用 stdint.h 重写协议字段定义（★★）

- **目标**：把用 `int`/`long` 声明的协议头改成 `uint16_t`/`uint32_t` 固定宽度，并固化尺寸契约
- **要求**：
  - 定义一个消息头结构体，所有字段用 stdint.h 的固定宽度类型（如 magic/version/flags/seq/length）
  - 用 `_Static_assert` 断言结构体总尺寸（先算清对齐填充，别想当然）
  - 提供 pack/unpack 函数：逐字段 `memcpy` 进字节缓冲（不直接写结构体），带缓冲容量检查
  - 打印字段一律用 `<inttypes.h>` 的格式宏（`PRIx16`/`PRIx32` 等），禁止写死 `%d`/`%ld`
- **验收**：`cc -Wall -Wextra -std=c11` 零警告；运行输出打包字节数与往返一致（pack 后 unpack 各字段相等），退出码 0

## 练习 2：为 Windows/Linux 分别封装路径分隔符（★★）

- **目标**：把路径分隔符、目录创建这类平台差异收敛成宏/函数，业务代码零 `#ifdef`
- **要求**：
  - `PATH_SEP` 用 `#ifdef _WIN32` 区分（`"\\"` vs `"/"`）
  - 封装目录创建：POSIX `mkdir(path, 0755)` 有权限位、Windows `_mkdir(path)` 只有一个参数——用宏或函数统一（注意 `#include` 差异：`<sys/stat.h>` vs `<direct.h>`）
  - 文件删除用 ISO C 的 `remove()`（天然跨平台，无需封装）
  - 演示流程：创建目录 → 用封装的路径拼接写一个文件 → 删除文件
- **验收**：`cc -Wall -Wextra -std=c11` 零警告；运行后目录创建成功、文件写入并删除成功（POSIX 分支实测，Windows 分支代码正确给出但需 Windows 验证）

## 练习 3：尝试用 GCC 和 Clang 编译同一项目（★）

- **目标**：同一份源码换编译器、换 `-std=` 编译，体会编译器差异与标准版本门控
- **要求**：
  - 用条件编译打印当前编译器（`_MSC_VER`/`__clang__`/`__GNUC__`，注意 Clang 同时定义 `__GNUC__`，判断顺序不能反）
  - 用 `__STDC_VERSION__` 门控：C99 及以后用"for 循环内声明"，否则回退到 C89 前置声明写法——同一份源码两种模式都要能编译
  - 给某个 GCC/Clang 扩展（如 `__builtin_expect`）用 `#ifdef` 包一层并给非 GCC 家族的回退实现
- **验收**：`gcc -Wall -Wextra -std=c11` 与 `clang -Wall -Wextra -std=c11` 均零警告（macOS 上 gcc 即 Apple clang，Linux 上同理）；`-std=c89 -pedantic-errors` 严格模式也能零警告编译并走 C89 回退分支；运行输出随编译器/标准版本变化

> **提示**：练习 1~3 分别对应主文档 3.5/3.4+3.3/3.2+4.3 的知识——先独立完成，再对照 `sol-*` 复盘。练习 3 若在 Linux 上做，`gcc` 是真实 GCC，输出会与 macOS 的 Apple clang 不同，这正是要观察的差异。
