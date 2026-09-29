# s19: MCP Tools — 外部能力即插即用

在 s18 基础上新增 **MCP 插件系统**：`MCPClient`（教学 mock）发现外部服务器工具，
`connect_mcp` 连接服务器，`assemble_tool_pool` 把内置工具与 MCP 工具组装成
**统一动态工具池**（`mcp__{server}__{tool}` 命名），agent_loop 双路径分发：
运行时表命中走动态 handler，未命中回退 execute_sync 静态 match。
s01–s18 全部机制保留（后台/流式/并行/任务图/错误恢复/权限/Hook/压缩/记忆/技能/子代理/cron/团队/协议/自治/worktree 照旧）。

```text
 ┌─────────────────────────────────────────────────────────────┐
 │ 模型调用 connect_mcp("docs")                                  │
 └───────────────────────────┬─────────────────────────────────┘
                             ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ MCP_STATE 注册表（连接顺序 + 客户端）                          │
 │  docs: [search, get_version]  deploy: [trigger, status]      │
 └───────────────────────────┬─────────────────────────────────┘
                             ▼ 本轮响应含 connect_mcp → 重组装
 ┌─────────────────────────────────────────────────────────────┐
 │ assemble_tool_pool()                                         │
 │  工具池 = 27 内置 + mcp__docs__search + mcp__docs__get_version│
 │  运行时表 = {mcp__docs__search → call_tool(search), ...}      │
 └───────────────────────────┬─────────────────────────────────┘
                             ▼ 下一轮起
 ┌─────────────────────────────────────────────────────────────┐
 │ agent_loop 分发（dispatch_tool）                              │
 │  表命中 → 动态 handler（快速内存调用）                         │
 │  未命中 → execute_sync 静态 match（内置，s12 起冻结）          │
 └─────────────────────────────────────────────────────────────┘
```

## 核心机制

### 1. MCPClient（教学 mock）

```text
MCPClient { name, tools: Vec<Tool>, handlers: HashMap<tool名, fn(&Value) -> Result<String,String>> }
```

- `register(tool_defs, handlers)`：模拟 MCP `initialize`/`listTools`——服务器声明
  工具定义 + 绑定 handler
- `call_tool(tool_name, args)`：未知工具 → `MCP error: unknown tool '{name}'`；
  handler 失败 → `MCP error: {e}`（对齐 Python 的异常捕获）
- handler 是**函数指针**（mock 无捕获，天然 Send + 'static），内部用强类型
  `#[derive(Deserialize)]` 解析参数（轨道惯例）

### 2. 服务器注册表：`.mcp.json` 配置驱动（前移）

| 服务器 | 工具 | 注解 |
|--------|------|------|
| docs | `search(query)` / `get_version()` | readOnly ×2 |
| deploy | `trigger(service)` / `status(service)` | destructive（trigger）/ readOnly |

**启动时读 `tutorials/rust/.mcp.json`**（候选链 `cwd/.mcp.json` → `cwd/tutorials/rust/.mcp.json`，
第一个有教学条目的生效；全部缺失回退内置兜底，内容与文件一致）：

```json
{ "mcpServers": { "docs": { "tools": [ { "name": "search", "description": "...",
  "inputSchema": { ... }, "handler": "docs_search" }, ... ] } } }
```

- **容错解析**：真实 Claude Code 的 stdio 条目（`command`/`args`，无 `tools` 字段）
  跳过并提示——本仓库根目录就有一个真实的 codegraph 配置，两种格式可在同一文件共存
- **handler 注册表**：配置文件只声明"工具由哪个 handler 实现"（`handler` 名），
  实现在 `mcp_handler_by_name` 里登记——新增服务器 = 改配置文件（+ 新行为时加一行注册表）
- 工具描述带 `(readOnly)` / `(destructive — requires approval in real CC)` 注解——
  **教学版不拦截，仅注解**（真实 CC 的 destructive 工具要人工确认）

### 3. connect_mcp 与命名规范化

| 情形 | 返回 |
|------|------|
| 已连接 | `MCP server '{name}' already connected` |
| 未知服务器 | `Unknown server '{name}'. Available: docs, deploy` |
| 成功 | `[mcp] connected: docs → ['search', 'get_version']`（红）+ `Connected to MCP server 'docs'. Discovered 2 tools: search, get_version` |

