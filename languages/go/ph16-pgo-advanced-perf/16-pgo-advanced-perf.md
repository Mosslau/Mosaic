# Go PGO 与高级性能优化阶段

> 面向"让编译器用真实运行数据做决策"：ph13 给了你 pprof 与 benchmark 这两把尺子，本阶段把它们测出来的东西——CPU profile——反哺回 `go build`，让内联、去虚拟化这类优化由实测数据驱动，再用基线 + 回归检查把优化成果钉在 CI 上，形成"采集 → 优化 → 度量 → 守门"的完整闭环。

## 1. 概述

本阶段是学习路线（roadmap 21 个阶段）里的第 16 步，Roadmap 目标一句话：**了解生产流量指导优化和更高级的性能调优方法**。前 15 个阶段里，"性能"一直是人肉视角——ph13 性能优化阶段教你用 `go test -bench`、pprof、逃逸分析**找到**问题并**手改**代码；本阶段换一个视角：**把采到的 profile 当作编译输入，让编译器自己按热度改自己**。同样一段保持可读的接口化代码，普通构建走 itab 间接调用，PGO 构建则根据 profile 把 99% 流量命中的那个实现改写成直接调用并内联（本阶段示例实测总收益约 3.5×，见 examples/README 实测记录）。除此之外，本阶段还覆盖两块"高级性能调优"的配套能力：内存布局与分配优化（优化"每次请求分配几次、数据结构占多大"），以及性能回归基线（让"快"从口头结论变成可挂 CI 的数字闸门）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| Profile Guided Optimization | `-pgo` 标志、`default.pgo` 自动约定、`go version -m` 印章验证；PGO 需要代表性 profile（roadmap 必会概念） |
| CPU profile 采集 | net/http/pprof 与 runtime/pprof 双路径的适用与取舍；profile 必须采在负载真正运行时 |
| 热点路径识别 | `go tool pprof` 的 top（谁最热）→ peek（谁调用它/它调用谁）→ list（热在哪一行）；热点代码更值得优化 |
| 内存布局和分配优化 | 字符串组装免分配（Builder + AppendInt）、结构体字段按对齐排序省 padding，用 B/op 与 allocs/op 证明 |
| 性能回归基线 | 中位数基线 + 阈值回归闸门（exit code 挂 CI）；性能优化要有基线和回归检查、不要为低频路径牺牲可读性 |

这个阶段只涉及「用 profile 指导编译与性能回归闭环」，**不涉及 pprof/benchmark 工具的基础用法（ph13 性能优化阶段已讲，本阶段直接复用）、版本与工具链管理（ph15 Go 版本、工具链阶段）、架构分层设计（ph17 架构设计与代码分层阶段，[展开版见 17-architecture-layering.md](../ph17-architecture-layering/17-architecture-layering.md)）、配置管理与发布策略编排（配置中心、feature flag、灰度/滚动发布与回滚、版本号与构建信息属 ph20 配置管理与发布策略阶段，roadmap 第 20 节，目录待建）** — 本阶段把"性能"钉在编译决策这一层：怎么用数据（profile）改变编译器行为、怎么用基线守住优化成果；服务怎么分层、发布怎么编排是后面阶段的事。

## 2. 来源与演变

