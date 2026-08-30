# 阶段项目：工程化配置库

对应 roadmap ph07 推荐项目第一个「工程化配置库」。拆成 error/config/logger 三模块 + 自测，覆盖本阶段几乎全部知识点：错误码体系、异常分层、RAII、noexcept、头文件规范、命名空间分层、日志接入。

## 需求

- `error.h`/`error.cpp` —— 错误码体系：`ErrCode` 枚举集中定义、消息表、`AppError` 异常、`throw_if_error` 边界转换
- `config.h`/`config.cpp` —— INI/键值配置：文件加载、key=value 解析、类型转换（string/int/double）、默认值、非法格式抛异常
- `logger.h`/`logger.cpp` —— 日志模块：级别过滤、时间戳、线程安全预留
- `main.cpp` —— 自测入口：用 assert 覆盖正常路径与异常路径
- `Makefile` —— 管理全部模块构建（增量构建生效）

## 功能清单

| 功能 | 说明 |
|------|------|
| 错误码体系 | `enum class ErrCode` + 消息表 + `AppError` + 边界转换 |
| 配置解析 | key=value、跳过空行与 `#` 注释、行内空白容忍 |
| 类型转换 | `get_string` / `get_int` / `get_double`，非法值抛 `ConfigError` |
| 日志 | 级别过滤、时间戳、`std::mutex` 预留 |
| RAII | 文件流 RAII、无裸 new/delete、资源随对象析构 |
| 头文件规范 | 自包含 + `#pragma once` + 命名空间分层 |
| 自测 | assert 覆盖正常路径、文件不存在、格式非法、类型不匹配 |

## 验收标准

- [ ] `make` 构建成功、`./config_app` 运行全部自测通过、退出码 0
- [ ] `touch config.cpp && make` 只重编 config.o（增量构建生效）
- [ ] 文件不存在、格式非法、类型不匹配分别抛出 `ConfigError` 且消息含上下文
- [ ] `g++ -Wall -Wextra -std=c++17` 编译零警告
- [ ] 无裸 new/delete；析构不抛异常；移动/swap 标 noexcept

## 扩展方向

- 加 `config.get_bool(key, default)` 与 `config.get_list(key)`（为 ph09 文件/网络系统编程打底）
- 加 `--config <path>` 命令行参数解析（复用 ph05 参数处理）
- 把 logger 换成异步输出（为 ph08 并发编程打底）
- 加 JSON/YAML 后端（为 ph17 序列化打底）

## 验证环境

- Apple clang 17（g++ 兼容），`-Wall -Wextra -std=c++17`
- 构建：`make`
- 运行：`./config_app`
- 清理：`make clean`
- 验证状态：已验证
