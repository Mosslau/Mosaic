# ph06 阶段项目：多模块日志分析工具（log-analyzer）

对应 roadmap ph06 推荐项目「多模块日志分析工具：parser、aggregator、cli 分层清楚」。用 workspace 组织三个 crate，形成 `log-cli → log-aggregator → log-parser` 的单向依赖链——每一层只依赖下一层，替换任一层的实现不影响其他层。

## 需求

解析制表符分隔的日志文件（每行 `ts\tlevel\tsource\tmessage`），统计并输出：

- **log-parser**（库）：解析层。`Level` 用 enum 表达（衔接 ph05），坏行（缺列、时间戳非法、级别未知、来源为空）跳过
- **log-aggregator**（库）：聚合层。按级别 / 来源统计条数、Error 占比、Top 来源，全部输出有序
- **log-cli**（二进制）：CLI 层。读取文件 → 调用 parser / aggregator → 打印报告；文件不存在时优雅报错（退出码 1）

## 功能清单

- [x] `Level` enum（Debug / Info / Warn / Error）：实现 `FromStr` 解析与 `Display` 输出，替代魔法字符串
- [x] `log_parser::parse` / `parse_all`：单行解析 + 坏行自动跳过，返回 `Option<LogLine>`（不 panic）
- [x] `log_aggregator::count_by_level`：按级别统计（BTreeMap 按键排序输出）
- [x] `log_aggregator::count_by_source`：按来源统计
- [x] `log_aggregator::error_rate`：Error 占比，空输入返回 `None`
- [x] `log_aggregator::top_sources`：条数降序的 Top 来源（条数相同按名称升序）
- [x] `log_cli` 入口：读文件 + 打印报告，默认读 `sample.log`，缺文件优雅报错
- [x] 13 个 `#[test]` 单元测试：覆盖解析边界、聚合语义、空输入、排序与截断
- [x] 样例数据 `sample.log`：含四种级别、三个来源与一条坏行

## 验收标准

- [ ] `cargo build --workspace` 编译零警告
- [ ] `cargo test --workspace` 全部测试通过
- [ ] `cargo run -p log-cli` 输出：总条数 9、按级别统计 `DEBUG: 1, INFO: 4, WARN: 2, ERROR: 2`、按来源统计 `api-server: 4, db-layer: 2, worker-1: 3`、Error 占比 `22.2%`
- [ ] `cargo run -p log-cli -- missing.log` 输出 `读取 missing.log 失败: ...` 且退出码为 1
- [ ] `cargo fmt --check` 零输出；`cargo clippy --workspace -- -D warnings` 零警告（质量门禁三连）

## 扩展方向

- 时间维度：按小时聚合趋势、过滤指定时间窗口（衔接 ph09 集合与迭代器）
- 来源排序参数化：`-s <n>` 指定 Top N、`-l <level>` 过滤级别（衔接 ph21 命令行参数成熟做法）
- 错误处理工程化：把 `Option` / `String` 错误升级为自定义 `Error` 枚举（衔接 ph11 错误处理阶段）
- 并发解析：多线程分块解析大文件（衔接 ph12 并发与异步阶段）
- 输出格式化：JSON 报告（features + 可选依赖，衔接本阶段示例 4 / 练习 4）

## 验证环境

- rustc 1.92.0 + cargo 1.92.0，纯标准库（零第三方依赖，无需网络）
- 目录：`project/log-analyzer/`（workspace 根）
- 构建：`cargo build --workspace`
- 运行：`cargo run -p log-cli [日志文件路径]`（缺省读 `sample.log`）
- 测试：`cargo test --workspace`
- 验证状态：已验证（rustc 1.92.0），验证后 `target/` 已清理
