# Rust 文件、网络与系统编程阶段

> 面向数据基础设施与命令行工具方向：本阶段把 Rust 程序接入真实世界——文件系统（`std::fs`/`std::io`）、跨平台路径（`Path`/`PathBuf`）、TCP/UDP 网络、JSON/TOML 序列化（serde）与命令行解析（clap），并落地「资源释放由 Drop 管理」的 RAII 心智。

## 1. 概述

Rust 文件、网络与系统编程阶段对应 roadmap 第 13 节，目标是**能使用 Rust 处理文件、路径、网络和常见系统资源**。具体定位是：**用 `std::fs` 做文件读写与元数据、用 `BufReader`/`BufWriter` 做缓冲 I/O、用 `Path`/`PathBuf` 写跨平台路径、用 `TcpListener`/`TcpStream`/`UdpSocket` 写真实网络程序（含超时与断连处理），再用 serde 落地 JSON/TOML 序列化、用 clap 落地命令行解析**。本阶段承接 ph04 Option 和 Result 阶段与 ph11 错误处理与工程质量阶段（`io::Result<T>` 是 `Result` 最经典的应用场）、ph08 生命周期阶段（I/O 里的引用返回会撞上 E0515）、ph12 并发与异步阶段（多客户端服务器每连接一线程）；并为 ph19 内存布局、零拷贝与协议解析阶段与 ph25 数据基础设施阶段铺路。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件 | `std::fs` 一键读写、`OpenOptions` 精细控制、元数据、`read_dir` 遍历（3.1） |
| I/O 抽象 | `Read`/`Write`/`BufRead` trait、`BufReader`/`BufWriter` 缓冲、`flush` 时机、E0515 实测（3.2） |
| 路径 | `Path` 借用视图 vs `PathBuf` 拥有拼接、`push` 绝对路径陷阱、`components()`、跨平台（3.3） |
| 网络 | `TcpListener`/`TcpStream` 回显、读超时、`Ok(0)` 断连检测、连接被拒；`UdpSocket` 数据报边界（3.4） |
| 序列化 | serde derive + serde_json/toml：`#[serde(rename/default)]`、错误行列定位（**已验证 serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4**）（3.5） |
| 命令行 | `std::env::args` 手写解析（裸机版）→ clap derive（**已验证 clap 4.6.6**）（3.6） |

这个阶段只涉及**同步阻塞式**的文件与网络系统编程、serde/clap 的基础用法，**不涉及异步 I/O 与 tokio 深入（`tokio::fs`/`tokio::net`）、unsafe 与裸指针、宏与元编程（derive 宏只「用」不「写」）、性能剖析与零拷贝协议解析和 FFI 跨语言调用** — 那些是 ph12 并发与异步阶段、[ph14 Unsafe Rust 与安全抽象阶段](../ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md)、ph15 宏与元编程阶段、ph19/ph23 阶段的内容（ph15/ph19/ph23 目录待建）。承接 [ph11 错误处理与工程质量阶段](../ph11-error-handling/11-error-handling.md)：`io::Error` 的结构化判定（`ErrorKind`）是 ph11 错误分类思想的标准库落地；承接 [ph12 并发与异步阶段](../ph12-concurrency-async/12-concurrency-async.md)：本阶段的网络示例都是**阻塞式**的，异步网络（tokio 版 `TcpListener`）见 ph12 示例 9。

## 2. 来源与演变

