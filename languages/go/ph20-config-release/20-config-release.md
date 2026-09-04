# Go 配置管理与发布策略阶段

> 面向"服务怎么在不同环境里安全地跑起来并发布"：ph17/ph18/ph19 教会你服务内部的架构、对外契约和异步通信，本阶段回答服务生命周期的收尾环节——配置如何分层组织并在 dev/test/prod 间安全切换（环境变量/配置文件/配置中心）、新功能如何用 feature flag 灰度开关逐步放量、发布如何做决策与回滚、二进制如何自报版本、数据库迁移如何兼容旧版本服务、哪些配置能热更哪些必须重启。终点是一个"多环境配置模块"工程，把发布前要回答的四件事拧成一次可执行走查。

## 1. 概述

本阶段是学习路线（roadmap 21 个阶段）里的第 20 步。回顾前序：ph17 把服务组织成 handler/service/repository 并讲了"配置、日志、错误码、接口边界"的分层纪律；ph18 把**对外同步契约**讲透——接口与错误结构稳定、字段只增不删；ph19 把**异步世界**讲透——消息至少一次投递、消费者幂等、事件 schema 有版本；ph11 把**配置中心**作为微服务基础设施列了名（etcd/Consul/Nacos/Apollo 的概念表），但明确"完整落地属 ph20"；ph12 讲了 12-Factor 的**环境变量最小可靠形态**与容器/K8s 载体层的灰度回滚，同样留了话头——"配置中心的完整形态属 ph20"。本阶段兑现 ph11/ph12 的两条预告，回答 Roadmap 目标：**让服务在多环境中安全发布和运行**。

一句话定位：**前几个阶段关心"代码写得对不对、接口稳不稳、消息会不会丢"，本阶段关心"这一份代码放进 dev/test/prod、放到线上、再回滚，会不会出事"**——配置与发布是"服务生命周期"问题，不是语法问题，所以本阶段几乎没有新语法，真正的学习对象是**分层覆盖的心智模型**（3.2）、**灰度决策的确定性**（3.3~3.5）、**发布信息的可追溯**（3.5~3.6）与**变更的兼容纪律**（3.6~3.8）。ph19 主文档「下一阶段」预告的衔接点——"3.8 提到谁在灰度期间发新 schema 需要发布治理——那正是 ph20 的 feature flag 与灰度策略要管的事；消费端配置在 ph20 会变成每环境可覆盖的配置，而不是写死在代码里的常量"——正是本阶段 3.3/3.4 与 3.7 兑现的内容。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 配置载体 | 环境变量（12-factor III）、配置文件（多环境 profile）、配置中心（etcd/consul 概念与 watch）、命令行 flag |
| 分层合并 | default→file→env→flag 优先级、字段级覆盖 vs 数组整替换、env 字符串的类型解析点、来源可追溯 |
| feature flag | 布尔开关/百分比放量/用户分桶三种策略、盐隔离、放量单调性、生命周期（introduced→beta→GA→removed）、故障兜底 |
| 发布策略 | 金丝雀/滚动/蓝绿对照、健康驱动的放量决策（hold/advance/rollback）、回滚预案、与 ph12 载体层的分工 |
| 版本信息 | 语义化版本、ldflags -X 注入、runtime/debug.ReadBuildInfo 的 VCS 兜底、版本自报与 /version |
| 数据库迁移 | 前滚不后滚、expand→contract 双阶段、迁移执行时机与"兼容旧版本服务"的关系 |
| 热更新边界 | 可热更项（日志级别/限流/灰度百分比）vs 必须重启项（监听地址/DSN/TLS）、原子快照热替换 |

这个阶段只涉及**应用侧**的配置组织、发布决策与版本/迁移纪律，**不涉及容器镜像与 Kubernetes 的编排载体**（Deployment 滚动升级、Ingress/网关流量灰度、Helm rollback、镜像 tag 追溯——ph12 云原生与部署阶段已讲，本阶段只在 3.5 借用其"执行"背景，聚焦"决策与信息"），**不涉及服务注册发现与 RPC 通信形态**（ph11 微服务与 RPC 阶段已讲），**不涉及消息发布的 schema 灰度治理的完整服务化部署**（ph19 3.8 已声明"消息的发布治理属 ph20"，本阶段以 feature flag + 发布策略给出机制，schema registry 服务化部署仍属工程展开），**不涉及设备端/边缘侧的嵌入式配置形态（如 CAN/车载控制器 OTA 参数下发、边缘网关本地配置缓存）——那是 [ph21 IoT / 车联网 / 嵌入式相关 Go 阶段](../ph21-iot-vehicle-edge/21-iot-vehicle-edge.md)的内容**；深度的密钥管理服务（Vault/KMS 轮换、加密落盘）超出本阶段，只守住"敏感信息不进仓库、走 secret 通道"这条底线。本阶段把**服务端**配置与发布这一整块讲透；**生产侧（设备/网关）怎么接入数据**是 ph21 的事。

## 2. 来源与演变

配置管理与发布策略的历史比 Go 语言早，而且几乎是"单体部署→微服务→云原生"每一轮演进都会重新发明一次的东西。**设计哲学一句话加粗：配置管理的本质是"把环境差异从代码里剥出来、并让每个环境的取值可追溯"，发布策略的本质是"把风险从一次全量动作拆成可观测、可回退的小步"——两者合起来，就是服务生命周期的安全带。**

**配置侧的演进主线**：2009 年前后 12-Factor 方法论（2011 年由 Heroku 的 Adam Wiggins 整理成文）把"配置存于环境（config III）"立为 SaaS 应用铁律——一份基准代码（repo）可部署到任意环境，差异全靠环境注入。这在"进程即 Heroku dyno"的世界是对的，但落到需要复杂嵌套配置（多数据源、feature 树）的企业服务时就力不从心：环境变量是扁平的字符串，表达不了结构化配置。于是 **Viper**（2014 年，spf13，Hugo 作者）一类库把"文件 + env + flag 分层合并"做成 Go 事实标准；**koanf**（2019 年，knadh）以更小的核心与显式顺序重做了同类合并，强调"层级解析器是你自己排的，库不替你猜"。与此同时，微服务把"改配置要不要重新发版"变成痛点，**配置中心**登台：**etcd**（2013，CoreOS，ph11 已列）与 **Consul**（2014，HashiCorp）用分布式 KV + watch 提供"配置集中管理、改配置不重启"；国内业务又演进出 **Apollo**（携程 2016 年开源）与 **Nacos**（阿里 2018 年开源）这类自带管理界面的企业级配置中心。

**发布侧的演进主线**：最早的"发布"是停机替换，后来是**滚动发布**（新版本实例逐批替换旧实例，集群始终有容量）——Kubernetes Deployment 的默认策略就是它；**金丝雀发布（canary）**让新版本先接一小部分真实流量验证再逐步放量，成本低、回退快；**蓝绿发布**（blue/green）准备一整套新环境、验证后整体切流量，回滚是"切回去"所以最干脆但成本翻倍。**feature flag**（也叫 feature toggle，Martin Fowler 2009 年的文章让它广为人知；2014 年 LaunchDarkly 等 SaaS 把它产品化）把"发布"与"上线"解耦成两个动作：代码可以已经上线（deploy），但功能是否对用户可见由开关控制（release）——这给了"随发布带新功能、按用户灰度、事故一键关"的能力。semver（语义化版本，Semantic Versioning 2.0.0，2013 年正式定稿）则为"版本号能表达兼容性"立了规矩。下表是本主题的关键里程碑：

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Go 1.0（含标准库 flag/os.Getenv） | 2012 | flag 解析与环境读取进标准库；配置三来源的最原生形态 |
| 12-Factor 方法论成文 | 2011 | 配置存于环境（III）；代码/配置分离成为 SaaS 公约 |
| semver 2.0.0 定稿 | 2013 | 版本号 MAJOR.MINOR.PATCH 表达兼容性，发布可比较 |
| Viper | 2014 | file+env+flag 分层合并成为 Go 配置事实标准 |
| etcd / Consul | 2013/2014 | 分布式 KV + watch；配置中心与服务发现的存储底座 |
| Kubernetes（含滚动发布） | 2015 | Deployment rollingUpdate 成为容器发布默认 |
| Apollo | 2016 | 携程开源的配置中心：管理界面 + 热发布 + 灰度 |
| Nacos | 2018 | 阿里开源：注册发现 + 配置中心一体化 |
| koanf | 2019 | 显式层级合并、零魔法的小型配置库 |
| Argo Rollouts / OpenFeature | 2020/2021 | K8s 原生金丝雀编排；feature flag 的标准接口层（CNCF） |

