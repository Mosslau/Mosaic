# Go 架构设计与代码分层阶段

> 面向"中大型 Go 服务怎么组织代码不失控"：把业务逻辑从 handler 里救出来，用 service 承载规则、repository 隔离存储，再用依赖注入打开层与层之间的接缝——让代码可测试、可换实现、可演进，最后想清楚"什么样的单体值得拆成服务、什么时候拆"。

## 1. 概述

本阶段是学习路线（roadmap 21 个阶段）里的第 17 步。回顾前序：ph09 Web 后端开发阶段已经能用标准库 net/http 写单体 HTTP 服务（路由、中间件、JSON 请求响应），ph10 数据库阶段把内存 map 换成了真实数据库，但代码整体仍是"一个 handler 干所有事"的形态——handler 里既解析 HTTP 又判断业务又直接读写存储；ph11 微服务与 RPC 阶段讲了服务之间的通信形态（gRPC、注册发现、超时重试），但"单个服务内部怎么组织"没有展开。本阶段回答 Roadmap 目标：**能组织中大型 Go 服务代码，避免业务逻辑混乱**。

一句话定位：ph09/ph10 教会你"把服务跑起来"，ph11 教会你"把服务拆成多个"，本阶段教会你"**单个服务内部怎么分层、层与层之间传什么数据、怎么把依赖接起来、以及什么样的单体值得拆**"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 分层与职责 | handler/service/repository 三层职责、判定标准与依赖方向；handler 不承载复杂业务、repository 隔离存储细节 |
| 层间数据形态 | 领域模型 domain / DTO / 请求-响应结构各自的边界、转换函数与取舍 |
| 依赖注入 | 手写构造函数注入（Go 惯例）vs 容器（wire 编译期 / dig、fx 反射），为什么 Go 偏爱显式组装 |
| 工程横切设施 | 配置（flag/env/文件）、结构化日志 slog、错误码与错误包装、接口边界与循环依赖控制、internal/ 包布局 |
| 演进路径 | 单体到服务化：拆的时机、拆什么、模块化单体路径，衔接 ph11 的技术形态与 ph16 的性能前提 |

这个阶段只涉及"单个服务内部"的分层组织与工程横切设施，**不涉及 REST/gRPC 接口设计、版本管理与向后兼容（属 [ph18 API 设计与兼容性阶段](../ph18-api-design-compat/18-api-design-compat.md)）、服务间 RPC 通信与注册发现（ph11 微服务与 RPC 阶段已讲，本阶段只在"拆的时机"层面衔接）、容器化部署与可观测性工具链（ph12 云原生与部署阶段已讲）、性能剖析与优化的工具用法（ph13 性能优化阶段与 ph16 PGO 与高级性能优化阶段已讲，本阶段只保证"分层让热点可被接口形态承载"）、配置中心与 feature flag 发布控制（属 [ph20 配置管理与发布策略阶段](../ph20-config-release/20-config-release.md)）、车联网设备的实时协议接入（MQTT/WebSocket 遥测上行属 [ph21 IoT / 车联网 / 嵌入式相关 Go 阶段](../ph21-iot-vehicle-edge/21-iot-vehicle-edge.md)——本阶段 project 的"设备管理"止于 HTTP 管理面）** — 本阶段把"组织代码"本身讲透；接口长什么样、跨服务怎么调用、怎么发布，是其它阶段的事。

## 2. 来源与演变

分层不是 Go 的发明，它是一套比 Go 老得多的软件组织思想，被每个时代的主流语言各自"翻译"了一遍。**设计哲学一句话加粗：分层的第一动机是"可测试与可演进"，不是目录仪式**——roadmap 把这句话列为必会概念之首。若分层不能换来"单测不用起数据库"、"换存储不动业务"、"新同事知道规则去哪找"，那它只是把一堆文件换个地方摆。

经典三层架构（presentation / business / data）从 1990 年代企业应用开始流行，是最早的"界面逻辑、业务逻辑、数据访问各居其位"的划分；2002 年 Martin Fowler 的《Patterns of Enterprise Application Architecture》为这套结构补齐了词汇——Transaction Script（事务脚本，把每个用例写成一段顺序过程）与 Domain Model（领域模型，规则长在对象上）是两种业务组织范式，Repository 模式则专门回答"业务层怎么假装数据只是内存里的集合"。2003 年 Eric Evans 的《领域驱动设计》（DDD）把这些概念推进到"以业务语言建模"的高度：聚合、领域服务、Repository 都成为标准词汇。2005 年前后 Alistair Cockburn 提出六边形架构（端口与适配器），把"业务核心"与"外界适配器（HTTP、数据库、消息）"明确为内外两层；2012 年 Robert C. Martin（Uncle Bob）的 Clean Architecture 把依赖规则讲成一句话：**依赖只能指向内层，外层是内层的"适配器"**——本阶段 Go 版分层（handler/service/repository/domain）就是这条规则的极简落地。

Go 生态进场晚但取简：net/http 的 Handler 是无状态函数、database/sql 让存储实现互相替换、interface 是结构化的（见第 4 章），因此 Go 社区把"依赖规则"实践成了三件事——**接口定义在使用方**、**组装只在 main**、**internal/ 包做编译期隔离**。工具链侧，Google 2018 年开源 wire 把依赖注入做成编译期代码生成（区别于 Java 世界的运行时反射容器），2023 年 log/slog 进入标准库，结构化日志成为默认。下表是这条演变的里程碑：

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| 经典三层架构 | 1990 年代 | 表现层 / 业务层 / 数据层三分；最早回答"代码放哪" |
| Fowler《PoEAA》 | 2002 | 提出 Transaction Script vs Domain Model、Repository、Service Layer 等至今沿用的词汇 |
| Evans《领域驱动设计》 | 2003 | 聚合、领域服务、Repository 规范化；强调以业务语言建模（bounded context） |
| Cockburn 六边形架构 | 2005 | 端口与适配器：业务核心与外界（HTTP/DB/消息）分离 |
| Uncle Bob Clean Architecture | 2012 | 依赖规则：依赖只能指向内层；用例层与实体层分离 |
| Go internal 包机制 | Go 1.4（2014） | 编译器级导入边界：internal 目录只能被父目录以内的包引用 |
| golang-standards/project-layout | 2017 前后 | 社区标准布局：cmd/、internal/、pkg/ 的约定俗成 |
| Google wire | 2018 | 编译期生成依赖注入代码；区别于 dig/fx 的运行时反射容器 |
| log/slog 进标准库 | Go 1.21（2023） | 结构化日志（键值对、级别、Handler 抽象）成为官方默认 |