Rust 的 I/O 故事分两层：**标准库给最小完备抽象，生态给格式与便利**。`std::fs`/`std::io`/`std::net` 随 Rust 1.0（2015）进入标准库，设计哲学是**「syscall 的薄封装 + trait 组合」**——`Read`/`Write` 两个 trait 抽象一切字节源/汇，`File`、`TcpStream`、`&[u8]` 都实现它们，于是「读文件」与「读 socket」共用一套代码（这与 Go 的 `io.Reader`/`io.Writer` 异曲同工，都源自 Unix「一切皆文件」的传统）。路径抽象 `Path`/`PathBuf` 则从第一天就面对跨平台问题：Unix 路径是字节序列、Windows 是 UTF-16，所以 `Path` 内部存 `OsStr` 而非 `String`——**「路径不一定是合法 UTF-8」是 Rust 路径 API 一切设计的出发点**。网络 API 直接继承 1983 年 BSD sockets 的 listen/accept/connect 心智。生态层：serde 由 Erick Tryzelaar 发起、David Tolnay 接手，2017 年 4 月发布 1.0，靠「数据模型与格式解耦」成为 Rust 序列化事实标准；clap 由 Kevin Beck（kbknapp）创建并维护至 2.x，3/4 起由 Ed Page（epage）接手，4.0（2022-09）把 builder 与 derive 两套 API 合并为一个 crate。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 1983 | BSD sockets（4.2BSD） | listen/accept/connect/send/recv 心智沿用至今，Rust `std::net` 直接映射 |
| 2015 | Rust 1.0：`std::fs`/`std::io`/`std::net` 稳定 | `Read`/`Write` trait + `io::Result` 成为 I/O 统一抽象 |
| 2015 | `Path`/`PathBuf` 随 1.0 稳定 | 跨平台路径：`OsStr` 内核，不为 UTF-8 假设买单 |
| 2017 | serde 1.0 发布（2017-04-20） | 「数据模型 ↔ 格式」解耦：一套 derive 适配 JSON/TOML/YAML/… |
| 2022 | clap 3（2022-01）→ clap 4（2022-09） | builder 与 derive API 合并；`derive` feature 成为主流写法 |
| 2023 | `File::create_new` 稳定（Rust 1.77） | 原子「不存在才创建」，补 `OpenOptions` 的常用路径 |
| 2025 | 本环境工具链：rustc 1.92.0 + serde 1.0.229 + serde_json 1.0.151 + toml 1.1.4 + clap 4.6.6 | 本文全部 std 示例与 crate 示例均在此环境实测 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（与 ph10~ph12 一致：全仓库代码层统一 `rustc --edition 2021` 单文件编译；本阶段 std 部分的核心 API——`fs`/`io`/`Path`/`net`——自 1.0 全部稳定，是本阶段语法中最稳定的部分）。**依赖策略**：std 部分（示例 1~6、全部练习、综合项目）只用标准库，零依赖、不联网；**serde/clap 部分（示例 7~9）为第三方 crate，本环境已通过 rsproxy 国内镜像成功拉取并完整编译运行——serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4 / clap 4.6.6，全部标注「已验证」**（拉取失败环境则按「未在本环境验证」处理，见 examples/README）。编译错误码（E0515）与全部运行输出均在本环境实测后写入；网络行为（超时 kind、断连检测、数据报边界）全部实测，平台差异处已如实标注。

## 3. 语法与参数

### 3.1 std::fs：文件读写与元数据

`std::fs` 提供两档 API：**一键函数**（读整个文件/写整个文件）与 **`File` + `OpenOptions`**（精细控制）。

```rust
use std::fs::{self, OpenOptions};
use std::io::Write;

// 一键读写（适合小文件；大文件用 3.2 的缓冲流式）
fs::write("/tmp/a.txt", "hello rust\n")?;      // 覆盖式写（&str 或 &[u8]）
let text = fs::read_to_string("/tmp/a.txt")?;  // 要求合法 UTF-8，否则 Err
let bytes: Vec<u8> = fs::read("/tmp/a.txt")?;  // 原始字节，可处理任意二进制

// OpenOptions 精细控制（追加/只读/不存在才创建…）
let mut f = OpenOptions::new().append(true).open("/tmp/a.txt")?;
writeln!(f, "第二行")?;                        // File 实现 io::Write

// 元数据与目录
let meta = fs::metadata("/tmp/a.txt")?;
println!("{} 字节, is_file={}", meta.len(), meta.is_file());
for entry in fs::read_dir("/tmp")? {           // 迭代器每项也是 io::Result
    let entry = entry?;
    println!("{:?}", entry.path());
}
```

常用一键函数与错误判定（实测摘录自 examples/ex01）：

| 函数 | 作用 | 备注 |
|------|------|------|
| `fs::read_to_string` / `fs::read` | 读整个文件为 String / Vec\<u8\> | 前者要求 UTF-8 |
| `fs::write` | 覆盖式写整个文件 | 不存在则创建 |
| `fs::copy` | 复制文件，返回字节数 | 实测复制 43 字节 |
| `fs::create_dir_all` / `fs::remove_dir_all` | 递归建/删目录 | 已存在不报错 |
| `fs::rename` | 重命名/移动 | 同文件系统内是原子操作 |

**错误处理：`io::Error` + `ErrorKind` 结构化判定**。`fs` 操作全部返回 `io::Result<T>`；判断错误**类别**用 `kind()`（跨平台），打印给人看的文本用 `Display`（与 OS 相关）：

