# sol-03 —— 练习 3 参考实现：天气查询 CLI 选型报告

> 参考实现（先自己做再看）。本文给出报告的**结构与写法**——取证数据会随 crates.io 状态漂移，跑下面的命令如实记录后填入「取证数据表」即可。
> 验证环境：bash + curl + python3 + rustc/cargo 1.92.0（未在本环境验证；crates.io API 输出字段以官方文档为准）。

## 0. 取证命令（roadmap 练习「检查 crate 最近发布和 issue 状态」）

```bash
# 1. crates.io API：最近发布 / 更新时间 / 下载量（对 reqwest / ureq / hyper 各跑一次）
curl -s "https://crates.io/api/v1/crates/reqwest" -H "User-Agent: ph17-sol03/0.1" | python3 -c '
import json, sys
c = json.load(sys.stdin)["crate"]
print(c["name"], "| latest:", c["max_version"], "| updated:", c["updated_at"],
      "| recent:", c.get("recent_downloads"))'
# 2. issue 响应迹象：去 GitHub 仓库 Issues 页看「无人应答的 open issue 占比 / 维护者最近是否回复」
#    （reqwest/ureq/hyper 的仓库地址在 crates.io 页面或 docs.rs 顶部）
# 3. 依赖成本对照（在临时空 crate 里分别 cargo add 后跑）：cargo tree --depth 1
```

## 1. 取证数据表（写作时快照，须重取）

| 候选 | 最近发布 | 更新时间 | 近 90 天下载量 | issue 迹象（快照） | 依赖成本（depth 1） |
|------|---------|---------|---------------|-------------------|-------------------|
| reqwest | 快照值 A | 快照值 B | 极高 | 活跃维护、issue 有响应 | tokio/hyper/rustls 一揽子 |
| ureq | 快照值 C | 快照值 D | 中 | 社区维护、节奏较慢 | 轻（无 tokio，可配 rustls） |
| hyper | 快照值 E | 快照值 F | 高（但作为引擎被 reqwest 间接消费） | 活跃维护 | 只含协议层，TLS/连接池自配 |

（取证的目的是「有据可查」，不是背数字——真实值以你跑命令的结果为准。）

## 2. 选型结论

**选 reqwest（`default-features = false` + `rustls-tls` + `json`）**。

## 3. 理由（≥3 条）

1. **同步 vs 异步的权衡**：CLI 起步期「单文件、顺序查询」用同步（ureq 或 reqwest blocking）最快；但场景预告了「缓存 + 多数据源」，多数据源并发查询是 async 的自然场景——reqwest 同时提供 blocking 与 async 两条路，起步用 blocking、扩容期切 async 不用换 crate（ureq 是纯同步，届时要么换库要么包线程）。
2. **TLS 后端**：reqwest 支持 `rustls-tls`（纯 Rust），不把 OpenSSL 系统依赖带进 CLI 的部署环境；ureq 配 rustls 也可以，但 reqwest 的 rustls 组合是生态里验证最广的路径。
3. **维护活跃度与生态位**：取证显示 reqwest 是 HTTP 客户端生态的下载量与活跃度第一梯队（ureq 社区维护、节奏较慢；hyper 是引擎不是客户端）——选生态验证最多的路，安全补丁与示例跟进最及时。
4. **JSON 免手写**：`json` feature 让 `res.json::<Weather>()` 一步到位，配合 serde 反序列化（主文档 3.3），比 ureq 的手工 serde_json 少一层样板。

## 4. 什么条件下改选

- 未来需求证明「完全不需要 async、且依赖面敏感」→ 改 **ureq**（纯同步、依赖更轻），代码改动集中在请求层
- 需求变成「写一个给别人用的 HTTP 客户端库/协议层」→ 改 **hyper**（+ hyper-util + hyper-rustls），但那是另一个工程了
- 决策记录：本报告即「引入前说明理由」的产物——按主文档 3.2 六维清单归档进 project/ 的依赖评审表即可
