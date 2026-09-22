# exercises —— Option 和 Result 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：先做 1、4 热身，再做 2、3，最后挑战 5。本阶段主题是「消灭裸 unwrap」：除练习 4 的观察环节外，**所有练习的生产路径都不得出现裸 `unwrap()` / `expect()`**——失败用 `Result` 返回 + `?` 传播或 `match` 处理。

## 练习 1：猜数字输入改造（★）

**目标**：把 ph01/ph02 猜数字里 `guess.trim().parse().expect("...")` 的裸 panic 写法，改成返回 `Result` 并用 `match` 处理

**要求**：
- 写 `fn parse_guess(input: &str) -> Result<u32, String>`：空输入与非数字返回带原因的 `Err`
- `main` 里用 `match` 处理 `Ok` / `Err` 两条路径，程序不 panic
- 生产路径零 `unwrap` / `expect`

**验收**：`parse_guess("42")` → `Ok(42)`；`parse_guess("abc")` → `Err(带原因)` 且程序正常运行不崩溃；支持从命令行参数传入输入（无参数时用内置示例）。

## 练习 2：AppConfig 可选配置项（★★）

**目标**：为第 6 章示例 2 的 `AppConfig` 添加 `max_connections: Option<u32>`、`enable_tls: Option<bool>` 两个可选字段

**要求**：
- 新增 `effective_max_connections`（默认 100）、`effective_enable_tls`（默认 false）两个方法
- 可选字段一律用 `Option` 表达，读取默认值用 `unwrap_or` / `unwrap_or_else` / `as_deref` 组合子
- 生产路径零 `unwrap`

**验收**：未设置时默认值正确（100 / false）；设置 `Some(...)` 后 `effective_*` 返回设置值；`println!("{:?}", cfg)` 能打印全部字段。

## 练习 3：parse_endpoint 解析管线（★★）

**目标**：写 `parse_ip`、`parse_port`、`check_port_range` 三个返回 `Result` 的函数，用 `?` 串联成 `parse_endpoint(host: &str, port: &str) -> Result<(String, u16), String>`

**要求**：
- 每个函数各自返回带原因的 `Err`（空 host 报错、非数字端口报错、端口 0 报错）
- 串联处只写 `?`，不出现 `match` 嵌套
- 生产路径零 `unwrap`

**验收**：`("127.0.0.1", "8080")` → `Ok(("127.0.0.1", 8080))`；`("localhost", "0")` → `Err`（端口 0）；`("", "80")` → `Err`（空 host）；`("::1", "abc")` → `Err`（端口非数字）。

## 练习 4：unwrap 灾难现场（★）

**目标**：亲身体会"裸 unwrap 在 None 上 panic"，再改写为安全的 `match` / `unwrap_or`

**要求**：
- 先写 `let nums: Vec<i32> = vec![]; let first = nums.first().unwrap();` 运行，记录 panic 消息
- 再改写为 `match`、`unwrap_or`、`unwrap_or_else` 三个安全版本，覆盖 `Some` / `None` 两条路径

**验收**：能说出 panic 消息中的关键片段（`called \`Option::unwrap()\` on a \`None\` value`）；改写后对空列表与有值列表都能正常运行不崩溃。
**注意**：panic 版本仅供观察，提交的参考实现只含安全版本。

## 练习 5：扩展配置解析器（★★★）

**目标**：在第 6 章示例 4 的基础上，为 `Config` 添加 `host`（必需）和 `max_connections`（可选 u32，默认 100）字段及校验逻辑

**要求**：
- `host` 缺失报 `missing value for field: host`，空串报 `invalid host: ...`；`max_connections` 为 0 报错
- 错误消息必须带字段名（如 `invalid number for field: port`）
- `Result` + `?` 贯穿整条管线，生产路径零 `unwrap`

**验收**：缺 `host` → 报 `missing value for field: host`；`max_connections=0` → 报错；全部合法 → 输出含 `host` / `max_connections` 的完整 `Config`。
