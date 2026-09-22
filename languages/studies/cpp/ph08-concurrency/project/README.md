# 阶段项目：异步日志系统

对应 roadmap ph08 推荐项目第一个「异步日志系统」（第二个「多线程任务调度器」按规范选做、未落地）。业务线程把日志投到有界内存队列，后台线程批量写出，覆盖本阶段几乎全部知识点：有界队列 + 双谓词等待、锁外执行、jthread + stop_token 协作取消、atomic 统计计数、RAII 生命周期管理。

## 需求

- `async_logger.h` / `async_logger.cpp` —— 异步日志核心：级别过滤、有界队列投递（满则丢弃并计数）、后台 `jthread` 批量写出、停止时排空残余日志
- `main.cpp` —— 自测入口：4 个生产者线程并发写 1000 条日志，校验统计与文件行数
- `Makefile` —— 管理多文件构建（增量构建生效）

## 功能清单

| 功能 | 说明 |
|------|------|
| 级别过滤 | `enum class LogLevel`，低于最小级别的日志直接丢弃（atomic 读取，无需加锁） |
| 有界队列 | 容量固定，满则丢弃并计数——日志系统绝不阻塞业务线程 |
| 批量写出 | 后台线程被唤醒后一次排空整批，减少 IO 次数 |
| 协作取消 | `condition_variable_any::wait(lock, stop_token, pred)` 收到停止请求立即醒来 |
| 优雅关闭 | 停止请求 → 排空残余队列 → flush → jthread 析构自动 join，不丢已入队日志 |
| 统计 | `produced / written / dropped` 三个 atomic 计数器 |
| 线程安全 | 互斥锁保护队列；时间戳用 `localtime_r`（`std::localtime` 非线程安全） |

## 验收标准

- [ ] `make` 构建成功、`./async_logger_demo` 运行全部断言通过、退出码 0
- [ ] 4 线程并发投递 1000 条：文件行数恰好 1000，`dropped == 0`
- [ ] `touch async_logger.cpp && make` 只重编对应目标（增量构建生效）
- [ ] `-std=c++20 -Wall -Wextra -pthread` 编译零警告
- [ ] `-fsanitize=thread` 构建运行无数据竞争报告
- [ ] 无裸 new/delete；锁全部走 RAII（lock_guard / unique_lock）

## 扩展方向

- 加定时 flush（后台线程每 N ms 主动醒一次：`wait_for` + stop_token）
- 加双缓冲（前台队列 / 写出队列交换），进一步缩短持锁时间
- 队列满时改为阻塞等待（加 `not_full_` 第二个条件变量，练习 3 的模式）
- 输出目标抽象成接口（文件 / 控制台 / 网络），为 ph09 文件、网络与系统编程阶段打底
- 按大小滚动日志文件（需要 std::filesystem，属于 ph09 的内容）

## 验证环境

- Apple clang 21 / Homebrew clang 21.1.8（g++ 兼容），`-Wall -Wextra -std=c++20 -pthread`
- 构建：`make`
- 运行：`./async_logger_demo`（或 `make run`）
- 清理：`make clean`
- 验证状态：已验证（含增量构建与 TSan 检查）
