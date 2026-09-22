# Go API 设计与兼容性阶段

> 面向"接口怎么设计得稳定、清晰、可演进"：服务内部组织好之后（ph17），对外暴露的契约如何不随内部重构而碎、错误如何让客户端敢写代码、字段如何只增不删地长大、文档如何与实现永不漂移——最后想清楚什么时候该引入版本、什么时候不必。

## 1. 概述

本阶段是学习路线（roadmap 21 个阶段）里的第 18 步。回顾前序：ph09 Web 后端开发阶段能用标准库 net/http 写单体 HTTP 服务，ph11 微服务与 RPC 阶段讲了 gRPC 的通信形态（方法、消息、注册发现），ph17 架构设计与代码分层阶段把服务内部组织成了 handler/service/repository 三层——但"层内该传什么结构""handler 出口的错误结构长什么样""接口一旦发布怎么改"没有展开。本阶段回答 Roadmap 目标：**设计稳定、清晰、可演进的 API**。ph17 在 3.2 埋下"domain 不该被 HTTP 格式绑架"、在 3.6 埋下"错误码只增不删"，正是本阶段的两个入口——本阶段把它们兑现成可操作的纪律：字段怎么演化、错误结构怎么稳定、API 文档怎么与实现同步。

一句话定位：ph09/ph11/ph17 教会你"服务怎么写、内部怎么组织、跨服务怎么调"，本阶段教会你"**服务对外的契约怎么定、怎么在不打断老客户的前提下长大、怎么让文档永不骗人**"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| REST 接口设计 | 资源建模与 URL 约定、HTTP 方法语义（GET/POST/PUT/PATCH/DELETE）、状态码选择、幂等语义 |
| 兼容性心智 | 向后/向前兼容的定义、破坏性 vs 非破坏性变更判定、兼容窗口——全章的统一标尺 |
| 版本管理 | URI 版本 / 请求头 / 媒体类型三种策略对比、v1/v2 共存与 DTO 按版本裁剪、Deprecation/Sunset 通告、下线流程 |
| 错误契约 | 稳定错误 envelope、错误码注册表只增不删、code/message 必填永在、错误码 → HTTP 状态的集中映射、错误文档表 |
| 集合接口 | 分页（offset vs cursor）、过滤、排序的稳定性规则（total 语义、决胜键、排序白名单） |
| 字段演化 | 字段只增不删、字段语义不漂移、domain/DTO 解耦、JSON 序列化陷阱（omitempty/null/未知字段） |
| 文档与实现同步 | spec-first、OpenAPI 结构与最小解析器、契约测试（双向对账）、生成器/校验器工具链 |
| protobuf / gRPC | wire format 兼容机制、字段号纪律、gRPC 接口设计、google.rpc 错误模型与 HTTP 状态映射 |

这个阶段只涉及"对外 API 契约"的设计与兼容纪律（REST 与 gRPC 两种形态），**不涉及消息中间件与事件驱动架构、事件 schema 的版本管理（属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)）、配置中心与 feature flag 灰度发布（属 [ph20 配置管理与发布策略阶段](../ph20-config-release/20-config-release.md)）、数据遥测上行与实时协议接入 MQTT/WebSocket（属 [ph21 通用数据采集与接入网关方向 Go 阶段](../ph21-data-ingest-gateway/21-data-ingest-gateway.md)）、服务间 RPC 的注册发现与负载均衡（ph11 微服务与 RPC 阶段已讲，本阶段只借用其 gRPC 技术形态讲接口设计）** —— 本阶段把"接口本身怎么定、怎么演进"讲透；消息、发布、数据接入是其它阶段的事。

## 2. 来源与演变

API 设计成为一门有章法的学问，比 Go 语言老得多，而且**先有 HTTP 的传输层事实，后有 REST 的抽象总结**。**设计哲学一句话加粗：接口契约是服务对调用方最长久的承诺——字段可以加、语义不能漂、文档必须真。** HTTP 1.0（1996）时代 URL 只是"取文件"的地址，Web 服务靠"动词塞 URL"（`/deleteDevice?id=1`）表达动作，无结构可谈。Roy Fielding 2000 年在他的博士论文里提出 REST（Representational State Transfer），把 Web 归纳为"资源 + 统一接口 + 无状态 + 超媒体"，"资源"成为建模单元——但论文是架构风格而非规范，落地靠社区解读。2008 年 Leonard Richardson 提出 Richardson Maturity Model（把"资源化 + HTTP 动词 + 状态码 + 超媒体"排成四级台阶），给了团队一个"做到哪一级算 RESTful"的可操作阶梯。

工具链侧的演进同样关键。API 描述语言从 2011 年 Swagger 开始（一个 JSON 描述 REST API 的项目），2015 年捐赠给 Linux Foundation 更名 OpenAPI Initiative，OpenAPI 3.0 于 2017 年发布——从此"API 文档"从 Word 进化为**可被机器消费的规范**，生成器、校验器、契约测试都有了单一输入。RPC 侧，Google 2015 年开源 gRPC（内部 Stubby 的对外版），与 2016 年发布的 proto3 一起把"强类型 IDL + HTTP/2 + 二进制编码"做成服务间通信的新默认；2017 年 gRPC 进入 CNCF。错误表达从"随意字符串"走向标准：RFC 7807（2016，Problem Details for HTTP APIs）与 2023 年的 RFC 9457 定义了机器可读的错误响应结构；RFC 8594（2019）定义了 Deprecation/Sunset 响应头，让"版本下线"第一次有了标准通告信号。下表是这条演变的里程碑：

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| HTTP/1.0、Web API 萌芽 | 1990s | URL 是"动作"入口；服务端用动词 URL 表达副作用 |
| Fielding 博士论文（REST） | 2000 | "资源 + 统一接口 + 无状态"：URL 命名资源而非动作 |
| Richardson Maturity Model | 2008 | 四级台阶：资源化、HTTP 动词、状态码、超媒体 |
| Swagger | 2011 | 首个广为流传的 REST API 描述格式（JSON） |
| protobuf 开源 / proto2 | 2008 | 二进制序列化 + IDL；字段号成为跨版本契约 |
| proto3 | 2016 | optional 演进、去 required、更多语言一等支持 |
| gRPC 开源 | 2015 | Google Stubby 对外版：HTTP/2 + protobuf 的 RPC 框架 |
| OpenAPI Initiative（Swagger 更名） | 2015 | Swagger 捐给 Linux Foundation，规范社区化 |
| OpenAPI 3.0 | 2017 | paths/components/多态；成为 API 工具链的统一输入 |
| RFC 7807 → 9457（Problem Details） | 2016/2023 | HTTP API 错误响应的标准结构（type/title/detail） |
| RFC 8594（Sunset） | 2019 | "这个版本何时下线"有了标准响应头 |

本文示例以 **Go 1.25** 为基线（本阶段全部示例/练习/项目的 go.mod 写 `go 1.25.0`：net/http 方法路由（1.22）、encoding/json、errors.Is/As（1.13）、slog（1.21）等本阶段用到的特性在基线上全部稳定可用，也与 ph15/ph16/ph17 对齐的仓库工具链版本一致），验证工具链 go1.25.6（darwin/arm64；零第三方依赖——examples/exercises/project 只使用标准库，`go build ./...`、`go test ./...`、`go vet ./...` 命令均已给出，GOCACHE/GOMODCACHE 可重定位到 /tmp 临时目录）。一个定心话：本阶段几乎没有"新语法"，全是**资源建模、兼容性判断、文档纪律**这些设计决策——它是整个 roadmap 里**语法最安静、心智负担主要在"承诺了什么、怎么守承诺"**的阶段。

## 3. 语法与参数

第 3 章按"设计一层层外扩"的顺序展开：先从**资源与方法**（3.1）和**兼容性判定标尺**（3.2）打好地基；再讲承诺太重时的**版本管理**（3.3）；接着是把承诺稳定化的三个具体战场——**错误结构**（3.4）、**集合接口**（3.5）、**字段演化**（3.6）；最后是**让承诺可机器检验**的 OpenAPI（3.7）与二进制世界的 protobuf/gRPC（3.8、3.9）。

### 3.1 REST 接口设计规范

REST 的第一纪律不是"优雅的 URL"，而是**先想清楚资源是什么，再用 HTTP 方法表达动作**。把动作塞进 URL（`POST /v1/devices/deleteDevice`、`GET /devices/delete?id=1`）是 2000 年代 Web 服务的遗风——它让每个动作成为新的端点承诺、让 GET 可能带副作用、让客户端无法从方法语义推测安全性。资源建模的三个惯例：