本文示例以 **Go 1.25** 为基线（本阶段全部示例/练习/项目的 go.mod 写 `go 1.25.0`，与仓库 ph15~ph19 对齐的工具链版本一致；本阶段用到的标准库——os/flag/encoding/json/runtime/debug/hash/fnv/errors/sync/atomic——在该基线上全部稳定可用），验证工具链 go1.25.6（darwin/arm64）。验证口径如实声明：**本机（macOS）无 Docker/etcd/consul 等配置中心，无法连真配置中心验证**——因此全部 examples/exercises/project 采用"离线可测"策略（与 ph19 假 broker 先例同构）：分层合并（env/file/flag）、feature flag 语义、灰度决策逻辑、版本注入（ldflags）、迁移顺序模拟、原子热替换全用纯标准库实现，`go vet ./... && go build ./... && go test ./...`（project 另含 `-race`）**已在本机实测全绿并标注「已验证」**；真配置中心客户端（etcd clientv3、consul api）、Viper 深度接入、Apollo 接入在文中如实标注「未在本环境验证」，并给出安装/运行命令。一个定心话：本阶段真正的"语法"很少——**几乎全是"纯函数决策 + 标准库组合 + 工程纪律"，学的是怎么把"配置与发布"变成可测试、可追溯、可回滚的系统**，这也是 Go 生态里"标准库先行"哲学最典型的一章。

## 3. 语法与参数

第 3 章按"从配置到发布到回滚"的顺序展开：先讲**配置怎么来**——环境变量与 12-factor（3.1）、配置文件与分层合并（3.2）、配置中心（3.3）；再讲**发布怎么控**——feature flag 灰度开关（3.4）、灰度/滚动/回滚的决策（3.5）；最后讲**信息与纪律**——版本号与构建信息注入（3.6）、数据库迁移与发布顺序（3.7）、运行时热更新边界（3.8）。学习目标不是背 API，而是建立三条判断线：**每个配置值从哪一层来、这个功能对谁开、这次发布能不能回滚**。

### 3.1 环境变量与 12-factor：配置存于环境

12-Factor 第三条（config III）说：**配置（数据库地址、密钥、feature 开关等环境差异物）要存于环境变量，而不是写进代码或提交进仓库**。ph12 已经落地了"环境变量注入"的最小可靠形态（`Config` 集中定义、必填项 fail-fast、`errors.Is/As` 判缺失、DSN 脱敏），本小节把环境变量的**读取语义**补透——这是最容易踩坑的一层：

```go
// 完整可运行版见 examples/ex01-env-file-flag/config.go
// 验证环境：go1.25.6（已验证），零第三方依赖

v := os.Getenv("PORT")     // 取不到返回空串——无法区分"没设置"与"设置为空"！
v, ok := os.LookupEnv("PORT") // ok=true 表示"确实设置了"，哪怕值是空串
```

为什么这个区别重要？分层合并（3.2）里"是否显式给出"决定该层**是否覆盖**：`PORT=""`（显式清空）和"未设置"（保持下层）是两种语义。**凡是做覆盖判断，一律用 `os.LookupEnv` 而不是 `os.Getenv` 判空**。类型转换也在这层发生（env 是字符串世界）：

| env 值 → 目标类型 | 标准库做法 | 典型错误 |
|------------------|-----------|---------|
| 整数（端口/超时秒数） | `strconv.Atoi` + 范围校验（1~65535） | 忽略校验，`-1` 也能进监听器 |
| 布尔（开关） | `strconv.ParseBool`（接受 1/t/T/TRUE 等） | 手写 `v == "true"`，别的写法全丢 |
| 字符串 | 原样 | 忘记它仍可能含首尾空白 |
| 必填项 | 取不到 → 立即报错（fail-fast） | 留空运行，运行时才连不上库 |

一个工程级建议：**getenv 函数注入化**（`Load(getenv func(string)(string,bool))`），让测试不依赖真实进程环境——ph12 examples/ex02 已示范，本阶段所有加载代码沿用同一模式（sol-01 的 `Options.Getenv`）。

> env 能优雅表达的配置有上限：**扁平、少量、简单类型**。连接串、密钥这种"一行一个"的正好；嵌套的 feature 树、数组、多数据源放 env 会变成一串可读性极差的变量名——那是 3.2 配置文件的主场。

### 3.2 配置文件与分层合并：default→file→env→flag

真实服务几乎同时用四个来源，且它们有固定的**优先级**，从低到高：**default（代码内默认）→ file（配置文件）→ env（环境变量）→ flag（命令行）**。为什么是这种顺序？**越靠后的来源离"这次运行"越近、越临时**：default 是所有人共享的兜底；file 按环境区分（dev/test/prod 各一份）；env 由编排系统按部署注入（docker/K8s/CI，ph12）；flag 只属于某一次进程启动（调试、单次覆盖）。examples/ex02-config-layering-merge 把这条流水线做成了可运行的模块，核心是一个纯函数化的合并：

```go
// examples/ex02-config-layering-merge/merge.go —— MergeInto：src 层递归合入 dst（截取）
// 验证环境：go1.25.6（已验证），零第三方依赖

func MergeInto(dst, src map[string]any, srcName string, trace Trace) {
	mergeInto(dst, src, srcName, trace, "")
}

func mergeInto(dst, src map[string]any, srcName string, trace Trace, prefix string) {
	for k, sv := range src {
		path := k
		if prefix != "" {
			path = prefix + "." + k
		}
		// 两边同名且都是 map → 递归合并：字段级覆盖，只动重叠子键。
		if dv, ok := dst[k].(map[string]any); ok {
			if srcMap, ok := sv.(map[string]any); ok {
				mergeInto(dv, srcMap, srcName, trace, path)
				continue
			}
		}
		// 标量/数组整体替换；新对象整体置入。trace 记录每个叶子的来源层。
		dst[k] = sv
		trace[path] = srcName
	}
}
```

这背后有三条合并语义，理解它们才能预测"改一处会波及哪里"：

| 合并语义 | 规则 | 例子 |
|---------|------|------|
| **字段级覆盖（map 递归）** | 同名字段高层覆盖低层，不同字段互不干扰 | file 只给 `features.dark=true`，default 的 `features.newtelemetry.percent` 不受影响 |
| **数组整替换** | 数组不做"逐元素合并"，整条替换才可预期 | default `retries:[1,2,3]` + file `retries:[5]` = `[5]`，不是 `[1,2,3,5]` |
| **按键竞争、非整层赢者通吃** | 每层只赢它显式给出的键 | port 来自 flag、dark 来自 file、percent 来自 env、name 保持 default——互不牵连 |

**env 层的桥接问题**：file 层的值来自 JSON，天然带类型；env/flag 是字符串，且键是扁平的（`APP_FEATURES__DARK`）。合并不是"字符串拼 map"——要把 env 的扁平键落到结构化树的叶子上，并且**按目标叶子现有类型解析字符串**（叶子原本是 bool 就 `ParseBool`，是 int 就 `Atoi`）。ex02 的 `ApplyDotted` 做了这件事，并守两条防线：**拼写错误的键拒绝（ErrUnknownKey）**——防止"改了个寂寞"（配置没生效还没人知道）；**目标叶子是复合值（map/数组）时拒绝（ErrNotReplaceable）**——env 是字符串世界，不允许用字符串整替换复杂结构。另一个工程配套是**来源可追溯**：合并时记录每个最终键来自哪一层（ex02 输出的 `trace` 表、sol-01/project 的 `SourceMap`）。线上排障最经典的对话是"这个值到底是哪来的？"——没有来源表就只能人肉推理。

