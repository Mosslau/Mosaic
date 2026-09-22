# sol-01 —— 练习 1 参考实现：reqwest vs hyper 对比

> 参考实现（先自己做再看）。本文为分析题的答案文档，非可运行代码；结论基于主文档 3.5 与 2025 年 12 月 crates.io 的版本状态（reqwest 0.12 / hyper 1.x）。
> 验证环境：rustc/cargo 1.92.0（未在本环境验证；依赖面数字以写作时 crates.io 为准，随时间漂移）。

## 场景再述

「需要控制 HTTP/1.1 连接复用细节的下载器」。先把场景拆成两个子问题：

1. **我要不要控制连接复用细节？** 大多数「下载器」要的是「并发下可靠地下载多个文件 + 断点续传 + 重试」——这些 reqwest 的连接池（自动复用 keep-alive 连接）已覆盖，控制粒度到「每个 host 的连接数上限」（`ClientBuilder::pool_max_idle_per_host`）即可
2. **我是在写业务还是在写协议层？** 写业务 → 选 reqwest；写「别人要用的 HTTP 客户端/代理/框架」→ 才轮到 hyper

## 对比表

| 维度 | reqwest | hyper |
|------|---------|-------|
| 定位 | 面向应用开发者的高层 HTTP 客户端 | HTTP/1.1 + HTTP/2 协议引擎（客户端 + 服务端） |
| API 风格 | `Client::get(url).send().await`，builder 配超时/重定向/代理/cookie | 手写 `Request` 构造、`conn` 连接管理、流式 body 处理 |
| 连接复用 | 内置连接池，可调 idle 上限 | 复用由你搭（`hyper_util` 的 legacy Client 是官方示例） |
| TLS | feature 二选一：`rustls-tls`（纯 Rust）/ `native-tls`（OpenSSL 系） | 不内置：自己接 `tokio-rustls` / `hyper-rustls` |
| 依赖成本 | 自带 tokio/rustls 等一揽子（`cargo tree --depth 1` 可数） | 只含协议层；把 TLS/运行时/连接池都留给你组合 |
| 学习曲线 | 低（示例遍地） | 高（要懂连接、版本协商、body 流式语义） |
| 适用 | 业务代码「发请求拿响应」 | 写 HTTP 库/框架/网关；要极致控制协议行为 |

## 判据问题（至少两条）

1. **「发请求」还是「管连接」**：你的代码想表达业务意图（下载、查询、上传），还是想表达协议行为（连接如何建立/复用/升级）？前者 reqwest，后者 hyper。
2. **依赖成本谁买单**：hyper 方案你还要自己接 TLS（hyper-rustls）+ 连接池 + 重试，最终依赖面往往 ≥ reqwest 且代码量大几倍——只有这些控制**真的被用到**才划算。
3. **生态信号**：需求是「下载器」这种常见形态时，生态里没人用裸 hyper 写业务客户端——跟着主流走降低维护成本（这是维护活跃度维度的反向用法：你在消费一个生态，选生态里验证最多的那条路）。

## 结论与反例

- **结论**：这个下载器选 **reqwest（rustls-tls + json feature，default-features = false）**。理由：连接复用细节 reqwest 的连接池已覆盖（`pool_max_idle_per_host` 够用）；你要控制的是「下载策略」而不是「HTTP 协议行为」。
- **反例 A（选 hyper 的代价）**：为「少一个依赖」直接用 hyper——结果要手写 TLS 接入、连接池、重试，代码量与踩坑时间远超省下的依赖面，且 reqwest 的 JSON/重定向/代理等免费能力全部丢失。
- **反例 B（无脑 reqwest 的代价）**：你的真实需求是「在框架里提供 HTTP/1.1 服务端能力」（写 axum 这类框架的中间件层）——这时 reqwest 是客户端，帮不上服务端；正确对象是 hyper 的 server 侧。

## 什么条件下改选 hyper

需求变成「自己实现/魔改 HTTP 协议行为」（自定义版本协商、h2 流控细节、非标准方法语义），或「做一个给别人用的 HTTP 客户端库」时，才值得下沉到 hyper + hyper-util + hyper-rustls 的组合。