| 设计点 | 惯例 | 示例 |
|--------|------|------|
| 资源路径 | 集合用复数名词，单对象是集合的子路径 | `/v1/devices`、`/v1/devices/{id}` |
| 动作表达 | 动作要么是既有方法的语义（DELETE 注销），要么建模为子资源（命令队列） | `DELETE /v1/devices/{id}`、`POST /v1/devices/{id}/commands` |
| 层级深度 | 一层子资源足够；再深（`/a/{id}/b/{id}/c`）说明建模或检索方式出了问题 | `/v1/devices/{id}/firmware` 即可表达"固件"是设备下的从资源 |

Go 1.22+ 的 net/http 把 HTTP 方法写进路由模式（`mux.HandleFunc("POST /v1/devices", h)`，见 ph09），让"方法语义"成为路由的一等公民——这正是 REST 设计落地的语言侧前提。ex01-rest-design 的实现顺序可以说明这套纪律：

```go
// examples/ex01-rest-design/server.go —— 路由 = 资源路径 + HTTP 方法（截取）
// 验证环境：go1.25.6，零第三方依赖；构建/测试/vet 命令见文件头
// 验证状态：已验证（go1.25.6 本机实测 vet/build/test 全绿，见 examples/README）

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/devices", s.handleList)          // 集合：只读
	mux.HandleFunc("POST /v1/devices", s.handleCreate)       // 创建：副作用 + 新资源
	mux.HandleFunc("GET /v1/devices/{id}", s.handleGet)      // 单对象：只读
	mux.HandleFunc("PUT /v1/devices/{id}", s.handleReplace)  // 全量替换
	mux.HandleFunc("PATCH /v1/devices/{id}", s.handlePatch)  // 部分更新
	mux.HandleFunc("DELETE /v1/devices/{id}", s.handleDelete) // 删除（幂等）
}
```

**HTTP 方法的语义与幂等性是契约的核心**——它决定客户端能不能安全重试。方法幂等（idempotent）指"同一请求执行 N 次与执行 1 次的副作用相同"，这是 roadmap 必会概念 3「幂等接口更适合重试」的地基：

| 方法 | 语义 | 幂等？ | 副作用位置 | 客户端重试策略 |
|------|------|--------|-----------|---------------|
| GET | 读资源 | 是 | 无 | 天然可重试；超时重发即可 |
| DELETE | 删除资源 | 应设计为是 | 有 | 超时可重发：重复删除应得到同样的成功（不存在也 204） |
| PUT | 用请求体完整替换资源 | 应设计为是 | 有 | 超时可重发：替换成同一状态是安全的 |
| POST | 创建资源或触发动作 | 否 | 有 | 超时**不可盲目重发**——可能已创建（见 3.6 的幂等键） |
| PATCH | 部分更新 | 不保证 | 有 | 视语义而定，保守策略同 POST |

ex01 的 `handleDelete` 演示了 DELETE 的幂等落地——资源已不存在也回 204，不让重复删除的客户端困惑（注释里写着这句理由）。设计 DELETE 时真正的分歧点是"幂等 204" vs "严格 404"：前者对重试友好（客户端不用先 GET 再删），后者对调用方排查"目标在不在"有用；二选一后必须**写进文档**并保持，因为"第一次 204、第二次 404"会让自动重试逻辑无所适从。

**PUT 与 PATCH 的分工**是新手最容易含糊的一对。PUT 是"请求体 = 完整表示"，缺的字段落零值——客户端没传 `online`，结果就是 `false`；PATCH 是"只更新给出的字段"，需要区分"没传"与"传了 false"，Go 里用指针字段区分这两种情况：

```go
// examples/ex01-rest-design/server.go —— PATCH 部分更新：指针区分"没传"与"传了零值"（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

var req struct {
	Name   *string `json:"name"`   // *string：nil = 没传；非 nil = 客户端显式给值（含 "")
	Online *bool   `json:"online"` // *bool 同理：区分"没传"与"传了 false"
}
// ...解码后...
if req.Name != nil {
	cur.Name = *req.Name
}
if req.Online != nil {
	cur.Online = *req.Online
}
```

**状态码也是契约**。客户端会为状态码写分支，因此状态码的选择要能回答"调用方拿到它能做什么"：2xx 表示成功且语义明确（200 读/写成功、201 创建成功 + Location 指向新资源、202 已受理异步执行、204 成功且无响应体）；4xx 是调用方的问题（400 请求体/参数不合法、401 未认证、403 无权限、404 资源不存在、409 状态冲突、422 语义上无法处理）；5xx 是服务端的问题（500 兜底、503 暂不可用可稍后重试）。一条工程纪律：**4xx/5xx 的边界别画错**——把"缺参数"回成 500，客户端将无法区分"我的错"与"你的错"，重试与报障策略随之失灵。

> 网关层的能力（限流 429、鉴权、聚合）与"服务网格/网关的 API 发布面"属于 ph11/ph12 的工程形态，本阶段聚焦服务自身出口的接口设计；实时双向通信（长连接推送、MQTT 遥测）不是 REST 方法语义能表达的，属 [ph21 通用数据采集与接入网关方向 Go 阶段](../ph21-data-ingest-gateway/21-data-ingest-gateway.md)。

### 3.2 兼容性基础：破坏性变更的判定

版本管理、错误结构、字段演化本质都在回答同一个问题：**一次改动会不会打破已经上线运行的老客户端？** 因此先立全章的统一标尺——兼容性的两种方向：

| 方向 | 含义 | 谁在受益 |
|------|------|---------|
| 向后兼容（backward compatible） | **新服务端**仍能服务**老客户端**：老客户端不升级也能照常工作 | API 语境默认指这个：加字段、加端点都不算破坏 |
| 向前兼容（forward compatible） | **新客户端**能读**老服务端**的数据：老数据/老响应不含新字段也能被容忍 | 客户端先于服务端发布、灰度回滚期、消息队列里老 producer 新 consumer |

"兼容"不是字面什么都不许改，而是**老客户端依赖的行为不被悄悄改变**。判断一次改动是否破坏性，用"一个已上线的客户端会不会因此出错"来检验，而不是"URL 变没变"。对照表（3.3~3.8 的细则都从这张表派生）：

| 变更 | 破坏性？ | 为什么 / 反例 |
|------|---------|--------------|
| 响应**加可选字段** | 否 | 老客户端解析 JSON 时忽略未知字段（Go 的 json.Decoder 默认忽略），不会报错 |
| 请求**加可选参数** | 否 | 老客户端不传新参数，服务端用默认值即可 |
| 响应**删字段** | **是** | 客户端代码里 `resp.xxx` 直接编译不过 / 运行时取到空值还不自知 |
| 字段**改名 / 改 JSON 名** | **是** | 形同删旧字段加新字段；客户端按旧名取数据全部落空 |
| 字段**语义漂移** | **是** | 名字没变但含义变了（如 `online` 从"进程活着"变成"最近 5 分钟心跳过"）——编译不报错，行为悄悄错，最阴险 |
| 字段**类型变化** | **是** | `status` 从字符串变枚举对象；数值单位从秒变毫秒 |
| 加**必填校验 / 新必填字段** | **是** | 老客户端从不传该字段，一旦服务端强制必填，老请求全部 400 |
| 排序 / 分页语义变化 | **是** | 客户端翻页依赖稳定顺序，默认排序变了就重漏（见 3.5） |
| 错误码删除 / 复用 | **是** | 客户端为 `code` 写的分支退化成"未知错误"兜底（见 3.4） |
| 增加端点、增加状态码 | 否 | 新能力；老客户端用不到也不受影响（新状态码需谨慎，见 3.4） |

由此得到本阶段反复出现的一条总则（roadmap 必会概念 1）：**字段只增不删更利于兼容——可加的永远通过"追加"完成，不可加的（删、改、改语义）视为一次需要走版本管理的破坏性变更**。3.3 讲"破坏性变更才升版本"，3.6 讲"怎么把演进做在追加里"，3.4/3.5 讲"错误与集合契约如何遵守同一张表"。

兼容性还有成本的一面：**兼容窗口**。永远兼容不现实（数据结构会腐烂），工程上要给"老承诺"设过期——这需要明确的宣布（RFC 8594 的 Deprecation/Sunset，见 3.3）与可执行的过渡期，而不是某天静默改掉。兼容窗口多长没有标准答案：外部公开 API 通常按年承诺，内部服务可能一个季度；关键是**窗口长度要写进文档，别让客户端猜**。

