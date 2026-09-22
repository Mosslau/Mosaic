# s16: Team Protocols — 队友之间要有约定

在 s15 基础上新增结构化协议层：**ProtocolState 状态机 + request_id 关联 +
match_response 类型校验 + consume_lead_inbox 统一消费 + 队友 idle loop**。
s01–s15 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理/cron/团队 照旧）。

```text
  Lead                                    Teammate
   │  request_shutdown(teammate)            │
   │  PENDING_REQUESTS[req].pending         │
   │  bus_send("shutdown_request",{req_id}) │
   │ ──────────────────────────────────────▶│  idle 轮询收到
   │                                        │  dispatch → handle_shutdown_request
   │  consume_lead_inbox → match_response   │  bus_send("shutdown_response",{req_id})
   │  PENDING_REQUESTS[req].approved ◀──────│
   │                                        │  break → summary → finished
```

## 两种协议，一套机制

| 协议 | 方向 | 消息类型 |
|------|------|----------|
| 关机握手 | Lead → 队友 | `shutdown_request` / `shutdown_response`（带 `approve`） |
| 计划审批 | 队友 → Lead | `plan_approval_request` / `plan_approval_response`（带 `approve` + `feedback`） |

`request_id` 贯穿全链路：发请求时创建 `ProtocolState{pending}`，收回复时
`match_response` 按 ID 关联、校验类型、更新状态（pending → approved/rejected）。

## 相对 s15 的改动

| s15 | s16 |
|-----|-----|
| 协调：松散文本消息 | 结构化请求-响应协议 |
| 请求追踪：无 | `ProtocolState` + `PENDING_REQUESTS`（Mutex<HashMap>） |
| 队友生命周期：最多 10 轮 | **idle loop**：LLM 无工具调用后每秒轮询 inbox，收到 shutdown_request 响应退出，收到新消息继续工作（无轮数上限） |
| Lead inbox：check_inbox 与唤醒分支分别读 | 统一 `consume_lead_inbox`：先路由协议响应再返回（避免消息被读走但协议状态没更新） |
| 消息格式：五字段 | + `metadata`（request_id/approve；旧消息 `#[serde(default)]` 兼容） |
| 工具：20 个 | **23 个**（+ request_shutdown / request_plan / review_plan） |
| 队友工具：4 个 | **5 个**（+ submit_plan） |
| 队友 system prompt | + "Check inbox for protocol messages (shutdown_request, etc)." |

## 运行

```bash
# 在仓库根目录准备好 .env（参考 .env.example）
cargo run -p s16_team_protocols
```

试试这些 prompt：

1. `Spawn alice as a backend dev. Ask her to create a file. Then request her shutdown.`
2. `Spawn bob with a refactoring task. Have him submit a plan first. Then review and approve it.`

**关机握手验证**：spawn 队友 → 干完进入 idle → `request_shutdown("alice")` →
`[protocol] shutdown_request → alice (req_xxxxxx)`（紫）→ alice idle 轮询收到 →
`[protocol] alice approved shutdown (req_xxxxxx)`（紫）→ Lead 被唤醒，
`consume_lead_inbox` 路由 `shutdown_response` → `[protocol] shutdown ✓ (req_xxxxxx: approved)`（绿）→
`[teammate] alice finished`。

**计划审批验证**：队友调 `submit_plan` → Lead 收到 `plan_approval_request` →
`review_plan(req_id, approve=true)` → 队友收到 `[Plan approved] Proceed with the task.` 继续。

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **request_id 贯穿全链路** | 发请求创建 pending 状态，回复带同一 ID，`match_response` 关联——一步一追溯（对齐 Python 四步流程） |
| **类型校验** | shutdown 请求只接受 `shutdown_response`，plan_approval 只接受 `plan_approval_response`——一个响应不会误批另一类请求（`[protocol] type mismatch` 红字） |
| **重复回复去重** | 已决请求的再次回复被忽略（`already {status}, ignoring duplicate` 黄字） |
| **统一 inbox 消费** | `consume_lead_inbox` 被 check_inbox 工具与 main 唤醒分支共用：先路由协议，再返回注入——协议状态不会因消息被消费而丢失 |
| **idle loop** | 队友无轮数上限（对齐 Python）：LLM 停后每秒轮询 inbox；`teammate_idle` 抽出为可测函数（返回 Continue/Shutdown） |
| **metadata 向后兼容** | 消息 JSON 加 `metadata` 字段；旧收件箱消息（s15 时代）经 `#[serde(default="default_metadata")]` 归一为空对象（`Value::Default` 是 Null，必须归一，对齐 Python `msg.get("metadata", {})`） |
| **强类型协议** | `ProtocolType`/`ProtocolStatus` 枚举替代 Python 字符串（编译期校验）；`PENDING_REQUESTS` 用 Mutex（Python 靠 GIL） |
| **bus_send 零改动** | 新增 `bus_send_meta`（带 metadata）；`bus_send` 保持 5 参转发——s15 冻结代码与既有测试不动 |
| **无执行门控** | 教学版只演示消息流程，未在未批准时拦截 bash/write（对齐 Python 注释；真实 CC 有 permission gating） |
| **协议标记走 stderr** | `[protocol]`/`[bus]` 走 stderr（对齐 s15 队友标记惯例），不插入流式回复 |