```rust
match fs::read_to_string("/tmp/nope.txt") {
    Ok(_) => {}
    Err(e) => {
        // 实测（macOS）：kind=NotFound, 消息=No such file or directory (os error 2)
        assert_eq!(e.kind(), std::io::ErrorKind::NotFound);
    }
}
```

常用 `ErrorKind`：`NotFound`（文件不存在）、`PermissionDenied`（无权限）、`AlreadyExists`（`create_new` 撞名）、`IsADirectory`（把目录当文件读）、`UnexpectedEof`（读截断）。网络相关的 `ConnectionRefused`/`WouldBlock` 见 3.4。

### 3.2 std::io：Read/Write/BufRead 与缓冲 I/O

`std::io` 的核心是三个 trait——**一切字节源/汇都实现它们，代码面向 trait 写就能同时服务文件、socket、内存缓冲**：

| trait | 关键方法 | 实现者举例 |
|-------|---------|-----------|
| `Read` | `read`、`read_to_end`、`read_to_string` | `File`、`TcpStream`、`&[u8]`、`Stdin` |
| `Write` | `write`、`write_all`、`flush` | `File`、`TcpStream`、`Vec<u8>`、`Stdout` |
| `BufRead`（需有缓冲） | `read_line`、`lines()`、`fill_buf` | `BufReader<R>` |

**为什么需要 BufReader/BufWriter**：裸 `File` 每次 `read` 都是一次系统调用（read(2)）。逐字节读约 30 万字节（298894）≈ 30 万次 syscall；包一层 `BufReader`（默认 8 KiB 缓冲）后每次 syscall 读 8 KiB，行循环的 `read_line` 从缓冲里切——**缓冲把 syscall 次数降了几个数量级**。写侧同理，`BufWriter` 攒够一批才落盘：

```rust
use std::io::{BufRead, BufReader, BufWriter, Write};

let reader = BufReader::new(File::open("big.txt")?);
for line in reader.lines() {        // 迭代器，每行 io::Result<String>（不含 '\n'）
    let line = line?;
    // 处理一行——内存占用与文件大小无关（流式）
}

let mut w = BufWriter::new(File::create("out.txt")?);
writeln!(w, "...")?;
w.flush()?; // 关键！BufWriter 的 Drop 也会 flush，但会**忽略错误**——显式 flush 才能拿到写失败
```

实测（examples/ex02）：`BufWriter` 写 1 万行（298894 字节）约 0.7ms，`BufReader` 逐行统计约 8ms。

**逐行读的两种姿势**：`lines()` 消费 `BufReader` 返回迭代器（每行分配新 String）；`read_line(&mut buf)` 复用同一个 `String` 缓冲（零分配循环，适合大文件热路径），返回读取字节数、0 表示 EOF、行尾含 `\n`。

**I/O 里的生命周期陷阱（ph08 的应用场，E0515 实测）**：把读出来的内容以引用形式返回，会撞上「返回指向局部数据的引用」：

```rust
// 故意出错示例：不能编译（教学性覆盖）
fn first_line(path: &str) -> io::Result<&str> {
    let s = std::fs::read_to_string(path)?; // s 是局部 String
    Ok(s.lines().next().unwrap()) // 返回指向 s 的 &str
}
```

rustc 1.92.0 实测报错：

```text
error[E0515]: cannot return value referencing local variable `s`
 --> src/main.rs:4:5
  |
4 |     Ok(s.lines().next().unwrap()) // 返回指向 s 的 &str
  |     ^^^-^^^^^^^^^^^^^^^^^^^^^^^^^
  |     |  |
  |     |  `s` is borrowed here
  |     returns a value referencing data owned by the current function
```

修复：返回 `String`（所有权转移）或把数据的所有权也一起返回。**「读取的内容归谁所有」在 I/O 边界必须想清楚**——这正是 ph08 生命周期规则在真实代码里的样子。

### 3.3 Path 与 PathBuf：跨平台路径

`Path` 之于 `PathBuf`，正如 `str` 之于 `String`：**`Path` 是借用视图（不可变、零开销），`PathBuf` 是拥有的、可拼接修改的**。路径内部是 `OsStr`（Unix 上是任意字节序列），所以 `to_str()` 返回 `Option<&str>`——路径不一定是合法 UTF-8。