**多环境 profile**：配置文件的常见组织是"同型不同值"——`config.dev.json`、`config.test.json`、`config.prod.json` 由 `-profile`/环境变量选中（sol-01 与 project 的 `configs/` 目录示范）。要点：**profile 文件只放"会随环境变的键"，不要三份各写一遍所有键**——把公共默认留在 default 层，profile 文件越小，日后改公共项就越不容易漏掉某份文件。配置文件的选择（profile 名、路径）应由环境/编排注入（env 或固定部署约定），**不能靠代码里写死 `if debug {}` 猜环境**。

> 本阶段用"default→file→env→flag"的显式分层合并讲透语义；**Viper** 是同类合并的成熟实现（支持更多文件格式与自动 env 映射），其合并心智与本节的 `MergeInto` 完全一致。真 Viper 深度接入的命令见 3.3 表格，标注「未在本环境验证」——因为本仓库离线可测，用纯标准库足以把语义讲清（零第三方优先，见第 1 章基线）。

### 3.3 配置中心（etcd/consul）：集中管理与 watch 热更新

配置文件+env 的组合在"实例数量少、配置变化不频繁"时足够可靠，但服务数量与实例数上来后会遇到三个问题：**配置散落在各服务各环境的文件里没有全局视图**；**改配置要重新发布/重启一批实例**；**不同服务之间需要共享同一份配置（数据源地址、阈值）却各存一份、极易漂移**。配置中心把配置"集中存管 + 动态下发"，概念模型（ph11 已列名）在服务端的完整形态由本阶段兑现：

| 配置中心 | 心智模型 | 服务端 Go 客户端 | 特点 |
|---------|---------|----------------|------|
| etcd | 分布式 KV + MVCC + watch | `go.etcd.io/etcd/client/v3` | CP、强一致；配置+服务发现通用底座 |
| Consul | KV + 服务目录 + 健康检查 | `github.com/hashicorp/consul/api` | AP 倾向；KV 带锁/session 语义 |
| Nacos | 注册发现 + 配置一体化 | `github.com/nacos-group/nacos-sdk-go` | 阿里系微服务栈常用 |
| Apollo | 面向业务的管理界面 + 热发布 | `github.com/apolloconfig/agollo` | 携程开源；配置灰度、回滚内建 |

**配置中心里存什么、不存什么**同样要划界：放**跨服务共享**与**需动态调整**的配置（数据源地址、限流阈值、feature flag、公共开关）；不放"只属于单实例的临时参数"（实例端口、debug 开关——env/flag 更直接）。**watch 是配置中心的灵魂**：客户端 `Watch` 配置键，变更事件推回进程，进程把新值原子替换进内存（3.8 讲边界、4.4 讲机制、examples/ex06 落地了"原子快照"的最小形态）。与"改文件 + 重启"相比，它把"改配置"从发布动作降级成运行动作——**但这也正是必须小心的地方：不是所有配置都该热更（见 3.8）**。

```go
// 示意：etcd 客户端形态（本机无 etcd，仅作 API 形状；可复现命令见下）
// 验证环境：需本地 etcd（docker run -d -p 2379:2379 ...etcd...）
// 验证状态：未在本环境验证（无 Docker/etcd；命令可复现）

cli, err := clientv3.New(clientv3.Config{Endpoints: []string{"127.0.0.1:2379"}})
// 读：resp, _ := cli.Get(ctx, "/svc/release-server/", clientv3.WithPrefix())
// 听：watchCh := cli.Watch(ctx, "/svc/release-server/", clientv3.WithPrefix())
//    每次事件 → 重新拉全量 → 校验 → 原子替换本地快照（ex06 的 Store）
```

> Viper 深度接入配置中心的形态是"把远程 provider 挂进合并链"（`viper.AddRemoteProvider("etcd", ...)` + `viper.WatchRemoteConfig()`），或直接对目标键监听并在回调里 `viper.Set`；Apollo/agollo 则自带"启动拉全量 + 长轮询增量"循环。**接入哪家的区别远小于"合并优先级、来源追溯、热更边界"这些语义——那些本章用纯标准库已讲透**。

真配置中心的安装与 Go 客户端接入命令（本机无 Docker/etcd/consul，**均「未在本环境验证」**，以你机器上的实际服务为准）：

```bash
# 1. etcd：起本地节点 + 拉客户端库
docker run -d -p 2379:2379 --name etcd quay.io/coreos/etcd:v3.5.16 \
  etcd --advertise-client-urls http://0.0.0.0:2379 --listen-client-urls http://0.0.0.0:2379
go get go.etcd.io/etcd/client/v3@latest

# 2. consul：起本地节点 + 拉客户端库
docker run -d -p 8500:8500 --name consul hashicorp/consul:1.20
go get github.com/hashicorp/consul/api@latest

# 3. 本仓库离线形态如何对照：配置中心 = "集中的 file 层 + watch 推送"，
#    合并与热替换语义即 examples/ex02 的 MergeInto + ex06 的 atomic 快照。
```

### 3.4 feature flag：灰度开关的语义与生命周期

feature flag 解决的问题是**"发布（deploy）"与"上线（release）"的解耦**：代码合并、构建、部署到全部实例 ≠ 功能对用户可见。feature flag 是一张"功能对谁可见"的裁决表，运行时查询，因此可以在不重新部署的前提下：对新功能做小范围灰度、按用户群逐步放量、出问题时一键关闭。**它把"发版风险"拆成了两个可独立控制的开关**——这是 ph12 3.8 只提到一句的"灰度分流"在应用内最可测试的形态（ph19 预告"谁在灰度期间发新 schema"要治理的正是这一层）。

灰度开关的**三种策略**（examples/ex03 的 `Strategy`）粒度逐级变细，不是一回事：

| 策略 | 语义 | 典型用途 | 判断粒度 |
|------|------|---------|---------|
| 关 / 全开（布尔） | 对所有请求恒 false / true | 新功能默认关、事故一键全关、GA 全量 | 全体一致 |
| 百分比放量 | 每 N% 的用户可见 | 从 5% 逐步放到 100% 的灰度过程 | 按人（分桶） |
| 用户分桶/白名单 | 指定用户/群体恒可见或恒不可见 | 内部团队先用、金丝雀用户群、AB 实验分组 | 按人（分桶） |

百分比放量必须**确定性**：判断函数对同一 (user, feature) 恒返回同一结果——否则同一用户两次请求有时新功能有时旧功能，体验与埋点全乱。实现就是 3.2 用过的决定性哈希（4.5 展开机制）：

```go
// examples/ex03-feature-flag/flag.go —— 命中判断（截取）
// 验证环境：go1.25.6（已验证），零第三方依赖

// HashBucket 决定性散列（FNV-1a）：同 (key, salt) 恒同桶 → 多实例灰度一致。
func HashBucket(key, salt string, total int) int {
	h := fnv.New32a()
	h.Write([]byte(key))
	h.Write([]byte{0}) // 分隔字节，防 key/salt 拼接边界混叠
	h.Write([]byte(salt))
	return int(h.Sum32() % uint32(total))
}

func (f Feature) IsEnabled(userKey string) bool {
	switch f.Strategy.Kind {
	case StrategyOff:
		return false
	case StrategyOn:
		return true
	case StrategyPercent: // 分桶号 < 放量百分比即命中
		return HashBucket(userKey, f.Name, 100) < f.Strategy.Percent
	}
	return f.Fallback // 未知策略 → 显式兜底，不 panic 不猜
}
```

由此引出灰度三条铁律，每条都能写成测试（ex03/sol-03 已钉住）：

