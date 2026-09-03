# ex08 Netty Echo（TCP）示例

> 用 Netty 写最简「读即回」的 Echo 服务端 + 客户端，演示 EventLoopGroup / ServerBootstrap / ChannelPipeline 三板斧（主文档 3.9 / 4.3）。Echo 是 Netty 文档里的 Hello World，看懂它就看懂了一个 Netty 服务的最小骨架。

## 验证状态

**已验证**（OpenJDK 17.0.18 + Netty 4.1.137.Final）：本机从 Maven Central 手动拉取模块 jar（无 mvn），`javac` 编译通过，实测 server 启动 → client 发送 → 收到逐字 echo（`PASS: ECHO OK`），进程优雅退出。

依赖获取方式（本机实操过的）：

```bash
# 无 mvn 时：手动拉核心模块 jar（4.1.137.Final 的 netty-all 是空聚合 jar，不含类，要拉模块）
V=4.1.137.Final
mkdir -p /tmp/netty-lib && cd /tmp/netty-lib
for M in netty-buffer netty-common netty-handler netty-resolver netty-transport netty-codec; do
  curl -sL -o $M.jar "https://repo1.maven.org/maven2/io/netty/$M/$V/$M-$V.jar"
done
```

有 mvn 的环境直接用 `pom.xml`（依赖 `netty-all:4.1.137.Final`，mvn 会解析成真实模块）。

## 编译与运行

```bash
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
LIB=/tmp/netty-lib
# 1. 编译（通配符 classpath：javac/java 都支持）
$JAVAC -encoding UTF-8 -cp "$LIB/*" -d /tmp/tl20-cls EchoServer.java EchoClient.java

# 2. 终端 1 启动服务端
java -cp "/tmp/tl20-cls:$LIB/*" EchoServer 18080

# 3. 终端 2 运行客户端（成功输出 PASS: ECHO OK）
java -cp "/tmp/tl20-cls:$LIB/*" EchoClient 127.0.0.1 18080
```

## 教学点（读代码时对照主文档）

1. **boss/worker 两组线程**：boss 组 1 个线程只 accept，worker 组默认 `2×CPU` 个线程服务连接读写——这就是主从 Reactor（主文档 4.3）。`EchoServer started on 18080` 打印后可 `jstack <pid>` 看到 `nioEventLoopGroup-*` 线程。
2. **ChannelHandler 无锁串行**：同一 channel 的读写永远由同一个 EventLoop 线程执行，业务 handler 不需要加锁（Netty 线程模型的核心卖点）。
3. **`ctx.writeAndFlush(msg)` 直接回写读到的 msg**：Netty 的 ByteBuf 引用计数由框架管理，原样转发不复制即零拷贝语义的一部分（主文档 3.9 零拷贝条目）。

## Netty 的 4.1.x 与 4.0/5.0 差异提示

示例 API（NioEventLoopGroup / ServerBootstrap）自 4.0 起基本未变，5.0（2026 年最新为 Alpha 版）也不改这套用法；教学基线统一 4.1.137.Final。