| 操作 | 方法 | 说明 |
|------|------|------|
| 创建视图 | `Path::new("/var/log/app.log")` | 零开销，不检查存在性 |
| 拼接 | `PathBuf::push` / `Path::join` | push 原地改、join 返回新值；**自动插入分隔符** |
| 提取部件 | `file_name` / `file_stem` / `extension` / `parent` | 都返回 `Option` |
| 分解 | `components()` | 跨平台语义分解（RootDir/Normal/…） |
| 判断 | `exists` / `is_file` / `is_dir` | 触碰文件系统 |
| 判断 | `is_absolute` | 纯词法判断，不触碰文件系统 |

**两个实测陷阱**（examples/ex03）：

```rust
let mut b = PathBuf::from("/base/dir");
b.push("/abs/other");              // push 遇到绝对路径会【整体替换】！
assert_eq!(b, PathBuf::from("/abs/other")); // 实测——不是 "/base/dir/abs/other"

// 拼接永远用 push/join，绝不 format!("{}/{}", a, b)——Windows 分隔符是 '\'
println!("{:?}", std::path::MAIN_SEPARATOR); // macOS/Linux 实测 '/'
```

**路径跨平台三戒律**：不硬编码 `/` 或 `\`（用 `push`/`join`）；不假设路径是 UTF-8（`to_str()` 处理 `None`）；不假设大小写敏感性（macOS 默认不敏感、Linux 敏感）。

### 3.4 TCP 与 UDP：std::net

**TCP（面向连接的字节流）**：服务端 `TcpListener::bind` → `accept` 拿 `TcpStream`；客户端 `TcpStream::connect`。`TcpStream` 同时实现 `Read` 和 `Write`——**收发就是读写字节流**。

```rust
let listener = TcpListener::bind("127.0.0.1:0")?;   // 端口 0 = OS 分配空闲端口（测试必备）
let (mut stream, peer) = listener.accept()?;         // 阻塞直到有连接
let mut buf = [0u8; 64];
loop {
    match stream.read(&mut buf) {
        Ok(0) => break,          // 关键：read 返回 Ok(0) = 对端正常关闭（EOF）
        Ok(n) => stream.write_all(&buf[..n])?, // 回显
        Err(e) => return Err(e),
    }
}
```

**三个必须处理的网络现实**（examples/ex04 全部实测）：

| 现实 | Rust API | 实测行为（macOS） |
|------|---------|------------------|
| 对端断开 | `read` 返回 `Ok(0)` | EOF 语义，不是错误——不处理会死循环 |
| 响应慢/永不返回 | `set_read_timeout(Some(d))` | 超时报错 kind=`WouldBlock`，消息 `Resource temporarily unavailable (os error 35)`（Windows 为 `TimedOut`） |
| 目标没人监听 | `connect` 报错 | kind=`ConnectionRefused`，消息 `Connection refused (os error 61)` |

> **注意**：`WouldBlock` 直译「本该阻塞」——设了超时后 socket 变非阻塞语义，超时即「此刻读不到」。**错误消息文本与 OS 相关，判定一律用 `kind()`**。

**多客户端**：`listener.incoming()` 迭代连接，每个连接交给一个 `thread::spawn` 处理（阻塞式服务器的标准形态，项目 `project/` 的 server 模式就是这么写的）；异步高并发形态见 ph12 示例 9（tokio）。

**UDP（无连接的数据报）**：`UdpSocket::bind` 后 `send_to`/`recv_from`——每个数据报自带对端地址。与 TCP 的本质差异（examples/ex05 全部实测）：

| 维度 | TCP | UDP |
|------|-----|-----|
| 连接 | 面向连接（connect/accept） | 无连接（send_to 带地址） |
| 消息边界 | **无边界**（字节流，两次 send 可能一次 read 收全——粘包） | **保留边界**（两次 send 永远是两次 recv，实测 `ab`+`cdef` 不会合并成 `abcdef`） |
| 可靠性 | 有序、不丢、不重 | 可能丢、乱序、重复 |
| 缓冲过小 | 剩余字节下次 read 继续读 | **超出部分直接丢弃**（实测：4 字节缓冲收 10 字节数据报得前 4 字节，后 6 字节丢弃） |

UDP 也可以 `connect()` 设默认对端——之后用 `send`/`recv`（不带地址），且内核只接收该对端的包。

### 3.5 serde：JSON/TOML 序列化（已验证 serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4）

serde 的设计核心是**「数据模型与格式解耦」**：`#[derive(Serialize, Deserialize)]` 只描述「我的结构体怎么映射为通用数据模型」，具体格式（JSON/TOML/YAML/MessagePack…）由各自 crate 实现。derive 宏本身属 ph15 内容，这里只「用」不「写」。