> 判断"这算不算破坏"时最容易犯的错是站在服务端视角（"我内部重构了，字段集合没变啊"）。判据永远站在客户端视角：客户端代码会不会编译失败、运行期取到空值/错值、重试会不会重复副作用。3.6 的 JSON 细节会把这个视角落到具体序列化行为上。

### 3.3 版本管理策略

版本存在的意义是：**当一次破坏性变更无法避免时，给老客户端留一条不升级也能跑的路**。先回答两个前置判断：

- **什么时候需要版本**：对外公开发布、调用方是你管不到或升级很慢的实体（第三方、独立团队、车载终端等嵌入式客户端）、同一份数据要同时服务行为差异巨大的调用方。反过来——**什么时候不需要**：内部服务单团队快速迭代、调用方与实现同步发布（一起部署一起升级）、破坏性变更可通过一次性迁移消化。roadmap 阶段验收要能说明接口兼容策略，第一条就是能判断"我这个接口要不要版本号"。给接口预埋 v1 却没想清楚"什么情况才升 v2"，通常只是仪式。
- **能用兼容路径就别升版本**：3.2 的判定表说明多数需求（加字段、加端点）走"追加"就能满足，不需要新版本。**版本是破坏性变更的出口，不是常规迭代的轨道**——每次发布都升大版本号的服务，等于告诉客户端"你们的兼容承诺一文不值"。

需要升版本时，三种载体对比：

| 载体 | 形态 | 优点 | 代价 |
|------|------|------|------|
| URI 前缀 | `/v1/devices`、`/v2/devices` | 最直观：URL 即契约，curl/日志/缓存天然区分；网关无需额外解析 | 语义上"版本"与"资源路径"耦合；同一资源有多个 URL |
| 请求头 / 媒体类型 | `Accept: application/vnd.device.v2+json` | 语义最强：URI 稳定、可表达"协商"（同一 URL 返回不同表示） | 调试不方便、缓存与网关要理解协商逻辑、出错时难排查版本 |
| Query 参数 | `/devices?v=2` | 实现最省事 | 污染 query、与分页/过滤参数混在一起、最不"资源化" |

Google API Design Guide 等现代实践多采用 **URI 版本 + 尽力兼容**的组合：URI 版本让"这是两代契约"显式可见；同时用 3.2 的纪律把"可追加的"留在当前版本内做掉，让版本号只在真破坏时+1。ex04-versioning 演示的 v1/v2 共存形态是这套组合的最小落地：

```go
// examples/ex04-versioning/server.go —— v1 老版本：v1 DTO + 弃用通告头（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

func (s *Server) handleGetV1(w http.ResponseWriter, r *http.Request) {
	d, err := s.store.Get(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusNotFound, "DEVICE_NOT_FOUND", "device not found")
		return
	}
	// Deprecation: true + Sunset 建议迁移期限——老版本还服务，但明确告知会下线。
	w.Header().Set("Deprecation", "true")
	w.Header().Set("Sunset", time.Now().AddDate(0, 6, 0).UTC().Format(http.TimeFormat))
	writeJSON(w, http.StatusOK, toV1(d))
}
```

**v1/v2 共存的关键形态：同一份领域数据 + 同一个 service，差异只在入口各裁剪各的 DTO**。版本是对外"表示"的分叉，不是业务逻辑的分叉——若升 v2 时把业务规则复制一份，两个版本会各自漂移、规则改一处忘一处。ex04 的 `deviceV1`/`deviceV2` 与 `toV1`/`toV2` 裁剪函数演示了这一点（v1 永不泄漏 v2 的 `model`/`lastSeen` 字段，单测钉住），project 把它放大为"领域模型无 json tag、不属于任何版本"的完整结构。

**下线的纪律**：弃用（deprecate）不是删除，RFC 8594 给出标准通告——每次响应带 `Deprecation: true`（或 RFC 版本日期）与 `Sunset: <HTTP-date>`，告诉客户端"该搬家了，最后期限是 X"。到期下线的两条注意：① 下线后老 URL 回 **410 Gone**（资源曾存在、故意不再提供）比 404 更有信息量——404 会让人以为只是路径写错；② 移除 v1 时契约测试会提醒你哪些客户端能力一并消失（project 的 contract_test 覆盖了 v1 路径集合，是"下线审计"的自动化雏形）。

> 灰度发布（新旧共存期间的流量切分、按版本路由、回滚）属 [ph20 配置管理与发布策略阶段](../ph20-config-release/20-config-release.md)；本阶段只管"契约层面新旧如何共存"，不管"流量层面如何切"。事件/消息里的 schema 版本管理（protobuf 兼容规则在消息队列里的同类问题）属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)。

### 3.4 错误结构与错误码演进

错误结构是服务对调用方"出错时能拿到什么"的承诺，兑现 ph17 3.6 埋下的"错误码只增不删"。**错误结构要稳定的含义有两层：JSON 的外形稳定（字段名、必填性）+ 错误码的语义稳定（code 出现即永远有效、含义不漂移）。** 分而治之的职责划分：

| 错误结构的组成部分 | 给谁看 | 稳定性要求 |
|-------------------|--------|-----------|
| `code` | 客户端程序逻辑（if/switch、重试、文案映射） | **只增不删、语义不漂移**；是机器可处理的稳定标识 |
| `message` | 人（日志、报障、默认文案） | 可改不可删；**客户端不得依赖它做逻辑判断** |
| `requestId` / `details`（可选追加） | 报障定位 / 结构化提示"哪个字段错了" | 追加字段对老客户端无害（JSON 忽略未知字段） |
| HTTP 状态码 | 传输层语义 | 与 code 是多对多映射（见下），但 4xx/5xx 边界稳定 |

用 ex02-error-struct-evolution 的对外结构看"外形稳定"如何落到 Go 代码——**`code`/`message` 不带 omitempty**，这两个字段任何时候都出现在响应体里：

```go
// examples/ex02-error-struct-evolution/errs.go —— 对外错误结构（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

type Error struct {
	Code      Code     `json:"code"`               // 必填永在：不带 omitempty
	Message   string   `json:"message"`            // 必填永在
	RequestID string   `json:"requestId,omitempty"` // v2 追加的可选字段：老客户端忽略即可
	Details   []Detail `json:"details,omitempty"`   // v2 追加的可选字段
	Err       error    `json:"-"`                   // 内部根因：只进日志，不出响应体
}
```

为什么"必填永在"要刻意用测试钉住？因为 Go 的零值序列化坑：若给 `code` 加 `omitempty`，零值 code 会被静默丢弃，响应体里字段缺失——老客户端解析不到 `code` 时退化成"猜"。ex02 的测试断言 `code`/`message` 序列化后永远存在（零值也输出），就是这条纪律的保险丝。`requestId`/`details` 这类"演进新字段"则相反，必须带 omitempty——它们缺失时老客户端应容忍零值，这正是 3.2 判定的"加可选字段 = 非破坏性"在序列化层的兑现。

**错误码是文档的一部分**：任何一个对外出现的 code 都要能在注册表里查到"哪一版发布、什么语义"。集中注册的意义不只是文档化，而是让"只增不删"可以自动化：

```go
// project/internal/apierr/apierr.go —— 错误码注册表：集中、带发布版本、只增不删（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

// 注册表：登记每个对外 code（含首次发布版本与语义）。删除 = 破坏性变更。
var registry = []struct {
	Code    Code
	Since   string
	Meaning string
}{
	{CodeBadRequest, "v1.0", "入参不合法（非法参数值/坏 JSON）"},
	{CodeNotFound, "v1.0", "设备不存在（查询/注销目标缺失）"},
	{CodeInternal, "v1.0", "服务内部错误（兜底；细节只进日志）"},
}
```

**为什么删码是破坏性变更**：客户端可能已经写了 `if code == "DEVICE_NOT_FOUND" { 提示用户重试 }` 这样的分支。删掉这个码不会让客户端编译失败，但会把它的错误处理静默踢进"未知错误"兜底——行为悄悄变坏，比 404 还难排查。同理，"复用"旧码表示新含义等于同时删了一个码又改了一个码的语义。因此新增错误码的时机也要克制：**客户端要编程处理的错误才配一个 code**（需要区分重试？需要区分"没找到"与"参数错"？），只是给人看的说明留在 message 里。码表粒度太细（每个字段错一个码）会让客户端写一堆永远用不上的分支——这是"错误结构稳定"的另一面：少而稳。

