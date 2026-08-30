# examples —— 模式匹配与枚举阶段完整示例

验证环境：rustc 1.92.0，零第三方依赖。编译命令统一 `rustc ex0X-*.rs -o /tmp/ex0X-*`，运行命令 `/tmp/ex0X-*`（输出到 `/tmp` 避免在仓库留下编译产物）。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-device-state.rs` | 设备状态建模：三种状态携带不同数据，match 一次性处理，matches! 判断可用性 | `rustc ex01-device-state.rs -o /tmp/ex01-device-state` | `/tmp/ex01-device-state` |
| `ex02-status-from-str.rs` | 字符串状态码改为 enum：from_str/as_str 双向转换，消除魔法字符串 | `rustc ex02-status-from-str.rs -o /tmp/ex02-status-from-str` | `/tmp/ex02-status-from-str` |
| `ex03-data-event.rs` | 数据事件处理器原型：五种事件类型 match 穷尽分发，matches! 统计分布 | `rustc ex03-data-event.rs -o /tmp/ex03-data-event` | `/tmp/ex03-data-event` |

三个示例均已在 rustc 1.92.0 下零警告编译并运行验证（已验证）。
