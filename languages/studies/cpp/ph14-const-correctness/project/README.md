# ph14 阶段项目：配置读取只读接口

对应 roadmap ph14 推荐项目第一个「配置读取只读接口」（第二个「设备状态快照模型」作为扩展方向实现——本项目"拷贝即只读快照"就是其最小形态）。项目是一个 **header-only 的只读配置库 + 演示 CLI + 自测**：把「接口全部 const」（Con.2）、「查询返回 `string_view` 观察不拥有」（SL.str.2）、「mutable 只用于物理状态（查询统计）」、「无 public 修改方法 → 改配置只能构造新对象（不可变快照）」（Con.4）四个本阶段核心规则固化成可复用的 `Config`，再用 demo 与自测证明这些性质成立。

## 需求

- `config.hpp` —— `Config`：构造时一次性解析 `key=value` 文本（跳过 `#` 注释与空行），条目用 `string_view` 指向对象自有的原始文本（零拷贝）；**全部 public 接口 const**：`get`（返回 `std::optional<std::string_view>`）/ `contains` / `size` / `keys`；查询统计 `lookup_count()` 是 mutable 物理状态；无任何 public 修改方法
- `demo.cpp` —— 演示 CLI：`config-demo <文件> [key ...]`，只给文件打印条目数与全部键，带 key 逐个查询（缺失显示 `<缺失>`）并打印查询统计；文件打不开走 stderr、退出码 1
- `test_config.cpp` —— 自测：编译期断言（**全部查询接口是 const 成员函数**、Rule of 0 拷贝/移动）+ 16 组运行期断言（7 个测试段落：解析、查询/缺失、contains/keys、const 接口完整性、**mutable 统计实测**、只读快照、**string_view 视图稳定性**）；普通版 + ASan 版都过
- `Makefile` —— 构建 + 测试（含 ASan 变体）+ 运行 + 清理，产物隔离 `build/`
- `samples/app.conf` —— 演示样例配置

## 功能清单

| 功能 | 说明 |
|------|------|
| 接口全 const | 全部查询成员函数标 const（Con.2）；成员指针类型 `static_assert` 编译期锁定 |
| 观察不拥有 | `get` 返回 `std::string_view`（SL.str.2），视图指向对象自有文本，查询零拷贝 |
| mutable 物理状态 | `lookups_` 统计是 mutable——const 接口内累加，不影响配置语义（逻辑 const） |
| 不可变快照 | 无 public 修改方法；「改配置」只能构造新对象；拷贝即只读快照（Rule of 0） |
| optional 缺失 | `get` 用 `std::optional<std::string_view>` 表达"可能不存在"（ph06 衔接） |
| 演示 CLI | 查询/缺失/统计一条链路；错误走 stderr 且退出码非零 |
| 自测 | 编译期 6 组静态断言 + 运行期 16 组断言（7 段落）；普通版 + ASan 版都过 |
| 产物纪律 | 产物全在 `build/`，`make clean` 即净，仓库不落二进制 |

## 验收标准

- [ ] `make` 构建成功且零警告；`./build/config-demo samples/app.conf host port missing_key` 输出 3 条查询（`missing_key = <缺失>`）与 `lookup_count = 3`
- [ ] `make test` 输出 `=== 自测结束：16 组检查，0 组失败 ===`、退出码 0；ASan 版同样通过
- [ ] `./build/config-demo samples/app.conf` 输出 `条目数 = 3` 与 `keys: host, port, debug`；`config-demo /tmp/不存在` 走 stderr、退出码 1
- [ ] 编译期断言生效：`Config::get/contains/size/keys` 的成员指针类型均为 const 限定（改动接口即编译失败）
- [ ] mutable 统计实测：const 对象上多次查询后 `lookup_count` 递增且值正确（自测 [5] = 7）
- [ ] `make clean` 后目录只剩源码与样例数据，无 `build/` 残留
- [ ] 仅用标准库；无裸 new/delete（R.11）；接口全部 const（Con.2）；无 `const_cast`（接口不需要撒谎）

## 扩展方向

- **设备状态快照模型**（roadmap 推荐项目②）：本项目"拷贝即只读快照"是快照模型的最小形态——进一步可做 `Snapshot` 类型别名 + 周期快照（`latest()` 返回 `Config` 拷贝），演示"不可变对象 + 值语义 = 天然线程安全读"（承接 ph08 并发编程）
- **哈希索引**：`entries_` 目前线性扫描，可换成 `std::unordered_map<std::string_view, std::string_view>`（承接 ph04 STL 阶段）——注意 string_view 作键时容器生命周期管理（键视图仍指向 `text_`）
- **只读迭代器**：把 `keys()` 的拷贝返回改为 const 迭代器（`begin()` / `end()`），零拷贝枚举（复用 ph04 的迭代器心智）
- **前缀/模糊查询**：加 `find_prefix(std::string_view)` 只读接口，返回 `std::vector<std::string_view>` 视图集合（练习 3 进阶玩法）
- **线程安全读**：`lookups_` 改成 `mutable std::atomic<std::size_t>`（承接 ph08 并发阶段的 atomic 基础），const 接口在并发读下无数据竞争

## 验证环境

- Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20 -Wall -Wextra` 双编译器零警告
- 构建：`make`；测试：`make test`（含 ASan 变体）；演示：`make run`；清理：`make clean`
- 验证状态：已验证（双编译器零警告、输出一致；普通版 + ASan 版自测 16 组检查 0 组失败；demo 三命令与错误路径退出码实测；clean 无残留）