**错误码与 HTTP 状态码是多对多映射**，需要一张集中表而不是散落的 if：同一个 `NOT_FOUND` 语义在 REST 映射 404、在 gRPC 映射 `google.rpc.Code.NotFound`（3.9）、在内部 RPC 里可能只是布尔结果。集中映射的好处是换协议只改这一层（ph17 3.6 已在 handler 层做过一次，本阶段把它列为对外契约的一部分并加测试）：

```go
// exercises/sol-02-error-schema/httperr/httperr.go —— 错误码 → HTTP 的集中映射（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

// Map 把 error 翻译成 (HTTP 状态码, 对外错误结构)。调用方负责写响应，
// 映射本身保持纯函数——service 层只产生领域错误，翻译只在这一层发生一次。
func Map(err error) (int, errs.Error) {
	var e *errs.Error
	if !errors.As(err, &e) {
		// 未知错误类型：兜底 500，Message 用通用文案——真实原因在调用方日志里。
		return http.StatusInternalServerError, errs.Error{
			Code:    errs.CodeInternal,
			Message: "internal error",
			Err:     err,
		}
	}
	return codeHTTP(e.Code), *e
}

// codeHTTP 错误码 → HTTP 状态码映射表（多对一的集中登记处）。
func codeHTTP(c errs.Code) int {
	switch c {
	case errs.CodeValidation:
		return http.StatusBadRequest // 400
	case errs.CodeNotFound:
		return http.StatusNotFound // 404
	case errs.CodeConflict:
		return http.StatusConflict // 409
	case errs.CodeRateLimit:
		return http.StatusTooManyRequests // 429
	default:
		return http.StatusInternalServerError // 500 兜底（含 INTERNAL）
	}
}
```

配套的错误结构演进实验见 examples/ex02（v1 `{code,message}` 演进到 v2 追加 `requestId`/`details`，老客户端解析新响应不炸），错误码注册表纪律的自动化验证见 project 的 apierr_test（"历史发布 code 永不可删"）。**roadmap 阶段验收 3 的"给 API 写示例和错误说明"**指的就是：每个 code 配一段文档——什么时候返回、调用方可做什么——客户端不读代码也能处理错误（exercises/README 练习 2 专门要求交这份错误码文档表）。

> 错误结构演进（v1 加可选字段升 v2）与 3.6 的字段演化是同一条纪律的两个应用场景，本阶段 examples/ex02 与 project 各演示一处。发送给消息队列的错误/事件结构（消费方也是"客户端"）遵循同样的只增不删，但事件 schema 的版本与兼容窗口策略属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)展开。

### 3.5 分页、过滤、排序

集合接口（`GET /devices`）是列表数据的主战场，也是最容易被"悄悄改坏"的契约——因为翻页正确性依赖顺序稳定性，而顺序稳定性通常没人写进文档。集合接口的三件套按此顺序设计：

**① 过滤先于分页**。`total` 必须是**过滤后**的总数，否则客户端看到的"共 X 条"与翻出来的数据对不上。处理管线固定为：过滤 → 排序 → 切片。ex03-pagination-filter 把这条规则做成可脱离 HTTP 的纯函数：

```go
// examples/ex03-pagination-filter/query.go —— 过滤 → 排序 → 切片（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

func Apply(all []Device, q Query) Page {
	filtered := make([]Device, 0, len(all))
	for _, d := range all {
		if q.Status != "" && d.Status != q.Status {
			continue // 过滤：枚举精确匹配
		}
		if q.Q != "" && !strings.Contains(d.Name, q.Q) {
			continue // 过滤：文本模糊匹配
		}
		filtered = append(filtered, d)
	}
	// ...排序（见下）...
	items := append([]Device(nil), filtered[start:end]...) // 本页是副本，不共享底层数组
	return Page{Items: items, Total: len(filtered), Offset: start, Limit: q.Limit}
}
```

**② 稳定排序 = 唯一决胜键**。任何排序都必须"可预测"，否则翻页重复或遗漏：主排序字段相等时落到一个**唯一的决胜键**（通常是 id）。ex03 的排序实现里，无论按 name 还是 status 排序，比较器最终都回落到 `a.ID < b.ID`。翻页测试的黄金断言就是：**把全部数据翻完，断言各页并集 = 全集且无重复**（exercises 练习 1 的验收标准）。排序字段用**白名单**而不是任意字段：每开放一个可排序字段，就等于承诺了它的语义与稳定性（字段改名/语义变化会破坏依赖排序的客户端）；白名单外的排序请求——回退默认排序而非报 400——因为返回 400 会把"排序能力"变成一次承诺，回退则是温和的降级（ex03 注释写明这个理由）。默认排序要选**最稳定**的键（id 或创建时间），并写进文档。

**③ 分页：offset vs cursor**。两种分页模型各有取舍：

| 维度 | offset + limit | cursor（游标） |
|------|---------------|----------------|
| 跳页 | 支持（offset=100 直接跳） | 不支持（只能顺着游标走） |
| 数据变动下的稳定性 | 翻页期间有插入/删除会重复或漏项 | 游标锚定排序键，插入删除只影响游标附近 |
| 服务端实现 | 简单：排序后切片 | 需要持久或可编码的游标（`?cursor=<opaque>`） |
| 深翻页代价 | offset 大时全量排序成本高 | 每次 O(游标之后) 或索引跳转 |
| 典型适用 | 管理后台、总量小、可接受快照抖动 | 面向用户的信息流、体量大、实时变动 |

offset 分页要定义**缺省值与上限**（如 limit 缺省 20、最大 100），且把非法参数（负数、超上限）当作客户端错误回 400——上限的额外意义是防恶意大页请求拖垮服务。响应 envelope（`{items,total,offset,limit}`）里的每个字段都是对外契约，字段只增不删同样适用（ex03 data.go 注释明示）。

**过滤语法**的分寸：单值过滤（`?status=offline`）与文本模糊（`?q=关键字`）用扁平的 query 参数即可，简单、可被 OpenAPI 描述；通用表达式语法（OData `$filter`、GraphQL 式任意查询）表达能力虽强，但每个操作符都成为新的契约承诺，解析与校验成本随复杂度上升，需要权衡后再上。**参数校验的错误码要稳定**（非法枚举回什么 code、非法数字回什么 code），因为客户端会为它们写重试/纠错逻辑。

> 游标的具体编码（base64 封装排序键与过滤上下文）与"游标过期"语义各家实现不同，本阶段以理解 offset 的局限与 cursor 的取舍为目标，examples/ex03 用 offset 落地全流程；通用查询语法（$filter/$orderby 的解析）属于"把过滤做成协议"的进阶形态，不是默认需求。

### 3.6 资源与字段的长期演化

3.2 给了判定表，本小节把"字段怎么演化"落成可操作的 Go 纪律——兑现 ph17 3.2 埋下的"domain 不该被 HTTP 格式绑架"。**资源结构一旦对外发布，它的字段集合就是契约**（ex01 model.go 的注释："资源结构的稳定性 = 字段只增不删、字段语义不漂移"）。四个层次逐层展开：

**第一层：domain 与对外视图解耦（DTO 是契约的物理载体）**。领域模型是服务内部的事实源，字段随业务演进自由生长；对外承诺的是 **DTO**——每个版本一份、只含该版本承诺的字段。ph17 3.2 的"domain 不该被 HTTP 格式绑架"在这里兑现为：**domain 结构不带 json tag、不直接序列化；序列化的是 DTO，json tag 只出现在 DTO 上**。project 的内部结构是这条纪律的完整标本：

```go
// project/internal/devices/device.go —— 领域模型 vs 按版本裁剪的 DTO（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

// Device 领域模型（内部表示；对外字段集合由各版本 DTO 决定）——无 json tag。
type Device struct {
	ID       string
	Name     string
	Online   bool
	Model    string // 领域层早就有的字段，v1 用户不该看到
	LastSeen int64  // unix 秒
}

// DeviceV1 v1 响应视图：发布时的字段契约。
type DeviceV1 struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Online bool   `json:"online"`
}

// DeviceV2 v2 响应视图：v1 超集 + model/lastSeen（字段只增不删）。
type DeviceV2 struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Online   bool   `json:"online"`
	Model    string `json:"model"`
	LastSeen int64  `json:"lastSeen"`
}
```

**第二层：字段只增不删，演进靠追加**。给响应加字段对老客户端无害（JSON 解析忽略未知字段），所以"v2 比 v1 多一个字段"是合法的超集演进；老客户端解析 v2 响应时按 v1 的 DTO 结构忽略 `model`/`lastSeen` 即可。project 用 handler_test 断言"v1 响应绝不泄漏 v2 字段"——超集方向只允许新版本对新版本：**v1 保持原样，能力从 v2 起追加**。反过来，若 v1 泄漏了 v2 字段（把领域对象直接序列化了），等于 v1 悄悄扩大了承诺，未来收不回来。

