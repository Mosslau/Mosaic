# ph25 阶段项目：mini-kv-service（Rust 收官三合一）

对应 roadmap 第 25 节推荐项目与附录「阶段性项目验收标准」——Rust 路线的收官工程。落地为 [`mini-kv-service/`](./mini-kv-service/)：**Mini LSM-KV 持久化引擎 + Axum HTTP + Agent 工具 API** 的三合一服务，一台可跑、可崩、可恢复的最小 KV 服务。

## 为什么是这个形态

ph25 的 examples/ex01~ex08 把数据基础设施按组件拆开演示（WAL replay、SSTable+Bloom、compaction 模拟、Mini Raft 状态机、HNSW toy、Axum 服务、pyo3 加速、Agent 工具后端）；收官项目把它们收进一个「服务进程」，回答 roadmap 阶段验收的三句话：

1. **写得安全**：任何 `put/delete` 先落 WAL（fsync 才确认）再改内存表——崩溃/重启后 WAL 重放恢复；
2. **读得有序**：key 在有序内存表里，`get` 点查、`scan` 闭区间返回——range scan 是 HTTP 一等公民；
3. **调得可信**：Agent 工具 API（`/tools/call`）按 `x-client-id` 声明权限 scope，逐次调用写审计、按决策计数，`/metrics` 暴露。

## 与 ph24 供应链流水线的衔接

本工程直接复用了 ph24 沉淀的安全发布流水线形态：

- `deny.toml` —— 复制自 ph24 `relpipe/deny.toml`（注明来源），schema 经 cargo-deny 校验；
- `release-check.sh` —— 形态复制自 ph24 `relpipe/release-check.sh` 的本地 9 步流水线（fmt → clippy -D warnings → test → audit → deny → 打包审查 → CHANGELOG 校验）。

这兑现了 ph24 主文档「下一阶段」的预告：ph24 的 deny.toml、audit job 与 release-check.sh 被 KV/LSM 工程直接拿去用——「安全地写出来」与「可信地发出去」在此汇合成「安全可信的数据基础设施」。

## 验收标准（四关，全部可在本机复现）

```text
1. 引擎关：cargo test 全绿（WAL 恢复 / get-put-delete / range scan / 工具调用）
2. 冒烟关：bash scripts/smoke.sh 四关通过（CRUD / scan / 工具权限 / 重启恢复）
3. 流水线关：bash release-check.sh 9 步通过（本地可跑步骤；audit 视网络）
4. 指标关：/metrics 暴露 total_calls 等计数，越权调用返回 403、超时返回 504
```

详细的需求拆解、目录结构、启动/测试命令与边界声明见 [`mini-kv-service/README.md`](./mini-kv-service/README.md)。
