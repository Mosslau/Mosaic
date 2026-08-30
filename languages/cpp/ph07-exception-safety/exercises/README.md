# exercises —— 异常、安全与工程规范阶段练习

完成顺序建议：按 1~4 顺序完成。参考实现在 `sol-*` 文件中，做完再看。验证环境：Apple clang 17（g++ 兼容），`g++ -Wall -Wextra -std=c++17`。

## 练习 1：日志模块（★）

- **目标**：实现一个支持级别过滤的日志模块，为后续并发打底
- **要求**：
  - 级别：`enum class LogLevel { Debug, Info, Warn, Error }`
  - 级别过滤：低于最小级别的日志被丢弃
  - 时间戳：`YYYY-MM-DD HH:MM:SS` 格式
  - 线程安全预留：用 `std::mutex` + `std::lock_guard` 保护输出（本阶段单线程即可运行）
  - 支持输出到 stdout 或 stderr（构造/配置时指定）
- **验收**：`g++ -Wall -Wextra -std=c++17 -pthread` 零警告；设置最小级别为 Info 后 Debug 日志不输出、Info/Warn/Error 输出且含时间戳

## 练习 2：配置读取模块（★★）

- **目标**：读取 `key=value` 格式的配置文件，支持类型转换与默认值
- **要求**：
  - 逐行解析，跳过空行与 `#` 注释行，行内 `=` 前后空白可容忍
  - `get_string(key)` / `get_int(key, default)` / `get_double(key, default)` 三类取值接口
  - 文件不存在、格式非法（无 `=`）、值类型不匹配时用异常或错误码**明确表达**，不静默吞掉
  - 头文件自包含 + include guard，类名 PascalCase、成员尾部下划线
- **验收**：能读入含合法与非法行的配置文件，合法键正确取值、非法键走默认、非法格式抛 `std::runtime_error` 派生异常；`g++ -Wall -Wextra -std=c++17` 零警告

## 练习 3：错误码体系（★★）

- **目标**：设计一套集中式错误码，并提供错误码 → 异常的边界转换
- **要求**：
  - `enum class ErrCode : int` 集中定义（Ok/NotFound/InvalidParam/IoError 等）
  - 消息表：`err_code_to_string(ErrCode)` 返回可读消息，不散落 magic string
  - 自定义异常 `AppError : std::runtime_error` 携带 `ErrCode`
  - 边界转换函数：`void throw_if_error(ErrCode, const std::string& context)`，非 Ok 时抛 `AppError`
  - 底层函数返回 `ErrCode` 不抛异常，上层用转换函数统一转异常
- **验收**：底层返回非 Ok 时上层能捕获 `AppError` 并取出正确的 code 与消息；`g++ -Wall -Wextra -std=c++17` 零警告

## 练习 4：给已有代码补单元测试（★★★）

- **目标**：不依赖 gtest 等框架，用 `assert` + 手写 main 给练习 2 的配置模块补单元测试
- **要求**：
  - 正常路径：读合法配置、取 string/int/double、默认值生效
  - 异常路径：文件不存在、格式非法、类型不匹配分别触发预期异常
  - 用 try/catch 验证「该抛的真的抛了」（`bool caught = false; try {...} catch (...) { caught = true; } assert(caught);`）
  - 测试与实现分离：测试文件只依赖公开头文件，不碰内部实现
- **验收**：`g++ -Wall -Wextra -std=c++17` 编译测试文件零警告；运行后全部断言通过、退出码 0

> **提示**：练习 1~4 与 roadmap ph07「练习」小节的四项承诺一一对应。练习 4 依赖练习 2 的实现——先独立完成，再对照 `sol-*` 参考实现。
