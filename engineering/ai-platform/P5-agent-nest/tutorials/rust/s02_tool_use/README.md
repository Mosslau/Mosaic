# s02: Tool Use — 多个工具 + 查表分发

在 s01 的 while 循环基础上，将硬编码的 `if name == "bash"` 换成 `match name { ... }` 查表分发。  
加一个工具 = 加一行 schema 定义 + 一个 handler 函数，不再需要碰循环体。

```
+----------+      +-------+      +---------+
|   User   | ---> |  LLM  | ---> |  Tool   |
|  prompt  |      |       |      |  map    |
+----------+      +---+---+      +----+----+
                      ^               |
                      |   tool_result |
                      +---------------+
                      (loop continues)
```

## 新增工具

| 工具 | 参数 | 用途 |
|------|------|------|
| `bash` | `command` | 执行 shell 命令（从 s01 携入） |
| `read_file` | `path`, `limit?` | 读文件，可选截断行数 |
| `write_file` | `path`, `content` | 写文件，自动创建父目录 |
| `edit_file` | `path`, `old_text`, `new_text` | 精确替换文本第一次出现的位置 |
| `glob` | `pattern` | 按 glob 模式匹配文件名 |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s02_tool_use
```

可选环境变量同 s01：

| 变量 | 作用 | 默认 |
|------|------|------|
| `EFFORT_LEVEL` | 思考强度 low/medium/high/xhigh/max | 不带该字段 |
| `MAX_TOKENS` | 输出 token 上限 | 8000 |
| `ANTHROPIC_BETA` | `anthropic-beta` 头透传 | 不带该头 |
| `S01_DEBUG` | =1 打印原始请求/响应 | 关闭 |

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **强类型参数** | 每个工具有独立 `#[derive(Deserialize)]` 结构体（`BashInput`、`ReadInput` 等），serde 做运行时类型校验，错误信息精确到字段 |
| **match 分发** | 编译器穷尽所有工具名，忘加分支编译不过 |
| **路径沙箱** | `safe_path()` 用 `canonicalize()` 解析符号链接和 `..`，确保 `../../etc/passwd` 被拦截 |
| **错误即文本** | 所有工具失败（参数校验、I/O 错误、路径逃逸）都返回字符串给模型，模型看到 `Error:` 会自行纠正 |

## 结构

```
s02_tool_use/
├── Cargo.toml          # 在 s01 基础上新增 glob = "0.3"
├── README.md
└── src/
    └── main.rs         # 1001 行：数据模型、5 个工具 handler、API 客户端、REPL
```

## 测试

```bash
cargo test -p s02_tool_use
```

19 个单元测试，覆盖：
- `truncate_lines` 截断边界（从 s01 携入）
- serde 契约模型（含 thinking signature round-trip）
- bash 黑名单 + 输出捕获
- `safe_path` 路径逃逸拦截
- read_file 行数截断 + 文件不存在报错
- write/read/edit/glob 各工具的 I/O 路径

## 与 Python 版对比

对照 `../../python/s02_tool_use/code.py`。s02 Rust 版在 s01 差异表基础上的新增差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 参数解析 | `input.get("path")` 手动取 | `serde_json::from_value::<T>(input)` 自动反序列化 |
| 工具分发 | `if-elif` 链 | `match name.as_str()` 编译期穷尽检查 |
| 路径安全 | `Path.resolve().relative_to(cwd)` | `canonicalize()`（消符号链接）+ `strip_prefix` 按组件判断 | 后者防同名前缀兄弟目录（/ws2 vs /ws）绕过 |
| edit_file 限制 | `replace(old, new, 1)` | 同 Python `replacen(..., 1)` |
| glob 安全性 | 无额外校验 | 每个匹配结果都过 `safe_path()` |
| write_file 回报 | `len(content)` = 字符数 | `.len()` = UTF-8 字节数 | 非 ASCII 内容数值不同，仅影响 "Wrote N bytes" 文案 |
| read_file limit=0 | 0 是假值 → 读全文 | `Some(0)` 视为限制 0 行 → 返回 "... (N more lines)" | 边界语义差异，正常用法（正整数 limit）一致 |

## 后续章节

| 章节 | 主题 | 在 s02 基础上增加 |
|------|------|--------------------|
| s03 | Permission | 执行前权限判断（三道闸门） |
| s04 | Hooks | 生命周期钩子 |
| ... | ... | ... |
| s20 | Comprehensive | 完整集成示例 |