**第三层：字段语义是隐形的契约**。`online` 从"进程活着"漂移成"最近 5 分钟有心跳"——字段名没变，客户端的时间判断逻辑全错。语义漂移是破坏性变更里最阴险的一种（编译不报错、文档可能没改），防法只有一个：**改语义当作破坏性变更走版本流程，而不是顺手改掉**。同样地，字段的类型与单位是语义的一部分：`lastSeen` 用秒还是毫秒、`status` 是字符串还是枚举对象，发布即承诺。

**第四层：JSON 序列化的具体陷阱**。Go 的 encoding/json 有三个行为必须在设计时想清楚，否则会在演进时反咬：

| JSON 行为 | Go 侧事实 | 演进启示 |
|-----------|----------|---------|
| 未知字段忽略 | `json.Unmarshal` 默认丢弃未声明字段；`DisallowUnknownFields` 可开启严格模式 | 新服务端给老请求/老客户端忽略新字段——加字段安全的前提。**但**开了严格模式的服务端会拒绝任何带新字段的请求，与向前兼容冲突（ex02 的 errs_test 专门演示） |
| 零值省略 | `,omitempty` 让零值字段不出现在 JSON 里 | 对"必填永在"的字段（错误结构的 code/message）绝不能加 omitempty（3.4）；对可选演进字段恰恰要加 |
| null vs 缺失 | `null` 与"没这个键"解码后都是零值，无法从结果区分 | 需要区分"没传"与"传了 null"时用指针字段（3.1 的 PATCH 已经用过一次）；两者都让老客户端读到零值——设计上把零值定为"无意义" |

**幂等：让资源操作可安全重试**。字段演化解的是"数据结构怎么长大"，幂等解的是"操作怎么重试不坏事"，同属资源契约的稳定性（roadmap 必会概念 3）。3.1 已给出方法级幂等（GET/PUT/DELETE 幂等、POST 不幂等）；对 POST 这类天然不幂等的操作，标准解法是 **幂等键（Idempotency-Key）**：客户端为一次"意图"生成唯一键随请求发送，服务端记住"这个键已经处理过、结果是 X"，重放同键请求直接返回 X 而不重复执行副作用。配套纪律：服务端处理中的同键并发请求要串行或让后到者等待；幂等键有存储成本与过期时间（不能永远记住）；键的生成与重试窗口由客户端负责。设备指令下发（`POST /devices/{id}/commands`）是典型场景——离线设备重发指令，服务端要能识别"这是同一条指令的重试"而不是第二次执行。

> 消息系统的"at-least-once 投递 + 消费者幂等"是幂等思想在异步侧的延续，但事件流水、重试/死信的具体机制属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)；本阶段只建立"POST 不幂等、需要幂等键兜底重试"这条 REST 侧纪律。

### 3.7 OpenAPI 文档与实现同步

roadmap 必会概念 4：「API 文档应和实现同步」。先承认一个残酷事实：**手写的文档几乎必然与实现漂移**——服务端加了个字段忘了改文档，删了条路由忘了更新，新同事对着过期的 curl 示例联调失败。OpenAPI（前身 Swagger）把"文档"从人读的 Markdown 变成**机器可消费的规范**（JSON/YAML），同步问题才第一次有工程解法。

**spec-first vs code-first** 是两条相反的路线：

| 路线 | 流程 | 优点 | 代价 |
|------|------|------|------|
| spec-first（规范先行） | 先写 OpenAPI 文档（承诺）→ 再按文档实现 → 契约测试双向对账 | 承诺先于代码存在；文档天然权威；可先给客户端 mock | 实现必须"照着承诺写"，多一道对账工序 |
| code-first（代码先行） | 先写 handler/结构体 → 用工具（swaggo 等）从代码注解生成文档 | 实现即真相，代码改文档跟着生成 | 文档质量取决于注解纪律；生成的文档常缺 example/语义描述 |

spec-first 的价值在于**让承诺先于实现存在**——写文档的过程就是设计决策的过程：这个端点收什么参数、回什么结构、每种错误长什么样，全在写代码前被逼着想清楚。ex05-openapi-sync 用"手写 openapi.json + 契约测试"演示这条路线的核心机制（零第三方下的最小化实现；真实工程换成 oapi-codegen/buf 等工具链，原理相同）：

```go
// examples/ex05-openapi-sync/contract_test.go —— 文档与实现同步的契约测试（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

// TestRoutesMatchSpec：spec.paths 与实现 Routes() 双向一一对应——漂移双向拦截。
func TestRoutesMatchSpec(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	// spec 侧
	specRoutes := map[string]bool{}
	for path, p := range spec.Paths {
		for _, m := range p.Methods() {
			specRoutes[m+" "+path] = true
		}
	}
	// 实现侧：Routes() 是 handler 暴露的路由清单（可自省，见 4 章）
	implRoutes := map[string]bool{}
	for _, rt := range Routes() {
		implRoutes[rt.Method+" "+rt.Path] = true
	}
	for k := range specRoutes {
		if !implRoutes[k] {
			t.Fatalf("spec declares %s but implementation has no such route", k)
		}
	}
	for k := range implRoutes {
		if !specRoutes[k] {
			t.Fatalf("implementation serves %s but spec does not declare it", k)
		}
	}
}
```

契约测试在 CI 里跑，**任何漂移（实现多一条路由、响应多一个字段、错误结构不一致）都在合并前变红**——这就是"文档与实现同步"的机制保证，而不是靠自觉。spec 文档要写到"别人照抄就能联调"的程度：每个 2xx 响应带 **example**（而不是空壳 schema）、每种错误带 **description 与示例 code**、错误响应统一引用共享的 Error 组件（避免每个端点手抄一份错误结构、抄着抄着不一致）。OpenAPI 的共享组件（`components/schemas`、`components/responses`）正是为"错误结构只写一处"而生——这与此阶段 3.4 的"错误结构稳定"形成呼应：**文档里的错误组件单一、实现里的错误注册表单一，两者由契约测试锁死**。

**同步的三个自动化层次**（由轻到重）：① 契约测试——断言"spec 声明的路由/参数/字段 ⊇ 且 ⊆ 实现"（本阶段 examples/ex05 与 project 落地的是这一层）；② 生成器——用 oapi-codegen 直接从 spec 生成 Go handler 接口与模型，实现只是填空，结构天然一致（工具属 ph15 工具链实践的进阶用法，本阶段零第三方不做）；③ schema 级校验——运行期把响应体对 spec 的 JSON Schema 做校验，最严格但性能与调试成本最高。真实工程通常组合使用：spec-first 出契约 → 生成器产桩 → 契约测试守住漂移。

**谁对谁同步**要明确方向：spec 是权威（单一来源），实现追 spec；契约测试是"追"这个动作的机器保证。若允许实现与 spec 互相"覆盖"（改代码顺手改 spec），方向就丢了。本阶段的 examples/exercises/project 都用"spec 权威 + 实现对齐 + 测试锁死"这个方向。

> OpenAPI 3.0/3.1 的完整语义（多态 oneOf/anyOf、安全声明、回调、链接）与工具链（oapi-codegen、swaggo、go-openapi、stoplight）属于"规范深水区"，本阶段目标是理解"文档为何能与实现同步"的机制与最小实现；把 YAML/JSON 规范编译为类型安全桩的完整工具实践留给你在真实项目里按 spec 规模选用。

### 3.8 protobuf 兼容规则

REST/JSON 讲的是文本契约的演进；protobuf 是二进制世界里同一问题的答案，而且它的机制更"物理"——兼容性建立在**编码规则**上而不是客户端宽容度上。protobuf 消息的兼容哲学与 JSON 世界呼应但实现不同：**JSON 靠"客户端忽略未知字段"实现向前兼容；protobuf 靠"解码器跳过未知字段号"实现兼容，字段号（field number）取代字段名成为契约的锚点**。

protobuf wire format 的消息体是一串 `(tag, payload)` 的级联：`tag = (字段号 << 3) | wire type`。wire type 决定负载怎么解释（0=varint、2=length-delimited、5=32-bit 等）。关键机制：解码器**不认识某个字段号时，仍然能按 wire type 跳过它的负载继续前进**——这就是"老程序读新消息、新程序读老消息"都不炸的全部秘密。ex06-protobuf-wire-compat 用标准库手写了一个最小 wire format 实现来演示（真实工程用 protoc 生成代码，但编码规则是公开规范）：

