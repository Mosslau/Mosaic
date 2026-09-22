# ph20 高级 Java 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与 roadmap「20. 高级 Java 阶段」练习小节的对应**：四题一一对应 roadmap 列出的四个练习——练习 1 = 手写简易 IOC、练习 2 = 手写线程池、练习 3 = RPC demo、练习 4 = Netty TCP server。四题是「把 ex05 的反射/代理、ex03 的线程池、ex08 的 Netty」从『看懂』推到『自己写一遍』的递进链。
> **验证纪律**：练习 1~3 纯 Java，用 `/opt/homebrew/opt/openjdk@17/bin/javac|java` 本机实测过，验收命令见各题；练习 4 依赖 netty 4.1.137.Final（本机手动拉 jar 实测通过，jar 获取步骤见 [`examples/ex08-netty-echo/README.md`](../examples/ex08-netty-echo/README.md)）。

| 练习 | 参考实现 | 用到的本阶段机制 | examples 参照 |
|------|---------|------------------|------|
| 1 手写简易 IOC | sol-01-mini-ioc/ | 反射构造/装配/单例缓存（3.8 反射部分） | ex05 |
| 2 手写线程池 | sol-02-threadpool/ | 线程池四段路径 + Future（3.4） | ex03 |
| 3 RPC demo | sol-03-rpc-demo/ | 动态代理 + 反射 + socket 序列化（3.8/3.4） | ex05 |
| 4 Netty TCP server | sol-04-netty-tcp/ | Netty pipeline + codec + EventLoop（3.9） | ex08 |

## 练习 1：手写简易 IOC（★★）

**目标**：写一个几十行的迷你容器：注册「接口 → 实现类」，getBean 时自动完成构造器依赖注入，理解「IOC = 对象的创建与装配从调用方转移给容器」。
**要求**：
- 容器提供 `register(接口类型, 实现类)` 与 `getBean(接口类型)`
- 用反射选「参数最多」的构造器，按参数类型递归 `getBean` 完成注入（可只支持构造注入）
- 同一类型的 bean 缓存为单例（两次 getBean 同一实例）
- 不得使用 Spring 等任何现成容器
**验收**：写一个 A 依赖 B、B 无依赖的例子，`getBean(A)` 后能直接调用 A 的方法且 B 被正确注入；两次 getBean 是同一实例。参考实现见 `sol-01-mini-ioc/`。

## 练习 2：手写线程池（★★★）

**目标**：在 examples/ex03 的 execute 主链（core → queue → max → reject）之上，补上 `submit(Callable)` 返回 `Future` 的能力。
**要求**：
- `submit(Callable)` 返回一个能 `get()` 到结果的对象（提示：`FutureTask` 既是 Runnable 又是 Future——把任务包一层再丢进 execute 就是 ThreadPoolExecutor.submit 的做法）
- 任务内抛异常时，`Future.get()` 应把异常抛给调用方（而不是吞掉）
- `shutdown()` 后新任务被拒绝（抛 `RejectedExecutionException`），已入队任务仍执行完
- 不得使用 `java.util.concurrent.ThreadPoolExecutor`（`FutureTask` 等工具类可用）
**验收**：提交 10 个 `Callable` 返回 `id*2`，逐个 `get()` 求和 = 110；一个抛异常的任务能通过 `ExecutionException` 观察到原因。参考实现见 `sol-02-threadpool/`。

## 练习 3：RPC demo（★★★）

**目标**：用「动态代理 + 反射 + TCP socket」写一个最小 RPC：客户端像调本地方法一样调远程服务。
**要求**：
- 服务端：持有一个服务实现实例，循环接收请求（服务名/方法名/参数），用反射调用本地实现并把结果写回
- 客户端：用 `Proxy.newProxyInstance` 为接口生成桩，`InvocationHandler` 里把方法调用序列化发给服务端、读回结果返回
- 接口至少两个方法（一个返回 String、一个返回 int），验证两类返回值都正确
- 不引入任何 RPC/网络框架，只用 JDK
**验收**：客户端调用 `remote.hello("x")` 得到服务端实现的计算结果（本机回环即可）。参考实现见 `sol-03-rpc-demo/`。
**进阶思考（不做也行）**：短连接改长连接、请求加 id 支持并发、报文加版本号——这三点每加一个就是向生产级 RPC 迈一步。

## 练习 4：Netty TCP server（★★★）

**目标**：基于 examples/ex08 的 Netty 骨架，写一个按「行」处理的 TCP 服务：收到一行文本，转大写回传。
**要求**：
- 用 `ServerBootstrap + NioEventLoopGroup` 搭服务（ex08 已有）
- pipeline 里加 `LineBasedFrameDecoder`（按 `\n` 切帧，处理粘包/半包）+ `StringDecoder/StringEncoder`（ByteBuf ↔ String）
- 业务 handler 收到的是完整的 `String` 行而非原始 ByteBuf——体会 codec 链把字节细节消化掉
- 客户端连发多行，逐行断言回显 = 原行大写
**验收**：本机起 server，client 发 3 行、收到 3 行大写回显且逐字匹配。参考实现见 `sol-04-netty-tcp/`（依赖 netty 4.1.137.Final，jar 获取与命令见文件头）。

## 完成后

做完四题继续到 [`project/`](../project/)：简易 IOC 容器（roadmap 推荐项目之一，注解驱动 + 循环依赖检测），把练习 1 的手写容器升级成可扫描、可注入、可检测循环依赖的完整版。
