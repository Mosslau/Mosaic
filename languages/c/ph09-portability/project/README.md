# ph09 阶段项目：跨平台日志库

对应 roadmap ph09 推荐项目第一个「跨平台日志库」：在示例 5（`examples/ex05-portable-log.c`）骨架基础上，补上线程安全、按大小轮转日志、级别过滤与固定宽度文件头——把本阶段"标准 C 为主干 + 平台差异收进封装"的写法做成一个完整库。

## 需求

实现一个线程安全、跨平台的日志库（`log.h` / `log.c`），配演示程序（`main.c`）：多线程并发写日志，支持级别过滤与按大小轮转，文件头用固定宽度字段 + `_Static_assert` 固化尺寸契约。平台差异（锁、getpid）用 `#ifdef` 收进实现内部，调用方头文件零 `#ifdef`。

## 功能清单

- [x] 线程安全：全部写路径持锁（POSIX 用 `pthread_mutex_t`，Windows 用 `CRITICAL_SECTION`，`#ifdef` 收敛成 `lock_t`）
- [x] 级别过滤：`log_set_level` 低于阈值的消息直接丢弃（默认 `LOG_INFO`）
- [x] 固定宽度文件头：12 字节（magic/version/flags/header_size/reserved），`_Static_assert(sizeof == 12)` 编译期固化
- [x] 按大小轮转：超过 `MAX_LOG_SIZE` 把当前文件改名为 `app.log.N`（序号递增、不覆盖，轮转不丢行），重开新文件写头
- [x] 追加模式重开不重复写文件头：已有内容只追加，不截断、不覆盖
- [x] 跨平台抽象演示：`lock_t` 与 `getpid` 两处差异全部收进 `log.c`，`log.h` 与 `main.c` 零 `#ifdef`
- [x] Makefile 增量构建：`CC`/`CFLAGS`/`OBJS` 变量分离，改一个 `.c` 只重编它

## 验收标准

- [ ] `make clean && make` 构建成功，`-Wall -Wextra -std=c11 -pthread` 零警告
- [ ] `make clean && make test`（即 `./logdemo`）输出 `全部日志文件行数合计: 802 (期望 802)` 与 `自检结果: 通过`，退出码 0（802 = 4 线程 × 200 条 INFO + 主线程 2 条；每线程 50 条 DEBUG 被级别过滤正确丢弃；轮转次数随行宽略有浮动，只要 ≥1 即通过）
- [ ] `touch log.c && make` 只重编 log.o（增量构建生效）
- [ ] 连续运行 20 次结果稳定（无数据竞争导致的偶发行数错误）
- [ ] `make clean` 清空全部产物（含轮转备份 `app.log.*`）

## 扩展方向（可选）

- 加备份保留上限（如只留最近 N 份，轮转时删除最旧备份）——为 roadmap 第 16 节（待建）存储引擎的日志/清理策略打底
- 用 `clang -fsanitize=thread`（TSan）验证无数据竞争 — 属于 ph11 Sanitizer / 静态分析 / 单元测试阶段的内容
- 日志文件头做字节序处理（`htonl` 等）以支持跨机器交换 — 属于 ph12 字节序、内存对齐与二进制格式解析阶段的内容
- 把 `log_set_level` 改成原子读写，支持运行时动态调整级别；`MAX_LOG_SIZE` 提为配置参数
- 另一推荐项目「协议字段类型定义库」由示例 1（ex01）与 exercises 练习 1 覆盖，可在此基础上扩展为完整消息类型集合

## 验证环境

- Apple clang 21.0.0（`cc`），macOS（Darwin arm64），`-Wall -Wextra -std=c11 -pthread`
- 构建：`make`；运行/测试：`make clean && make test`
- 验证状态：已验证（构建零警告；`make test` 自检通过、退出码 0；连续运行 20 次稳定；追加重开不重复写头、不丢数据；`_WIN32` 分支（`CRITICAL_SECTION`/`_getpid`）未在本环境验证——需 Windows）
