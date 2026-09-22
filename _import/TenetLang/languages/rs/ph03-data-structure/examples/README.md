# ph03 基础数据结构 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：rustc 1.92.0（无第三方依赖）。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-three-structs.rs | 三种结构体 + derive(Debug/Clone/PartialEq) | `rustc ex01-three-structs.rs -o /tmp/ex01` | `/tmp/ex01` |
| ex02-builder.rs | impl 方法 + 构建器模式（self 接收者） | `rustc ex02-builder.rs -o /tmp/ex02` | `/tmp/ex02` |
| ex03-vec-ops.rs | Vec 可变借用遍历 + 过滤 + 排序 | `rustc ex03-vec-ops.rs -o /tmp/ex03` | `/tmp/ex03` |
| ex04-hashmap-group.rs | HashMap entry API 分组统计 | `rustc ex04-hashmap-group.rs -o /tmp/ex04` | `/tmp/ex04` |
| ex05-index-registry.rs | 索引注册表（struct + Vec + HashMap 综合） | `rustc ex05-index-registry.rs -o /tmp/ex05` | `/tmp/ex05` |

全部已在本环境用 `rustc 1.92.0` 编译运行验证（零警告）。