| 铁律 | 含义 | 违反的后果 |
|------|------|-----------|
| **放量单调不回退** | percent 从 20% 抬到 50% 时，原本可见的用户必须保持可见，只会新增 | 用户忽有忽无，体验/数据撕裂 |
| **盐隔离（feature 名当 salt）** | 两个 feature 对同一用户的灰度互不相关 | 所有 feature 同时命中同一批人，灰度退化成固定分群 |
| **兜底要显式** | 无用户身份（批量任务/服务端路径）、规则写坏时有明确 Fallback | 用随机/猜默认，行为不可解释 |

feature flag 也有**生命周期**（sol-03 的 `Stage`）：新功能从 `introduced`（内测白名单）→ `beta`（百分比放量）→ `GA`（全量）→ `removed`（摘除）。生命周期纪律有一条反直觉但重要的规则：**removed 阶段必须先强制关闭（HardOff）观察一段时间再删代码**——因为"删代码"要跟着下一个发布走，如果删代码和关开关同时发生，发布中途新旧代码混跑时，旧实例可能还在读已删的 flag 定义，行为就不可解释了。sol-03 的 `Validate()` 把这条固化成错误：`removed 阶段的 feature 必须 HardOff`。

> 复杂 feature flag 平台（LaunchDarkly、OpenFeature、Unleash）还有**多级定向规则**（按地区/客户端/属性叠加）与**AB 实验框架**；本阶段以"布尔/百分比/分桶 + 优先级 + 生命周期"的最小语义为核心——多级规则无非是这些原语的组合，优先级裁决顺序想清楚（sol-03 的 HardOff > 白名单 > 百分比）就能自己排。

### 3.5 灰度发布、滚动发布与回滚：决策逻辑可测

上一节的 feature flag 控制的是**功能可见性**（用户维度）；本节的灰度/滚动/回滚控制的是**实例与流量**（部署维度）。两者互补且常组合：灰度发布用小流量验证新版本的**实例健康**，feature flag 控制功能在已验证版本上的**可见范围**。ph12 已讲过载体层的执行（K8s Deployment 滚动策略、镜像 tag 追溯、Helm rollback）——**本阶段不重复载体，讲"决策"：给定健康观测，该前进、暂停还是回滚？** 这个决策逻辑可以（也应该）被写成纯函数、喂入确定性健康曲线来测试，examples/ex05-rollout-decision 就是一个放量状态机：

```text
canary 5% → rolling-30% → rolling-70% → full-100%
每档要求连续 N 轮健康才放量；连续 M 轮不健康 → rollback
```

| 发布策略 | 做法 | 回滚成本 | 适用 |
|---------|------|---------|------|
| 金丝雀（canary） | 新版本先接一小部分流量，健康再逐步放量 | 低（撤流量即可） | 大多数在线服务 |
| 滚动（rolling） | 新版本实例逐批替换旧实例，始终保容量 | 中（反向逐批替换） | 集群默认节奏 |
| 蓝绿（blue/green） | 整套新环境验证后整体切流量 | 最低（切回即可） | 状态变更大、需整体验证的发布 |

决策器（ex05）的核心是"健康采样 → 动作"的映射：健康比例达标且攒够观察窗 → `advance`（放量到下一档）；健康不达标 → `hold`（维持当前比例观察）；**连续不健康超过阈值 → `rollback`**。健康采样来自探针聚合（`/healthz`、错误率预算——ph12 的探针是它的输入）。为什么把决策做成**离线可测的状态机**而不是让发布走完才知道？因为"发布要不要回滚"的判断必须可以排练：**回滚预案演练、发布走查、CI 对健康曲线的模拟**都喂同一套决策器——ex05 的三个故事与 project 的发布预检就是排练形态。

**回滚的三层含义要分清**，混在一起会误操作：

| 回滚层 | 动作 | 什么时候用 | 载体/工具（ph12 已讲） |
|--------|------|-----------|------------------|
| 镜像回滚 | 把实例换回旧版本镜像 | 新版本崩溃/回归 | K8s rollout undo、Helm rollback |
| 流量回滚 | 把流量从新版本切回旧版本（不换镜像） | 正在灰度、想先止血 | 网关权重、Argo Rollouts |
| 配置/开关回滚 | 关掉 feature flag 或恢复旧配置 | 功能级问题（无需重发） | feature flag、配置中心历史版本 |

**一条发布底线：每次发布都要有回滚预案，且回滚预案不能是"到时候再说"**——project 的发布预检里 `rollback-plan-present` 就是把它变成可检查项：预案至少写清"回到哪个版本 / 切回哪条流量 / 关掉哪个开关"。这与 roadmap 必会概念「发布要可回滚」直接对应。

**灰度发布与 feature flag 的组合编排**是生产里最常见的完整形态，三层各司其职、互相不可替代：

```text
发布编排（实例/流量层）                feature flag（功能可见层）           回滚兜底
canary 5% 实例 上线 v2.0  ──▶  新功能默认 off，白名单内测  ──▶  异常：关 flag（秒级）
     ↓ 健康                        ↓ 放量 10%→50%          异常：撤流量/回滚镜像
rolling 逐批替换到 100%      GA 全量（flag 常开）        数据/契约问题走 expand-contract
```

即：**实例健康靠 canary/rolling 把关，功能可见靠 flag 把关，数据兼容靠 expand-contract 把关**——三层合起来才是一个"可灰度、可观测、可回滚"的发布。把三层混为一谈（例如用 flag 的百分比替代实例健康验证，或用 canary 的流量切分替代功能开关）是发布事故的常见来源：flag 全开时新代码可能在尚未滚完的旧实例上读取开关、canary 只验证了流量却没法控制功能对特定用户可见。排障顺序也据此定：**先看是哪一层的问题**（实例不健康 / 功能对不该见的人可见 / 数据不兼容），再动对应的闸门。

### 3.6 版本号与构建信息注入：让二进制自报家门

"线上跑的到底是哪个版本"是排障的第一问，答案必须在**运行中的二进制内部**——日志、`/version` 端点、崩溃栈都能自报，而不是查部署记录猜。两部分组成：**语义版本**（semver，MAJOR.MINOR.PATCH，2.0.0 于 2013 定稿——`v1.2.3` 表达兼容性，发布脚本可据此做自动比较与升级决策）与**构建信息**（git commit、构建时间、Go 版本、GOOS/GOARCH）。

Go 的标准注入方式是 **`-ldflags "-X"`**，在链接期把字符串写进包级变量（examples/ex04 完整演示，本机实测）：

```go
// examples/ex04-version-injection/version.go —— 注入点（截取）
// 验证环境：go1.25.6（已验证），零第三方依赖
var (
	version = "dev"     // -X main.version=v1.2.3
	commit  = "none"    // -X main.commit=9f1a2b3
	date    = "unknown" // -X main.date=2026-09-03T00:00:00Z
)
```

```bash
# 构建时注入（ex04 目录内实测命令；产物写 /tmp 不落仓库）
go build -ldflags "-X main.version=v1.2.3 -X main.commit=9f1a2b3 \
  -X main.date=2026-09-03T00:00:00Z" -o /tmp/ph20-ex04 .
```

默认值设计（`dev`/`none`/`unknown`）不是偷懒而是**诚实的探针**：忘了传 ldflags 的构建一眼能看出"没走发布流水线"——发布预检里 `version-injected`（拒绝 version=dev）正是拿它当防线。三个技术点：

| 技术点 | 说明 |
|--------|------|
| 注入目标要写对 | 变量在 main 包 → `-X main.version`；在子包 → `-X <模块路径>/<包路径>.变量名`（project 用 `tenetlang/go/ph20-config-release/project/internal/version.Version`，需是包级**导出** string 变量；-X 对导出变量同样生效，实测可行） |
| 值里不要带空格 | `-X` 值含空格会破坏命令行解析，注意引号与转义（时间戳没空格则无碍） |
| VCS 信息是自动兜底 | `runtime/debug.ReadBuildInfo()` 读构建元数据——`go build`/`go run` 会自动写入主模块路径与 `vcs.revision`/`vcs.time`（在 git 仓库内构建时）。即使忘传 ldflags，也能答出"构建的是哪个提交" |

