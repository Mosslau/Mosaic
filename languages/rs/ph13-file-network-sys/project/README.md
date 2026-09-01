# ph13 阶段项目：日志转发器（log-forwarder）

对应 roadmap ph13 推荐项目「日志转发器：读取文件尾部变化并通过 TCP 发送到服务端」。在主文档 std::fs / Path / TCP / 缓冲 I/O 的基础上，落地为带**三模式 CLI + 断线重连 + 自包含验收**的完整程序。**纯 std、单文件**（`rustc` 直接编译，零第三方依赖）。

## 需求

一个 `tail -f` 风格的日志转发器：

1. **server 模式**：TCP 服务端，接收转发的日志行并打印（带来源地址）。
2. **tail 模式**：轮询跟踪文件尾部增长，把新增完整行经 TCP 转发；连接断开自动重连（≤3 次，间隔 100ms）。
3. **demo 模式**：进程内同时起服务端 + 转发器 + 日志源，端到端验证 5 行日志按序转发并断言。

## 功能清单

- [x] `logfwd server <addr>`：多客户端并发接收（每连接一个线程，BufReader 逐行）
- [x] `logfwd tail <file> <addr>`：跟踪文件增长（offset + 轮询 50ms），只转发完整行（半行留到下轮）
- [x] 断线重连：写失败自动重连，耗尽 3 次报 `ConnectionAborted`
- [x] `logfwd demo`：自包含验收——用 mpsc 就绪信号消除「日志源抢跑」竞态
- [x] 用法错误（缺参数/未知模式）打印 usage 并以退出码 2 退出

## 构建与运行

```bash
# 1. 编译（产物输出 /tmp，仓库零二进制残留）
rustc --edition 2021 -D warnings src/main.rs -o /tmp/logfwd
# 2. 自包含验收（推荐先跑这个）
/tmp/logfwd demo
# 3. 真实三端演示
/tmp/logfwd server 127.0.0.1:9000          # 终端 1
/tmp/logfwd tail /tmp/app.log 127.0.0.1:9000   # 终端 2
echo "hello" >> /tmp/app.log               # 终端 3（任何程序追加写都会触发转发）
```

验证环境：rustc 1.92.0（macOS arm64），零第三方依赖。**已验证**。

## 实测输出

demo 模式（连跑 3 次输出一致，端口每次不同）：

```text
[demo] 进程内起服务端 + 转发器 + 日志源，验证端到端转发
[tail] 已连接 127.0.0.1:57611
[demo] 转发器发送 5 行；服务端收到 5 行
[demo] 收到[1] = "log line 1"
[demo] 收到[2] = "log line 2"
[demo] 收到[3] = "log line 3"
[demo] 收到[4] = "log line 4"
[demo] 收到[5] = "log line 5"
[demo] 断言通过：5 行日志全部按序转发成功
```

真实双进程模式（server 监听 9101，tail 跟踪 /tmp/app.log，追加两行）也已实测：

```text
[server] 监听 127.0.0.1:9101
[server] 127.0.0.1:57686 │ first line
[server] 127.0.0.1:57686 │ 第二行
```

断线重连路径（已手动实测）：server 运行中直接杀掉，tail 继续追加多行触发写失败 → 重连 3 次（间隔 100ms）→ 报 `ConnectionAborted` 退出：

```text
[tail] 发送失败，第 1 次重连…
[tail] 发送失败，第 2 次重连…
[tail] 发送失败，第 3 次重连…
Error: Custom { kind: ConnectionAborted, error: "重连 3 次仍失败，放弃发送 \"line-2\"" }
```

## 验收标准

- `rustc --edition 2021 -D warnings` 编译零警告（已验证）
- `demo` 模式：5 行日志按序转发、`assert_eq!` 断言通过、退出码 0（已验证，连跑 3 次）
- 双进程模式：终端 3 追加的行 1 秒内出现在 server 端（已实测）
- 断线重连逻辑已实现并实测（写失败 → 重连 ≤3 次 → `ConnectionAborted`）；该路径未在 demo 中覆盖，改用「双进程模式杀服务端 + 追加多行」实测（见上）

## 扩展方向（可选）

- 转发协议改成 JSON 行（`{"ts": ..., "line": ...}`）——用 examples/crates/ex07 的 serde_json（已验证 1.0.151）
- CLI 换成 clap 子命令（`logfwd server` / `logfwd tail` / `logfwd demo`）——对照 ex09（已验证 clap 4.6.6）
- 用 tokio 改异步版：`tokio::fs` + `tokio::net::TcpListener`（承接 [ph12 并发与异步阶段](../../ph12-concurrency-async/12-concurrency-async.md) 示例 9）
- 心跳与批量发送：N 行或 T 毫秒攒一批再发，减少小包
