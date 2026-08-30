# ph07 阶段项目：序列化接口 —— 统一编码 trait

对应 roadmap ph07 推荐项目「序列化接口：为日志记录、索引元数据、向量记录实现统一编码 trait」。在主文档示例 1 的基础上扩展为 CSV / JSON 两种编码策略、批量导出与单元测试。

## 需求

数据基础设施里，日志记录、索引元数据、向量记录三类数据都需要"落盘前编码为文本行"。本项目定义统一的 `Encode` 行为契约，让三类记录共享同一套编码管线：

- `Encode` trait：核心方法 `encode(&self) -> String`，附加默认实现 `encode_pretty`
- 三类记录：`LogRecord`（日志）、`IndexMeta`（索引元数据）、`VectorRecord`（向量记录）各自实现 `Encode`
- 两种编码策略：每种记录同时支持 CSV（逗号分隔）与 JSON（手写字符串拼接，零第三方依赖）——用**关联类型**或**带参方法**表达"编码格式"由实现者决定
- 泛型批量导出函数 `export_all<T: Encode>(items: &[T]) -> String`：只依赖 `Encode` 契约，新增记录类型零改动
- 用 `where` 子句写一个"可编码 + 可克隆"的批量快照函数 `snapshot<T>(items: &[T]) -> Vec<T>`

## 功能清单

| 功能 | 说明 |
|------|------|
| 统一 Encode trait | 核心 `encode()` + 默认 `encode_pretty()` |
| 三类记录实现 | LogRecord / IndexMeta / VectorRecord 各自 `impl Encode` |
| 双编码格式 | 每条记录支持 `encode_csv()` 与 `encode_json()` 两种输出 |
| 泛型批量导出 | `export_all<T: Encode>` 通吃三种类型 |
| where 子句快照 | `snapshot<T: Encode + Clone>` 演示多约束组合 |
| 单元测试 | `#[cfg(test)]` 模块覆盖 CSV/JSON 编码、批量导出、快照克隆 |

## 验收标准

- [ ] `rustc --test src/main.rs -o /tmp/proj_test && /tmp/proj_test` 全部测试通过（不少于 6 个用例）
- [ ] `rustc src/main.rs -o /tmp/proj && /tmp/proj` 编译零警告，输出三种记录、两种格式的编码结果
- [ ] 新增一个 `StorageRecord` 类型只需 `impl Encode`，`export_all` 零改动即可导出
- [ ] `snapshot` 的约束用 where 子句书写（`T: Encode + Clone`）

## 扩展方向

- 加 `decode` 反向解析（从 CSV 行还原记录），配合 ph10 错误处理返回 `Result`
- 用 `impl Iterator<Item = String>` 把批量导出改为惰性迭代（衔接 ph09 迭代器）
- 把 JSON 拼接换成 serde（ph06 已学依赖管理），对比手写与库的质量差异
- 编码输出写入文件（ph11 文件 I/O），做成真实的"落盘导出器"

## 验证环境

- rustc 1.92.0（macOS arm64），零第三方依赖
- 编译：`rustc src/main.rs -o /tmp/proj`
- 运行：`/tmp/proj`
- 测试：`rustc --test src/main.rs -o /tmp/proj_test && /tmp/proj_test`
- 验证状态：已验证（编译零警告，8 个单元测试全部通过）