版本自报的产品形态：启动日志一行 `Summary()`；HTTP 服务暴露 `/version`（JSON，字段即接口契约，发布后不许乱改名——ph18 的"字段只增不删"纪律）；运维侧支持 `binary -version` 单行输出（sol-02 把 run/io 分离做成可测）。project 把"注入 → 自报 → 预检拒绝 dev"串成了闭环。

### 3.7 数据库迁移与发布顺序：向前兼容旧版本服务

**数据库 schema 是"慢变量"，发布却是"快动作"**——当一批实例在滚动发布时，新旧版本服务会**同时**连同一个数据库（旧实例在慢慢退出、新实例在慢慢进来）。这意味着数据库的每一次变更都必须保证"发布窗口里任何时刻，还在跑的任意版本代码都能正常工作"。roadmap 必会概念「数据库变更要兼容旧版本服务」就是这条铁律。

数据库迁移的两条总纪律：

| 纪律 | 含义 | 违例后果 |
|------|------|---------|
| **迁移前滚不后滚（forward-only）** | 迁移只追加不回退；回滚代码≠回滚数据库 | 代码回滚后数据库已变，新旧代码对不上 |
| **变更分两类：兼容 vs 破坏** | 加列/加表/加索引=兼容（旧代码可忽略新增）；删列/改类型/重命名=破坏（旧代码会崩） | 把破坏性变更直接跑在滚动窗口里 = 旧实例崩溃 |

对**破坏性变更**的标准解法是 **expand → contract 两阶段**：先在**阶段一**发布"expand 迁移 + 兼容新老代码的新版本"（加新列、写新旧两处、读新列时容忍旧值为空/默认）→ 等全部实例都升到新版本、旧代码彻底退出 → 再在**阶段二**发布"contract 迁移"（删旧列/旧代码路径）。examples 与 project 里把它固化成可检查项（`breaking-migration-expanded`）：**contract 迁移必须声明其前置 expand 版本，且该版本必须已在"已发布版本"列表里**——机器检查"expand 还没全员上线就不许发 contract"，比人肉记发布日历可靠：

```go
// project/internal/release/release.go —— 预检片段（截取，sol-04 同构）
// 验证环境：go1.25.6（已验证），零第三方依赖

for _, m := range c.Migrations {
	if !m.Breaking {
		continue // 加列/加表：兼容变更，随时可跑
	}
	if m.ExpandIn == "" || !released[m.ExpandIn] {
		return fmt.Errorf("破坏性迁移 #%d 的 expand 版本 %q 尚未发布，禁止 contract", m.ID, m.ExpandIn)
	}
}
```

**迁移工具的 Go 生态速查**（真实项目落地迁移文件与顺序，命令可复现；本仓库离线练习用"迁移元数据 + 预检校验"表达同一纪律）：

| 工具 | 安装 | 心智 | 与 expand-contract 的关系 |
|------|------|------|--------------------------|
| golang-migrate | `go get -tool github.com/golang-migrate/migrate/v4` | 目录编号迁移文件（`001_x.up.sql`/`.down.sql`），`migrate up/down` | up 即前滚；本阶段纪律建议把 down 当"补偿手段"，发布回滚靠代码回滚而非 down 迁移 |
| goose | `go get github.com/pressly/goose/v3` | 支持 Go 内嵌迁移与 SQL，`goose up` | 同理；`goose status` 看已跑序号 |

真库接入（**未在本环境验证**，无数据库可连；命令可复现）：`docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:17` + `migrate -path ./migrations -database "postgres://postgres:dev@localhost:5432/app?sslmode=disable" up`。本阶段的迁移"纪律"（编号单调、前滚不后滚、破坏变更两阶段）在任何工具上都是同一套——project 的 `migration-ids-monotonic`/`breaking-migration-expanded` 两个 check 就是把它变成可测的形态。

**迁移在发布窗口里的执行时机**（两种形态）：

| 形态 | 谁跑迁移 | 前提 | 说明 |
|------|---------|------|------|
| 发布前独立迁移（migrate before deploy） | CI/发布脚本单独跑 | 迁移兼容旧版本 | 最稳：库先就绪，新代码进来即可用 |
| 新实例启动时迁移（app 内迁移） | 新版本自己跑 | 必须幂等 + 加锁（防多实例并发跑） | 小服务方便，但要小心"迁移和启动谁先谁后" |

与 ph19 的衔接：事件 schema 演进的"加字段=非破坏、删/改名=破坏"（ph19 3.8）与本节的数据库 schema 纪律是**同一条原则的两个载体**——消息字段与 DB 列都是"旧消费者/旧代码要能继续读"的共享契约。而**"谁在灰度期间发新 schema/跑 contract"正是 ph20 的发布治理要管的**（ph19 预告兑现）。project 预检把这两条并进一份候选检查：迁移编号单调（`migration-ids-monotonic`）保证顺序可复现、破坏性迁移必须有已发布的 expand（`breaking-migration-expanded`）保证兼容窗口闭合。

### 3.8 运行时配置热更新的边界：该热更与必须重启

配置中心/watch 在机制上**什么都能热更**——把新值推送进内存即可。但"技术上能"和"工程上该"是两回事。热更新边界的判断标准不是"推送通道通不通"，而是**"改了能不能安全生效"**：有些配置在进程启动时就被一次性消费成了连接、监听器、证书——运行时改它不会生效，只会制造"进程里的值与想设的值不一致"的假象；有些配置是请求路径上每次现读的——热更立即生效且无副作用。examples/ex06 把边界固化成一张**可审查的分类表**：

```text
hot(可热更)          log.level / rate.limit.* / circuit.breaker.* / http.timeout.*
feature-flag(下发)   feature.*（需全实例一致，走独立通道）
restart(必须重启)    server.port / server.addr / db.dsn / db.pool.* / tls.* / secret.*
```

| 类别 | 例子 | 为什么 |
|------|------|--------|
| 请求路径现读（hot） | 日志级别、限流阈值、熔断阈值、灰度百分比 | 每次请求读当前值，改了下一次就生效，无连接级副作用 |
| 下发式（feature-flag） | 开关与灰度规则 | 需要"同一时刻全实例一致"，走配置中心/flag 通道而非本地文件 |
| 启动期一次性（restart） | 监听地址、DB DSN/连接池、TLS 证书、密钥 | 启动时已 bind/建池/加载；运行时改不生效，还会制造"改了没生效"的误判 |

"该热更的用热更、必须重启的别假装能热更"的另一半是**机制**：热更的落地要保证读方永远看到**完整一致的快照**，绝不出现"读到一半新一半旧"的撕裂视图。标准做法是**原子快照指针**——不可变快照 + `atomic.Pointer`，读者无锁拿当前快照、写者换新指针（examples/ex06 的 `LiveConfig`，与 `-race` 一起实测）：

```go
// examples/ex06-hot-reload-boundary/reload.go —— 原子热替换（截取）
// 验证环境：go1.25.6（已验证，go test -race 全绿），零第三方依赖

type Snapshot struct {
	Version  int    // 每次发布 +1，供观测与审计
	LogLevel string // 可热更字段（hot）
	MaxQPS   int    // 可热更字段（hot）
}

type LiveConfig struct {
	ptr atomic.Pointer[Snapshot]
}

func (l *LiveConfig) Load() *Snapshot  { return l.ptr.Load() } // 无锁读
func (l *LiveConfig) Store(s *Snapshot) { l.ptr.Store(s) }     // 原子换新
```