## 结构

```
s16_team_protocols/
├── Cargo.toml          # s15 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 8477 行：s15 全套 + Team Protocols（~1000 行新增）
```

## 测试

```bash
cargo test -p s16_team_protocols -- --test-threads=1
```

223 个单元测试（197 从 s15 携入 + 26 新增），覆盖：
- `match_response` 矩阵：unknown request_id / 类型不匹配 / approve→approved /reject→rejected / 重复回复忽略
- 协议工具：`run_request_shutdown`（状态 + 消息落盘 + metadata.request_id 一致）、`run_request_plan`、`run_review_plan`（not found / already / approve + 响应送达）、`teammate_submit_plan`（sender=队友 + payload）
- `handle_inbox_message`：shutdown 停止 + 响应落盘（content "Shutting down gracefully."）、plan approved/rejected 注入、普通消息放行
- `teammate_idle`：shutdown → Shutdown、普通消息 → Continue + `<inbox>` 注入
- `consume_lead_inbox`：协议响应路由 + 状态更新、普通消息原样返回
- metadata：往返、**无 metadata 旧消息兼容**（默认 `{}`）
- check_inbox 新格式：`[{from}] [{type} req:{req_id}]` / `[{from}] [{type}]`
- 工具集/输入校验：all_tools 恰 23、teammate_tools 恰 5、serde 缺字段拒绝
- 队友窗口配对清理回归：窗口截断产生的孤儿 tool_result 被 sanitize 替换占位

## 与 Python 版对比

对照 `../../python/s16_team_protocols/code.py`。ProtocolState 字段、四种协议消息类型、
`request_id` 关联语义、`[protocol]` 全部输出文案与颜色、`[Plan approved] Proceed with the task.` /
`[Plan rejected] Feedback: ...` 注入文案、`Plan submitted (req_xxx). Waiting for approval...` /
`Shutdown request sent to {t} (req: {id})` 返回文案——逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | 14 工具简化栈（去 cron，无错误恢复/记忆/技能/压缩/hook） | s15 全量保留（23 工具 + 全部机制，cron 照旧） |
| REPL | 回退简单 input 循环（无 poller），每轮末尾 consume_lead_inbox 注入 | **保留 s15 select! 三路 + inbox_poller**：协议响应到达即自动唤醒 Lead（无需用户输入）；唤醒分支同样走 consume_lead_inbox |
| 协议类型 | 字符串 `"shutdown"` / `"plan_approval"` | 强类型 `ProtocolType`/`ProtocolStatus` 枚举 |
| 线程安全 | dict + GIL | `Mutex<HashMap>` 显式加锁 |
| idle 等待 | `time.sleep(1)` 同步阻塞线程 | `tokio::time::interval` 异步（不阻塞 runtime） |
| metadata 兼容 | 无旧数据问题（新字段直接加） | `#[serde(default="default_metadata")]` 归一空对象（`Value::Default` 是 Null） |
| 消息路由 | `handle_inbox_message` 闭包内嵌 | 抽出独立函数 + `teammate_idle`（返回 Continue/Shutdown）——纯函数可单测 |
| 单元测试 | 无 | 25 个新增 |

## 已知行为（TEST.md 注意事项同步）

- **协议状态是内存态**：`PENDING_REQUESTS` 不落盘，重启即失（对齐 Python；教学版无持久化需求）；
- **队友 idle 无超时**：无轮数上限，靠 shutdown 协议退出——spawn 后不干活也不关机的队友会一直驻留（对齐 Python；真实 CC 有 idle_notification 机制）；
- **Lead 盲等（实测现象，教学版未解决）**：教学版无 `idle_notification`——Lead 不知道队友何时空闲/完成，实测中模型用 `bash sleep 15/30/45/60/90`长轮询等待、`send_message` 催促（Python 版同样）。真实 CC 队友 idle 时发`idle_notification` 给 Lead；**s17 用 idle_poll + 任务看板认领从架构上消除该问题**（队友自己认领任务，Lead 无需知道其空闲状态）；
- **协议送达无回执（实测现象，教学版未解决）**：`plan_approval_response`经 idle 注入自动送达队友，但 Lead 模型不知情——实测 `review_plan` 后模型又手动 `send_message` 催了一次（双重通知，无害但冗余；队友实际按协议响应继续工作）。教学版无送达回执；真实 CC 有更完整的协议感知。
- **执行门控未实现**：`submit_plan` 后队友仍可调用 bash/write——教学版靠模型自觉等待审批（对齐 Python 注释说明）；
- **`[protocol]`/`[bus]` 走 stderr**（对齐 s15 标记惯例）；
- **并行测试竞态**：`PENDING_REQUESTS` 是共享静态；协议测试用**唯一 request_id +只查自己记录**（不做全局 len/is_empty 断言，避免 Mutex 中毒连锁），并行稳健——仅 s14 cron 继承竞态按 `--test-threads=1` 约定。

## 后续章节

| 章节 | 主题 | 在 s16 基础上增加 |
|------|------|--------------------|
| s17 | Autonomous Agents | 队友自组织：看板认领任务，无需 Lead 分配 |
| s18 | Worktree Isolation | 每任务独立 git worktree |
| s19 | MCP Plugin | 外部工具接入同一工具池 |
| s20 | Comprehensive | 完整集成示例 |