```rust
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug)]
struct ServerConfig {
    #[serde(rename = "host_name")]      // JSON 键名与字段名不同
    host: String,
    port: u16,
    #[serde(default = "default_workers")] // 缺省时用函数给默认值
    workers: u32,
}

let json = serde_json::to_string_pretty(&cfg)?;       // 结构体 → JSON 字符串
let cfg: ServerConfig = serde_json::from_str(&json)?; // JSON 字符串 → 结构体
```

TOML（Cargo.toml 同款格式）只需换一个 crate，**结构体定义原样复用**：

```rust
let cfg: AppConfig = toml::from_str(CONFIG_TOML)?; // 嵌套表 [server] → 嵌套结构体
let text = toml::to_string_pretty(&cfg)?;
```

**serde_json 的错误带行列定位**，对排查配置文件极友好（examples/ex07 实测）：

```text
invalid type: string "not-a-number", expected u16 at line 1 column 42
```

> 本阶段只演示 serde 的「日常用法」：derive、字段属性、JSON/TOML 互转。**手写解析器原理**（Tokenizer + 递归下降）做成练习 4 的裸机版；**自写 Serialize 实现、零拷贝反序列化（`#[serde(borrow)]`）属 ph19 阶段**，这里不展开。

### 3.6 命令行参数：std 手写 → clap（已验证 clap 4.6.6）

**裸机版（`std::env::args`）**：`env::args()` 返回 `String` 迭代器，`args[0]` 是程序名。手写解析就是「遍历 + match 分派 + 带值选项消费下一项」（examples/ex06 完整实现）：

```rust
let args: Vec<String> = std::env::args().collect();
// 手写循环："-v" | "--verbose" => verbose = true,
//           "-n" | "--count"    => 消费 args.next() 并 parse::<u32>(),
//           _ if starts_with('-') => Err(未知选项),
//           _ => 位置参数
```

手写版让你看清工作量：**解析、校验、类型转换、错误提示、--help 文本**全都得自己写。clap 用 derive 把这些全部自动化——**struct 定义即 CLI 定义**（examples/ex09 实测 clap 4.6.6）：

```rust
use clap::Parser;

/// 日志转发器命令行（doc 注释自动变成 --help 说明文字）
#[derive(Parser, Debug)]
#[command(name = "logfwd", version = "0.1.0", about = "日志转发器：tail 文件并经 TCP 转发")]
struct Cli {
    /// 要监听的日志文件
    input: String,                               // 位置参数（必填）
    #[arg(short, long)]
    verbose: bool,                               // -v / --verbose
    #[arg(short, long, default_value = "127.0.0.1:9000")]
    server: String,                              // 缺省值
    #[arg(short = 'n', long, default_value_t = 3)]
    retries: u32,                                // 非字符串默认值用 default_value_t
}

let cli = Cli::parse(); // 真实程序入口就一行：解析失败自动打印错误并 exit(2)
```

实测行为：`--help` 自动生成（首行即 about 文本）；缺必填参数报 `error: the following required arguments were not provided:`；类型错误报 `error: invalid value 'abc' for '--retries <RETRIES>': invalid digit found in string`。教学与测试时用 `Cli::try_parse_from(["logfwd", "-v", "app.log"])` 喂固定参数向量，输出确定（examples/ex09 就是这么做的）。子命令（`tool add`/`tool list`）的手写裸机版做成练习 5；clap 的 `Subcommand` derive 是同思路的自动化。

## 4. 底层原理

### 4.1 文件与 socket 都是文件描述符

Unix 哲学「一切皆文件」：Rust 的 `File`、`TcpStream`、`UdpSocket` 底层都是**文件描述符**（fd，一个小整数，内核资源表的索引）。`read`/`write` 最终落到 read(2)/write(2) 系统调用，从用户态切到内核态——**这就是为什么缓冲 I/O 重要：syscall 的切换成本远高于内存拷贝**。

```text
用户态:  your code ──▶ BufReader(8KiB 缓冲) ──▶ File/TcpStream ──▶ read(2) syscall
内核态:                                                        ▼
                          页缓存 / socket 缓冲 ◀── 磁盘 / 网卡
```

### 4.2 资源释放由 Drop 管理（RAII）

`File`/`TcpStream` 离开作用域时 `Drop` 自动 `close(2)`——**没有显式 close，也不会泄漏**（GC 语言的 `with`/try-with-resources 在 Rust 里是类型系统行为）。这把「资源管理」变成了所有权管理的推论：所有权清晰，资源生命周期就清晰。例外要记住：`BufWriter` 的 Drop flush **会忽略写错误**，所以关键数据落盘前必须显式 `flush()?`。

