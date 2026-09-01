# examples —— 文件、网络与系统编程阶段完整示例

对应主文档 `13-file-network-sys.md` 第 6 章示例 1~9。分成两组：

- **ex01~ex06（纯 std）**：零第三方依赖，`rustc --edition 2021 -D warnings` 单文件编译，产物输出 `/tmp/`。
- **ex07~ex09（serde/clap）**：第三方 crate，独立 cargo 工程 `crates/`，经 rsproxy 国内镜像拉取。

验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4 / clap 4.6.6（**已验证**）。

## 第一组：纯 std（rustc 单文件，零依赖）

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-fs-read-write.rs` | 示例 1 | `std::fs` 速览：写/读字符串/读字节/追加写/元数据/复制；`ErrorKind::NotFound` 判定（实测：21 字节读回、`os error 2` 消息） | `rustc --edition 2021 -D warnings ex01-fs-read-write.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-bufio-lines.rs` | 示例 2 | 缓冲 I/O：`BufWriter` 写 1 万行（实测约 0.7ms）、`BufReader` 逐行读 + 迷你 wc（实测 10000 行 / 60000 词 / 298894 字节）、`read_line` 复用缓冲 | `rustc --edition 2021 -D warnings ex02-bufio-lines.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-path-pathbuf.rs` | 示例 3 | `Path`/`PathBuf`：借用 vs 拥有、`push`/`join` 拼接、部件提取、`components()` 分解、**push 绝对路径整体替换**陷阱（实测） | `rustc --edition 2021 -D warnings ex03-path-pathbuf.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-tcp-echo.rs` | 示例 4 | TCP：回显协议、读超时（实测 macOS `WouldBlock` + `os error 35`）、对端断开检测（`read` 返回 `Ok(0)`）、连接被拒（`ConnectionRefused` + `os error 61`） | `rustc --edition 2021 -D warnings ex04-tcp-echo.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-udp-datagram.rs` | 示例 5 | UDP：`send_to`/`recv_from`、**数据报边界保留**（两次 send 不会粘包，实测）、缓冲过小截断丢弃、`connect()` 设默认对端 | `rustc --edition 2021 -D warnings ex05-udp-datagram.rs -o /tmp/ex05` | `/tmp/ex05` |
| `ex06-args-manual.rs` | 示例 6 | 纯 std 手写命令行解析：`env::args`、长短选项、带值选项、位置参数、错误与用法提示（clap 的「裸机版」） | `rustc --edition 2021 -D warnings ex06-args-manual.rs -o /tmp/ex06` | `/tmp/ex06`（可加真实参数如 `-v -n 3 f.txt`） |

## 第二组：serde/clap（cargo 工程 `crates/`，已验证）

`crates/` 是独立 cargo 工程（`Cargo.toml` 声明 serde/serde_json/toml/clap 四个依赖，`Cargo.lock` 已提交锁定版本）。国内网络实测步骤：

```bash
# 1. 配置国内镜像（一次即可）：写入 $CARGO_HOME/config.toml
#    [source.crates-io]
#    replace-with = "rsproxy"
#    [source.rsproxy]
#    registry = "sparse+https://rsproxy.cn/index/"
# 2. 构建与运行（CARGO_TARGET_DIR 指向 /tmp，仓库零二进制残留）
cd examples/crates
CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex07-serde-json
CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex08-serde-toml
CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex09-clap-cli
```

| 文件 | 对应示例 | 说明 | 实测输出要点 |
|------|---------|------|-------------|
| `src/bin/ex07-serde-json.rs` | 示例 7 | serde derive：结构体 ↔ JSON、`#[serde(rename/default)]` 属性、解析错误行列定位（已验证 serde 1.0.229 / serde_json 1.0.151） | `invalid type: string "not-a-number", expected u16 at line 1 column 42`；往返一致断言通过 |
| `src/bin/ex08-serde-toml.rs` | 示例 8 | TOML 配置解析：嵌套表 → 嵌套结构体、序列化回 TOML（已验证 toml 1.1.4） | `[server]` 嵌套节往返；类型错误消息 `invalid type: integer '123', expected a string` |
| `src/bin/ex09-clap-cli.rs` | 示例 9 | clap derive：`struct` 即 CLI 定义、自动 `--help`、默认值与类型转换（已验证 clap 4.6.6）；用 `try_parse_from` 喂固定向量保证输出确定 | 缺参数 `error: the following required arguments were not provided:`；类型错误 `invalid value 'abc' for '--retries <RETRIES>'` |

## 运行注意事项

- **ex04 的端口与对端地址每次运行不同**（绑定 `127.0.0.1:0` 由 OS 分配空闲端口），其余输出确定。
- **ex04 的超时错误 kind 与平台相关**：macOS/Linux 实测为 `WouldBlock`（消息 `Resource temporarily unavailable (os error 35)`），Windows 为 `TimedOut`；代码用 `matches!` 同时接受两者。
- **ex06 第 1 段**打印真实 `env::args` 个数，随调用方式而变；第 2~3 段用固定向量演示，输出确定。
- 全部编译产物输出到 `/tmp/`（或 `CARGO_TARGET_DIR`），仓库内零二进制残留。

## 验证状态汇总

- 第一组：6 个示例均在本环境 `rustc --edition 2021 -D warnings` 编译零警告并运行验证（已验证：rustc 1.92.0）。
- 第二组：serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4 / clap 4.6.6 经 rsproxy 镜像成功拉取并完整编译运行（已验证），输出均为实测。