本文示例以 **Go 1.25** 为基线（本阶段全部示例/练习/项目的 go.mod 写 `go 1.25.0`：slog（1.21）、泛型（1.18）、errors.Is/As（1.13）、net/http 方法路由（1.22）等本阶段用到的特性在基线上全部稳定可用，也与 ph15/ph16 对齐的仓库工具链版本一致），验证工具链 go1.25.6（darwin/arm64；零第三方依赖——examples/exercises/project 只使用标准库，`go build ./...`、`go test ./...`、`go vet ./...` 命令均已给出，GOCACHE/GOMODCACHE 可重定位到 /tmp 临时目录）。一个定心话：本阶段几乎没有"新语法"，全是包结构、接口、错误处理这些既有语言机制的组合——它是整个 roadmap 里**语言特性最稳定、心智负担主要在"代码放哪"而不在"怎么写"**的阶段。

## 3. 语法与参数

### 3.1 分层与职责：handler / service / repository

roadmap 示例用一行依赖链给出骨架：`handler → service → repository → database`。把它画成带方向的图，箭头是"谁依赖谁"（import 方向），数据流正好反过来（请求从 handler 流入，数据从 repository 取出）：

```text
HTTP 请求 ──▶ handler（翻译层）──▶ service（业务层）──▶ repository（数据层）──▶ 存储
                                  ▲                          │
                                  └──── 领域对象（domain） ◀──┘
依赖方向：handler ──▶ service ──▶ repository ──▶ domain（谁也不依赖的汇点）
```

三层各回答一个问题，判定"某行代码该不该在这一层"的标准就是"它在回答谁的问题"：

| 层 | 回答的问题 | 出现即放错层的迹象 | 职责边界 |
|----|-----------|-------------------|---------|
| handler | 这个 HTTP 请求怎么变成一次业务调用、结果怎么变成响应？ | 出现业务规则（状态迁移表、版本比较、余额计算）；直接操作 map/数据库/SQL | 解析路径/query/body → 调 service → 写 JSON/状态码；只做翻译 |
| service | 这个用例的业务规则是什么？ | 出现 HTTP 词汇（w/r、状态码、JSON tag）；出现存储语句（表名、SQL、文件路径） | 校验与业务不变量、跨 repository 的协调、事务边界 |
| repository（store） | 数据存哪、怎么查、怎么把"行"变回领域对象？ | 出现业务判断（"订单已支付所以拒绝"）；向上层泄漏存储细节（返回 map、表结构） | 封装库/表/map/文件；提供 Get/Save/Delete/List 语义；可换实现 |

判定标准的自检提问：把这段代码删掉，影响的是"HTTP 层长什么样"还是"业务规则变不变"？前者属于 handler 的翻译，后者属于 service；而"数据从哪来"如果换一种存储就要重写，那它属于 repository。三层**全都要薄**：handler 薄（不藏规则）、repository 薄（不藏业务）、service 负责真正的厚度——但 service 的厚度是"规则的清晰罗列"，不是又长又绕的函数。

把一次请求在三层里的穿行逐行看一遍（`POST /todos`，examples/ex01-three-layer 的实景）：

```text
① handler.create      解码 JSON body → createRequest{Title}        （翻译：JSON → 请求结构）
② handler.create      调 svc.Add(req.Title)                        （翻译：请求结构 → 业务调用）
③ service.Add         校验 Title 去空白后非空 → 生成 ID → Save     （规则：标题不能为空）
④ store.Save          map[t.ID] = t                                （存储：放进内存 map）
⑤ service.Add         返回领域对象 todo.Todo                        （数据形态：领域对象）
⑥ handler.create      writeJSON(201, t)                            （翻译：领域对象 → JSON 响应）
```

每一行都只做自己那一层的事，规则（第 ③ 步的"非空"）全程只出现一次——这是"分层职责"最小的可运行标本，完整代码在 examples/ex01-three-layer。

```go
// examples/ex01-three-layer/internal/service/service.go —— 业务层截取
// 验证环境：go1.25.6，零第三方依赖；构建/测试/vet 命令见文件头（已验证：go1.25.6 本机实测全绿）

// Toggle 的业务规则：只有存在的 todo 才能切换完成态。
// 函数里没有任何 HTTP 词汇——它不知道调用方是 curl 还是另一个 service。
func (s *Service) Toggle(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		return todo.Todo{}, fmt.Errorf("toggle todo %s: %w", id, err) // 包装，不吞
	}
	t.Done = !t.Done
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("toggle todo %s: %w", id, err)
	}
	return t, nil
}
```

handler 端对应的纪律是：**出现业务判断就上移**。例如"标题为空回 400"写在 handler 里看起来很顺手，但下次另一个入口（CLI、消息队列消费者）也要建 todo，规则就复制了一份；把它收进 service.Add 后，所有入口自动共享。常见反模式与症状见下表：

| 反模式 | 症状 | 修法 |
|--------|------|------|
| 胖 handler（God Handler） | 一个 handler 函数 > 100 行，规则与 HTTP 交错 | 规则下沉 service；handler 只留"解码 → 调用 → 编码"三行骨架 |
| 贫血 service | service 只是透传 store，规则散落在 handler 与 store 之间 | 把散落的校验/状态迁移集中回 service |
| 泄漏的 repository | 业务代码出现 `WHERE status = 'paid'` 之类 SQL/表名 | repository 返回领域对象与领域错误，查询语义由接口方法名表达 |
| 穿透层 | service 直接 import 了 net/http 或具体存储驱动 | 见 3.7 依赖方向：让依赖只能向内指 |

> 关于"三层够不够"：更细的分层（UseCase 层、基础设施层等）是整洁架构在其它语言的展开，Go 社区默认三层加一个 domain 包就够；本阶段 project 用 handler/service/store/domain 四包落地，多一层还是少一层以"职责可判、依赖无环"为准，不以目录数量论英雄。

### 3.2 层间数据形态：领域模型、DTO 与请求/响应

分层之后，第二个问题随之而来：层与层之间传什么？答案是**三种不同的结构**，混用是新手最常见的乱源：