- `normalize_mcp_name`：非 `[a-zA-Z0-9_-]` 一律替换为 `_`（字符遍历，无 regex 依赖）
- 连接顺序写入 `MCP_STATE.order`——工具池顺序可复现（对齐 Python dict 插入序）

### 4. assemble_tool_pool + 双路径分发（s19 核心）

```rust
fn assemble_tool_pool() -> (Vec<Tool>, HashMap<String, PoolHandler>)
```

- 工具池 = `all_tools()`（27 内置）+ 每个已连接服务器的工具（`mcp__{safe_server}__{safe_tool}`）
- 运行时表 = 前缀名 → 闭包（捕获 server/tool 两个 String，调用时按名查全局再
  `call_tool`）——等价 Python 的 `lambda *, c=mcp_client, t=..., **kw: c.call_tool(t, kw)`
- agent_loop 每轮经 `dispatch_tool`：**表命中 → 动态 handler；未命中 → execute_sync**
  （静态 match 不动，冻结惯例）

### 5. 动态池的"即插即用"时刻

- agent_loop 循环外组装一次池；**本轮响应里出现过 connect_mcp 调用 → 循环尾部重组装**
  （`response_uses_connect_mcp` 检测）——新工具从下一轮起出现在 API 请求里
- system prompt：tools 段补 `MCP tools are prefixed mcp__{server}__{tool}.`；
  有连接时加 `Connected MCP servers: docs, deploy` 段
- **Rust 保留 s10 prompt 缓存并正确失效**：`connected_mcp` 进 `PromptContext`
  缓存键——连接新服务器后 ctx 序列化值变化，缓存自动失效（Python 直接删了缓存）

### 6. 队友侧零 MCP

队友工具集固定 8 个（bash/read_file/write_file/send_message/submit_plan/
list_tasks/claim_task/complete_task），不查运行时表 → **MCP 工具只有 Lead 能调**
（Rust 是类型层面隔离：队友线程根本不持有 MCP 表）。

## 相对 s18 的改动

| s18 | s19 |
|-----|-----|
| 工具集静态（26 个，`all_tools` 数组） | **27 内置 + 动态 MCP 工具**（+ connect_mcp；`Tool.name/description` 改为 String 承载动态名） |
| agent_loop 直接 execute_sync 分发 | `dispatch_tool` 双路径：MCP 运行时表 → execute_sync 回退 |
| 无外部工具概念 | `MCPClient` / `normalize_mcp_name` / `MCP_STATE` 全局注册表 |
| 服务器注册表硬编码工厂表（`MOCK_SERVERS`） | **`.mcp.json` 配置驱动**（启动时读 + 容错跳过真实 CC 条目 + 内置兜底） |
| system prompt 无 MCP 段 | tools 段前缀约定 + `Connected MCP servers:` 段（有连接时） |
| PromptContext 4 字段 | + `connected_mcp: Vec<String>`（进缓存键，连接后自动失效） |
| — | connect_mcp 被调用后重组装工具池（下一轮生效） |

## 运行

```bash
cd /Users/ninebot/code/mosslau/AgentNest   # 仓库根（git 上下文，worktree 工具需要）
cargo run --manifest-path rust/Cargo.toml -p s19_mcp_plugin
```

**启动横幅**（配置加载）：

```
[mcp] config: skip 'codegraph' — not a teaching entry (real CC stdio config?)
[mcp] config loaded: 2 server(s) from .../tutorials/rust/.mcp.json
```

**核心验证**：`Connect to the docs MCP server and search for "agents".`

预期观察：
- `[mcp] connected: docs → ['search', 'get_version']`（红）
- 模型下一轮调 `mcp__docs__search`（工具池生效）→ 返回 `[docs] Found 3 results for 'agents'`
- 再连 deploy → 池含 4 个 MCP 工具；重连 docs → `already connected`

## 关键设计

