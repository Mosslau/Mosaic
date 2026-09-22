# ph03 阶段项目：RAII 文件类

## 需求

对应 Roadmap「3. C++ 内存模型阶段」推荐项目第一个。实现一个 RAII 文件类 `WalFile`，封装 `std::FILE*`：追加写入、flush、自动关闭，禁止拷贝、允许移动。采用多文件组织：`wal_file.h`（声明 + include guard）、`wal_file.cpp`（实现）、`main.cpp`（演示入口 + 断言式测试）。

## 功能清单

- [ ] `WalFile(path)` 构造：以追加模式 `"ab"` 打开文件
- [ ] `~WalFile()` 析构：自动 `fflush` + `fclose`
- [ ] 禁止拷贝（`= delete`）、允许移动（移动后源对象句柄置 `nullptr`）
- [ ] `append(key, value)`：追加一行 `key\tvalue`
- [ ] `flush()`：显式刷盘
- [ ] `explicit operator bool()`：查询是否成功打开

## 验收标准

- `g++ -Wall -Wextra -std=c++17 main.cpp wal_file.cpp -o wal_file` 编译零警告
- 运行 `./wal_file` 全部断言通过
- 作用域结束文件自动关闭，回读内容与写入一致
- 移动后源对象 `operator bool()` 为 `false`

## 扩展方向（可选）

- 用异常替代 `operator bool` 表达打开失败 —— 属于 ph07 异常阶段
- 加 `sync()`（`fsync`）保证落盘，对应数据库 WAL 崩溃恢复 —— 属于 ph22 存储引擎阶段
- 用 `std::unique_ptr<FILE, decltype(&fclose)>` 实现 Rule of 0 版本 —— 属于 ph13 RAII 进阶阶段

## 验证环境

Apple clang 17.0.0（g++ 兼容），标准 C++17。编译：`g++ -Wall -Wextra -std=c++17 main.cpp wal_file.cpp -o wal_file`；运行：`./wal_file`。已在本环境验证。
