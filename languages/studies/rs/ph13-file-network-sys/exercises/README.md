# exercises —— 文件、网络与系统编程阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 3 章 3.1~3.6 与第 6 章示例的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。全部为单文件、零第三方依赖（练习 4/5 的手写解析器是 serde/clap 的「裸机版」——理解原理后再用 crate），统一用 `rustc --edition 2021 -D warnings` 单文件编译。

## 练习 1：迷你 wc（★）

- **目标**：掌握 `BufReader` 逐行流式处理——内存占用与文件大小无关（对应 roadmap 练习「读取大文件并逐行处理」）
- **要求**：
  - 实现 `count(path) -> io::Result<Counts>` 统计行数/词数/字节数
  - 词数按 `split_whitespace` 口径；字节数含换行符（与 `wc -c` 一致）
  - 文件不存在时错误向上传播（`?`），由调用方打印 `ErrorKind`
- **验收**：`rustc --edition 2021 -D warnings sol-01-mini-wc.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出含 `行数 = 3, 词数 = 6, 字节数 = 64`、`不存在文件: kind=NotFound`、`断言通过`

## 练习 2：递归统计目录大小（★★）

- **目标**：`fs::read_dir` + `Path`/`PathBuf` 综合——递归遍历目录树
- **要求**：
  - 实现 `walk(path, stat)`：递归统计文件数、目录数（含根）、总字节数
  - 拼接路径一律用 `Path::join`/`PathBuf::push`，不拼字符串
  - `read_dir` 迭代器每项是 `Result<DirEntry>`，错误要处理
- **验收**：`rustc --edition 2021 -D warnings sol-02-dir-size.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出含 `Stat { files: 3, dirs: 2, bytes: 26 }`、`断言通过`

## 练习 3：TCP 时间戳服务器（★★）

- **目标**：`TcpListener`/`TcpStream` + 读超时 + 对端关闭检测（对应 roadmap 练习「写一个 TCP echo server」的变体）
- **要求**：
  - 服务端：接受连接后延迟 200ms 回发当前毫秒时间戳文本，然后主动关闭
  - 客户端：先设 50ms 读超时（预期第一次 `read` 超时），再放宽超时用 `read_to_string` 读到 EOF
  - 断言时间戳是 13 位纯数字；服务端与客户端在同一进程用线程演示
- **验收**：`rustc --edition 2021 -D warnings sol-03-tcp-time-server.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出含 `C. 首次 read 超时: kind=WouldBlock`（Windows 为 `TimedOut`）、`C. 收到时间戳 …（13 位）`、`断言通过`

## 练习 4：手写极简 JSON 解析器（★★★）

- **目标**：亲手实现「Tokenizer + 递归下降」的最小形态——理解 serde_json 替你做了什么（对应 roadmap 练习「解析 JSON 配置」；真实项目用 serde_json，见 examples/crates/ex07）
- **要求**：
  - 支持扁平对象 `{"k": 值}`，值为字符串/数字/布尔；解析结果存 `HashMap<String, Json>`（`Json` 用 enum 建模）
  - 错误消息带字节位置；空对象 `{}` 合法；对象后有多余内容要报错
  - 有意简化：不支持嵌套对象/数组/转义字符（聚焦解析器骨架）
- **验收**：`rustc --edition 2021 -D warnings sol-04-json-parser.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；输出含 `1. 解析成功: 4 个键`、`2. 空对象解析通过`、`3. 解析错误 @ 字节 7: 无法解析的值开头 Some('o')`、`解析错误 @ 字节 10: 对象后有多余内容`

## 练习 5：手写子命令式 CLI 解析器（★★）

- **目标**：把「解析结果建模为 enum」用起来——`tool add <名> [-n 次数] | list | remove <名>`（clap Subcommand 的裸机版）
- **要求**：
  - `enum Cmd { Add { name, count }, List, Remove { name } }`——非法组合无法表示
  - `add` 支持 `-n/--count` 带值选项（缺省 1）；`list` 不接受参数；`remove` 恰好 1 个参数
  - 每个错误路径给出具体消息 + 用法提示（未知子命令/缺参数/无效数字/多余参数）
- **验收**：`rustc --edition 2021 -D warnings sol-05-subcommand-cli.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；输出含 `1. add: Add { name: "写笔记", count: 3 }`、6 条错误路径演示、`断言通过`

> **提示**：练习 1~3 练 std I/O 与网络，练习 4~5 练「手写解析」理解 serde/clap 的原理。卡壳时先回读主文档 3.x 对应小节（3.1 std::fs、3.2 缓冲 I/O、3.3 Path、3.4 TCP/UDP、3.5 serde、3.6 命令行参数），最后再看 `sol-*`。
