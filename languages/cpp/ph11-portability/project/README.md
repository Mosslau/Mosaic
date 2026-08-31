# ph11 阶段项目：跨平台文件工具库

对应 roadmap ph11 推荐项目第一个「跨平台文件工具库」（第二个「编译器兼容性实验项目」是扩展方向，见下）。项目是 **路径适配层（path_util）+ 文件信息层（file_info）+ CLI（main）** 三层结构：路径拼接/规范化/扩展名提取这类"平台差异明显"的能力用平台宏隔离成适配层，文件大小/时间戳/目录遍历这类"标准库已替你跨平台"的能力直接用 `std::filesystem`——这正是本阶段「跨平台代码应隔离平台相关层」与「能用 std::filesystem 就别手写」两个必会概念的落地产物。

## 需求

- `path_util.h` / `path_util.cpp` —— 平台适配层：`separator()` / `join()` / `normalize()` / `extension()`，**接口头零平台宏**，全部 `#if defined(_WIN32)` 只出现在 .cpp 实现里
- `file_info.h` / `file_info.cpp` —— 基于 `std::filesystem` 的可移植层：`file_info()`（大小/修改时间/是否目录）、`list_dir()`（目录条目排序）；失败返回 `std::optional`/空 vector（E.2：失败用返回值表达）
- `main.cpp` —— CLI 入口：`join` / `normalize` / `ext` / `info` / `ls` 五个子命令，错误走 stderr 且退出码非零
- `test_path.cpp` —— path_util 自测：**同一份测试代码编译两个平台分支**（POSIX 与 `-D_WIN32` 模拟 Windows），期望值用 `separator()` 动态构造，两个分支都成立
- `Makefile` —— 构建 + 测试 + 清理，产物隔离 `build/`

## 功能清单

| 功能 | 说明 |
|------|------|
| 路径拼接 | `join(base, rel)`：自动补/去分隔符（POSIX `/`，Windows `\`） |
| 路径规范化 | `normalize(path)`：合并重复分隔符、去结尾分隔符、空串返回 `.` |
| 扩展名提取 | `extension(path)`：普通扩展名（`.json`）、隐藏文件（`.gitignore` 返回空）、结尾点（`file.` 返回空） |
| 文件信息 | `info <path>`：大小（`uintmax_t` 固定宽度）+ 修改时间 + 文件/目录判断 |
| 目录遍历 | `ls <dir>`：`std::filesystem::directory_iterator` 列出条目并排序 |
| 平台自测 | `make test`：同一份测试跑 POSIX 与 `-D_WIN32` 两个分支，断言全过 |
| 产物纪律 | 全部产物在 `build/`，`make clean` 即净，仓库不落二进制 |
| 零警告 | `-std=c++20 -Wall -Wextra` 全目标编译零警告（Apple clang 21 与 Homebrew clang 21 双编译器验证） |

## 验收标准

- [ ] `make` 构建成功且零警告；`./build/ftool join data config.json` 输出 `data/config.json`
- [ ] `make test` 全部断言通过、退出码 0；`-D_WIN32` 分支输出 `separator = '\'`（POSIX 分支是 `'/'`），同一份测试代码两分支都过
- [ ] `./build/ftool normalize data//sub///x.txt` 输出 `data/sub/x.txt`；`ext data/config.json` 输出 `.json`
- [ ] `./build/ftool info build/ftool` 输出大小与修改时间；对不存在的路径输出 stderr 错误且退出码 1
- [ ] `./build/ftool ls build` 列出目录条目（排序）
- [ ] `make clean` 后目录只剩源码与 Makefile，无 build/ 残留
- [ ] 仅用标准库（`std::filesystem` + `<cstdint>`），无第三方依赖；无裸 new/delete（R.11）；失败用返回值表达（E.2）；接口头零平台宏

## 扩展方向

- **编译器兼容性实验项目**（roadmap 另一个推荐项目）：收集本阶段全部示例/练习的"哪家编译器、哪个 `-std` 下报什么错"记录，整理成自己的编译器差异速查表——本机只验证了 Apple clang 与 Homebrew clang，GCC/MSVC 需对应机器
- **CMake 版**：把 Makefile 换成 CMake 组织（复用 ph10 examples/ex06 的多目标写法），`-D_WIN32` 分支可进一步按平台选源文件
- **递归遍历**：`list_dir` 加 `recursive_directory_iterator` 支持子目录；加文件过滤（如只列 `*.log`）
- **路径层级操作**：`basename()` / `dirname()` 或相对路径解析（`a/../b` 折叠），注意折叠需按分隔符语义做，别用字符串替换
- 给 `file_info` 的错误分支加异常版本（`std::filesystem` 的 throwing 重载），对比 `optional` 与异常两种失败模型（承接 ph07 异常安全阶段）

## 验证环境

- Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra`
- 构建：`make`；测试：`make test`；示例运行：`make run`；清理：`make clean`
- 验证状态：已验证（编译零警告 + 22 条断言双分支通过 + CLI 各子命令实测 + clean 无残留；验证在 /tmp 副本与 build/ 中进行，仓库无产物残留；Windows 分支为 `-D_WIN32` 模拟验证，真 Windows/MSVC 未在本环境验证）