### 4.3 TCP 字节流 vs UDP 数据报

TCP 在内核里维护「发送缓冲 → 拥塞控制 → 接收缓冲」的可靠有序**字节流管道**：应用层的两次 `write` 在内核/对端看来没有边界（粘包）。UDP 每个 `send_to` 对应一个独立**数据报**——内核原样封装、原样交付（或整个丢失），边界天然保留。

```text
TCP:  write("ab") write("cdef") ──▶ 字节流 ──▶ read 可能得 "abcdef"（粘包）
UDP:  send("ab")  send("cdef")  ──▶ 数据报 ──▶ recv 得 "ab"，再 recv 得 "cdef"（边界保留）
```

选型：**要可靠有序用 TCP（日志转发、RPC、HTTP）；要低延迟容忍丢失用 UDP（DNS、音视频、心跳）**。本阶段项目（日志转发器）选 TCP——日志丢行不可接受。

### 4.4 serde 的双层架构

serde 把序列化拆成两层：**数据结构侧**（`Serialize` trait：「我有哪些字段、什么类型」）与**格式侧**（`Serializer` trait：「字段名和值怎么编码成文本/字节」）。derive 宏为结构体生成前者，serde_json/toml 实现后者——所以同一份结构体定义能原样适配所有格式。这也是「数据模型与格式解耦」的落地机制。

## 5. 使用场景

- **配置驱动的一切程序**：读 TOML/JSON 配置 → serde 反序列化为强类型结构体（parse, don't validate）——这是 Rust 服务启动的标准姿势
- **日志与数据管道**：`BufReader` 逐行流式处理 GB 级日志（内存 O(1)），经 TCP 转发（本阶段项目）；批处理 ETL 同理
- **命令行工具**：clap 是 Rust CLI 生态事实标准（ripgrep、fd、cargo 本身都在用）；子命令式工具的解析结果用 enum 建模（练习 5）
- **网络服务**：阻塞式 `TcpListener` + 每连接一线程适合连接数适中的内网工具；高并发（万级连接）选 tokio 异步（ph12 示例 9）；DNS/监控心跳选 UDP
- **跨语言对比**：Go 的 `io.Reader`/`Writer` 与 Rust `Read`/`Write` 同为「一切皆流」；Java 用 `Path`/`Files` 对应 `Path`/`std::fs`；C 的 `FILE*` 已带缓冲（`fgets`），Rust 则要显式 `BufReader`——**Rust 把「要不要缓冲」的决定权显式交给程序员**（为 analysis/ 与 Tenet 合成积累素材）

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件与运行命令在 [`examples/`](./examples/)（std 六个：`rustc --edition 2021 -D warnings` 单文件；serde/clap 三个：cargo 工程 `crates/`，已验证 serde 1.0.229 / serde_json 1.0.151 / toml 1.1.4 / clap 4.6.6）。全部片段为 examples 文件逐字摘录（省略处用 `...` 表示）。

### 示例 1：std::fs 速览（ex01-fs-read-write.rs）

```rust
// examples/ex01-fs-read-write.rs —— std::fs 一站式速览
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-fs-read-write.rs -o /tmp/ex01
// 运行：/tmp/ex01
fs::write(&file, "hello rust\n第二行\n")?; // &str / &[u8] 均可
let text = fs::read_to_string(&file)?;
println!("2. read_to_string: {} 字符 / {} 字节", text.chars().count(), text.len());
// 注意：len() 是字节数——"第二行" 3 个汉字占 9 字节
...
match fs::read_to_string(format!("{dir}/no-such.txt")) {
    Ok(_) => println!("7. 不可能到这里"),
    Err(e) => {
        println!("7. 错误: kind={:?}, 消息={}", e.kind(), e);
        assert_eq!(e.kind(), io::ErrorKind::NotFound);
    }
}
```

实测输出（节选）：`2. read_to_string: 15 字符 / 21 字节`；`6. fs::copy 复制了 43 字节`；`7. 错误: kind=NotFound, 消息=No such file or directory (os error 2)`。

### 示例 2：缓冲 I/O 与迷你 wc（ex02-bufio-lines.rs）

