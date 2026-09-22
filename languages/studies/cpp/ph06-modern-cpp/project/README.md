# ph06 阶段项目：配置管理模块

对应 Roadmap「6. 现代 C++（C++11~C++23）阶段」推荐项目第一个「配置管理模块」。用 `config.h` + `config.cpp`（实现）+ `main.cpp`（自测与 CLI）多文件组织，覆盖本阶段一半以上知识点：variant 类型安全多态、optional 表达缺失、string_view 只读视图、unique_ptr 管理缓冲、std::format 输出、enum 替代宏与 lambda。

## 需求

实现一个 key=value 配置文件管理模块：`Config` 类以 `std::unordered_map<std::string, Value>` 存键值，`Value` 是 `std::variant<bool, int64_t, double, std::string>`；查询用 `std::optional` 表达"配置项可能不存在"，拒绝 `-1`/空串哨兵值；加载用 `std::unique_ptr<char[]>` 管理读入缓冲（RAII 替代裸 `new[]`/`delete[]`），`std::string_view` 零拷贝视图逐行解析；`std::format` 输出配置清单。

## 功能清单

| 功能 | 说明 |
|------|------|
| 加载 | `load(path)`：支持 `#` 注释、空行、`key = value`/`key=value`、首尾空白；坏行（缺 `=`、key/value 为空）跳过；文件打不开抛异常 |
| 值类型推断 | 按内容自动推断 `bool` → `int64` → `double` → `string`（strtoll/strtod 全串匹配） |
| 类型化查询 | `get_int` / `get_double` / `get_bool` / `get_string`：缺失或类型不匹配返回 `nullopt` |
| 缺失表达 | `get(key)` 返回 `std::optional<Value>`，配合 `value_or(default)` 给默认值 |
| 配置清单 | `dump()`：`std::visit` 取出 variant 当前分支，`std::format` 输出 `key = value` |
| 只读视图 | 全部查询/加载参数用 `std::string_view`，不拷贝 |
| 缓冲管理 | `load` 用 `make_unique<char[]>` 读入整个文件，作用域结束自动释放（R.11 无裸 new/delete） |
| 自测 | `main.cpp` 无参数时生成 `sample.conf` 并跑 assert 自测；带参数时作为 CLI 加载并 dump |
| 样例数据 | `sample.conf`（无参数运行时生成，含注释/空行/四种类型/坏行） |

## 验收标准

- [ ] `g++ -Wall -Wextra -std=c++23 config.cpp main.cpp -o config_app` 编译零警告
- [ ] `./config_app` 运行输出「Config 自测全部通过（6 条配置）」且所有 assert 通过
- [ ] `./config_app sample.conf` 输出 6 条 `key = value` 配置清单，坏行被跳过
- [ ] 缺失配置项 `get_int("missing")` 返回 `nullopt`、`value_or(3)` 返回 3；类型不匹配（`get_int("host")`）返回 `nullopt`
- [ ] 代码遵循 C++ Core Guidelines：无裸 `new`/`delete`（R.11）、能 `const` 的成员函数全 `const`（Con.2）、参数用 `string_view`（SL.str.2）、`variant` + `optional` 表达类型安全语义

## 扩展方向

- 支持 `include "other.conf"` 嵌套加载与重复 key 覆盖——对齐 ph07 工程化配置库
- 用 `enum class ConfigSource`（文件/环境变量/命令行）替代固定文件路径——覆盖本阶段 enum class 知识点
- `dump()` 支持按 key 排序输出与 `--set key=value` 覆盖写入——对齐 ph09 配置中心客户端
- 加异常安全等级说明（ph07 详解 try/catch 与强保证）
- 值类型扩展 `std::vector<std::string>`（逗号分隔数组），练习 variant 多分支

## 验证环境

- Apple clang 17（g++ 兼容），标准 C++23（`<format>`/`<print>` 可用）
- 编译：`g++ -Wall -Wextra -std=c++23 config.cpp main.cpp -o config_app`
- 运行：`./config_app`（自测）/ `./config_app sample.conf`（CLI）
- 运行产物 `sample.conf` 为样例数据（保留在仓库）；`config_app` 验证后 `rm` 清理
- 验证状态：已验证