| 形态 | 生命周期 | 放哪 | 用途 |
|------|---------|------|------|
| 领域模型（domain） | 贯穿 service 与 repository，是业务不变量所在 | domain 包 | 业务规则直接作用的对象；字段名用业务语言（`Status`、`Firmware`） |
| DTO（Data Transfer Object） | 跨层/跨进程传输的"视图"，只在边界短暂存在 | 需要它的层（通常是 handler 或 repository 出口） | 隔离"领域长什么样"与"传输长什么样"：domain 改字段不连累对外格式 |
| 请求/响应结构 | HTTP 边界，一请求一生 | handler 包 | 只描述本次接口的入参与出参，含 json tag 与校验提示 |

判定的简单准则：**规则作用的字段用领域对象承载，网络传输的字段用请求/响应或 DTO 承载**。一个常见的教学简化是给领域结构直接加 json tag 并序列化它（本项目与 examples 都这么做并注释声明了），它适用于字段稳定、响应就是"把对象原样给出去"的内部小服务；一旦对外部客户端开放、字段会演进，就应该在 handler 出口做一次 DTO 转换，理由有三：① 领域对象改名/重组时不影响已发布的 JSON 字段；② 可以只暴露该暴露的字段（不把 LastSeen 之类的内部字段泄漏出去）；③ 转换函数是显式代码，比"字段名恰好对上"的隐式契约好读。

```go
// examples/ex03-error-code-wrap/api.go —— 请求/响应结构（接入层词汇）截取
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

type renameRequest struct {
	Title string `json:"title"` // 请求结构：只描述本次接口的入参
}

type errResponse struct {
	Code    Code   `json:"code"`    // 响应结构：统一错误格式，见 3.6
	Message string `json:"message"`
}
```

DTO 转换的方向值得多说一句：**转换发生在边界，而不是业务代码里**。service 永远操作领域对象；只有 handler 的进出口（解码请求 → 构造领域对象、领域结果 → 组装响应）才出现"传输结构 ↔ 领域对象"的映射。若每个 service 方法都收 DTO 出 DTO，业务层就退化成了无意义的转发层——这是"DTO 滥用"的典型症状。另外注意 slice/map 字段的**引用共享**：领域对象转给另一层时若直接返回内部 map，调用方可能悄悄改掉内部状态（examples/ex04 的 sites.Store.Sites 就做了 copy 再返回，注释说明了理由）；共享可变状态要么深拷贝，要么只读传递。

> 对外 API 的兼容性纪律（字段只增不删、错误结构稳定、版本策略）属 [ph18 API 设计与兼容性阶段](../ph18-api-design-compat/18-api-design-compat.md)，本阶段只需建立一条认知：**domain 不该被 HTTP 格式绑架**——先有这条认知，ph18 的字段演进才有的放矢。

### 3.3 接口定义在使用方附近

Go 的接口是**结构化（隐式）**的：一个类型不需要声明"我 implements 谁"，方法签名对上就算满足。这条机制催生了与 Java/C# 截然相反的惯例——**接口应该定义在使用方（消费方）包附近，而不是实现方包附近**（golang-patterns 规范的 "Define Interfaces Where They're Used"）：

| 语言传统 | 接口归谁 | 实现方如何声明 |
|---------|---------|---------------|
| Java / C# | 接口常定义在实现库，消费方引用库的接口 | 实现类显式 `implements`，编译器双向核对 |
| Go | 接口定义在使用方，描述"我需要的形状" | 无声明；方法签名一致即满足，组装点做编译期断言 |

为什么这样更好？三个理由：① **依赖方向正确**——service 声明它需要的 Store 接口，存储实现包不 import service，依赖图保持"业务不依赖存储实现"（若接口定义在存储包，service 就得 import 存储包才能引用接口，依赖方向立刻反转）；② **接口随使用演化**——接口只有"调用方真正用到的方法"才存在，实现方新增能力不污染接口；③ **测试替身免费**——测试文件里写一个 fake 结构体，签名对上即可注入，不必 import 真实实现。

```go
// examples/ex04-interface-consumer/internal/report/report.go —— 接口在消费方声明
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

// ReportStore 是本包（消费方）对数据源的全部需求。
type ReportStore interface {
	Sites(ctx context.Context) ([]domain.Site, error)
}
```

配套的 Go 惯例是"**accept interfaces, return structs**"：函数参数收接口（只依赖最小形状），返回值给具体类型（调用方拿到实在的东西，不必猜实现）。实现方一侧的编译期校验放在组装点（main）而不是实现包里：

```go
// examples/ex04-interface-consumer/main.go —— 组装点断言
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

var _ report.ReportStore = (*sites.Store)(nil) // 断言写在双方第一次碰面的 main
```

例外与边界：标准库里 io.Reader/io.Writer 定义在 io 包、由 os 包等实现，看起来是"接口在第三方"——但那是**同一生态内接口与实现同层**的特例，且 std 库接口极简稳定；业务代码里"自己先定义大接口再写实现"（接口先行）几乎总是 YAGNI。**只有一个实现时先别抽接口**，等第二个实现或测试替身真正出现再抽——接口是使用方压力逼出来的，不是设计稿里画出来的（3.4 的依赖注入也不要求每层都接口化）。

接口污染（interface pollution）是反向的病：把实现的所有方法都塞进接口，消费方被迫"实现一个它用不到的庞然大物"：

```go
// 坏味道：接口定义在实现包、方法集是实现的全集——任何 fake 都得实现 7 个方法
type UserRepository interface {
	Get(id string) (*User, error)
	List(filter Filter) ([]*User, error)
	Save(u *User) error
	Delete(id string) error
	CountByOrg(org string) (int, error)   // ← 大多数调用方根本用不到
	BatchInsert(users []*User) error      // ← 还让 fake 越来越难写
	Truncate() error
}

// 好形态：接口收窄到调用方需求（Service 只要 Get + Save）
type UserStore interface {
	Get(id string) (*User, error)
	Save(u *User) error
}
```

修法就是 3.3 开头的原则：把接口砍到"调用方真正调用的方法"，实现包继续保留它丰富的方法集，fake 只实现窄接口。

### 3.4 依赖注入：从手写构造函数到 wire / dig

依赖注入（DI）解决一个问题：**对象需要的依赖，不是自己 new、不是从全局拿，而是由外部在组装时给进来**。Go 里的反面是包级全局变量 + init() 里连数据库——全局态让测试互相污染、让"谁初始化了谁"靠猜（golang-patterns 规范明确 Avoid Package-Level State）。三种组装手段对比：

