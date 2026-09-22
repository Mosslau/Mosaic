# ph04 阶段项目：配置解析器（config-parser）

对应 roadmap ph04 推荐项目「配置解析器：读取端口、超时、开关项，输出结构化配置或明确错误」。用 Cargo 工程组织（lib + bin），生产路径零裸 unwrap，自定义错误类型贯穿全流程。

## 需求

实现一个命令行配置解析器：从多行文本（支持 `key=value` 行、`#` 注释行、空行）解析出结构化 `Config`：

- `port`：必需 u16，取值 1~65535
- `timeout`：可选 u32，默认 30（秒）
- `debug`：可选 bool，默认 false（接受 true/false/1/0/yes/no）
- `log_level`：可选字符串，默认 "info"

解析失败时返回**带字段名的明确错误**（自定义 `ConfigError`，实现 `Display` + `std::error::Error`），错误消息可直接展示给用户。

## 功能清单

- [x] 从多行文本解析 `key=value` 配置，跳过空行与 `#` 注释
- [x] 必需字段缺失报 `MissingField`，错误带字段名（如 `缺少必需字段: port`）
- [x] 数字字段非法报 `InvalidNumber`，含字段名、原始值与解析原因
- [x] 布尔字段非法值报 `InvalidBool`，含字段名与可接受值列表
- [x] 未知字段报 `UnknownKey`（配置拼写错误即时暴露）
- [x] 端口 0 报 `InvalidValue` 语义校验错误
- [x] 可选字段缺省应用默认值：timeout=30、debug=false、log_level="info"
- [x] 自定义 `ConfigError` 实现 `Display` + `std::error::Error`
- [x] `#[test]` 单元测试覆盖 11 个用例（正常路径 / 默认值 / 各类错误路径）

## 验收标准

- [ ] `cargo build` 零警告，`cargo test` 全部通过（生产代码与测试均无裸 unwrap）
- [ ] 合法输入（含注释、空行）输出结构化 Config
- [ ] 缺 `port` / `port=0` / `timeout=abc` / `debug=maybe` / `unknown_key=1` 分别给出带字段名的明确错误
- [ ] 任意输入都不 panic，错误路径以非零退出码结束

## 扩展方向

- 支持 INI 风格的 `[section]` 分组与从文件路径读取（衔接 ph13 文件与系统编程阶段）
- 用 `thiserror` 派生宏替代手写 `Display` / `Error` impl（衔接 ph11 错误处理与工程质量阶段）
- 支持环境变量覆盖默认值、`log_level` 枚举值校验、`max_connections` 等更多字段

## 验证环境

- rustc 1.92.0（cargo 1.92.0），edition 2021，零第三方依赖
- 编译：`cargo build`
- 测试：`cargo test`
- 运行：`cargo run`（stdin 喂入多行配置）；`cargo run -- 'port=8080'`
- 验证状态：已验证（rustc 1.92.0）
