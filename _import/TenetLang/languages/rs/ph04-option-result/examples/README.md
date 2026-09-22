# examples —— Option 和 Result 阶段完整示例

验证环境：rustc 1.92.0，零第三方依赖。编译命令统一 `rustc ex0X-*.rs -o /tmp/ex0X-*`，运行命令 `/tmp/ex0X-*`（输出到 `/tmp` 避免在仓库留下编译产物）。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-unwrap-to-result.rs` | 把随意 unwrap 改为 Result 返回：`map_err` + `?` 传播，非法输入不再 panic | `rustc ex01-unwrap-to-result.rs -o /tmp/ex01-unwrap-to-result` | `/tmp/ex01-unwrap-to-result` |
| `ex02-option-config.rs` | 用 Option 处理可选配置项：`unwrap_or` / `as_deref` 提供默认值 | `rustc ex02-option-config.rs -o /tmp/ex02-option-config` | `/tmp/ex02-option-config` |
| `ex03-parse-pipeline.rs` | 一组解析函数用 `?` 串联：端口解析 + 范围校验 + 服务名映射 | `rustc ex03-parse-pipeline.rs -o /tmp/ex03-parse-pipeline` | `/tmp/ex03-parse-pipeline` |
| `ex04-config-parser.rs` | 配置解析器：Option/Result 贯穿、组合子链式转换、`?` 传播 | `rustc ex04-config-parser.rs -o /tmp/ex04-config-parser` | `/tmp/ex04-config-parser` |

四个示例均已在本环境（rustc 1.92.0）零警告编译并运行验证（已验证）。