| 设计点 | 说明 |
|--------|------|
| **动态工具名 → String** | `Tool.name/description` 从 `&'static str` 改为 String——`mcp__{server}__{tool}` 是运行时拼的，静态借用放不下 |
| **连接顺序确定性** | `MCP_STATE.order: Vec<String>`——HashMap 迭代无序，池顺序（builtins → docs → deploy）必须可复现才能测、才能对齐 Python 插入序 |
| **函数指针 handler** | mock handler 无捕获 → `fn(&Value) -> Result<String,String>` 天然 Send + 'static，避免闭包进 static 的生命周期问题 |
| **池 handler 闭包只捕获 String** | 调用时按名从全局取客户端——等价 Python 闭包捕获 mcp_client，但无生命周期/线程问题 |
| **双路径分发** | 动态表是旁路，execute_sync 静态 match 一字不动（冻结惯例）——新机制不重构旧机制 |
| **配置驱动注册表（前移）** | 服务器不再写死在代码里：`.mcp.json` 声明 server → 工具定义 + handler 名；handler 注册表是"配置 ↔ 实现"的桥（JSON 表达不了函数）；真实 CC 的 stdio 条目容错跳过（本仓库根目录就有 codegraph 配置） |
| **MCP 仅 Lead** | 队友线程不持有 MCP 表 → 类型层面隔离（Python 靠"队友不注册 handler"，机制不同效果同） |
| **缓存正确失效（前移）** | Python 去掉了 prompt cache；Rust 保留并把 connected_mcp 纳入缓存键——连接即失效，无需每轮重组装 |
| **快速路径** | MCP handler 纯内存调用，仍走 spawn_blocking（与内置统一）——不特殊化，槽位结构不变 |

## 结构

```
s19_mcp_plugin/
├── Cargo.toml          # s18 依赖全集（无新增）
├── README.md
└── src/
    └── main.rs         # 10345 行：s18 全套 + MCP 系统（~960 行净增）
../.mcp.json            # Rust 轨道的 MCP 服务器配置（docs/deploy，已提交）
```

## 测试

```bash
cargo test -p s19_mcp_plugin -- --test-threads=1
```

280 个单元测试（250 从 s18 携入 + 30 新增），覆盖：
- `normalize_mcp_name`：合法保留 / 特殊字符→`_` / 中文→逐字`_` / 空串
- `MCPClient.call_tool`：成功 / 未知工具 / handler 错误包装 / 缺字段 serde 错误
- 配置构建：内置兜底 `default_mcp_config` + `build_client` 产物（docs/deploy 工具集、
  readOnly/destructive 注解、schema 透传、handler 解析后可直接 call_tool）
- `connect_mcp`：成功文案与注册表 / 重连拒绝 / 未知服务器（Available 排序 deploy, docs）
- `assemble_tool_pool`：空池=27 纯内置 / docs 后 29 前缀正确 / 双服务器 31 且
  顺序 builtins→docs→deploy / handler 路由到对应 mock / 描述与 schema 透传
- `dispatch_tool`：MCP 命中 / 内置回退（bash）/ 未知工具回退 execute_sync 文案
- system prompt：无连接无 MCP 段 / 有连接按序列出 / tools 段前缀约定
- `update_context`：enabled_tools 含 mcp__* 工具、connected_mcp 按连接序
- **prompt 缓存失效**：连接前后 prompt 不同、ctx 不变时命中缓存
- `response_uses_connect_mcp`：命中/不命中/非工具 block/空
- 幂等：重复 connect 池大小不变；队友工具集不含 mcp__* / connect_mcp
- **配置加载（前移 6 个）**：读文件（inputSchema 键映射）/ 容错跳过真实 CC 条目 /
  缺失·坏 JSON·缺 mcpServers 报错 / handler 注册表命中与未知 / build_client 未知
  handler 拒绝 / **配置扩展**：换配置连新服务器（wiki）→ 池含 mcp__wiki__lookup、
  可用列表随配置变化（Drop 守卫保证 panic 也还原全局配置，防级联）

## 与 Python 版对比