为什么快照必须**不可变**？因为"热更"是换指针而不是改内存：在途请求持着旧快照引用继续用旧值（一致），新请求拿新值——GC 会在旧请求结束后回收旧快照。**配置中心 watch → 拉全量 → 校验 → 构建新快照 → Store**就是这条链的真实形态（etcd watch 的底层机制见 4.4）。热更还有一条"配套纪律"：**能热更 ≠ 该无审批热更**——日志级别/灰度百分比这类低风险值适合热更，牵涉金额/合规的值即使技术上可热更也建议走发布与审批流程（把"热更"也当成一次可审计的变更）。

## 4. 底层原理

配置与发布看起来是"应用层工程"，但每一条纪律背后都有一个"标准库/运行时/中间件在做的事"——看穿它们，纪律就不再是背诵。本章挑五个机制拆开看：进程环境变量怎么存（4.1）、flag 怎么解析（4.2）、分层合并的覆盖语义的数学形式（4.3）、配置中心 watch 怎么实现"推送"（4.4）、灰度分桶哈希为什么必须一致性（4.5）。

### 4.1 环境变量：进程启动时的一次性快照

环境变量不是"读数据库"，它是一张**进程启动时定格、此后基本不变**的表：操作系统为每个进程维护 `environ`（`KEY=VALUE` 的字符串数组）；Go 的 `os.Getenv` 在多数平台上走一次系统调用把 `KEY=VALUE\n` 从 `/proc/<pid>/environ` 或进程内存镜像里解析出来。两个由此推出的底层结论：

- **env 是"出生证明"不是"体检报告"**：进程内 `os.Setenv` 只改本进程视图、不影响父进程与兄弟进程，容器里改它也不回写编排系统——所以"发布时注入 env"必须在进程**启动前**完成（docker run -e / K8s env / CI export），服务运行中靠改 env 通知自己是靠不住的（那正是配置中心 + 热更的用武之地，见 4.4/3.8）。
- **`LookupEnv` 返回两个值不是语法糖**：底层能分辨"这个键存在但值是空串"（`=` 后为空）与"键不存在"（environ 里没有这一项）——3.1 讲的分层覆盖语义正是建立在"存在性"这个位上的。

### 4.2 flag 解析：标准库做了什么

`flag` 包把命令行参数（`os.Args[1:]`）按"flag 定义表"逐个匹配：遇到 `-name` / `--name`（两者等价）查表取类型与默认值；`-name=value` 与 `-name value` 都接受；遇到**第一个非 flag 参数**（不以 `-` 开头）即停止解析，剩余作为位置参数返回（`FlagSet.Args()`）——这就是"子命令"能实现的原因（`tool sub -x` 时外层解析到 `sub` 停下，把 `sub -x` 交给内层 FlagSet）。三个工程推论：

| 推论 | 说明 |
|------|------|
| 每个 flag 都有"当前值" | parse 前是默认值、parse 后是命令行值——sol-01/project 靠"parse 前后对比"判定某字段是否真的被 flag 覆盖，比记录"哪个 flag 传了"更省事 |
| 未知 flag 立即报错 | flag 包遇未定义 flag 返回 error（`ContinueOnError`）——配置项拼错在启动即暴露，绝不静默 |
| 别解析整个 `os.Args` | 库代码要接受注入的 `[]string`（`Args`），否则测试二进制会被 `go test` 的 `-test.*` 参数污染（sol-01 踩过、已用 `Args=nil 即跳过 flag 层` 规避） |

### 4.3 分层合并的覆盖语义：偏序覆盖与类型解析点

3.2 的 `MergeInto` 其实是一个**键级偏序**：每层是一个 `map[key]→value`，覆盖就是"在键上取优先级更高的层的值"。形式化之后能推出几个容易出错的点：

```text
final[key] = 按层高到低找第一个"该层显式定义了 key"的层的值
            （map 递归合并 = 对每个子键重复同一规则）
```

- **"字段级"与"整层替换"的本质差别**：如果 file 层整体替换 default 层，`features.dark=true` 会把 default 的整个 `features` 子树删掉重建；字段级递归只改重叠子键——所以 **default 里新增一个键，低层补默认键时不会破坏任何 file 层**（file 没写它就继续用 default），这正是"profile 文件越短越安全"的底层原因。
- **env/flag 的"字符串世界"决定了类型解析的位置**：JSON 文件在 decode 时已经定了类型（bool/int/嵌套），env 却只给字符串。把类型解析**推迟到合并完成后统一做**（如 ex02 在 `ApplyDotted` 按目标叶子类型解析）比"每层各自解析"好在：类型只在叶子上定义一次，高层字符串只按叶子的类型解释；叶子是复合值（map/数组）时 env 根本表达不了 → 拒绝（`ErrNotReplaceable`）。这也是为什么**结构化配置的 schema（叶子类型）是文件层的领地**——default/file 定义结构与类型，env/flag 只负责覆盖标量。
- **trace 就是合并过程的副作用**：每落一个键记一笔"谁写的"。工程上不要事后对比整棵 diff 猜来源——合并时顺手记录（O(键数)）比事后推理便宜得多。

### 4.4 配置中心 watch 与热更新：从"轮询"到"版本号订阅"

配置文件方案的本质是**启动时读一次、再也不看**；配置中心的热更本质是**把"配置有变化"变成事件流推给订阅进程**。以 etcd 为例拆机制：

- etcd 存储是 **MVCC**：每个键的每次修改都产生一个新版本（`revision`），旧版本按压缩策略保留——"配置的历史版本"因此天然存在（回滚配置 = 取旧 revision）。
- **watch 是"从某 revision 开始订阅变更"**：客户端 `Watch(key, WithRev(rev))` 后，服务端把该键在此后每次写入产生的事件（PUT/DELETE + 新值 + revision）推给客户端。这正是"推送"的物理含义：不是客户端每秒轮询，而是**连接 + 游标（revision）**。
- 客户端侧落地链条：watch 收到事件 → 重新拉全量（避免事件丢失/漏合并）→ 校验新配置合法 → 构建**新快照** → `atomic.Pointer.Store`（3.8 的 ex06 快照）。**at-least-once 语义同样适用**：watch 断线重连后从断点 revision 续订，可能重复收到事件——消费端（热更处理器）要对同 revision 幂等（重复 Store 同值无副作用），这与 ph19 消费端幂等是同一条纪律的又一次出现。
- **一致性取舍**：etcd 是 CP（写入多数派确认，分区时宁可不可用也要一致），Consul 的 KV 偏向 AP 可用性——对"配置中心"这种"写少读多、错了全体错"的场景，多数团队选强一致（CP），配合"客户端本地缓存 + 重连续订"保可用。工程上更实际的教训是：**配置中心是共享依赖，它挂掉时服务不能跟着挂**——客户端要缓存最后一份成功快照，中心不可达时继续用旧配置运行（stale-while-unavailable），这正是 3.4 讲"兜底要显式"在配置层的版本。

### 4.5 灰度分桶的一致性：为什么不能随机、为什么要盐

灰度判断对同一用户必须恒定，否则体验会随机闪跳。为什么"哈希取模"是对的、而"伪随机数"或"一致性哈希环"在这里不必要？

| 方案 | 特性 | 灰度分桶适用性 |
|------|------|--------------|
| 决定性哈希取模（FNV/xxhash mod 100） | 同 key 恒同桶；桶的粒度是"均匀分布"而非"稳定性" | ✅ 主推：简单、可测、跨进程恒定 |
| 伪随机（rand） | 每次不同 | ❌ 同用户两次判断不同 |
| 一致性哈希环（ring） | key 到节点映射，节点增减只迁移少量 key | 不需要：放量改的是"阈值"不是"桶集合"，没有节点增减 |

