# ph05 阶段项目：数据事件处理器（data-event-processor）

对应 roadmap ph05 推荐项目「数据事件处理器：处理写入、删除、更新、过期和告警事件」。用 `enum DataEvent` 建模五种数据事件，`match` 穷尽分发处理并输出结构化日志，按事件类型分组统计。

## 需求

数据平台会产生五类事件：写入（Write）、删除（Delete）、更新（Update）、过期（Expire）、告警（Alert）。本项目实现一个事件处理器：

- `enum DataEvent`：五种事件各携带类型化数据（key、value、版本号、时间戳、告警级别等），**非法事件组合不可表达**
- `process(&DataEvent) -> String`：`match` 穷尽分发，为每种事件生成结构化日志行
- `EventStats`：逐事件累计五类计数，`report()` 输出汇总
- `AlertLevel`：告警级别本身用 enum 表达（Info / Warning / Critical），替代魔法字符串

## 功能清单

- [x] `enum DataEvent` 五种变体：`Write { key, value }`、`Delete { key }`、`Update { key, value, old_version }`、`Expire { key, at }`、`Alert { level, message }`
- [x] `enum AlertLevel`（Info / Warning / Critical）：`from_str` 解析 + `Display` 输出，替代 `level: String`
- [x] `process()` 用 `match` 穷尽分发五种事件，`Write` / `Update` 输出 value 大小，`Alert` 按级别区分前缀
- [x] `EventStats::record()` 用 `match` 逐事件累计计数，`total()` 求总数
- [x] `main` 演示样例事件流：完整日志 + 汇总统计，零裸 `unwrap`
- [x] `#[test]` 单元测试覆盖：五种事件分发、计数准确性、`kind()` 标签、`AlertLevel` 解析与显示

## 验收标准

- [ ] `rustc data_event_processor.rs -o /tmp/data_event_processor` 编译零警告
- [ ] 运行 `/tmp/data_event_processor` 输出五种事件的结构化日志与事件统计
- [ ] `rustc --test data_event_processor.rs -o /tmp/data_event_processor_test` 编译测试零警告，`/tmp/data_event_processor_test` 全部测试通过
- [ ] 给 `DataEvent` 新增一个变体（如 `Merge`）后 `process` / `EventStats::record` 的 `match` 立即报 E0004——用编译器验证穷尽性

## 扩展方向

- 增加事件时间戳字段并支持按时间窗口分组统计（衔接 ph04 Option/Result 与后续集合阶段）
- 用 `HashMap` 按 key 聚合事件序列，实现"最近一次事件"查询（衔接 ph09 collections 阶段）
- 事件持久化：把结构化日志写入文件，做 append-only 事件流（衔接 ph13 文件与系统编程阶段）
- 告警升级策略：同一 key 连续 N 次 Alert 升级为 Critical（衔接 ph11 错误处理阶段）

## 验证环境

- rustc 1.92.0，零第三方依赖（单文件，无需 Cargo）
- 编译：`rustc data_event_processor.rs -o /tmp/data_event_processor`
- 运行：`/tmp/data_event_processor`
- 测试：`rustc --test data_event_processor.rs -o /tmp/data_event_processor_test && /tmp/data_event_processor_test`
- 验证状态：已验证（rustc 1.92.0）