```go
// examples/ex06-protobuf-wire-compat/pbwire.go —— 未知字段按 wire type 跳过（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

// Parse 对每一个 tag 读出 wire type，据此跳过/读取负载。不认识的字段号不会被拒绝，
// 而是照常按 wire type 前进——这就是"未知字段被安全忽略"的实现机制。
func Parse(data []byte) ([]Field, error) {
	var out []Field
	pos := 0
	for pos < len(data) {
		tag, next, err := skipVarint(data, pos)
		if err != nil {
			return nil, err
		}
		pos = next
		number := int(tag >> 3) // 高 29 位 = 字段号
		wire := int(tag & 7)    // 低 3 位 = wire type
		f := Field{Number: number, Wire: wire}
		switch wire {
		case wireVarint:
			// ...读出 varint 负载...
		case wireBytes:
			// ...读出长度前缀 + 负载字节...
		case wireFixed32:
			// ...跳过 4 字节...
		default:
			return nil, fmt.Errorf("field %d unsupported wire type %d", number, wire)
		}
		out = append(out, f)
	}
	return out, nil
}
```

由此推导出 protobuf 演进的四条铁律（与 JSON 世界的规则一一对应）：

| protobuf 规则 | JSON 世界的对应 | 违例后果 |
|--------------|----------------|---------|
| **字段号是契约，字段名不是**：改名（`id` → `device_id`）不影响线上格式 | JSON 的字段名即契约 | 字段名随意改导致生成代码不同步，但线上字节流不变——两边的坑互为镜像 |
| **新字段用新字段号追加**，绝不能复用已删除的号（回收要 `reserved` 声明） | 加新字段名 | 复用一个旧号 = 新旧代码对该字段的解释错位，静默产生脏数据 |
| **删除字段必须 reserved 占位**，防止未来复用号 | 删字段用 omitempty/文档声明"不再使用" | 同上；reserved 是给未来自己的便签 |
| **类型演进限兼容位宽**：int32↔int64 等数值可扩；string 与 int 互换破坏；optional/oneof 语义不可逆转 | 类型变化 = 破坏性变更 | 读写双方按各自理解的类型解释同一字节 |

字段号还受**范围纪律**约束：1~15 的 tag 只占 1 字节（省空间，留给高频字段），19000~19999 保留给 protobuf 实现。`oneof` 的演进比普通字段更谨慎——oneof 内的成员变化会改变"哪个字段被选中"的语义，与 3.6 的"字段语义不漂移"同理。protobuf 兼容测试的意义在于把"字节流仍然可互读"变成可执行的断言（ex06 的四组实验分别验证加字段老 reader 无损跳过、老数据缺字段落零值、改字段号造成无声错位、reserved 拦截复用）。

> wire format 的编码细节（varint 的 7 位分组、zigzag、嵌套消息的长度前缀）在 4 章展开；本小节的落点是"为什么 protobuf 敢说向前/向后兼容"——因为未知字段跳过是解码器结构性的行为，不是文档里的一句承诺。

### 3.9 gRPC 接口设计与错误模型

ph11 微服务与 RPC 阶段讲过 gRPC 的通信形态（方法、服务定义、调用方式）；本小节补上**接口设计视角**：service 定义里怎么设计 RPC 方法、怎么用错误模型表达失败、gRPC 与 REST 的映射怎么统一。gRPC 的 IDL（`.proto`）本身就是契约文档——比 REST 的 OpenAPI 更早做到"接口即代码、代码即接口"，proto 文件编译出的服务接口与消息结构就是双方唯一的对齐点。

**方法设计（Unary vs Streaming）**：`.proto` service 里每个 RPC 的形态要在"一次请求一次响应"与"流式"之间选择：

| RPC 形态 | proto 写法 | 适合 | 不适合 |
|---------|-----------|------|--------|
| Unary（一元） | `rpc GetDevice(GetDeviceRequest) returns (Device)` | 请求-响应式查询与命令 | 大列表（一次全量返回撑爆内存） |
| Server streaming | `rpc WatchDevices(WatchRequest) returns (stream DeviceEvent)` | 服务端推送（状态变化订阅） | 请求式语义 |
| Client streaming | `rpc UploadTelemetry(stream Sample) returns (Summary)` | 客户端大批量上行 | ph21 设备遥测上行的候选形态 |
| Bidirectional streaming | `rpc Chat(stream Req) returns (stream Resp)` | 双向对话、实时控制面 | 简单请求响应场景（过度设计） |

与方法语义呼应：**一元方法应当设计成幂等/可重试的**（查询天然幂等；命令类方法若需重试安全，与 3.6 同理）。流式方法里"连接断开"是常态（超时、网络抖动），客户端要能重连并从断点续传——这是 ph21 遥测上行的前提认知。

**错误模型：google.rpc.Code 而非 HTTP 状态码**。gRPC 的错误不是"响应体里放个 JSON"，而是**随状态返回一个规范错误码**（google.rpc.Code 枚举，跨语言、跨版本稳定）+ 可选的错误消息与 details（携带结构化诊断）。这个枚举是 gRPC 生态的"错误结构稳定"总纲——REST 侧的 4xx/5xx 映射表（3.4）在这里有一张官方的对照（grpc-gateway 用它把 gRPC 错误翻译成 HTTP）：

| google.rpc.Code | 数值 | 典型语义 | HTTP 映射 |
|-----------------|------|---------|----------|
| OK | 0 | 成功 | 200 |
| INVALID_ARGUMENT | 3 | 参数/请求体非法 | 400 |
| NOT_FOUND | 5 | 资源不存在 | 404 |
| ALREADY_EXISTS | 6 | 资源已存在（创建冲突） | 409 |
| FAILED_PRECONDITION | 9 | 前置条件不满足（如设备离线） | 400 / 409 |
| OUT_OF_RANGE | 11 | 分页越界、值超范围 | 400 |
| UNAVAILABLE | 14 | 服务暂不可用（**可重试**信号） | 503 |
| DEADLINE_EXCEEDED | 4 | 超时 | 504 |
| INTERNAL | 13 | 内部错误 | 500 |
| UNIMPLEMENTED | 12 | 方法未实现 | 501 |

与 3.4 同构的纪律：**客户端该为"可重试错误"（UNAVAILABLE、DEADLINE_EXCEEDED 视情况）与"不可重试错误"（INVALID_ARGUMENT、NOT_FOUND）写不同分支**；gRPC 客户端库自带重试策略时（ph11 讲过），重试只会作用于可重试码——所以服务端**别用 INTERNAL 表达"刚才超时了"**，那是把可重试信号埋掉了。错误细节进 `details`（结构化、可编程处理），人类可读说明进 message——与 3.4 的"code 给机器、message 给人"完全同构。

**REST 与 gRPC 的契约收敛**：同一个业务服务常同时暴露两种形态（外部 REST + 内部 gRPC），此时**共享的领域错误定义**（语义层：not-found、conflict、invalid-argument）要定义一次，两边的映射表各自翻译（REST 侧查 3.4 的表，gRPC 侧查上表）——ph17 3.6 的"集中映射 = 换协议只改一处"在双协议并存时兑现为"一张语义错误表 + 两个翻译层"。错误码、字段名、语义描述若两套契约各写各的，迟早漂移成两个不同的 API。

> gRPC 的传输细节（HTTP/2 帧、流控、连接管理）在 4 章与 ph11 里讲；本小节不展开实现，聚焦接口设计层的三个决策：方法形态、错误码选择、双协议契约收敛。gRPC 服务治理（拦截器、超时重试、负载均衡）属 ph11，协议接入与遥测上行属 [ph21 通用数据采集与接入网关方向 Go 阶段](../ph21-data-ingest-gateway/21-data-ingest-gateway.md)。

## 4. 底层原理

**HTTP/2：一个连接上并行多个请求**。REST/JSON 跑在 HTTP/1.1 上时，同一连接同一时刻只能处理一个请求（head-of-line blocking），并发靠浏览器/客户端开多连接。HTTP/2 把连接切成**流（stream）**，每个流独立承载一次请求-响应，帧（frame）是流上的最小数据单元；一个 TCP 连接可以并行几十个流，还能做头部压缩（HPACK）与二进制帧。对 API 设计者这意味着：**并发请求不再消耗成倍连接，长连接保持活跃的开销大幅下降**——这是 gRPC 敢把"多次独立 RPC"复用在一个 HTTP/2 连接上的传输层前提，也是"连接复用 + 双向流"成为可能的原因。