| 手段 | 形态 | 优点 | 代价 |
|------|------|------|------|
| 构造函数注入（手写） | `func NewService(store Store, logger *slog.Logger, opts ...Option) *Service` | 显式、零依赖、IDE 可跳转、测试直接传替身 | 依赖多时 main 的组装代码变长 |
| 服务定位器 / 全局容器 | 包级 `Get("store")` | 调用处代码短 | 隐藏依赖、运行期才报错、测试要清空容器状态；**Go 社区普遍不用** |
| 容器（wire/dig/fx） | 声明"怎么构造"，容器自动填依赖 | 依赖图大（几十个构造器）时省组装样板 | 多一层工具与生成代码；出错信息离代码远 |

Go 的默认是**手写构造函数注入**——标准库自己就这么干（http.Server 把 Handler/Timeout 当字段注入、sql.Open 返回句柄由使用者传递），社区 90% 的服务不需要容器。注入的两种形态都要会：**字段级**（struct 存依赖，构造时注入，如 service.Service）与**函数级**（依赖只在该次调用需要，直接做参数，如 report.Generate(ctx, store)）。构造函数返回**具体类型**（*Service）而不是接口——接口留给"真有多实现"的接缝处（3.3），返回接口反而把调用方的自由没收了。

```go
// examples/ex02-constructor-injection/notifier.go —— 构造函数注入 + 选项函数
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

func NewNotifier(sender Sender, opts ...Option) *Notifier {
	nf := &Notifier{sender: sender, retries: 1} // 必选依赖进参数，可选配置走 Option
	for _, opt := range opts {
		opt(nf)
	}
	return nf
}
```

**选项函数（functional options）**处理"可选依赖"：必选依赖（store、logger）放参数，可选调优（重试次数、超时）用 `WithRetries(n)` 这类返回闭包的函数注入，默认值在构造器内兜底——比"一堆可空参数 + nil 判断"干净得多（golang-patterns 规范的 Functional Options Pattern）。组装代码的位置纪律是：**只允许在 main（或 main 调用的一个 newServer/assembly 函数）里 new 依赖并接线**，业务包内部禁止 import 具体实现来 new——这样"换实现"永远只改一个文件。

字段级注入与函数级注入的取舍：

| 注入形态 | 形态 | 何时用 |
|---------|------|--------|
| 字段级（构造函数注入） | `svc := New(store, logger)`，依赖存 struct 字段 | 依赖跨多个方法使用（repository、logger 是典型） |
| 函数级（参数注入） | `Generate(ctx, store)`，依赖只在该次调用出现 | 依赖是"本次操作的一次性输入"；无状态函数更易测 |
| 选项函数 | `NewX(必选..., WithTimeout(d))` | 可选配置、默认值存在、构造参数过多时收口 |

资源生命周期与组装方向相反：main 里 `store → service → handler` 的顺序 new 依赖，关闭（连接、文件句柄）则按反序在进程退出前执行——手写组装的另一个好处是**生命周期显式可见**；换到 wire 容器时仍要自己安排关闭顺序（容器不替你关资源）。

容器值得用的信号：构造器超过十几个、依赖图深到 main 难以一眼看懂、团队统一用 wire 并接受其生成代码。wire 与 dig/fx 的差别在于时机——**wire 在编译期**根据构造函数签名生成组装代码（依赖图错在编译期暴露，生成的还是普通 Go），dig/fx **在运行期**用反射解析（灵活，但配置错误推迟到启动后才发现，且反射让"依赖从哪来"变隐晦）。对 Go 的"显式优于隐式"取向，wire 是比 dig/fx 更 Go 的方案；本阶段 examples/exercises/project 全部手写注入、零第三方，目的就是把"接线"这一件事练到不用工具也能一眼看穿。

> wire/dig/fx 的完整用法（依赖图、provider 集合、生命周期钩子）属于进阶工具实践，本阶段只建立判断力：**先手写，装不下再容器**。任何情况下服务定位器/包级全局都不在本阶段选项内。

### 3.5 配置、日志与横切设施

**配置**：12-factor 应用的原则是"配置进环境、不进代码"。Go 的落地顺序是命令行 flag 优先（最显式、适合人工启动），环境变量其次（容器/CI 注入，见 ph12 云原生与部署阶段），配置文件最后兜底（复杂默认值）。三条纪律：① 全部配置先解析进一个 config 结构体再下发各层，**禁止业务代码散读 os.Getenv**——散读让"这个服务到底有哪些配置项"无法一页看全；② 配置不合法就**启动期 fail-fast**（打日志退出），不带病运行；③ 版本号/构建信息注入属 ph15 Go 版本、工具链阶段，配置中心与灰度开关属 [ph20 配置管理与发布策略阶段](../ph20-config-release/20-config-release.md)，本阶段只做进程内的 flag/env/文件解析。

```go
// project/internal/config/config.go —— 配置收口（截取）
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

// Load 解析命令行与环境变量，返回完整配置。
func Load() Config {
	addr := flag.String("addr", envOr("ADDR", "127.0.0.1:18084"), "监听地址")
	kind := flag.String("store", envOr("STORE", "mem"), "存储实现: mem | file")
	flag.Parse()
	return Config{Addr: *addr, Store: *kind, /* ... */ }
}

func envOr(key, def string) string { // flag 未设时回退环境变量，再回退默认值
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
```

**日志**：自 Go 1.21 起标准库 log/slog 提供结构化日志——键值对、级别、可插拔的 Handler（JSON/Text）。日志的两条纪律是**结构化**（`logger.Info("http_access", "method", ..., "duration", ...)` 而不是 `fmt.Printf("GET %s took %v")`）与**分层归位**（横切逻辑不该散进各层业务代码）：

| 层 | 记什么 | 级别 |
|----|--------|------|
| 中间件/handler | 访问日志（method/path/status/duration）、请求级联调信息 | Info |
| service | 业务事件（注册、升级、拒绝原因），可带业务 id | Info / Warn（规则拒绝） |
| repository | 一般不记，或 Debug 级记录慢查询 | Debug |
| 边界错误出口 | 5xx 的真实原因（带完整错误链） | Error |