```rust
// examples/ex02-bufio-lines.rs —— BufReader/BufWriter 缓冲 I/O
// 编译：rustc --edition 2021 -D warnings ex02-bufio-lines.rs -o /tmp/ex02
let mut w = BufWriter::new(file); // 默认 8 KiB 缓冲
for i in 1..=10_000 {
    writeln!(w, "line {i} the quick brown fox")?; // 每行 26 + i 的位数 字节（含 \n）
}
w.flush()?; // 关键！缓冲里的最后一批数据要 flush 才真正落盘
...
for line in reader.lines() {
    let line = line?;
    lines += 1;
    words += line.split_whitespace().count() as u64;
    bytes += line.len() as u64 + 1; // +1 补回被剥掉的 '\n'
}
```

实测输出：`wc: 10000 行 / 60000 词 / 298894 字节`（写约 0.7ms、统计约 8ms，耗时随机器而异）。

### 示例 3：Path 与 PathBuf（ex03-path-pathbuf.rs）

```rust
// examples/ex03-path-pathbuf.rs —— 跨平台路径
// 编译：rustc --edition 2021 -D warnings ex03-path-pathbuf.rs -o /tmp/ex03
let mut b = PathBuf::from("/base/dir");
b.push("/abs/other"); // 绝对路径 → 整个替换！常见陷阱
println!("4. push 绝对: {b:?}");
assert_eq!(b, PathBuf::from("/abs/other"));
```

实测输出：`4. push 绝对: "/abs/other"`；`6. MAIN_SEPARATOR = '/'`（macOS）。

### 示例 4：TCP 回显 + 超时 + 断连（ex04-tcp-echo.rs）

```rust
// examples/ex04-tcp-echo.rs —— TCP：回显、读超时、断连检测、连接被拒
// 编译：rustc --edition 2021 -D warnings ex04-tcp-echo.rs -o /tmp/ex04
match c2.read(&mut buf) {
    Ok(_) => println!("2. 意外：第一次就读到了"),
    Err(e) => {
        // 超时错误 kind：macOS/Linux 是 WouldBlock，Windows 是 TimedOut
        println!("2. 读超时: kind={:?}, 消息={}", e.kind(), e);
        assert!(matches!(
            e.kind(),
            io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
        ));
    }
}
```

实测输出（macOS）：`2. 读超时: kind=WouldBlock, 消息=Resource temporarily unavailable (os error 35)`；`S1. read 返回 Ok(0)：对端已关闭连接（EOF）`；`3. 连接被拒: kind=ConnectionRefused, 消息=Connection refused (os error 61)`。

### 示例 5：UDP 数据报边界（ex05-udp-datagram.rs）

```rust
// examples/ex05-udp-datagram.rs —— UDP：边界保留、截断、connect 默认对端
// 编译：rustc --edition 2021 -D warnings ex05-udp-datagram.rs -o /tmp/ex05
client.send_to(b"ab", server_addr)?;
client.send_to(b"cdef", server_addr)?;
...
println!(
    "3. 边界保留: {:?} ({m1} 字节) 然后 {:?} ({m2} 字节)，不会合并成 \"abcdef\"",
    &b1[..m1],
    &b2[..m2]
);
```

实测输出：`3. 边界保留: [97, 98] (2 字节) 然后 [99, 100, 101, 102] (4 字节)`；`4. 缓冲 4 字节收 10 字节数据报: 得到 [48, 49, 50, 51]，后 6 字节被丢弃`。

### 示例 6：纯 std 手写命令行解析（ex06-args-manual.rs）

```rust
// examples/ex06-args-manual.rs —— env::args 手写解析（clap 的裸机版）
// 编译：rustc --edition 2021 -D warnings ex06-args-manual.rs -o /tmp/ex06
while let Some(arg) = args.next() {
    match arg.as_str() {
        "-v" | "--verbose" => verbose = true,
        "-n" | "--count" => {
            // 带值选项：消费下一个参数
            let val = args
                .next()
                .ok_or_else(|| format!("-n/--count 缺少值\n{}", usage(&prog)))?;
            count = val
                .parse()
                .map_err(|_| format!("无效的次数 {val:?}（应为正整数）\n{}", usage(&prog)))?;
        }
        ...
    }
}
```

实测输出：`2. 解析成功: Config { verbose: true, count: 3, input: "input.txt" }`；错误路径 `未知选项 "--verbse"` / `-n/--count 缺少值` / `缺少输入文件`。

### 示例 7~9：serde/clap（cargo 工程 crates/，已验证）