对照 `../../python/s19_mcp_plugin/code.py`。MCPClient 语义、normalize 规则、
两个 mock 服务器的工具与注解、connect_mcp 三种返回文案、`mcp__{server}__{tool}`
命名、池结构（builtins + MCP 按连接序）、agent_loop 的 connect_mcp 后重组装、
system prompt 的 MCP 段——逐字对齐。差异：

| 维度 | Python 版 | Rust 版 |
|------|-----------|---------|
| 承载机制 | 18 工具简化栈 | **27 内置 + 动态 MCP 表**（s01–s18 全部机制照旧） |
| handler 类型 | 闭包 `lambda *, c=..., t=..., **kw` | mock 用**函数指针**（无捕获）；池表闭包只捕获 (server, tool) 两个 String |
| 分发 | dict 查找（builtins 也在 dict 里） | `dispatch_tool` 双路径：MCP 表 → execute_sync 静态 match（队友天然隔离） |
| 参数解析 | `handler(**args)`（TypeError → `MCP error: {e}`） | 强类型 `#[derive(Deserialize)]`（serde 错误 → `MCP error: {e}`，等效文案） |
| prompt 缓存 | **去掉**（no prompt cache） | **保留 + connected_mcp 进缓存键自动失效**（优于 Python，前移） |
| 池大小 | 18 / 20 / 22 | 27 / 29 / 31（内置工具集差异） |
| **服务器注册（前移）** | `MOCK_SERVERS` 硬编码工厂表 | **`.mcp.json` 配置驱动**（启动时读、容错跳过真实 CC stdio 条目、内置兜底；Python 无） |
| 可用列表顺序 | dict 插入序（docs, deploy） | 配置键排序（deploy, docs）——JSON 对象键无序，排序保证确定性 |
| 单元测试 | 无 | 24 个新增 |
| 输出通道 | `[mcp] connected` print stdout | println（Lead 专属工具，不进队友线程；轨道惯例） |

## 已知行为（TEST.md 注意事项同步）

- **MCP 工具只有 Lead 能用**：队友工具集固定 8 个（教学取舍，对齐 Python）——
  真实 CC 的 teammate 可配置自己的 MCP 服务器；
- **工具池在"连接后的下一轮"生效**：connect_mcp 当轮已执行，但其发现的新工具
  要等下一轮 LLM 请求才出现在 tools 数组里（对齐 Python 的重组装时机）；
- **配置文件是启动时读的**：进程生命周期内不变，改 `.mcp.json` 需重启；
  候选链 `cwd/.mcp.json` → `cwd/tutorials/rust/.mcp.json`，第一个有教学条目的生效；
  真实 CC 的 stdio 条目（如根目录 codegraph）被容错跳过并提示——不会报错；
  文件缺失回退内置兜底（内容与 `tutorials/rust/.mcp.json` 一致，章节可独立运行）；
  可用列表按配置键**排序**（`deploy, docs`）——Python 是插入序（差异已记录）；
  **handler 是代码实现**：配置里的 `handler` 名必须存在于注册表，且参数契约
  由 handler 决定（配置 schema 要与其一致，未知 handler 名连接时报配置错误）；
- **normalize 在 mock 名上是空操作**：docs/deploy/search/get_version/trigger/status
  本就合法——规范化是教学机制（真实服务器名常带空格/点），测试覆盖语义；
- **destructive 仅注解不拦截**：`(destructive — requires approval in real CC)`
  只进描述，教学版不拦 trigger 调用（真实 CC 需人工确认）；
- **`[mcp] connected` 走 println**（Lead 专属，不进队友线程）；队友可达函数仍全走 stderr；
- **MCP_STATE 全局 + 测试**：mock 服务器名只有 docs/deploy 两个，无法用唯一名
  隔离 → 测试用 `#[cfg(test)] reset_mcp_state()` 先清后连；配置扩展测试用
  `set_mcp_config` + Drop 守卫（panic 也还原，防级联）（`--test-threads=1` 下单线程确定）；
- **并行测试竞态**：s19 无新增并发状态；仅 s14 cron 继承竞态按 `--test-threads=1` 约定。

## 后续章节

| 章节 | 主题 | 在 s19 基础上增加 |
|------|------|--------------------|
| s20 | Comprehensive | 全部机制集成演示（含动态工具池骨架） |