slog 的 logger 与配置一样走**注入**：main 里 `slog.New(slog.NewJSONHandler(os.Stdout, nil))` 一次，作为构造函数参数发给各层（service/handler 收 *slog.Logger），层内不再自己造 logger——可测试性随之而来（测试注入 io.Discard 的 handler 即可静音，project 的 handler 单测就这么干）。

```go
// project/cmd/deviceapi/main.go —— logger 组装与中间件（截取）
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

logger := slog.New(slog.NewJSONHandler(os.Stdout, nil)) // JSON 结构化，一次组装全局下发
svc := service.New(st)                                  // 各层通过构造函数收 logger
h := handler.New(svc, logger)

// 访问日志是横切逻辑的落点（中间件），不掺进任何一层业务代码
func accessLog(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("http_access", "method", r.Method, "path", r.URL.Path,
			"duration", time.Since(start).String()) // 键值对，机器可解析
	})
}
```

### 3.6 错误码与错误包装

Go 的错误哲学是"error 是值"（ph02 函数与错误处理阶段已讲基础）。本阶段的增量是：**把 Go error（面向开发者）与业务错误码（面向调用方）这两种词汇接起来**。Go 侧用哨兵（`errors.New` 定义的固定错误，适合"事实恒定"）、自定义错误类型（带字段，适合"需要结构化信息"）与包装链（`fmt.Errorf("...: %w", err)` 逐层加上下文，errors.Is/As 沿链查找）；调用方侧用稳定字符串码（`"DEVICE_NOT_FOUND"`），只增不删、含义不漂移。两者在 service 的出口合流——service 返回"带业务码的领域错误"，handler 的边界处做唯一映射：

```text
存储层错误（哨兵 errNoRows / sql.ErrNoRows）
   │  service: 包装，不吞
   ▼
*errs.Error{ Code: "TODO_NOT_FOUND", Msg: "todo 不存在", Err: errNoRows }
   │  handler: errors.As 取回 → Code 查表映射 HTTP 状态
   ▼
HTTP 404 + JSON {"code":"TODO_NOT_FOUND","message":"todo 不存在"}
```

三层错误纪律：① **每层包装加上下文**——`fmt.Errorf("get todo %s: %w", id, err)`，让日志里能看出"哪一步、对哪个对象、为什么失败"；② **包装不等于替换**——用 `%w` 保留根因，`errors.Is(err, sql.ErrNoRows)` 永远可追溯；③ **service 不写 http 状态码**——"404 是传输层词汇"这种翻译只发生在 handler（或专门的映射函数），service 层出现 http 包即违规。

```go
// examples/ex03-error-code-wrap/errs.go —— 业务码 + 包装错误（截取）
// 验证环境：go1.25.6，零第三方依赖（已验证：go1.25.6 本机实测，对应文件 vet/build/test 全绿）

type Error struct {
	Code Code   // 稳定对外的业务码，给调用方翻译
	Msg  string // 人类可读说明
	Err  error  // 底层原因（可为 nil），错误链可被 errors.Is/As 穿透
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %s", e.Code, e.Msg) }
func (e *Error) Unwrap() error { return e.Err } // 实现 Unwrap 才能被 errors.Is/As 沿链查找
```

错误码与 HTTP 状态码的映射是**多对多**的，因此需要一张集中表而不是散落的 if：同一个 `CodeNotFound` 在 REST 里映射 404，在 gRPC 里映射 NOT_FOUND（ph11 已讲），在内部 RPC 里可能只是布尔结果——**集中映射 = 换协议时只改一处**。project 的映射表（internal/handler 的 fail 函数，完整代码见 project/）：

| 业务码 | HTTP 状态 | 触发场景（service 层规则） |
|--------|-----------|---------------------------|
| BAD_REQUEST | 400 | id/name 为空、固件不是 major.minor.patch、命令为空 |
| DEVICE_NOT_FOUND | 404 | 查询/心跳/升级/删不存在的设备 |
| DEVICE_EXISTS | 409 | 注册重复 id |
| DEVICE_OFFLINE | 409 | 离线设备下发命令 |
| CONFLICT | 409 | 固件版本回退 |
| INTERNAL（兜底） | 500 | 存储故障、未知错误类型（原因只进日志） |

响应体统一为 `{"code","message"}` 结构（与 roadmap §18 示例同构，本阶段先立结构、ph18 再讲其兼容演化）。未知错误类型（没包成领域错误的东西）一律兜底 500、**真实原因只进日志不进响应体**——这是"不向调用方泄漏内部"的底线。判错用 errors.Is/As（语义判断）而不用字符串比较，是 golang-patterns 规范反复强调的红线；"给 service 层写单元测试"（练习 3）里专门用用例把这条钉死。

### 3.7 接口边界、循环依赖与 internal/ 包布局

分层最终要落在包（package）上，于是第三个问题出现：**包的 import 图必须无环，且方向与分层一致**。Go 编译器在编译期检测 import 环并直接报错（`import cycle not allowed`），所以"分层设计破了"在 build 期就会暴露——这比运行期才炸友好得多。一个健康单体服务的依赖方向是单向向内的：

```text
cmd/deviceapi ──▶ handler ──▶ service ──▶ domain ◀── repository（store）
                        └──────▶ errs ◀── service、handler（只认 Code）
```

出现循环 import 时，三种修法按顺序试：① **把接口定义挪到使用方**（3.3）——A 依赖 B 的方法而 B 不该依赖 A 时，让 A 声明"我需要的形状"，B 隐式满足，A→B 的依赖就断了；② **把共享类型下沉到底层公共包**（domain）——两个包都要用的模型/哨兵放领域包，两边都依赖它；③ **把"谁调用谁"改成"谁被注入谁"**（3.4）——main 负责接线，业务包之间不再互相 import。修完的标准是：任何两个业务包之间至多有一个方向的依赖，且最终都能画进上面那张图。

**internal/ 包布局**是 Go 特有的编译期隔离：Go 1.4 起，`internal/` 目录下的包只能被"该 internal 目录的父目录之内"的代码 import——超出范围的引用是编译错误。语义上它是"仓库私有代码"的强制边界：单体应用把 handler/service/repository/config/domain 全部放 `cmd/<app>` 的兄弟 `internal/` 下（golang-standards/project-layout 的社区约定），对外只承诺 main 可执行；`pkg/` 则放"愿意对外开放复用"的库（本阶段不涉及，见 ph05 包管理与工程结构阶段）。internal/ 的主要价值不是防"坏人"，而是**防"自己人走捷径"**：目录结构本身就在告诉后来者"哪些是服务内部实现细节，别跨服务引用"。