**gRPC 帧协议**：gRPC 在 HTTP/2 之上再加一层自己的帧格式，每个消息帧 5 字节头 + 负载：

```text
gRPC over HTTP/2 的帧结构（每个消息一帧或多帧）
┌─────────────┬──────────┬───────────┬──────────────────────┐
│ 1 byte      │ 4 bytes  │ 1 byte    │ ...                  │
│ 压缩标志    │ 消息长度 │ 消息类型  │ protobuf 编码的负载  │
└─────────────┴──────────┴───────────┴──────────────────────┘
一条 gRPC 调用 = HTTP/2 流里：HEADERS（方法/路径/超时）→ DATA（请求消息帧）→ DATA（响应消息帧）→ HEADERS（grpc-status/错误码）
```

错误通过特殊的 **trailer 头 `grpc-status`** 返回（不是响应体），所以 gRPC 客户端可以在不解析消息体的情况下拿到错误码——这就是 3.9 表格里那些稳定码的传输位置。消息是 protobuf 编码的，因此 gRPC 的响应结构演进遵循 3.8 的全部规则。

**protobuf wire format 的兼容机制拆到底**。varint 编码：每字节 7 位有效数据 + 最高位作"延续位"，小整数 1 字节、大整数至多 10 字节；负数按 10 字节全量编码（除非用 sint/zigzag）。字段的 tag 编码：`(字段号 << 3) | wire type`，所以 1~15 号字段 tag 单字节（这也是高频字段放小区间的理由）。解码器结构性地支持"未知字段号照常前进"：

```text
消息编码 = 一串 (tag, payload)
tag = (字段号 << 3) | wire type       wire type: 0=varint 2=len-delimited 5=32bit ...

v1 定义 { 1: name }            v2 追加 { 2: online }
老 reader 读 v2 消息:
  tag(1, bytes) → 认识 1 号 → 按 length-delimited 读出 name
  tag(2, varint) → 不认识 2 号 → 按 wire type 0 跳过负载 → 继续前进 ✅
新 reader 读 v1 消息:
  tag(1, bytes) → 认识 1 号 → 读出 name；2 号不存在 → 落零值 ✅
若 v3 错误地复用 2 号给 name2（不同语义）:
  老 reader 跳过的还是 varint 负载，但新老 reader 对 2 号的解释不同 → 无声脏数据 ❌
```

"未知字段跳过"为什么必须**按 wire type** 而不是按字段号对应的声明类型？因为解码器只拿到 tag 里的 wire type，不知道（也不需要知道）字段号在本版本里的声明——同一个字段号在不同 proto 版本里 wire type 变了（如 int32 变 string），解码器按错类型跳过会把长度前缀读错、整条消息解析错位。所以 protobuf 的规则是"wire type 变了 = 不兼容"，这正是"int32 扩 int64 兼容、int 改 string 不兼容"的编码层原因。**向前/向后兼容在这里不是文档承诺，是解码器的结构性行为**——这也是 protobuf 敢把它写进规范而非建议的原因。

**OpenAPI 工具链的原理**：OpenAPI 文档本质上是一份可解析的 JSON/YAML 数据（paths → operations → 参数/响应 → schema 引用 components），工具链全部围绕"解析这份数据"展开：校验器把文档与 JSON Schema 校验器绑定；代码生成器把 paths/components 编译成语言桩代码（Go 的 oapi-codegen 生成 `ServerInterface` 与模型 struct，实现只需"填空"）；契约测试则把"文档声明的结构"与"实现的运行时结构"做双向对账。本阶段的 ex05/project 用标准库手写了一个**最小解析器**（只解析 paths、operation、responses、schema 子集），原理上就是真实工具链的缩小版——理解了"文档 = 数据结构，工具 = 对数据的变换"，生成器与校验器就不再是黑盒。契约测试能双向对齐的机制前提是：**实现侧把路由与响应结构做成可自省的清单**（不是散落在各 handler 里），spec 声明的每样东西才能一一对照——project 的 `Routes()`/响应字段集合正是为此暴露的。

**序列化性能与契约的取舍**（为 ph16/ph21 衔接）：JSON 是人类可读的文本协议，protobuf 是紧凑的二进制协议；同样的设备列表，protobuf 字节数通常小一个数量级、解码快一个数量级。但 JSON 的收益是调试友好、浏览器原生、工具链（OpenAPI）生态成熟。契约设计者选型时把"谁来消费"放在第一位：外部公开 API 默认 JSON；服务内部与设备上行的高吞吐场景，二进制契约的字节数与解析成本优势才值得付出"不可读、要 IDL 工具链"的代价。

## 5. 使用场景

**什么时候需要版本管理**（3.3 的判断放大成决策表）：

| 场景 | 要不要版本号 / 兼容窗口 | 理由 |
|------|------------------------|------|
| 对外公开 API，第三方/独立团队调用 | 要：URI 版本 + 明确 Sunset 承诺 | 调用方不受你控制，升级节奏不由你决定 |
| 嵌入式/车载终端等慢升级客户端 | 要，且窗口按年计 | 固件升级周期以月计，老版本必须长期可服务 |
| 公司内部服务，调用方与你同团队同步发版 | 不要（版本号是额外负担） | 破坏性变更通过一次性迁移消化，比维护双版本便宜 |
| 服务刚起步、接口还没外部用户 | 先不加，把 3.2 判定表当习惯 | 预埋 v1 不解决任何问题；等第一个外部消费者出现再立承诺 |
| 消息/事件驱动的消费者（跨团队） | 事件 schema 要版本纪律（ph19 详述） | 消费者可能滞后于 producer，schema 只增不删同理 |

**什么时候用 spec-first / 契约测试**：接口有外部消费者、多人协作（前后端并行、多个服务互相调用）、错误结构与分页规则需要向客户端交代清楚时，spec-first 的投入换回"文档不骗人"；内部一次性接口（工具脚本、原型）上契约测试是过度工程。**判据是"这个接口的承诺值不值得被机器锁住"**——没人依赖它，就没必要上对账工序。

**REST 还是 gRPC**（3.8/3.9 的选型浓缩）：对外浏览器/第三方消费 → REST + JSON + OpenAPI（生态最全、调试最友好）；服务间内部调用、强类型与跨语言生成需求强、需要双向流 → gRPC（IDL 即契约、错误码规范、流式支持）；两者常并存于同一服务（内部 gRPC、外部 REST 网关翻译，映射表共享语义层）。数据遥测上行（高吞吐、断点续传、半连接场景）通常两者都不理想——那是 [ph21 通用数据采集与接入网关方向 Go 阶段](../ph21-data-ingest-gateway/21-data-ingest-gateway.md)的协议接入战场。

**与其它语言同类机制的对比**（为 analysis/ 与 Tenet 合成积累素材）：

- Java 生态：OpenAPI 工具链最成熟（springdoc/jax-rs 注解生成 spec、OpenAPI Generator 多语言产码）；契约纪律同样从"文档与实现同步"出发，但 code-first 传统更深（注解长在代码上，spec 是生成的）——Go 社区则更愿意 spec-first（spec 是文件，代码照它写）。
- Python（FastAPI）：函数签名 + 类型注解**自动产出 OpenAPI 文档**，堪称"文档免费"的极致——但同步方向固定为 code-first，spec 是副产物；要 spec-first 得靠手工写 spec + 工具校验，与 Go 的取向相反。
- Rust（tonic/prost）：gRPC 一等的生态，proto 即契约天然 spec-first；HTTP 侧 axum 等靠宏/手工，无 Go 那种"自省路由写契约测试"的惯用法，契约同步更多靠生成器。
- TypeScript：OpenAPI 生成类型客户端（openapi-typescript 等）非常流行——"老客户端"在 TS 世界是**编译期类型**，字段删除直接让下游编译失败，这反过来强化了"字段只增不删"的纪律：破坏性变更的成本在 TS 里被编译器放大得最直观。

**反模式清单**（看到即警惕）：动词塞 URL（`/deleteDevice?id=`）与 GET 带副作用；不画 4xx/5xx 边界的 500 通吃；错误码满天飞却无注册表、客户端靠字符串匹配 message；分页无上限无默认、排序无白名单无决胜键（翻页重漏）；每次发布升版本号（版本贬值）；删字段不留文档、改语义不改版本；手写文档与实现漂移后"先改文档还是先改代码"靠开会决定；protobuf 复用已删除的字段号；gRPC 用 INTERNAL 表达超时（把可重试信号埋掉）。