**为什么放量（percent 变化）天然平滑**：percent=30 的"可见桶"是 `[0,30)`；抬到 50 时可见集合扩成 `[0,50)`——**每个用户的桶号没变**，变的只是阈值，因此"原本可见的保持可见、新增的只是 `[30,50)` 的用户"。放量单调性（3.4 铁律）不是约定的纪律，而是这个数学结构的必然结果。**为什么掺盐**：用户 key 直接取模会与别的 feature 的取模完全相关（user-0001 对 A/B 两 feature 的判断强相关），掺入 feature 名做盐后，两个 feature 对同一用户是两把独立的"均匀散列"——盐隔离让多个灰度互不绑定（ex03 的 `TestFeaturesAreIndependent` 用两把 50% 开关测出 ~25% 双命中验证了独立性）。**桶数的选择**：百分比灰度用 100 桶粒度够用（阈值 0~100 整数）；需要更细的放量（0.1%）才用 1000 桶。**哈希函数不必密码学安全**——FNV/CRC 就够，关键属性只有"均匀 + 跨进程稳定"。

## 5. 使用场景

**配置载体怎么选**——不是越重的越好，而是按"变化频率 × 影响范围 × 是否需要动态"三把尺子选：

| 场景 | 信号 | 选它 | 不选它的替代 |
|------|------|------|------------|
| 单机/小集群、配置很少变 | 改动频率以"发版"为单位 | 配置文件 + env | 配置中心是杀鸡用牛刀（引入一致性/运维成本） |
| 部署注入的环境差异（地址/密钥/端口） | 值随环境变、编排可控 | env（ph12 的 ConfigMap/Secret 注入通道） | 写死在配置文件里会被环境搞混 |
| 一次性的调试/单次覆盖 | 只影响一次启动 | flag | env 会污染整个部署单元 |
| 多服务共享同一份配置 + 需动态调整 | 改阈值不想重新发版、跨服务要一致 | 配置中心（etcd/consul/Apollo）+ watch 热更 | 各存一份文件 → 必然漂移 |
| 新功能要逐步放量 | 发布与上线要分离 | feature flag（3.4） | 直接上 = 出事只能回滚整个版本 |
| 配置含密钥 | 值敏感 | secret 通道（K8s Secret、云 KMS、Vault）挂载/env | 明文进配置文件/仓库 = 泄漏事故（发布预检里 `no-plaintext-secret` 就是闸门） |

**何时"文件就够"**：实例少、配置随发布走、变化可重启收敛（多数内部服务 80% 的配置属于这类）；**何时必须配置中心**：实例多到"重启一遍要很久"、配置变化需要秒级全量生效（限流/熔断阈值）、或者多个服务共享同一份"必须一致"的配置。判断一句话：**配置中心解决的是"改配置 = 一次线上变更且要快速安全"，如果"改配置等下次发布"可以接受，就别上中心**。

**发布/灰度策略的选择**：低风险内部发布可以直接滚动；对用户可见的功能走 canary + feature flag 双闸门（先 canary 验实例健康、再 flag 控功能可见度）；有状态/数据迁移重的大版本考虑蓝绿或 expand-contract 两阶段（3.5/3.7）。

**与其它语言同类机制的对比**（为 analysis/ 与 Tenet 合成积累素材）：

- Java/Spring：`application.yml` + `@ConfigurationProperties` + profile（`spring.profiles.active`）是分层配置的标准形态；微服务栈常配 Apollo/Nacos（配置中心天然带管理界面与灰度）；feature flag 有 Togglz/FF4J 等框架。对比 Go：Spring 靠**注解 + 框架扫描**把配置注入对象，Go 没有框架层，倾向"Config struct + 显式 loader 函数"——显式带来可测试，代价是样板代码要自己写（Viper 补一部分）。
- Python：12-Factor 影响最深，`os.environ` 直接读是默认动作，`dynaconf`（支持分层/多环境/secret 后端）与 `python-decouple` 是常见增强。对比 Go：两者都鼓励"配置即环境"，差异在 Python 动态类型下配置直接就是 dict/类属性，Go 要先把字符串解析进静态 struct。
- Rust：生态小而美——`figment`（分层合并、类似本阶段 MergeInto 心智）与 `config` crate 并存，server 框架（axum/actix）常各自带 `FromRef` 配置模式。对比 Go：Rust 的 trait 让"任意来源 → 类型化配置"可以做成泛型库，Go 靠显式函数，但分层合并的**语义（优先级/覆盖/来源）三语言完全共享**。
- 跨语言共性：**分层合并优先级（default→file→env→flag）、密钥不进仓库、发布可回滚、feature flag 生命周期、schema/字段只增不删**是工程公约，与语言无关——差异全在"框架注入 vs 显式组装"的封装度。Go 站"显式 + 标准库"一端，这也是本阶段所有示例零第三方的理由。

**反模式清单**（看到即警惕）：把密钥写进配置文件还提交仓库（`no-plaintext-secret` 拦）；配置文件三份全量复制（改公共项漏改某环境）；用 `os.Getenv` 判空做覆盖判断（空串被吞）；启动时读一次配置就再也不管"该热更的项"（错过故障止血窗口）；什么配置都塞进配置中心热更（DSN/证书热更了也不生效，反而制造不一致）；灰度开关用随机数或忘了掺盐（用户随机闪跳、feature 互相绑定）；放量从 50% 降到 20%（违反单调性，已可见用户被回退）；发布没有回滚预案、"到时候再说"；数据库删列和发新代码同一次发布（旧实例崩溃）；删 feature flag 代码和关开关同时发生（新旧代码语义分裂）；版本变量默认写死真实版本号（`version=v1.2.3` 手工改 = 所有构建都谎报版本）。

## 6. 代码示例

完整可运行示例在 [`examples/`](./examples/)（ex01~ex06 各自是独立的 Go module，零第三方依赖），本节的代码片段均标注来源文件与验证环境。**验证状态：ex01~ex06 全部「已验证」**（go1.25.6 本机实测：对应文件 vet/build/test 全绿、gofmt 合规；ex06 另跑 `-race` 全绿；ex04 与 project 另实测 ldflags 注入构建）；真配置中心客户端（etcd clientv3、consul api、Viper/Apollo 深度接入）在本机无 Docker/etcd/consul，不落地为可运行示例，语义与命令见 3.3 与 4.4（均标注「未在本环境验证」）。

| 示例 | 演示点 | 对应小节 |
|------|--------|---------|
| [`examples/ex01-env-file-flag`](./examples/ex01-env-file-flag) | 三来源读取：file/flag/env 各自独立、LookupEnv 区分"未设置 vs 空串"、类型解析带上下文 | 3.1 |
| [`examples/ex02-config-layering-merge`](./examples/ex02-config-layering-merge) | 分层合并：default→file→env→flag 逐层叠加、map 递归字段级合并、数组整替换、env 扁平键类型感知覆盖、来源 trace | 3.2 |
| [`examples/ex03-feature-flag`](./examples/ex03-feature-flag) | feature flag：关/开/百分比三策略、决定性分桶、放量单调、盐隔离、生命周期、兜底 | 3.4 |
| [`examples/ex04-version-injection`](./examples/ex04-version-injection) | 版本注入：ldflags -X 语义版本 + ReadBuildInfo 的 VCS/Go 信息、自报视图 | 3.6 |
| [`examples/ex05-rollout-decision`](./examples/ex05-rollout-decision) | 发布决策状态机：健康曲线驱动 hold/advance/rollback/complete、确定性回放演练 | 3.5 |
| [`examples/ex06-hot-reload-boundary`](./examples/ex06-hot-reload-boundary) | 热更新边界分类表 + 原子快照热替换（atomic.Pointer），`-race` 验证无撕裂视图 | 3.8 |

```go
// examples/ex02-config-layering-merge/merge.go —— 合并是纯函数：输入层、输出 trace（截取）
// 验证环境：go1.25.6，零第三方依赖；验证状态：已验证（go1.25.6 本机实测全绿）

func mergeInto(dst, src map[string]any, srcName string, trace Trace, prefix string) {
	for k, sv := range src {
		path := k
		if prefix != "" {
			path = prefix + "." + k
		}
		if dv, ok := dst[k].(map[string]any); ok {
			if srcMap, ok := sv.(map[string]any); ok {
				mergeInto(dv, srcMap, srcName, trace, path) // 字段级：递归只动重叠子键
				continue
			}
		}
		dst[k] = sv
		trace[path] = srcName // 每个叶子的来源在这里顺手记下
	}
}
```