```text
project/ 的包布局（本阶段综合项目）
├── cmd/deviceapi/        # 组装 + 启动（唯一知道"谁是谁"的地方）
└── internal/
    ├── config/           # 配置解析
    ├── domain/           # 领域模型 + ErrNotFound 哨兵（最内层）
    ├── errs/             # 业务错误码
    ├── service/          # 业务层（定义 DeviceStore 接口）
    ├── store/            # repository：mem.go / file.go（不 import service）
    └── handler/          # HTTP 接入层（唯一做错误码→状态码映射）
```

最后两个边界提醒：**internal 是"进程内私有的强制"，不是"模块间服务的边界"**——跨服务引用该走 ph11 的 RPC 而非 import；**别为每层都建一个只有一个文件的包**——包是内聚单元，handler/service/store 三四个包足够覆盖绝大多数单体（3.1 已述）。

给依赖图"上保险"的日常动作（每加一个新包就走一遍）：

```bash
# 1. 编译（含 import cycle 检查：有环直接报 import cycle not allowed）
go build ./...
# 2. 静态检查（internal 越界引用、未用代码等在此暴露）
go vet ./...
# 3. 想亲眼看依赖：列出 main 包的全部传递依赖，核对有没有"不该出现的包"
go list -deps ./cmd/deviceapi | grep internal
```

新增包时的自问：它会被谁 import？它 import 谁？两者都答得出且都在分层图上，才放行。

### 3.8 单体到服务化演进

本阶段的落点是演进判断：**一个服务什么时候值得拆成多个？拆什么？怎么拆？** 注意 ph11 微服务与 RPC 阶段已经教过"拆完之后长什么样"（gRPC、注册发现、超时重试、可观测性），本阶段补的是它前面那一半——**单体内部先把边界画对，才知道哪里能拆、何时该拆**。

先立反直觉的前提：**多数服务应该先做"分层良好的单体"，而不是一上来就微服务**。理由有三：① 微服务把"函数调用"换成"网络调用"，一致性、调试、部署复杂度系统性上升——ph11 必会概念明说"微服务解决组织和扩展问题，也引入复杂度"；② 拆分的粒度应该跟随**组织与变更边界**（Conway's Law：系统结构镜像沟通结构），团队还没按域分工时拆出的服务边界往往错；③ 拆分成本（服务框架、CI、监控）在规模小时是纯负债。

```mermaid
flowchart LR
    A["单体杂糅：handler 里全是业务与 SQL"] --> B["分层单体：handler/service/repository/domain"]
    B --> C["模块化单体：internal 包边界清晰、无横向依赖"]
    C --> D["服务化：按业务能力抽取独立服务（gRPC + 发现，ph11 形态）"]
    D --> E["独立演进：各自伸缩/部署/发布（ph12 形态）"]
```

拆的信号（全部出现两条以上再认真考虑）：**团队开始按业务域分工**（车队域/用户域/计费域各一组人）；**变更频率分化**（一个模块每周发版、其它月更，部署互相踩）；**需要独立伸缩或性能隔离**（一个热点模块要 20 副本，其它 2 个）；**独立部署有硬需求**（事故半径、发布窗口）。拆什么：按**业务能力/有界上下文**切，而不是按技术分层切——把"设备管理"整体抽成一个服务（含它自己的 handler/service/store），而不是"把全部 handler 放一个服务、全部 repository 放另一个"（那是**分布式单体**反模式：RPC 化了一堆没有业务边界的碎调用，比不分还糟）。

演进路径上，**模块化单体是承上启下的关键一步**：单体内部先把包边界画成"未来服务边界"的样子（internal 之间零横向依赖、共享只走 domain/errs 这类底层包），将来抽取时每个模块就是现成的服务雏形——它自己的 service 门面天然是未来 RPC 接口的候选契约（届时按 ph18 的契约设计纪律打磨）。先拆哪个：从**边界最稳 + 变更最频繁**的开始拆，一次只拆一个，拆完让系统回到绿色再拆下一个。

拆前 checklist（不是全部满足才拆，而是用来把"想拆"翻译成可评估的收益/成本）：

| 检查项 | 单体能满足就继续单体 | 明显不满足才考虑拆 |
|--------|---------------------|-------------------|
| 团队规模与分工 | 一个团队能维护全部代码、按模块 review | 多个团队按业务域分工、跨模块合代码互相等 |
| 变更耦合 | 模块各自发版互不阻塞 | 一个模块的每次变更都要拉着别的模块一起回归 |
| 伸缩与故障隔离 | 整体水平扩容够用、事故半径可接受 | 热点模块要独立伸缩、故障要能只炸局部 |
| 技术栈/合规 | 一套进程一个发布管道 | 模块需要独立选型、独立合规边界 |

```text
分层好单体的额外红利：ph16 的连接
service 层"接口注入的算法"形态（Signer/Codec 接口 + 90%/10% 实现）
── PGO 去虚拟化作用的对象（ph16 已实测约 3.5×）
── 反过来说：分层让热点可测、可被接口承载，profile 才有意义
```

> 服务化之后的完整技术形态（gRPC/发现/熔断/限流）属 ph11 微服务与 RPC 阶段（已建），容器化与发布编排属 ph12 云原生与部署阶段（已建）、灰度发布策略属 [ph20 配置管理与发布策略阶段](../ph20-config-release/20-config-release.md)——本阶段只给出"该拆了"的判断与"先单体后拆分"的路径，不重复讲那些阶段的工具。

## 4. 底层原理

**接口值的内存形态与依赖注入的成本**。Go 里一个接口变量在内存里是两个 word：`(itab, data)`——itab 指向类型元数据（方法表），data 指向实际对象（或对象本身）。所以"构造函数注入接口字段"在运行期就是一次 struct 赋值 + 一次方法表间接跳转，没有任何注册表/代理层。与 Java 的接口不同，Go 的 itab 在**编译期**按"这个具体类型有没有这些方法"装配（结构化满足），运行期零查找。代价是接口调用比直接调用多一次间接跳转——这正是 ph16 PGO 能"去虚拟化"的前提：profile 显示 99% 的调用都落在同一个实现上时，编译器把接口调用改写为"类型断言 + 直接调用 + 内联"。结论对架构有实际意义：**分层带来的接口化不必然牺牲性能，热点路径上的接口调用可以被编译器消掉**（ph16 的 ex02 实测约 3.5× 收益的前提正是接口化代码）。