**PGO（Profile-Guided Optimization，官方也称 FDO，Feedback-Directed Optimization）的思想是：编译器不再靠静态启发式"猜"哪条路径常见，而是拿一段真实运行的行为数据（profile）来回答。** 编译器优化里有大量"常见/罕见路径"的判断——哪些函数该内联、接口调用背后大概率是哪个实现、错误分支怎么放——没有数据时只能按函数体大小等静态特征猜；猜错就是收益浪费甚至倒退。PGO 把"运行期行为"变成编译期输入，这是 GCC/LLVM 生态用了几十年的老技术：早期是**插桩型**（instrumentation FDO，先插桩构建跑一遍负载收集执行计数，再用计数重新编译），2010 年代 Google 的 **AutoFDO** 把硬件采样器（perf）的采样结果直接当 profile 用，免去插桩与为收集而做的重部署——这正是"生产流量指导优化"的原型。Go 起步晚但走得顺：2023 年初预览、同年转正，把 PGO 门槛降到"放一个文件、跑一条构建命令"。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| GCC/LLVM 插桩型 FDO | 2000 年代 | GCC 的 `-fprofile-generate`/`-fprofile-use`、LLVM 的 `-fprofile-instr-generate` 系：两次构建，先插桩收集执行计数，再带计数重新编译 |
| 采样型 FDO / AutoFDO | 2010 年代 | Google AutoFDO 论文公开（CGO 2016）：硬件采样器（perf）直接产出 profile，免插桩、免为采集重部署；LLVM sample PGO（`-fprofile-sample-use`，2014 年已有 perf → sample profile 转换工具）同思路 |
| Go 1.20 | 2023-02 | PGO 以**预览**发布（官方博客 [Profile-guided optimization preview](https://go.dev/blog/pgo-preview)）：`go build -pgo=<profile>`，默认 `-pgo=off`，当时只用于内联决策；官方称典型 CPU 收益 2~4% |
| Go 1.21 | 2023-08 | PGO **转正**（官方博客 [Profile-guided optimization in Go 1.21](https://go.dev/blog/pgo)）：main 包目录存在 `default.pgo` 即默认开启（`-pgo=auto`）；新增 profile 驱动的条件去虚拟化；`go version -m` 盖 `-pgo` 印章；官方称典型收益 2~7% |
| Go 1.22 ~ 1.25 | 2024~2025 | 编译器持续扩大 PGO 的决策覆盖面；本阶段示例在 go1.25.6 上可见的决策输出（`-gcflags='-m'` 的去虚拟化/内联行）与收益量级见 examples/README 实测记录 |

官方口径的两个收益区间（1.20 的 2~4%、1.21 的 2~7%）是"典型负载"的中位数水平，不是保证值——真实收益取决于 profile 的代表性与热点形态（本阶段 ex02 是刻意放大的教学负载，实测约 3.5×，见 examples/README 实测记录）。官方 PGO 使用指南见 [go.dev/doc/pgo](https://go.dev/doc/pgo)，本阶段不再展开其全文。

本文示例以 **Go 1.25** 为基线（本阶段全部示例/练习/项目的 go.mod 写 `go 1.25.0`，实测工具链 go1.25.6——PGO 的内联/去虚拟化决策与收益随工具链版本变化，`-gcflags='-m'` 的决策输出和全部实测数字都锚定 go1.25.6；换工具链应重采、重建、重对比），验证工具链 go1.25.6（darwin/arm64，Apple M4 Pro，零第三方依赖：`go build -pgo`、`go tool pprof`、`go version -m`、`go test`/`go vet` 全部可用，示例逐项验证记录见 examples/README.md 的「验证说明」）。两个相关背景：① PGO 属于**构建期特性**，与 ph15 讲的版本治理直接相关——同一个 profile 用不同工具链编出的二进制不同，团队要统一工具链（go.mod 的 go 行 + toolchain 行）优化才可复现；② profile 会随源码漂移——官方建议把 `default.pgo` 当源码资产提交进仓库（含 `go get` 拉取），代码大改后重采一次。

## 3. 语法与参数

### 3.1 Profile Guided Optimization：-pgo 标志、default.pgo 约定、go version -m 印章

**PGO 的"语法"不是 Go 语言语法，而是 `go build` 的一个标志加一个文件约定**。输入是一份 CPU profile（pprof 格式，3.2 讲怎么采），输出是"按这份 profile 优化过的二进制"。三种构建形态：

| 形态 | 命令/约定 | 何时用 |
|------|----------|--------|
| 显式指定 | `go build -pgo=/path/to/cpu.pprof -o bin .` | 实验期、多个候选 profile 对比、CI 里 profile 单独存放 |
| default.pgo 自动 | profile 改名为 `default.pgo` 放进 **main 包目录**，直接 `go build`（`-pgo=auto` 自 Go 1.21 起是默认） | 生产常规：profile 与源码同目录同提交，`go get`/clone 即可复现构建 |
| 显式关闭 | `go build -pgo=off` | 对比基线、怀疑 profile 失真时的对照实验 |

三件配套动作是"PGO 真的生效了"的证明链，缺一不可（全部来自 ex02-pgo-build 的实测记录，见 examples/README.md）：

```text
# 1. 显式指定 profile 构建（ex02-pgo-build 的运行步骤，见 main.go 文件头）
$ go build -pgo=/tmp/ph16/ex02.pprof -o /tmp/ph16/ex02-pgo .
# 2. 印章验证：PGO 构建的二进制多一行 build -pgo=…（基线二进制无此行）
$ go version -m /tmp/ph16/ex02-pgo | grep -- '-pgo'
	build	-pgo=/tmp/ph16/ex02.pprof
# 3. 决策可见：PGO 构建多出"去虚拟化 + 内联"两行（基线构建没有）
$ go build -pgo=/tmp/ph16/ex02.pprof -gcflags='-m' . 2>&1 | grep -i 'devirt\|inlining call to (\*LCG)'
	./main.go:82:13: PGO devirtualizing interface call m.Mix to (*LCG).Mix
	./main.go:82:13: inlining call to (*LCG).Mix
```

三个要点：

- **印章是生效证明，不是性能证明**：`go version -m` 的 `-pgo=` 行只说明"这次构建采纳了 profile"；收益要另跑对比（3.5 的基线 + 自计时）才知道。default.pgo 约定实测同样会进印章（ex02 实测 `-pgo=/tmp/ph16/ex02auto/default.pgo`，见 examples/README）。
- **收益不是免费的**：PGO 用 profile 加权内联/去虚拟化决策，而 profile 来自"上一次负载"——负载形态变了（新接口、新流量分布）决策就可能过时。这就是 roadmap 必会概念「**PGO 需要代表性 profile**」：profile 里没有的热点，PGO 无从优化；采样太少甚至可能选错类型（练习 4 有实测反例）。
- **`-gcflags='-m'` 是观察编译器决策的窗口**：普通构建与 PGO 构建各打一份输出 diff，"PGO 多决策了什么"一目了然——这也是练习 2 的核心验收手段（用决策行证明 PGO 生效，而不是只报一个快慢数字）。

> 接口调用为什么是"间接跳转"、itab 长什么样，属于 **ph14 高级 Go 阶段**的内容；这里只需要结论：接口方法调用在运行时查 itab 间接跳转，编译器无法跨调用点优化，这正是 PGO 去虚拟化的作用对象。

### 3.2 CPU profile 采集：net/http/pprof 与 runtime/pprof 双路径

PGO 的原料是 CPU profile，采集有两条路径（ex01-profserver 一个程序演示两条，运行命令见其 main.go 文件头）：

```go
// examples/ex01-profserver/main.go —— 双路径的关键行（节选，行与文件一致；… 为省略行）
	_ "net/http/pprof" // 注册 /debug/pprof/* 到 DefaultServeMux——服务侧采集的唯一准备工作
	…
	if *batch {
		// 路径 B：runtime/pprof 包揽一段代码——适合 CLI、压测工具、离线任务
		if *prof != "" {
			f, err := os.Create(*prof)
			…
			if err := pprof.StartCPUProfile(f); err != nil {
				fmt.Fprintln(os.Stderr, "启动 CPU profile 失败:", err)
				os.Exit(1)
			}
			defer func() {
				pprof.StopCPUProfile() // 必须等 Stop 返回后文件才完整
				f.Close()
			}()
		}
		…
	}
	…
	// 路径 A：net/http/pprof——import 即注册，无需额外代码。
	// /debug/pprof/profile?seconds=N 在"服务正常接流量的同时"采样 N 秒，
	// 这就是"采集压测 profile"的标准动作（roadmap §16 练习 1）。
	http.HandleFunc("/work", workHandler)
```

```bash
# 1. 路径 A：起服务，另开 4 路并行 curl 持续压测 /work?n=20000000
go build -o /tmp/ph16/ex01 . && /tmp/ph16/ex01 -addr 127.0.0.1:18080 &
# 2. 压测窗口内采 3 秒（关键：profile 必须采在负载真正运行时）
curl -s 'http://127.0.0.1:18080/debug/pprof/profile?seconds=3' > /tmp/ph16/ex01-http.pprof
# 3. 路径 B：一次性批处理自采
/tmp/ph16/ex01 -batch -n 40000000 -cpuprofile /tmp/ph16/ex01-batch.pprof
```

| | 路径 A：net/http/pprof | 路径 B：runtime/pprof |
|---|---|---|
| 适用 | 常驻服务（边服务边采） | 一次性 CLI、批处理、压测工具 |
| 采集方式 | 服务 `import _ "net/http/pprof"` 注册端点；外部在压测期间 `curl /debug/pprof/profile?seconds=N` | 程序自己用 `pprof.StartCPUProfile`/`StopCPUProfile` 包住一段代码 |
| ex01 实测（见 examples/README） | 4 路并行 curl 压测 n=20000000 期间采 3s：`main.hashChain (inline)` flat 82.51%（4 核 cum 5.40s / 3s 窗口） | `-batch -n 40000000`：`main.hashChain (inline)` 100% |
| 产出 | 同一份 pprof 格式文件，同一套 `go tool pprof` 分析命令 | 同左 |

> ⚠️ **采集窗口 ≠ 程序运行期**：profile 必须采在负载真正打满 CPU 的窗口。ex01 实测的第一版是顺序 curl 压测——服务器大半时间在等请求，top 被 syscall 占据、业务热点根本进不了前列；改成 4 路并行压测后 `main.hashChain` 才以 82.51% 登顶（完整记录见 examples/README.md「ex01：CPU profile 双路径实测」）。压测工具（本阶段 project/cmd/loadgen）的职责之一就是把服务压到 CPU 忙，让采集窗口有代表性。

**两条路径怎么选**：服务进程在跑、能接受在流量中采样，用路径 A（这是 roadmap §16 练习 1「采集压测 profile」的标准动作——压测 + 外部采样）；程序是一次性跑完就退的 CLI/批处理，用路径 B 在代码里包窗口。两条路径的产物同格式、同分析命令，区别只在"谁负责在正确的时间窗口采样"。

### 3.3 热点路径识别：go tool pprof 的 top / peek / list

采到 profile 之后回答"优化哪里"——本阶段把 ph13 用过的 `go tool pprof` 组织成**下钻三件套**（ex03-pprof-analyze 实测输出，见 examples/README.md）：

```text
$ go tool pprof -top -nodecount=3 ex03 ex03.pprof
520ms  91.23%  main.validateRow          ← 业务热点直接登顶
$ go tool pprof -peek='renderBody' ex03 ex03.pprof
cum 30ms | main.renderBody              ← flat≈0%，症状全在 callee
         | runtime.concatstring2 100%   ← += 拼接的真实代价帧
$ go tool pprof -list='validateRow' ex03 ex03.pprof
190ms  190ms  for k := 0; k < 100; k++ {
300ms  310ms      h ^= uint64(r[i]) + uint64(k)   ← 热点精确到行
```

| 命令 | 回答的问题 | ex03 实测要点 |
|------|-----------|--------------|
| `go tool pprof -top -nodecount=N` | 谁最热？ | flat 占比最高的函数直接登顶：`main.validateRow` 91.23%——"热点代码更值得优化"（roadmap 必会概念）的读数依据 |
| `go tool pprof -peek='<fn>'` | 谁调用它、它调用谁？ | 症状帧 → 病因函数：`renderBody` 自身 flat≈0%，peek 显示其 callee 是 `runtime.concatstring2` 100%——`+=` 拼接的真实代价在 runtime，病因要沿调用链找回业务函数 |
| `go tool pprof -list='<fn>'` | 热在哪一行？ | flat/cum 集中在内层循环：`h ^= uint64(r[i]) + uint64(k)` 一行 300ms/310ms |

三个必懂的点：

- **flat vs cum**：flat 是该函数自己执行的时间，cum 含它调用的子孙。top 默认按 flat 排——所以"函数体很重"（大 cum）但 flat≈0% 的渲染函数进不了 top，它的代价以 `runtime.concatstring2`/`fmt.Sprintf` 等 **runtime 症状帧** 形态出现；先 top 找大头、再 peek 沿调用链找病根、最后 list 落到行，这是固定流程。
- **假热点陷阱**：函数体看起来重 ≠ 热点。判断标准是"调用频率 × 单次成本"——被高频调用的小函数（ex03 的 validateRow）才是真热点；低频的大函数（练习 3 的 auditExport，每 500 轮才跑一次）是假热点，先优化它是把力气花在低频路径上。
- **环境备注（本机实测现象）**：darwin/arm64 上对分配密集的单线程程序，CPU profile 会有部分采样落在 `runtime.kevent`/`pthread_cond` 等"被打断的空转线程"帧上（examples/README 的 ex03 环境备注）——本示例刻意把分配压到极低以获得干净归因；多 goroutine 服务（ex01 路径 A）无此现象。看到 runtime 长尾先别慌，沿调用链确认归属即可。

> `go tool pprof` 的交互模式与基础选项（top 各列含义、`-nodecount`、`-sample_index` 等）属于 **ph13 性能优化阶段**，本阶段直接复用；3.3 新增的是「top → peek → list」的下钻决策流程与"症状帧 → 病因函数"的归因心智。

### 3.4 内存布局和分配优化

高级性能调优的第二块：CPU 之外看**分配**。分配贵在两个地方——堆分配本身的 GC 压力、以及缓存不友好带来的内存带宽浪费。ex04-alloc-opt 用同一功能的"朴素版 vs 优化版"演示两类手法（源码与实测见 examples/ex04-alloc-opt/main.go 与 examples/README.md）：

```go
// examples/ex04-alloc-opt/main.go —— 分配优化与布局优化（节选，行与文件一致）
func FormatOpt(events []Event) string {
	var sb strings.Builder
	sb.Grow(len(events) * 40) // 预估每条约 40 字节
	var scratch [20]byte      // int64 十进制最长 20 位，栈上复用
	for _, e := range events {
		sb.WriteString("device=")
		sb.WriteString(e.DeviceID)
		sb.WriteString(" latency=")
		sb.Write(strconv.AppendInt(scratch[:0], int64(e.LatencyMs), 10))
		…
	}
	return sb.String()
}

// BadEvent 字段乱序：bool(1B) 与 int(8B)、string(16B) 交错，编译器被迫插入 padding。
type BadEvent struct {
	Online    bool   // 1B + 7B padding
	LatencyMs int    // 8B
	Valid     bool   // 1B + 7B padding
	DeviceID  string // 16B
}

// GoodEvent 同样的四个字段按对齐需求降序排列：大对齐字段在前，小字段收尾。
type GoodEvent struct {
	DeviceID  string // 16B
	LatencyMs int    // 8B
	Online    bool   // 1B
	Valid     bool   // 1B（+6B 尾部 padding 到 8 对齐）
}
```

ex04 实测（`-count=5` 取中位数，见 examples/README.md「ex04：分配与布局优化实测」）：

| 基准 | ns/op | B/op | allocs/op | 对比 |
|------|-------|------|-----------|------|
| FormatNaive（Sprintf+`+=`） | 1,704,325 | 22,907,866 | 3,547 | 基线 |
| FormatOpt（Builder+AppendInt） | 20,338 | 98,304 | 2 | **快 84×、内存省 233×、分配 3547→2** |
| LayoutBad（字段乱序 40B） | 822,069 | 4,005,898 | 1 | 基线 |
| LayoutGood（按对齐排序 32B） | 327,155 | 3,203,077 | 1 | **省 20% 内存、遍历快 2.5×** |

三个教学点（均与实测记录对应，见 examples/README.md）：

- **`fmt.Sprintf` 的隐藏成本是"每事件 ~3.5 次分配"**：参数装箱 + 中间字符串；`strconv.Itoa` 也会分配——换成栈上 `scratch` + `strconv.AppendInt` 才把分配归零（FormatOpt 全程序列化整体只剩 2 allocs/op）。
- **B/op 就是"结构体尺寸 × 元素数"的直接证据**：同样 10 万元素，BadEvent 40B 与 GoodEvent 32B 差了 800KB（实测 4.0MB→3.2MB）；结构体数组/切片的内存占用按单元素尺寸线性放大，字段按对齐降序排列（16B → 8B → 1B → 1B）是零成本的省内存手段。尺寸用 `unsafe.Sizeof` 验证（ex04 的 `go run .` 输出 `sizeof(BadEvent)=40 sizeof(GoodEvent)=32`，go1.25 arm64）。
- **正确性由等价测试保证**：`TestFormatEquivalence` 断言两版格式化输出逐字节一致（examples/README 验证说明）——优化是改写实现，不是改写行为。

> 逃逸分析怎么判"逃不逃"、sink 纪律为什么能防止编译器把被测代码优化没，属于 **ph13 性能优化阶段**；3.4 直接用其结论，重点是"分配与布局的可度量三列（ns/op、B/op、allocs/op）"如何指导改法。

### 3.5 性能回归基线

"快了多少"如果没有基线，就是无证据断言——roadmap 必会概念「**性能优化要有基线和回归检查**」与阶段验收「能避免无证据优化」都落在这一节。最小可用的基线形态：**同一基准跑多轮取中位数存成基线文件，之后每次重跑对比，中位数回归超过阈值即失败（exit 1），可挂 CI**。ex05-bench-baseline 的 `benchregress.sh` 用 bash + awk 实现了这个闸门（零第三方依赖），实测（见 examples/README.md「ex05：回归基线脚本实测」）：

```text
$ ./benchregress.sh baseline      → 基线中位数 27.65 ns/op 写入 /tmp
$ ./benchregress.sh check         → PASS   27.6 → 27.2 ns/op（-1.6%）   exit 0
$ SLOW=1 ./benchregress.sh check  → REGRESSION 27.6 → 103.5 ns/op（+274.5%） exit 1
$ benchstat baseline.txt current.txt → +278.39% (p=0.002 n=6)   ← 统计显著
```

```bash
# examples/ex05-bench-baseline/benchregress.sh —— 阈值判断骨架（节选，行与文件一致）
	delta=$(awk -v b="$base" -v c="$cur" 'BEGIN { printf "%.1f", (c-b)/b*100 }')
	verdict="PASS"
	# awk 做浮点比较：回归超过阈值即失败（负 delta = 变快，永远 PASS）
	if awk -v d="$delta" -v t="$THRESHOLD" 'BEGIN { exit !(d > t) }'; then
		verdict="REGRESSION"
		fail=1
	fi
```

工程要点（数字与结论均见 examples/README.md 实测记录）：

- **用中位数抵抗单次抖动**：`-count=6` 取 6 次采样，排序取中位（脚本 `medians()`），不取单次；本机同机波动就有 **±10~20%**，阈值默认 10% 并可用 `THRESHOLD` 覆盖——**阈值不要定太小**，否则噪声天天误报。
- **exit code 是给 CI 的接口**：`check` 无回归 exit 0、回归 exit 1、缺基线 exit 2——脚本化之后，回归是"构建红了"，不是"有人感觉慢了"。
- **benchstat 补统计显著性**：同一份数据喂给 `golang.org/x/perf/cmd/benchstat` 能拿到 p 值（实测 `+278.39% (p=0.002 n=6)`）。安装注意：benchstat 要求 go ≥ 1.26 构建自身，本环境实测通过 GOTOOLCHAIN 自动下载 go1.26.8 完成安装（`go install golang.org/x/perf/cmd/benchstat@latest`）——这正好复用了 ph15 的工具链自动切换机制。

> benchmark 的编写基础（`-bench`/`-benchmem`/`-count` 语义、避免编译器优化掉被测代码的 sink 纪律）属于 **ph13 性能优化阶段**；3.5 的新增是把多轮结果变成"基线 + 阈值闸门"的回归工程化，PGO 对比（练习 2/4 与 project）都要在这条基线上做。

## 4. 底层原理

PGO 的机制一句话：**普通构建的每个优化决策都基于静态启发式，PGO 构建把 profile 采样计数折算成"调用点权重"，让决策向实测热点倾斜**。数据流：

```text
representative load ──collect CPU profile──▶ cpu.pprof ──go build -pgo=cpu.pprof──▶ compiler
  (prod / loadgen traffic)            (pprof format)  (3.1)                                  │
                                                                                             ▼
                                weighted decisions, keyed by call-site hotness
                                      |-- inline hot call sites          ← 4.1
                                      |-- devirtualize hot types         ← 4.2
                                      `-- lay out hot / fallback path    ← 4.3
                                                                                             ▼
                              PGO binary: same source, same semantics, machine code
                              shaped by real traffic (verified by checksum equality)
```

profile 进入编译器后做的事可以概括为"哪条路径是热的，就把机器码往哪边偏"：

### 4.1 内联：把内联预算花在热调用点上

普通构建的内联按**静态代价**判断：函数体小到一定规模才内联，超过预算就放弃——因为内联膨胀代码、伤指令缓存。PGO 把 profile 的调用点热度加进代价模型：**profile 显示热的调用点，即使函数体偏大也内联；冷的调用点即使函数体偏小也保持调用**。官方 1.21 博客（[go.dev/blog/pgo](https://go.dev/blog/pgo)）的 mdurl 例子里，`mdurl.Parse` 因为太大本不能内联，PGO 看到它热就内联了——而内联的**下游收益**往往比"少一次调用"更大：函数被并进调用方后，逃逸分析能看清局部对象不逃逸，把本来的堆分配变成栈分配（官方博客实测该函数分配清零）；常量传播也有了下手空间。这正是 ex02 实测里"inlining call to (*LCG).Mix"跟在去虚拟化后面出现的原因——**去虚拟化是钥匙，内联及后续优化才是大头收益**。

### 4.2 条件去虚拟化：把间接调用改写成"类型检查 + 直连"

接口调用（如 ex02 的 `m.Mix(v)`）普通构建下运行时查 itab 间接跳转，且编译器无法跨调用点做字段提升、逃逸分析。profile 显示某个调用点 99% 命中了 `*LCG` 后，编译器把它改写为**条件去虚拟化**（conditional devirtualization）：

```text
普通构建：  s ^= m.Mix(v)  ──▶  itab 查表 ──▶ 间接跳转
                                            （每迭代一次 call/ret，且编译器无法跨调用点优化）

PGO 构建（profile 显示该调用点 99% 是 *LCG）：
        s ^= m.Mix(v)
            │   改写为
            ▼
        if t, ok := m.(*LCG); ok {       ← 热路径（99%）：类型断言命中，直接调用
            s ^= t.Mix(v)                ← 随即内联；字段 A/C 的提升因此解锁
        } else {
            s ^= m.Mix(v)                ← 冷路径（1% 的 XorFold）：保留接口形态回退
        }
```

三个机制要点：

- **profile 不是保证，类型断言兜底正确性**：热路径是"猜对了就快"，冷路径保留原间接调用——所以哪怕流量形态变了、某次真来了 XorFold，结果也正确，只是不享受优化。这是"PGO 不改语义"的结构性原因：ex02 实测基线与 PGO 二进制 checksum 相同（均为 1216），就是这个保证的可见证据。
- **字段提升是去虚拟化的隐藏赠品**：间接调用会阻止编译器把 `m.A`/`m.C` 这类字段加载搬出循环；去虚拟化 + 内联后编译器才能做提升。sol-02 的练习说明里"字段是去虚拟化后能提升的前提"，project 的 apiserver 注释也说 `fnvSigner` 带配置字段（A/C）正是为此设计。
- **为什么去虚拟化的对象是"多数派"那个类型**：编译器按 profile 权重选命中率最高的类型做热路径；权重来自采样——所以 profile 必须代表真实负载，采样太少会选错类型（练习 2/4 有实测反例：选到 5%/10% 那个类型反而变慢）。

### 4.3 分支布局：热路径直落、冷路径跳出

经典 FDO（GCC/LLVM）里 profile 还会驱动**分支布局 / 块重排**：把高频基本块排成顺序直落（不打断指令预取、不触发分支预测失败），把错误分支、回退分支这类冷路径移出主路径甚至做冷热分离。Go 编译器官方文档化的 PGO 优化聚焦内联与去虚拟化两处（见 4.1/4.2 与官方 1.21 博客）；去虚拟化插入的"类型断言热分支 + 间接调用回退"本身就构成了一个**热路径在前、冷路径在后的布局**——热分支顺序直通，冷分支跳出。理解这条通用机制即可：分支布局的意义在于**指令预取与分支预测器只奖励顺序执行的热代码**，任何把"99% 会走的那条路"排直的手法都在省 CPU 前端的时间。

### 4.4 为什么 ex02 有 3.5×、而链式版本零收益（本阶段核心教学增量）

ex02 实测基线与 PGO 各跑 3000 轮 × 64K 独立输入：基线 `ns/op=1.300`（elapsed 255.6ms）→ PGO `ns/op=0.359`（elapsed 70.5ms），约 3.5×，checksum 前后一致（见 examples/README.md「ex02：PGO 构建对比实测」）。3.5× 不是"去虚拟化"三个字的魔法，拆开看：

- **每次迭代省掉一次间接调用开销**：`process` 的内层循环对 64K 个独立输入逐次 `m.Mix(v)`——LCG 的函数体（`x*A + C`）极小，小到"调用本身的开销比函数体还贵"，正是去虚拟化收益最明显的形态。
- **两个前提缺一不可**（examples/README 实测结论）：
  1. **迭代间无依赖链**——第一版写成 `s = m.Mix(s)`（链式依赖）实测 PGO 零收益：乘加延迟链才是瓶颈，调用开销被 CPU 乱序执行掩盖，去掉也快不了；改成 `s ^= m.Mix(v)`（输入相互独立、可流水线并行）后，调用开销才暴露在关键路径上，收益才显形。
  2. **profile 必须来自代表性负载**——ex02 的负载是"3000 轮里 99% 用 LCG、1% 用 XorFold"（`r%100==0` 时切冷门实现），profile 里 LCG 的调用点权重才足够高，去虚拟化才选它。
- **收益的"保质期"取决于 profile 的新鲜度**：源码大改、负载形态变化后旧 profile 的权重失真，需要重采——这也是"性能回归基线"（3.5）要持续运行的原因：PGO 让你尝到甜头的同时，也让你需要证据来确认甜头还在。

## 5. 使用场景

| 场景 | 用什么 | 对应小节 |
|------|--------|---------|
| CPU 热点集中在少量调用点、流量形态可复现的服务/批处理 | PGO：代表性 profile + `-pgo` 或 `default.pgo` | 3.1 / 3.2 |
| 想知道"到底哪热、热在哪一行"再决定改哪 | `go tool pprof` top → peek → list | 3.3 |
| 高频字符串组装/格式化、大数据结构切片占内存 | Builder 预分配 + AppendInt、字段按对齐排序 | 3.4 |
| 证明"优化真的有效"、防未来回归 | 中位数基线 + `benchregress.sh` 阈值闸门（exit code 挂 CI） | 3.5 |
| 压测/生产期间采服务端 profile | net/http/pprof（路径 A） | 3.2 |
| 一次性 CLI/批处理自采 profile | runtime/pprof（路径 B） | 3.2 |

**什么时候不用 PGO / 用之前先想清楚**：

- **profile 没有代表性时不要用**：一次性启动即退、负载形态天天变、压测都打不满 CPU 的程序，profile 会误导编译器（选错去虚拟化目标反而变慢——练习 2/4 的实测反例）；这时的正确动作是先修"怎么让 profile 代表生产"，而不是上 PGO。
- **没有基线不要谈优化**：先跑 `benchregress.sh baseline` 这类动作把现状钉住，再动手——否则"快了"没有对照，"慢了"没有闸门，回到无证据优化。
- **收益不可度量时，PGO 不是第一优先级**：ex02 的 3.5× 是"调用开销暴露在关键路径 + profile 干净"的合成结果；真实服务常见收益是官方口径的个位数百分比量级。先度量、再优化，收益方向不对就换热点（roadmap 必会概念「不要为低频路径牺牲可读性」：PGO 的意义正在于让你**保持可读的接口/分层写法**、把"针对热点做丑化优化"这件事交给编译器按数据做——人肉把代码写弯去迁就某个猜测的热点，才是两头不讨好）。
- **版本与可复现性前提**：PGO 决策随工具链版本变化，profile 需与源码一起提交（ph15 的统一工具链是优化可复现的前提）；升级工具链后要重采、重对比，而不是沿用旧 profile 的旧结论。

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：

- Go（静态 AOT）：profile 外部采集（压测/生产），编译期一次性决策，构建产物内嵌 `-pgo` 印章可审计——适合"负载可复现、构建可复现"的服务
- C/C++（GCC/LLVM）：同类 FDO 更早更全（插桩/采样两套路线、还能驱动分支布局等），但配置与构建矩阵成本高
- Rust：走 LLVM 的 PGO（`-C profile-generate` / `-C profile-use` 等），形态与 C/C++ 相同
- Java/JVM：JIT 把"profile"内建在运行期——分层编译先以低优化级别跑，边跑边按实际执行做内联/去虚拟化，无需显式的 profile 文件，但要付出预热期代价
- 结论：Go 的 PGO = **把 JVM 的自适应思想搬回 AOT 编译器，用显式文件（default.pgo）在"采集环境"与"构建环境"之间交换数据**；与 Rust/C++ 同属编译期 FDO 家族，与 JVM 的运行时自适应是两条不同路线

## 6. 代码示例

> 示例运行前提：五个示例均为完整可运行 Go module（ex05 另含 bash 回归脚本），位于 [`examples/`](./examples/) 目录，每个示例一个子目录，先进入对应目录再运行；构建产物与 profile 一律写 /tmp 不进仓库。验证环境 go1.25.6（darwin/arm64，Apple M4 Pro），零第三方依赖；`go vet ./...`、`go test ./...` 全部通过（ex02 为构建对比演示，正确性由 checksum 前后一致保证）。完整验证说明与逐项实测数字见 [examples/README.md](./examples/README.md)。

| 文件 | 一句话说明 | 实测要点（出处：examples/README.md） |
|------|-----------|-----------------------------------|
| ex01-profserver/main.go | CPU profile 双路径采集：常驻服务 net/http/pprof 边压测边采 + 批处理 runtime/pprof 包一段代码 | 路径 A：`main.hashChain` 82.51%；路径 B：100% |
| ex02-pgo-build/main.go | PGO 构建对比：代表性 profile → `-pgo` 构建 → 印章 + 自计时 | 基线 255.6ms/1.300 → PGO 70.5ms/0.359，**快约 3.5×**，checksum 1216 一致 |
| ex03-pprof-analyze/main.go | 热点下钻三件套程序：两类热点（validateRow 纯 CPU + renderBody `+=` 拼接） | top 91.23%、peek 见 `runtime.concatstring2`、list 落到行 |
| ex04-alloc-opt/main.go | 内存布局与分配优化前后对比（格式化 + 结构体布局） | 快 84×/省 233×/3547→2；布局省 20% 内存、遍历快 2.5× |
| ex05-bench-baseline/main.go | 被基准守护的函数（checksum）+ benchmark 载体 | 基线中位数 27.65 ns/op |
| ex05-bench-baseline/benchregress.sh | benchstat 思路的回归闸门：baseline / check / exit code | PASS -1.6% exit 0；REGRESSION +274.5% exit 1 |

### 示例 1：CPU profile 双路径（ex01-profserver/main.go）

```go
// examples/ex01-profserver/main.go —— 路径 A 的注册与路径 B 的采集（节选，行与文件一致；… 为省略行）
	_ "net/http/pprof" // 注册 /debug/pprof/* 到 DefaultServeMux——服务侧采集的唯一准备工作
	…
	// 路径 B：runtime/pprof 包揽一段代码——适合 CLI、压测工具、离线任务
	if err := pprof.StartCPUProfile(f); err != nil {
		fmt.Fprintln(os.Stderr, "启动 CPU profile 失败:", err)
		os.Exit(1)
	}
	defer func() {
		pprof.StopCPUProfile() // 必须等 Stop 返回后文件才完整
		f.Close()
	}()
```

运行（见 main.go 文件头完整命令）：`go build -o /tmp/ph16/ex01 . && /tmp/ph16/ex01 -addr 127.0.0.1:18080 &` 起服务 → 4 路并行 curl 压测 `/work?n=20000000` → `curl 'http://127.0.0.1:18080/debug/pprof/profile?seconds=3'` 采 3 秒；或 `/tmp/ph16/ex01 -batch -n 40000000 -cpuprofile /tmp/ph16/ex01-batch.pprof` 走路径 B。**教学点**：路径 A 只有一行 import（注册端点），采样动作完全在服务外；路径 B 用 `StartCPUProfile`/`StopCPUProfile` 包窗口，且 `Stop` 返回后文件才完整。两条路径实测都验证了"profile 采在压测窗口内"时热点干净登顶（82.51% / 100%，见 examples/README 实测记录）。

### 示例 2：PGO 构建对比（ex02-pgo-build/main.go）

```go
// examples/ex02-pgo-build/main.go —— 热接口与热点调用点（节选，行与文件一致）
type Mixer interface {
	Mix(uint64) uint64
}

// process 是 profile 里的热点帧：对一批相互独立的输入逐一调用接口方法。
func process(m Mixer, in []uint64) uint64 {
	var s uint64
	for _, v := range in {
		s ^= m.Mix(v) // 热点调用点：PGO 在这里插入类型断言 + 直接调用 + 内联
	}
	return s
}
```

运行（main.go 文件头 5 步）：基线构建自计时 → `-cpuprofile` 采代表性 profile → `go build -pgo=/tmp/ph16/ex02.pprof` → `go version -m` 验证印章 → 对比自计时；再用 `-gcflags='-m'` diff 出"去虚拟化 + 内联"两行决策。**教学点**：`Mixer` 是"接口形态"的载体（两个实现，99% LCG / 1% XorFold），`process` 的输入相互独立（`s ^=` 而非 `s =`）让调用开销暴露在关键路径上；实测 `ns/op=1.300 → 0.359`（约 3.5×）、checksum 1216 前后一致（见 examples/README 实测记录）——印章证明"用了 profile"，checksum 证明"没改语义"，两条证据合起来才是完整的 PGO 验收。

### 示例 3：热点下钻三件套（ex03-pprof-analyze/main.go）

```go
// examples/ex03-pprof-analyze/main.go —— 两类热点的埋点（节选，行与文件一致；… 为省略行）
func validateRow(r string) uint64 {
	var h uint64 = 1469598103934665603
	…
		for k := 0; k < 100; k++ { // 内层循环：list 下钻后的热点行
			h ^= uint64(r[i]) + uint64(k)
			h *= 1099511628211
			h ^= h >> 13
		}
	…
}

// renderBody 是第二热点：故意用 `+=` 逐行拼接……
// 它在 profile 里 flat ≈ 0%，"症状"落在 runtime.concatstring2 / fmt.Sprintf 上——
// 这正是需要 peek 沿调用链找回病因的典型形态。
func renderBody(rows []string) string {
	s := "<table>\n"
	for _, r := range rows {
		s += fmt.Sprintf("<tr><td>%s</td></tr>\n", r) // 热点行：每次 += 都整体拷贝 s
	}
	return s + "</table>\n"
}
```

运行（main.go 文件头 4 步）：构建 + `-cpuprofile` 采集 → `go tool pprof -top` → `-peek='renderBody'` → `-list='validateRow'`。**教学点**：validateRow 是"以业务函数身份登顶"的第一热点（实测 91.23%，真热点，先优化它）；renderBody 是"症状全在 runtime"的第二热点（自身 flat≈0%，peek 显示 callee `runtime.concatstring2` 100%）——流程练的是 top 定大头、peek 沿调用链找回病因、list 落热点行的下钻纪律，不是背输出。

### 示例 4：内存布局与分配优化（ex04-alloc-opt/main.go）

```go
// examples/ex04-alloc-opt/main.go —— 优化版核心（节选，行与文件一致；… 为省略行）
func FormatOpt(events []Event) string {
	var sb strings.Builder
	sb.Grow(len(events) * 40) // 预估每条约 40 字节
	var scratch [20]byte      // int64 十进制最长 20 位，栈上复用
	…
		sb.Write(strconv.AppendInt(scratch[:0], int64(e.LatencyMs), 10))
	…
	return sb.String()
}
```

运行：`go test -run='^$' -bench='Format|Layout' -benchmem -count=5`（正确性另有 `go test -v ./...` 的 `TestFormatEquivalence`）；`go run .` 打印 `naive==opt: true` 与两个结构体尺寸。**教学点**：三列指标（ns/op、B/op、allocs/op）是分配优化的度量语言——FormatOpt 相对 FormatNaive 实测快 84×、省 233×、allocs 3547→2；BadEvent 40B vs GoodEvent 32B 证明"字段按对齐降序"在同数据下省 20% 内存、遍历快约 2.5×（以上数字见 examples/README 实测记录）。

### 示例 5：被基准守护的函数（ex05-bench-baseline/main.go）

```go
// examples/ex05-bench-baseline/main.go —— 被基准守护的函数（节选，行与文件一致；… 为省略行）
// checksum 是被基准守护的函数：FNV 风格逐字节混合，extra 控制额外混合轮数
// （extra 只用于教学演示"回归"——SLOW=1 时 benchmark 传 extra=2 模拟代码变慢）。
func checksum(data string, extra int) uint64 {
	h := uint64(1469598103934665603)
	for i := 0; i < len(data); i++ {
		h ^= uint64(data[i])
		h *= 1099511628211
		…
	}
	return h
}
```

运行：`go test -v ./...` 验正确性；`go run .` 打 checksum。**教学点**：这是"回归脚本守护什么"的答案——一个行为稳定、被基准覆盖的小函数；`extra` 参数是演示回归的开关（SLOW=1 时传 extra=2 人为变慢），真实代码里对应"有人改慢了热路径"。它单独存在没意义，必须与 benchregress.sh 配套成闸门。

### 示例 6：回归闸门脚本（ex05-bench-baseline/benchregress.sh）

```bash
# examples/ex05-bench-baseline/benchregress.sh —— 中位数提取（节选，行与文件一致）
	med=$(grep "^${b}-" "$file" | awk '{print $3}' | sort -n |
		awk '{a[NR]=$1} END { if (NR==0) exit 1; print (NR%2) ? a[(NR+1)/2] : (a[NR/2]+a[NR/2+1])/2 }')
```

运行（见文件头）：`./benchregress.sh baseline` 存基线（-count=6 中位数）→ `./benchregress.sh check` 重跑对比（回归 > 阈值 exit 1）→ `SLOW=1 ./benchregress.sh check` 人为回归验证报警。**教学点**：闸门 = 中位数（抗抖动）+ 阈值（默认 10%，覆盖 ±10~20% 的机器噪声）+ exit code（CI 接口），三段都是最小可用设计；benchstat 是它的"统计显著性升级版"（p 值判据），但闸门本身零第三方依赖即可落地。实测记录（PASS -1.6% exit 0 / REGRESSION +274.5% exit 1 / benchstat p=0.002）见 examples/README.md「ex05：回归基线脚本实测」。

## 7. 总结

### 关键要点

1. **PGO = 用运行数据改编译决策**：输入是 CPU profile（pprof 格式），`go build -pgo=<file>` 显式指定、`default.pgo` 放 main 包目录自动启用（Go 1.21+ 默认）；`go version -m` 的 `-pgo=` 印章是生效证明，`-gcflags='-m'` 的 devirt/inlining 行是决策证明
2. **PGO 需要代表性 profile**（必会概念）：profile 必须采在负载真正运行时（4 路并行压测 vs 顺序 curl 的实测对比），且能代表生产的流量形态——采样太少会选错去虚拟化类型（练习 2/4 实测反例）
3. **CPU profile 双路径**：常驻服务用 net/http/pprof（import 即注册，压测期间外部采）；一次性程序用 runtime/pprof（Start/Stop 包窗口，Stop 返回文件才完整）——产物同格式、分析命令同一套
4. **热点下钻三件套**：top 定"谁最热"（flat 口径）→ peek 沿调用链找回病因（renderBody flat≈0%、症状在 runtime.concatstring2）→ list 落热点行；判断"值不值得优化"看调用频率 × 单次成本，函数体大 ≠ 热点
5. **PGO 的两大机制**：热调用点内联（内联预算按 profile 加权，内联后解锁逃逸分析与常量传播）+ 条件去虚拟化（类型断言热路径直连内联、冷类型保留间接调用回退，正确性由类型检查兜底）——"热路径直落、冷路径跳出"的分支布局是同一思想
6. **收益有前提**：ex02 实测 3.5× 依赖"迭代无依赖链 + profile 干净"两条件；链式依赖版本实测零收益、冷门类型被选中去虚拟化反而变慢——快慢都要有证据
7. **内存布局与分配优化**：`fmt.Sprintf` 每事件 ~3.5 次分配 → Builder 预分配 + 栈上 scratch + `strconv.AppendInt` 归零（实测 3547→2 allocs/op）；结构体字段按对齐降序（实测 40B→32B，同数据省 20% 内存、遍历快 2.5×）
8. **性能回归基线**（必会概念）：`-count` 多轮取中位数 + 阈值（默认 10%，机器噪声 ±10~20%）+ exit code 挂 CI，是最小可用闸门；benchstat 补 p 值做统计显著性
9. **无证据优化是头号反面教材**（阶段验收）：先 baseline 后动手、基线/优化对比都用同口径（checksum/digest 一致性证明语义未变）、对比至少两遍取方向与量级
10. **不要为低频路径牺牲可读性**（必会概念）：保持接口化、分层化的可读写法，把"针对热点的丑优化"交给 PGO 按数据做；profile 与源码同提交、随代码漂移重采，工具链统一（ph15）是可复现优化的前提

### 阶段验收清单

- [ ] 能说明 PGO 适用条件：代表性 profile、热调用点集中、可复现构建——以及什么时候不该用（profile 失代、无基线、冷门类型可能被误选）
- [ ] 能完整走一遍 PGO 流程：采集代表性 CPU profile → `go build -pgo=`（或 `default.pgo` 约定）→ `go version -m` 印章验证 → 基线与 PGO 自计时/压测对比，checksum/digest 前后一致
- [ ] 能产出性能对比报告：同一负载下基线 vs PGO 的延迟分位数（p50/p95/p99/均值）与吞吐（req/s），并说清差异来源与离群处理（练习 4）
- [ ] 能用 top → peek → list 下钻定位热点行、沿调用链找回 runtime 症状帧背后的业务函数、识破假热点（示例 3 / 练习 3）
- [ ] 能避免无证据优化：先有基线（baseline 闸门）再动手，回归能被 exit code 拦截（示例 6）
- [ ] 能对分配与布局做有据优化：用 ns/op、B/op、allocs/op 三列与结构体尺寸证明收益（示例 4）

### 跨语言对比

- Go 的 PGO = "profile 文件（default.pgo）作为一等构建输入 + 印章审计"，与源码同提交、同 review——对比 Rust/C++ 走 LLVM/GCC 的 FDO（插桩/采样两套、配置更重但能力更全，还能驱动分支布局），以及 JVM 把 profile 内建在 JIT 运行期（无需显式文件但要预热）。**Go 的差异化：把"反馈优化"做成了零配置默认开启 + 产物可审计（-pgo 印章）的工程资产**，门槛低到"放一个文件、跑一条命令"
- 必会概念「不要为低频路径牺牲可读性」在语言间是通识：JVM 靠 JIT 自适应、Go/C++/Rust 靠显式 PGO——**把"丑优化"从人肉搬到编译器**是静态编译语言近十年的共同方向，为 analysis/ 与 Tenet 合成积累素材

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap §16 对齐：练习 1 ↔「采集压测 profile」、练习 2 ↔「用 PGO 构建服务」、练习 3 ↔ 学习内容「热点路径识别（pprof list 行级下钻）」、练习 4 ↔「对比优化前后延迟和吞吐」；roadmap 推荐项目「API 服务 PGO 实验」由本阶段 project/ 落地、「性能回归测试脚本」由 examples/ex05-bench-baseline 覆盖。完成 4 题后继续。

1. **采集压测 profile**（★★）：并发压测自己的 CPU 密集函数并采窗口内 profile，验证热点压在预期函数上（参考实现实测：`pprof -top` 第一行即业务函数 compressBlock，占绝对多数——sol-01-collect-profile/main.go 文件头验证块实测 84.01%，exercises/README 验收口径 ~86%；并解释"并发 worker 数 × 窗口时长 > 窗口采样时长"）
2. **用 PGO 构建服务**（★★★）：接口注入的命令分发内核走 PGO 四步，用印章 + `-gcflags='-m'` 决策行证明生效（参考实现实测 ~2.0×，ns/op 0.746→0.371，见 sol-02-pgo-build/main.go 文件头验证块；`//go:noinline` 与采样量的坑也记录在其注释里）
3. **热点路径识别——top/peek/list 三件套**（★★）：对三类热点（纯 CPU 热函数 / `+=` 拼接症状帧 / 低频假热点）依次回答三个问题并写依据输出（对应学习内容「热点路径识别」）
4. **对比优化前后延迟和吞吐**（★★★）：同一负载分别跑基线与 `-pgo` 二进制，报 p50/p95/p99/均值与吞吐（参考实现实测 p50 1.625µs→0.917µs、吞吐 ~590k→~955k req/s、digest 一致，见 sol-04-latency-throughput/main.go 文件头验证块；`-cpuprofile` 采集与逐请求计时互斥的原因也记录在其注释里）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**API 服务 PGO 实验**（roadmap 推荐项目）——`cmd/apiserver`（设备签名 API：GET /api/devices/{id}，Signer 接口分派 90% fnvSigner / 10% xorSigner，`/debug/pprof/*` 手动挂载，签名循环是纯 CPU 热点）+ `cmd/loadgen`（internal/workload 的薄 CLI，报延迟分位数与吞吐）+ `internal/workload`（HTTP 压测库：代表性负载 + 报告 p50/p95/p99/均值/吞吐）。运行与采集命令见各文件头（`go run ./cmd/apiserver -addr 127.0.0.1:18090 …` 起服务 → 压测期间 `curl '/debug/pprof/profile?seconds=5'` 采服务端 profile → `go build -pgo=` 构建 → `go run ./cmd/loadgen …` 对比基线 vs PGO 两份报告）；go.mod 为 `go 1.25.0`，`go test ./... && go vet ./...` 通过（验证状态见各文件头注释，2026-09-02 已实测）。roadmap 另一个推荐项目「性能回归测试脚本」已由 examples/ex05-bench-baseline 覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准：基线 vs PGO 两份延迟/吞吐报告齐全且 digest 一致、`go version -m` 印章存在、`go test ./... && go vet ./...` 通过

### 下一阶段

[架构设计与代码分层阶段](../ph17-architecture-layering/17-architecture-layering.md) — PGO 回答"怎么让编译产物更快"，架构分层回答"中大型 Go 服务怎么组织代码不失控"：handler/service/repository 分层、领域模型与 DTO、依赖注入、配置/日志/错误码/接口边界与单体到服务化演进。本阶段反复强调的"接口注入的算法可插拔形态"（Signer/Codec 接口 + 90%/10% 实现）正是 ph17 分层里"接口定义在使用方附近"的雏形——profile 驱动优化的前提是代码结构可测、热点可被接口形态承载。

---

*本文为纯写作交付，未新增任何运行验证。全部"实测"数字与"已验证"声明均引自既有文件——examples/README.md（ex01~ex05 五个示例的实测记录，2026-09-03）、examples/ 各源码文件头验证块（ex01~ex05）、exercises/sol-01~sol-04 文件头验证块（2026-09-02/03）、project/ 各文件头（cmd/apiserver、cmd/loadgen、internal/workload，2026-09-02），验证环境统一为 go1.25.6（darwin/arm64，Apple M4 Pro），数字随机器与 Go 版本波动 ±10~20%。Go 1.20/1.21 的 PGO 里程碑与官方收益区间（2~4%、2~7%）以 go.dev 官方博客与文档为准；不虚构验证结果。*
