# ph12 阶段项目：值语义配置对象

对应 roadmap ph12 推荐项目第一个「值语义配置对象」（第二个「所有权关系重构练习」是扩展方向，见下）。项目是一个 **值语义的 Config 配置对象库 + CLI**：`Config` 用 Rule of Zero（成员全是 `std::string`/`std::vector<Entry>`）获得"拷贝即深拷贝、移动即廉价转移"的值语义；通过"**构造后不可变 + `with()`/`merged_with()` 按值返回新对象**"的设计，让借用式查询（`find()` 返回 `std::string_view`）在对象存活期内天然稳定——这正是本阶段「值语义通常让代码更简单」与「借用式接口」两个必会概念的落地产物，也是 roadmap 推荐项目②「所有权关系重构练习」（`sol-05` 的完整版形态）的延伸。

## 需求

- `config.h` / `config.cpp` —— 值语义配置对象：`parse()` 解析 `key=value` 文本（`#` 注释、空行、CRLF、首尾空白、缺 `=` 抛异常），`find()` 借用式查询（返回 `string_view`），`with()` / `merged_with()` 值语义变换（原对象不变，返回新对象）
- `main.cpp` —— CLI 入口：`load` / `get` / `clone` / `merge` 四个子命令，错误走 stderr 且退出码非零
- `test_config.cpp` —— 自测：10 组测试覆盖解析、查询、值语义、拷贝独立、移动转移、合并、借用稳定性
- `Makefile` —— 构建 + 测试（含 ASan 变体）+ 运行 + 清理，产物隔离 `build/`
- `samples/` —— 样例配置（engine.conf + overlay.conf），供 `make run` 演示

## 功能清单

| 功能 | 说明 |
|------|------|
| 值语义 | Rule of Zero：拷贝=深拷贝（互不影响）、移动=廉价转移；对象可直接放容器（`std::vector<Config>`） |
| 不可变 + 按值变换 | 没有 `set` 方法；`with(key, value)` / `merged_with(other)` 返回新 Config，原对象不变 |
| 借用式查询 | `find(key)` 返回 `std::string_view`，不拷贝不转移；Config 不可变 → 借用在其存活期内稳定 |
| 解析 | `key=value` 文本，支持 `#` 注释、空行、CRLF、键值首尾空白去除；缺 `=` 抛 `std::runtime_error` |
| 值语义合并 | `merged_with`：other 覆盖同名条目、保留双方独有条目，a/b 本身不变 |
| 按值返回 | `parse()` 返回 prvalue，C++17 保证省略，零拷贝零移动（ex03 规则的实际应用） |
| CLI | `load` / `get` / `clone` / `merge`；`clone` 现场演示"副本修改、原件不变" |
| 测试 | 10 组 33 条断言，普通版 + ASan 版都过；错误路径退出码非零 |
| 产物纪律 | 产物全在 `build/`，`make clean` 即净，仓库不落二进制 |

## 验收标准

- [ ] `make` 构建成功且零警告；`./build/cfgcli load samples/engine.conf` 输出 5 行配置
- [ ] `make test` 输出 `全部断言通过（10 组测试 / 33 条断言）`、退出码 0；ASan 版同样通过（无越界/use-after-free/double-free）
- [ ] `./build/cfgcli get samples/engine.conf server.port` 输出 `8080`；`get` 缺失键输出 stderr 错误、退出码 1
- [ ] `./build/cfgcli clone samples/engine.conf` 输出 `-- original (unchanged) --` 与带 `app.mode=debug` 的副本——证明值语义"修改副本不影响原件"
- [ ] `./build/cfgcli merge samples/engine.conf samples/overlay.conf` 输出 `server.port=9090`（被覆盖）与 `feature.fast_path=on`（并入），engine.conf 本身不变
- [ ] `make clean` 后目录只剩源码与样例数据，无 `build/` 残留
- [ ] 仅用标准库；无裸 new/delete（R.11）；Rule of Zero（C.20）；借用用 `string_view`/`const&`（R.3）；失败用异常/退出码表达（E.2）

## 扩展方向

- **所有权关系重构练习**（roadmap 另一个推荐项目）：本项目是"值语义拥有"形态；把它改造成"`std::unique_ptr<Config>` 独占拥有"形态（引用 `sol-05`），对比两种所有权模型的接口差异——值语义适合小配置随手拷贝，`unique_ptr` 适合大对象转移所有权
- **共享所有权**：用 `std::shared_ptr` 做"同一份配置多处共享只读"（承接 ph06 智能指针），讨论与值语义的取舍
- **原地修改版**：给 Config 加一个 `set()` 原地修改接口，然后讨论它为什么会破坏"借用稳定"（`string_view` 会因 `std::vector` 重分配而失效——与 ph04 迭代器失效同源）
- **嵌套结构**：支持 `section.key=value` 的多级分组，返回 `ConfigView` 借用式视图
- **CMake 版**：把 Makefile 换成 CMake 组织（复用 ph10 的多目标写法），加 `-fsanitize=address` 的 Debug 配置

## 验证环境

- Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra` 双编译器零警告
- 构建：`make`；测试：`make test`（含 ASan 变体）；演示：`make run`；清理：`make clean`
- 验证状态：已验证（10 组 33 条断言双编译器通过、ASan 无地址错误、CLI 四子命令实测、错误路径退出码正确、clean 无残留；泄漏检测 LSan 在 macOS 不支持，实测报 `detect_leaks is not supported on this platform`，泄漏项需 Linux 验证——如实标注）