**import 环与 init 顺序**。编译器解析 import 图时做拓扑排序，发现环就报 `import cycle not allowed`——所以"分层破了"的代价是编译失败而不是运行期事故。包级变量与 init() 按依赖拓扑顺序执行（被依赖的先初始化），这一机制让"包级全局态 + init 里连数据库"看起来能跑，却把初始化顺序隐式化：谁依赖谁得靠猜。构造函数注入把顺序显式化在 main：`store → service → handler` 一行行看得见，init 被降级为"包内常量准备"这类无依赖工作。

**nil 接口 ≠ nil 指针（依赖注入的经典坑）**。一个接口值在 `(itab, data)` 里只要 data 非空——哪怕 data 指向的对象是 nil 指针——接口就不等于 nil：

```go
// 场景：把 *todos（nil 指针）塞进接口后，err == nil 的判断会骗过你
var svc *todos = nil
var err error = svc          // err 的 data 指向 nil 指针，但接口本身非 nil
if err == nil { /* 永不进入：err 已经是非 nil 接口值 */ }
```

构造函数注入时代码多是"先 new 再传"，踩坑概率低；一旦有人写"返回 (T, error) 时忘记 new 直接返回 nil 指针"，调用方用 `if err != nil` 判断就会漏判。纪律：**接口里永远放真实实例；拿不准就用 errors.Is/As 语义判断，不依赖接口值是否为 nil**（golang-patterns 规范：Never Ignore Errors）。

**internal/ 的编译期强制**。internal 规则在导入解析阶段执行：编译器/工具链检查"发起 import 的包的路径是否位于 internal 目录父目录之下"，不满足即报错。它是纯路径规则，不依赖运行时，因此对工具链（go vet、静态分析、go list）同样生效——这意味着 internal 边界是"整个 Go 工具链共同承认"的，不是某个 lint 的约定。

**错误链的实现**。error 是只有一个方法（`Error() string`）的接口，错误"值"本身可以任意被包装——`fmt.Errorf` 的 `%w` 会把原错误存进包装结构并让它实现 `Unwrap() error`；errors.Is/As 从最外层开始，沿 Unwrap 链逐层比较/类型断言，直到命中或链尽。一次 Is/As 的代价是 O(链长)，链一般 3~5 层，可以忽略；代价换来的收益是"每层都能加自己的上下文，而根因永远找得到"。领域错误包（errs.Error）实现 Unwrap 正是为了让业务码错误能继续挂在标准链上被 errors.Is 追到存储层哨兵。

```text
service 返回的错误在内存里的样子（错误链 = 链表）
*errs.Error{TODO_NOT_FOUND}
   └─ Unwrap ▶ fmt.wrapError{msg: "todo 不存在"}
                 └─ Unwrap ▶ 哨兵 errNoRows（errors.Is 的终点）
```

## 5. 使用场景

**什么时候用这套分层**：服务逻辑超过"单个文件能一眼看穿"的量级；多个 handler 共享同一套规则（不集中就会复制）；存储有更换/多实现可能；需要给业务规则写单测；多人协作需要"规则去哪找"有确定答案。分层单体是绝大多数后端服务的默认形态，不是大厂专利。

**什么时候不必分层**：一次性脚本、纯 CLI 工具、几十行的内部接口——分层有成本（多包样板、跳转心智、过早抽象），"先写一个能跑的文件，等它长出第二个用例再分层"（演进式重构）是务实路线。判断标准是**复杂度是否真实存在**：没有共享规则、没有换存储预期、没有测试诉求时，三个包并不比一个文件"更对"。

**与其它语言同类机制的对比**（为 analysis/ 与 Tenet 合成积累素材）：

- Java 生态：Spring 的注解 + 容器 DI 是标配，构造器由框架反射填充；Go 反其道——手写构造 + 组装函数，显式第一。Java 的接口常与实现同居一库并显式 implements；Go 的接口在使用方、隐式满足。代价与收益都来自同一取向：Go 少魔法、多样板。
- Python（FastAPI 等）：函数级依赖注入由装饰器/参数声明表达，动态语言里"接口"概念弱化，靠鸭子类型；Go 的编译期接口给了"形状错误提前暴露"的静态保障。
- C# / Kotlin：DI 容器（.NET DI、Koin）是标配，构造器注入同样流行；与 Go 的差异仍是容器 vs 手写——Go 直到依赖图大到疼才引入 wire，且 wire 选择编译期生成而非运行时反射，守住"显式"底线。

**反模式清单**（看到即警惕）：贫血模型极端化（service 把所有规则堆成超长函数、domain 只剩字段——规则应按内聚拆进领域方法或拆分 service）；接口先行 YAGNI（一个实现也抽接口 + 建 mock 工厂）；层间大 DTO 过度拷贝（每次调用都转 5 层结构体）；无限分层（为"可能的需求"预埋空层）；分布式单体（按技术层拆服务，见 3.8）。

## 6. 代码示例

完整可运行示例在 [`examples/`](./examples/)（ex01~ex04 各自是独立的 Go module，零第三方依赖），本节的代码片段均标注来源文件与验证环境，**全部已验证**（go1.25.6 本机实测：对应文件 vet/build/test 全绿、gofmt 合规）。

| 示例 | 演示点 | 对应小节 |
|------|--------|---------|
| [`examples/ex01-three-layer`](./examples/ex01-three-layer) | 迷你 Todo 三层骨架：职责分工、依赖单向向内、main 组装 | 3.1、3.4 |
| [`examples/ex02-constructor-injection`](./examples/ex02-constructor-injection) | 构造函数注入 + 选项函数，渠道实现可切换，fake 替身单测 | 3.4 |
| [`examples/ex03-error-code-wrap`](./examples/ex03-error-code-wrap) | 业务错误码 + 包装链 + 边界统一映射（errors.Is/As 测试钉死） | 3.6 |
| [`examples/ex04-interface-consumer`](./examples/ex04-interface-consumer) | 接口定义在使用方、实现方不 import 消费方、组装点编译期断言 | 3.3、3.7 |