## 6. 代码示例

完整可运行示例在 [`examples/`](./examples/)（ex01~ex06 各自是独立的 Go module，零第三方依赖），本节的代码片段均标注来源文件与验证环境，**全部已验证**（go1.25.6 本机实测：对应文件 vet/build/test 全绿、gofmt 合规）。

| 示例 | 演示点 | 对应小节 |
|------|--------|---------|
| [`examples/ex01-rest-design`](./examples/ex01-rest-design) | REST 资源与方法语义六条纪律：POST 201+Location、GET 只读、PUT 全量替换、PATCH 指针区分"没传"与零值、DELETE 幂等 204 | 3.1 |
| [`examples/ex02-error-struct-evolution`](./examples/ex02-error-struct-evolution) | 错误结构 v1→v2 演进：code/message 必填永在、可选字段追加、老客户端解析新响应不炸、注册表只增不删 | 3.4 |
| [`examples/ex03-pagination-filter`](./examples/ex03-pagination-filter) | 列表接口稳定性：过滤先于分页、total 语义、排序白名单 + id 决胜、limit 缺省/上限 | 3.5 |
| [`examples/ex04-versioning`](./examples/ex04-versioning) | URI 版本共存：v1/v2 共享 domain 与 store、DTO 按版本裁剪、Deprecation/Sunset 通告头 | 3.3、3.6 |
| [`examples/ex05-openapi-sync`](./examples/ex05-openapi-sync) | spec-first 契约同步：openapi.json 权威、契约测试双向对账、实现多字段/少路由即红 | 3.7 |
| [`examples/ex06-protobuf-wire-compat`](./examples/ex06-protobuf-wire-compat) | 手写 protobuf wire format：加字段老 reader 无损跳过、缺字段落零值、改字段号无声错位 | 3.8、4 |

练习参考实现与综合项目同样全绿：exercises 的 sol-01~sol-03（设备查询 API / 统一错误结构 / OpenAPI 契约测试）、project 的 spec-first 设备管理 API（v1/v2 双版本 + 契约测试五连），运行与测试命令见各自 README 与文件头。

```text
契约测试把文档与实现锁在一起的机制，examples/ex05 的最小实现：
spec 声明 [GET /v1/devices, POST /v1/devices, ...]  ┐
实现路由 [GET /v1/devices, POST /v1/devices, ...]  ├─ 双向逐条对照 → 漂移即测试红
响应字段 [spec properties ⊇ 实际 JSON 字段集合]    ┘
```

> 运行前提：每个示例都是独立 module（自带 go.mod），先 `cd` 进对应子目录再执行文件头给出的命令；示例产物（二进制、数据文件）请写 /tmp，避免污染仓库。HTTP 类示例的 curl 冒烟组合与预置数据见 `examples/README.md`。

## 7. 总结

### 关键要点

- REST 先建模资源再用 HTTP 方法表达动作：集合用复数名词、动作进方法或子资源；方法语义与幂等性是契约（GET/PUT/DELETE 幂等、POST 不幂等）；状态码的选择要回答"调用方能拿它做什么"
- 兼容性判定站在客户端视角（roadmap 必会概念）：加可选字段/参数非破坏，删字段/改名/类型变化/语义漂移/新必填是破坏；**字段只增不删更利于兼容**
- 版本是破坏性变更的出口不是常规轨道：能用追加就别升版本；URI 版本最直观，v1/v2 共享 domain/service、DTO 按版本裁剪，弃用用 Deprecation/Sunset 通告、下线回 410（roadmap 阶段验收：能说明接口兼容策略）
- 错误结构要稳定（roadmap 必会概念 2，兑现 ph17 3.6）：code 给机器（只增不删、语义不漂移、注册表集中登记）、message 给人（可改不可删）；code/message 必填永在（omitempty 禁令）；错误码 → HTTP 状态集中映射、未知错误兜底 500 不泄漏细节；每个 code 有文档说明
- 集合接口（roadmap 阶段验收：能处理分页和过滤）：过滤先于分页、total 是过滤后总数、稳定排序靠唯一决胜键、排序字段白名单、limit 缺省与上限、非法参数 400；offset 适合管理后台、cursor 适合高变动大体量
- 字段演化靠 domain/DTO 解耦（兑现 ph17 3.2）：domain 无 json tag 不属于任何版本、演进只改 DTO 与裁剪函数、v2 是 v1 超集、v1 不泄漏 v2 字段；字段语义漂移按破坏性变更走版本
- 幂等接口更适合重试（roadmap 必会概念 3）：方法级幂等 + POST 的 Idempotency-Key 兜底重试
- API 文档应和实现同步（roadmap 必会概念 4）：spec-first 让承诺先于实现，契约测试把漂移拦截在 CI；错误组件、example、参数声明都要写进 spec（roadmap 阶段验收：能给 API 写示例和错误说明）
- protobuf/gRPC：未知字段跳过是解码器的结构性行为（向前兼容的物理基础）；字段号是契约（reserved 防复用、1~15 给高频字段、类型演进限兼容位宽）；gRPC 用 google.rpc.Code 表达错误（UNAVAILABLE 才是可重试信号）；REST/gRPC 并存时共享语义错误表、两套翻译层

### 阶段验收清单

- [ ] 能说明接口兼容策略：给一次改动分类（非破坏/破坏），并决定走追加还是升版本（roadmap 阶段验收 1）
- [ ] 能判断"我的接口要不要版本号"，并设计 v1/v2 共存的 DTO 裁剪与 Sunset 通告
- [ ] 能处理分页和过滤：翻页不重不漏（决胜键）、total 语义正确、非法参数回 400（roadmap 阶段验收 2）
- [ ] 能给 API 写示例和错误说明：每个端点有 example、每个错误码有"何时返回/客户端可做什么"（roadmap 阶段验收 3）
- [ ] 能说出错误结构"稳定"的两层含义，并指认自己错误注册表的只增不删靠什么钉住
- [ ] 能解释 protobuf 为何敢声称向前/向后兼容，以及"字段号复用"为什么是灾难
- [ ] 能为一个真实接口走完 spec-first 流程并让契约测试通过（用 project 验证）

### 跨语言对比

- API 契约纪律（只增不删、稳定错误、文档同步）是跨语言的普适问题，差异在"违反的成本有多大"：TS 的编译期类型让删字段立刻爆炸，Java 的 code-first 注解让 spec 是副产物，Python/FastAPI 文档免费但方向固定为 code-first，Go 的取向是 spec 作为文件先存在、实现照它写、契约测试锁死——Go 对"显式、可 grep、可自省"的偏好从架构延续到了契约管理（为 analysis/ 与 Tenet 合成积累素材）
- 文本契约（JSON/OpenAPI）与二进制契约（protobuf/gRPC）是同一兼容哲学的两套物理实现：JSON 靠客户端宽容 + 文档约束，protobuf 靠解码器结构 + 字段号契约；选型由"谁来消费 + 吞吐量级"决定，外部人读接口默认 JSON、内部高吞吐走二进制

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题与 roadmap §18 对齐：练习 1 ↔「设计设备查询 API」、练习 2 ↔「设计统一错误结构」、练习 3 ↔「为接口补 OpenAPI 文档」。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**设备管理 API 规范**（roadmap 推荐项目二选一落地，选了 "spec-first + v1/v2 兼容" 的设备管理 API）——`internal/spec/openapi.json` 为唯一权威规范，v1/v2 双版本 DTO 裁剪、错误码注册表只增不删、根目录契约测试把规范与实现双向对账。roadmap 另一推荐项目「gRPC 兼容性实验」的思路已由 examples/ex06（手写 protobuf wire format 的兼容实验）覆盖其核心机制；完整 gRPC 服务（IDL + 拦截器）需第三方工具链，按本仓库零第三方约定不落地为独立项目。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 3 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`go build ./... && go test ./... && go vet ./...` 通过、契约测试五连全绿、v1/v2 冒烟行为符合文档）

### 下一阶段

[ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)——本阶段把同步请求-响应接口（REST/gRPC）的契约纪律讲透了，下一阶段进入异步世界：Kafka/NATS/RabbitMQ 的消费模型、at-least-once 投递下的幂等消费、重试与死信、以及"事件 schema 需要版本管理"——那是本阶段 3.8 protobuf 兼容规则与 3.6 字段纪律在消息侧的同一条纪律（本阶段 3.6 埋的"POST 靠 Idempotency-Key 兜底重试"，届时会演化为"消费端幂等表"的异步版本），具体以 roadmap 第 19 节为准展开。
