# examples —— 并发与异步阶段完整示例

对应主文档 `12-concurrency-async.md` 第 6 章示例 1~9。分成两组：

- **ex01~ex06（纯 std 并发 + 异步基础）**：零第三方依赖，`rustc --edition 2021 -D warnings` 单文件编译，产物输出 `/tmp/`。
- **ex07~ex10（tokio）**：第三方 crate，需要 cargo + 网络拉取 tokio，独立小工程 `tokio/`。

验证环境：rustc 1.92.0（macOS arm64）；tokio 1.53.1（已通过 rsproxy 国内镜像拉取，**已验证**）。

## 第一组：纯 std（rustc 单文件，零依赖）

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-thread-spawn-join.rs` | 示例 1 | 线程创建与等待：`thread::spawn` + `join`、move 闭包、命名线程、返回值（`子线程返回值: 42` 实测；多线程打印顺序不定，已如实标注） | `rustc --edition 2021 -D warnings ex01-thread-spawn-join.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-mpsc-channel.rs` | 示例 2 | 通道：多生产者（clone Sender）/单消费者、`drop(tx)` 关闭、`sync_channel` 背压（实测：缓冲 2 满后第 3 次 send 阻塞约 105ms 直到消费者开始收） | `rustc --edition 2021 -D warnings ex02-mpsc-channel.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-arc-mutex-counter.rs` | 示例 3 | 共享可变状态：`Arc<Mutex<u32>>` 计数器，8 线程 × 10 万次自增（实测 `最终计数 = 800000` 精确，无数据竞争） | `rustc --edition 2021 -D warnings ex03-arc-mutex-counter.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-rwlock-cache.rs` | 示例 4 | 读写锁：读并发（4 读者持锁 120ms 总耗时实测约 125ms，非 480ms）、写独占（读者被写者阻塞实测约 104ms） | `rustc --edition 2021 -D warnings ex04-rwlock-cache.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-send-sync-bounds.rs` | 示例 5 | Send/Sync 边界编译期验证：断言函数 + 反例注释（E0277 错误文本 rustc 1.92.0 实测，见主文档 3.4） | `rustc --edition 2021 -D warnings ex05-send-sync-bounds.rs -o /tmp/ex05` | `/tmp/ex05` |
| `ex06-async-std-executor.rs` | 示例 6 | 纯 std 的 async/await：自写极简 executor（`block_on` + 多任务轮询 `block_on_many`），`Timer` future + waker 唤醒（实测：3 个任务总耗时约 331ms，输出 `[2, 3, 4]`） | `rustc --edition 2021 -D warnings ex06-async-std-executor.rs -o /tmp/ex06` | `/tmp/ex06` |

## 第二组：tokio（cargo 工程，已验证 tokio 1.53.1）

`tokio/` 是独立 cargo 工程（`Cargo.toml` 声明 `tokio = { version = "1", features = ["full"] }`）。本环境实测步骤（国内网络）：

```bash
# 1. 配置国内镜像（一次即可）：写入 $CARGO_HOME/config.toml
#    [source.crates-io]
#    replace-with = "rsproxy"
#    [source.rsproxy]
#    registry = "sparse+https://rsproxy.cn/index/"
# 2. 构建与运行（CARGO_TARGET_DIR 指向 /tmp，仓库零二进制残留）
cd examples/tokio
CARGO_TARGET_DIR=/tmp/ph12-tokio-target cargo run --release --bin ex07-tokio-tasks
CARGO_TARGET_DIR=/tmp/ph12-tokio-target cargo run --release --bin ex08-tokio-timeout
CARGO_TARGET_DIR=/tmp/ph12-tokio-target cargo run --release --bin ex09-tokio-tcp-echo
CARGO_TARGET_DIR=/tmp/ph12-tokio-target cargo run --release --bin ex10-tokio-mpsc-backpressure
```

| 文件 | 对应示例 | 说明 | 实测输出要点 |
|------|---------|------|-------------|
| `src/bin/ex07-tokio-tasks.rs` | 示例 7 | tokio 任务与定时器：`tokio::spawn` + `tokio::time::sleep`（非阻塞定时器） | `任务 0/1/2 完成 @ 52/152/252ms`，返回值之和 `30` |
| `src/bin/ex08-tokio-timeout.rs` | 示例 8 | 超时与任务失败：`tokio::time::timeout` 取消、`JoinError` 收容任务 panic | `1) 超时: Err(Elapsed)`；`3) 任务失败: task 15 panicked with message "任务内部出错"（is_panic=true）` |
| `src/bin/ex09-tokio-tcp-echo.rs` | 示例 9 | tokio 异步网络 I/O：本机回环 TCP echo（`TcpListener`/`TcpStream` 异步版） | `客户端: 收到回显 "hello tokio"`（服务端端口每次运行不同） |
| `src/bin/ex10-tokio-mpsc-backpressure.rs` | 示例 10 | 异步背压：`tokio::sync::mpsc` 有界通道——容量满时 `send().await` 挂起**任务**而非线程 | 容量 2 满后生产 3/4 各挂起约 100ms 直到消费者取走，总耗时约 500ms |

## 运行注意事项

- **ex08**：任务内部故意 panic，虽被 `JoinError` 收容，stderr 仍会打印 1 行 panic hook 输出（`thread 'tokio-rt-worker' panicked ...`），程序退出码 0 正常继续——与 ex01 线程版行为一致，属正常现象。
- **多线程输出顺序不定**：ex01 的 4 线程打印、ex02 场景 B 的收包顺序、ex04 的读者完成顺序，每次运行可能不同——这是并发执行的本质，不是 bug（ex02 已排序后打印以保证验收确定性）。
- 全部编译产物输出到 `/tmp/`（或 `CARGO_TARGET_DIR`），仓库内零二进制残留。

## 验证状态汇总

- 第一组：6 个示例均在本环境 `rustc --edition 2021 -D warnings` 编译零警告并运行验证（已验证：rustc 1.92.0）。
- 第二组：tokio 1.53.1 经 rsproxy 镜像成功拉取并完整编译运行（已验证），三条示例输出均为实测。