```go
// examples/ex01-three-layer/internal/handler/handler.go —— 薄 handler 的样子
// 验证环境：go1.25.6，零第三方依赖；构建/测试/vet：go build ./... && go test ./... && go vet ./...
// 已验证：go1.25.6 本机实测（对应 examples 文件 vet/build/test 全绿）

func (h *Handler) toggle(w http.ResponseWriter, r *http.Request) {
	t, err := h.svc.Toggle(r.PathValue("id")) // 规则在 service，这里只调
	if err != nil {
		if errors.Is(err, store.ErrNotFound) { // 只认错误语义，映射 404
			writeError(w, http.StatusNotFound, "not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	writeJSON(w, http.StatusOK, t)
}
```

```go
// examples/ex02-constructor-injection/notifier_test.go —— 注入在测试里的兑现
// 验证环境：go1.25.6，零第三方依赖；测试：go test ./...（已验证：本机实测全绿）

func TestNotifyRetriesUntilSuccess(t *testing.T) {
	f := &fakeSender{fail: true} // 替身替掉真实渠道，单测不发网络请求
	nf := NewNotifier(f, WithRetries(3))
	err := nf.Notify(context.Background(), "a@b.c", "hi")
	if err == nil {
		t.Fatal("want error after all retries failed")
	}
	if f.calls != 3 {
		t.Fatalf("calls = %d, want 3", f.calls)
	}
}
```

> 运行前提：每个示例都是独立 module（自带 go.mod），先 `cd` 进对应子目录再执行文件头给出的命令；示例产物（二进制、数据文件）请写 /tmp，避免污染仓库。

## 7. 总结

### 关键要点

- 分层回答"代码放哪"：handler 翻译 HTTP、service 承载规则、repository 隔离存储、domain 承载领域模型；**判定标准是"这段代码在回答谁的问题"**，而分层的第一动机是可测试与可演进，不是目录仪式（roadmap 必会概念 1）
- handler 不承载复杂业务（必会概念 2）：规则出现一次且只在 service；repository 隔离存储细节（必会概念 3）：换存储不动业务
- 层间数据形态分三种：domain（业务不变量）、DTO（跨层视图）、请求/响应（HTTP 边界）；转换发生在边界，别让业务层收 DTO 出 DTO
- **接口定义在使用方附近**（必会概念 4）：隐式满足 + 组装点编译期断言，让依赖方向正确、测试替身免费
- 依赖注入默认手写构造函数 + 选项函数，组装只在 main；依赖图大到疼才考虑 wire（编译期）而非 dig/fx（运行期反射）
- 配置收口进结构体、日志用 slog 结构化并分层归位、错误码走"service 出 *errs.Error → handler 唯一映射 → 统一 {code,message}"、判错用 errors.Is/As
- import 环是编译错误也是设计警报；打破环的三招：接口挪到使用方、共享类型下沉 domain、调用改注入；internal/ 是编译期私有边界
- 单体到服务化：多数服务应该先做分层良好的单体；拆的信号看团队分工/变更频率/伸缩需求；模块化单体的包边界就是未来服务边界；杜绝分布式单体

### 阶段验收清单

- [ ] 能说明每层职责，并用"这段代码回答谁的问题"判定任意一行代码该放哪层（roadmap 阶段验收 1）
- [ ] 能通过接口替换依赖：给 service 换存储实现只改 main 一处，业务代码零改动（roadmap 阶段验收 2）
- [ ] 能控制循环依赖：画出自己服务的 import 图并证明无环、单向向内；遇到 import cycle 能说出三种修法（roadmap 阶段验收 3）
- [ ] 能说清 domain / DTO / 请求-响应三种形态的边界，并为自己的服务定一条"何时用 DTO"的规则
- [ ] 能给 service 层写表驱动单测（stub 替身、errors.Is/As 断言），不起服务器、不连真实存储
- [ ] 能解释"service 不知道 404 是什么"为什么是优点，并指认自己服务的唯一错误映射点
- [ ] 能给出"该拆服务了"的两条以上信号，并说明为什么多数项目该先做分层单体

### 跨语言对比

- 分层的三明治结构（接入/业务/数据）在所有主流语言里殊途同归，差异在"边界靠什么强制"：Go 靠包 + internal（编译期）+ 隐式接口；Java 靠包 + 显式 implements + 框架容器；Python 靠目录约定与鸭子类型（动态语言里最弱，靠自律与测试兜底）
- Go 把"依赖注入"做成了显式组装（构造函数 + main 接线）与编译期生成（wire）的取向，与 Java/C# 的运行时容器传统对照鲜明——同一目标，Go 选择让依赖关系可 grep、可跳转、可单测（为 analysis/ 与 Tenet 合成积累素材）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap §17 对齐：练习 1 ↔「重构 Todo API 分层」、练习 2 ↔「抽象存储接口」、练习 3 ↔「给 service 层写单元测试」、练习 4 ↔ 学习内容「错误码、接口边界」。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**车联网设备管理服务**（roadmap 推荐项目二选一落地）——分层单体的设备注册/状态查询/心跳/固件升级/指令受理 HTTP 管理面，handler/service/store（内存 + 文件两实现）+ domain/errs/config 分包，构造函数注入组装，service 与 handler 各带单元测试。roadmap 另一个推荐项目「分层 Web API 模板」的思路已由 examples/ex01 + exercises/sol-01 的结构示范覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`go build ./... && go test ./... && go vet ./...` 通过、两种存储可切换且行为符合预期、规则与映射单测全绿）

### 下一阶段

[ph18 API 设计与兼容性阶段](../ph18-api-design-compat/18-api-design-compat.md)——本阶段把服务内部组织好了，下一阶段回答"对外暴露的接口怎么设计得稳定、清晰、可演进"：REST/gRPC 接口设计、版本管理、分页/过滤/排序、向后兼容与错误结构的稳定化。本阶段在 3.2 埋的"domain 不该被 HTTP 格式绑架"、在 3.6 埋的"错误码只增不删"，正是 ph18 的入口——字段怎么演化、错误结构怎么稳定、API 文档怎么与实现同步，届时以 roadmap 第 18 节为准展开。

---

*验证说明：全部代码（examples/exercises/project）均已在 go1.25.6 本机实测（go vet / go build / go test 全绿、gofmt 合规），文件头与 README 标注「已验证」；运行环境零第三方依赖，GOCACHE/GOMODCACHE 可重定位到 /tmp。文中引用的后续阶段均已链到真实目录（Go 路线共 21 节，本阶段之后为 ph21 IoT / 车联网 / 嵌入式相关 Go，已建成）。*