```text
examples/ex05-rollout-decision 的 ex05 输出节选（发布故事 C：放量到 30% 后回归 → 回滚）
轮  3：档=canary(放量  5%)    健康=100% → advance(放量到下一阶段)
轮  4：档=rolling-30(放量 30%) 健康=100% → hold(维持当前比例)
轮  5：档=rolling-30(放量 30%) 健康=50%  → hold(维持当前比例)
轮  6：档=rolling-30(放量 30%) 健康=30%  → rollback(回滚旧版本)
```

练习参考实现（sol-01~sol-04）与综合项目（project，多环境配置模块）同样在 go1.25.6 全绿（project 另以 `go test -race` 复核，见 project/README）：exercises 的 4 个参考实现覆盖 roadmap §20 练习（写配置加载模块 / 注入构建版本信息 / 设计灰度开关 / 写发布检查清单），project 的 `release-server` 是"配置+版本+灰度+预检"四件套的完整落地，运行与测试命令见各自 README 与文件头。

> 运行前提：每个示例/练习都是独立 module（自带 go.mod），先 `cd` 进对应子目录再执行文件头给出的命令；单 main 包目录里 `go build ./...` 会生成二进制，验证后请删除或改用 `go build -o /tmp/<名字> .`——仓库不落二进制（构建产物一律写 /tmp）。

## 7. 总结

### 关键要点

- **配置和代码要分离（roadmap 必会概念 1）**：分层合并 default→file→env→flag 按优先级逐层覆盖，覆盖按"键"竞争而非"整层赢者通吃"；env 只能表达扁平标量、类型在叶子处按现有类型解析；**每个配置值的来源必须可追溯**（ex02 的 trace / project 的 SourceMap），排障不靠人肉推理
- **来源层的读取语义**：覆盖判断用 `os.LookupEnv`（区分"未设置"与"空串"），不要用 `os.Getenv` 判空；必填项 fail-fast 用 `errors.Is/As` 可命中的哨兵错误
- **敏感信息不能进仓库（roadmap 必会概念 2）**：密钥走 env/挂载的 secret 通道；把密钥明文写进配置 = 泄漏事故，发布预检 `no-plaintext-secret` 把它变成机器闸门；配置样例里也不放真口令
- **feature flag 是"发布与上线"的解耦开关**：布尔/百分比/分桶三策略、决定性哈希 + 盐隔离、放量单调不回退、显式兜底；生命周期 removed 必须先强制关再删代码
- **发布要可回滚（roadmap 必会概念 3）**：决策器（健康曲线 → hold/advance/rollback）写成离线可测状态机；每次发布都有回滚预案（镜像/流量/配置三层分清），预检 `rollback-plan-present` 兜底
- **数据库变更要兼容旧版本服务（roadmap 必会概念 4）**：迁移前滚不后滚；破坏性变更走 expand→contract 两阶段，contract 的前置 expand 必须已发布（预检 `breaking-migration-expanded` 把关）
- **版本注入与自报**：`-ldflags -X` 注入语义版本（默认 `dev` 是诚实探针），`ReadBuildInfo` 自动带 VCS/Go 信息作兜底；发布预检拒绝 `version=dev`
- **热更新边界**："该热更的"（日志级别/限流/灰度百分比）用不可变快照 + `atomic.Pointer` 原子替换；"必须重启的"（监听地址/DSN/TLS）别假装能热更；能热更 ≠ 无审批热更

### 阶段验收清单

- [ ] 能在 dev/test/prod 使用不同配置（roadmap 阶段验收 1）：`config.<env>.json` + env/flag 覆盖切换，能说出任一字段来自哪一层
- [ ] 能快速定位运行版本（roadmap 阶段验收 2）：能讲清 ldflags 注入的三个变量与 ReadBuildInfo 兜底，能跑通 `go build -ldflags "-X ..."` 并验证注入
- [ ] 能安全回滚服务（roadmap 阶段验收 3）：能说清"发布决策器如何决定回滚"，能给出镜像/流量/配置三层各自的回滚动作
- [ ] 能说清分层合并的三条语义（字段级/数组整替换/按键竞争）与来源追溯为什么重要
- [ ] 能设计一个灰度开关：策略选择、盐隔离、单调放量、removed 先关后删，并指出代码里 Validate/Evaluate 的位置
- [ ] 能解释 expand→contract 为什么是"旧服务升级"的栅栏，并指出预检里哪个 check 在把关
- [ ] 能说清热更新边界：举出"该热更"与"必须重启"各两个例子，并解释原子快照为什么不会出现撕裂视图

### 跨语言对比

- 分层合并优先级（default→file→env→flag）、密钥不进仓库、发布可回滚、feature flag 生命周期、schema/字段只增不删，是**跨语言共享的工程公约**（第 5 章对比 Java/Spring、Python、Rust）——差异只在"框架注入 vs 显式组装"的封装度：Spring 注解扫描注入、dynaconf 动态配置、Go 是 `Config` struct + 显式 loader（为 analysis/ 与 Tenet 合成积累素材）
- "配置即代码 vs 配置即环境"的哲学张力每门语言都有：Go 与 Rust 站在"显式 + 类型化 + 少框架魔法"一端，Java 站在"框架约定注入"一端，Python 站在"动态宽松 + 12-factor 最彻底"一端——选型本质是团队对"样板代码换可测试性"的接受度
- 灰度与发布语义（percent 单调放量、canary→rolling、expand-contract、回滚预案）与语言完全无关，etcd/consul/K8s 是跨语言基础设施——本阶段学的"语义"在 Java/Rust/Go 服务上同一套，能迁移的是心智不是库

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap §20 对齐：练习 1 ↔「写配置加载模块」、练习 2 ↔「注入构建版本信息」、练习 3 ↔「设计灰度开关」、练习 4 ↔「写发布检查清单」。四题均为离线可测形态，参考实现文件头附运行与测试命令。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**多环境配置模块（release-server）**（roadmap 推荐项目二选一落地，选了多环境配置模块；另一推荐「服务发布 checklist」的检查逻辑已作为 `internal/release` 纳入本工程——两份推荐项目在这里合成一个可执行走查 CLI）。工程兑现 roadmap 阶段验收三条：`-profile dev/test/prod` 切不同配置并报来源表、注入版本自报（dev 被预检拦下）、发布预检把回滚预案与迁移纪律固化成机器闸门。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`go build ./... && go test ./... && go vet ./...` 与 `go test -race ./...` 通过、`go run ./cmd/release-server -profile dev/test/prod` 三环境配置不同、注入版本全绿 / dev 版本被拦、能指认四件事各落在哪一行）

### 下一阶段

[ph21 IoT / 车联网 / 嵌入式相关 Go 阶段](../ph21-iot-vehicle-edge/21-iot-vehicle-edge.md)——（Go 路线最后一个阶段，现已建成）本阶段把"服务怎么在不同环境里安全地跑起来并发布"讲透：配置分层、feature flag 灰度、发布决策与回滚、版本注入、迁移兼容、热更边界，落点是一套"服务端发布准备"的完整机制。下一阶段把这条链路**接到真实的物联世界**：设备通过 MQTT/WebSocket/TCP 接入（ph19 的消息队列承接遥测上行），本阶段的配置与发布机制将应用到**车联网后端与边缘网关**——设备侧的连接参数、边缘网关的本地配置缓存与断网降级、OTA 升级服务的发布与回滚（本阶段第 1 章声明的边界："设备端/边缘侧的嵌入式配置形态属 ph21"在此兑现）。届时：本阶段的 expand-contract 迁移纪律、feature flag 灰度、回滚预案会直接出现在 OTA 与边缘网关的工程里；而设备端遥测上行（MQTT 接入、断线重连、鉴权）是 ph21 的主题——**服务端如何"安全地跑起来并发布"你已经会了，接下来是设备端怎么连进来**。具体以 roadmap 第 21 节为准展开。