```rust
// examples/crates/src/bin/ex07-serde-json.rs —— serde derive + serde_json（已验证 serde 1.0.229 / serde_json 1.0.151）
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex07-serde-json
#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct ServerConfig {
    #[serde(rename = "host_name")] // JSON 里的键名与字段名不同
    host: String,
    port: u16,
    #[serde(default = "default_workers")] // 缺省时用函数给默认值
    workers: u32,
    #[serde(default)] // 缺省时用 Default::default()（bool → false）
    tls: bool,
}
```

```rust
// examples/crates/src/bin/ex09-clap-cli.rs —— clap derive（已验证 clap 4.6.6）
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex09-clap-cli
/// 日志转发器命令行（doc 注释自动变成 --help 里的说明文字）
#[derive(Parser, Debug)]
#[command(name = "logfwd", version = "0.1.0", about = "日志转发器：tail 文件并经 TCP 转发")]
struct Cli {
    /// 要监听的日志文件
    input: String, // 位置参数（必填）
    ...
}
```

实测要点：ex07 解析错误 `invalid type: string "not-a-number", expected u16 at line 1 column 42`、往返一致断言通过；ex08 TOML 嵌套表 `[server]` → 嵌套结构体往返；ex09 `--help` 自动生成、类型错误 `invalid value 'abc' for '--retries <RETRIES>'`。

## 7. 总结

### 关键要点

- `std::fs` 一键读写适合小文件；**大文件必须 `BufReader`/`BufWriter` 流式处理**——缓冲把 syscall 次数降几个数量级，`BufWriter` 落盘前显式 `flush()?`（Drop 的 flush 会吞错误）
- `Path`（借用）/`PathBuf`（拥有）如 `str`/`String`；**拼接只用 push/join，绝不拼字符串**；`push` 绝对路径会整体替换（实测陷阱）；路径不一定是 UTF-8
- TCP 是字节流：`read` 返回 `Ok(0)` = 对端正常关闭（EOF），必须处理否则死循环；**生产代码必设 `set_read_timeout`**；UDP 保留数据报边界、缓冲不足直接截断丢弃
- 错误判定一律用 `io::Error::kind()`（跨平台 `ErrorKind`），`Display` 文本只给人看（与 OS 相关，实测 `os error 2/35/61`）
- serde「数据模型 ↔ 格式」解耦：一份 derive 适配 JSON/TOML/…；clap「struct 即 CLI」：解析/校验/帮助全自动——**手写裸机版（ex06、练习 4/5）是理解它们替你做什麽的捷径**
- 资源释放由 Drop 管理（RAII）：`File`/`TcpStream` 离开作用域自动关闭，无泄漏

### 阶段验收清单

- [ ] 能写出清晰的 I/O 错误处理（`?` 传播 + `ErrorKind` 结构化判定，不 unwrap）
- [ ] 能让路径处理不依赖硬编码分隔符（全程 push/join，说出 `OsStr` 存在的理由）
- [ ] 能让网络程序处理断连（`Ok(0)`）和超时（`set_read_timeout` + `WouldBlock`/`TimedOut`）
- [ ] 能用 serde derive 完成结构体 ↔ JSON/TOML 互转并用字段属性定制
- [ ] 能说清 TCP 粘包与 UDP 边界保留的区别及选型依据
- [ ] 能用 clap derive 定义带默认值/类型转换的 CLI，并说出手写版的工作量在哪

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题（迷你 wc / 目录递归统计 / TCP 时间戳服务器 / 手写 JSON 解析器 / 手写子命令 CLI）后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**日志转发器（log-forwarder）**——`tail -f` 风格跟踪文件尾部增长，新增完整行经 TCP 转发到服务端，带断线重连（≤3 次）与自包含 demo 验收（roadmap 推荐项目；纯 std 单文件，demo 模式 5 行按序转发断言已实测连跑 3 次一致，断线重连路径「杀服务端后重连 3 次报 ConnectionAborted」双进程实测）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[Unsafe Rust 与安全抽象阶段](../ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md) — `unsafe` 关键字、裸指针、`unsafe fn`、FFI 调用基础与安全抽象封装：本阶段打下的 I/O 地基将直接延伸（ph19 的零拷贝协议解析建立在 `Read`/`BufRead` 之上，ph23 的 FFI 需要理解本阶段的 fd 与系统资源模型，ph25 的 Axum/Tonic 数据服务则把 ph12（异步）+ ph13（网络）两条线汇合）。在此之前可先按推荐学习顺序巩固 ph11~ph13 的练习与项目。
